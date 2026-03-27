# GCP Dev VDI Setup

This project automates the deployment and management of development VDI VMs (Linux and Windows) in GCP that can be accessed via Chrome Remote Desktop or RDP (for YubiKey support).

## Setup

1.  **Clone the repository:**

    ```
    git clone https://github.com/your-username/gcp-dev-vdi.git
    cd gcp-dev-vdi
    ```

2.  **Install dependencies:**

    ```
    pip install -r requirements.txt
    ```

    ```
    export GCP_PROJECT="your-gcp-project-id"
    ```

3.  **Bootstrap the Cloud Environment:**
    The project includes an automated script that configures your GCP environment conforming to the principle of least privilege. It ensures the configuration bucket is generated and provisions dedicated Service Accounts for the orchestration system.

    ```bash
    chmod +x scripts/setup_gcp.sh
    ./scripts/setup_gcp.sh
    ```
    **What this script does:**
    * Prompts and establishes a secure GCS bucket using Uniform Bucket Level Access.
    * Provisions a target **Orchestrator Service Account** (`vdi-deployer-sa`) holding the minimal rules required to orchestrate instance creation and safely isolate file transfers via programmatic IAM roles.
    * Provisions a strictly-isolated **VM Instance Identity Account** (`vdi-vm-sa`).

4.  **Configure the project:**
    * Follow the format in `config/config.yaml` and replace the placeholder values with your GCP options.
    * Ensure you place the newly created VM Identity (`vdi-vm-sa@...`) as the `service_account` option under your users if leveraging configuration file mappings.
    * Upload your initialized `config/config.yaml` file to the GCS bucket dynamically generated.

5.  **Deploy the Orchestrator Cloud Function:**
    * Deploy the `main.py` utilizing your dedicated IAM profile.

        ```bash
        gcloud functions deploy gcp-dev-vdi \
            --runtime python39 \
            --service-account="vdi-deployer-sa@your-gcp-project-id.iam.gserviceaccount.com" \
            --trigger-resource="vdi-config-your-gcp-project-id" \
            --trigger-event google.storage.object.finalize
        ```

## Configuration & OS Selection

To configure your VDI VMs, Edit `config/config.yaml`.
You can select the Operating System by changing the `source_image`.

### Secure Startup File Injection
The project supports securely copying files directly from an internal GCS bucket into VM deployments at boot time without exposing the GCS bucket to the external internet or leaking long-lived IAM permissions.

**How it works:**
1. You define files under the `startup_files` array within `config.yaml`.
2. You **must** provide the generated VM Identity `vdi-vm-sa` as the specific `service_account` for the VM to facilitate the transfer.
3. The deployment Cloud Function (`main.py`) temporarily grants this Service Account the `roles/storage.objectViewer` permission mapping strictly against **only the specific runtime files you configured**. The rest of the GCS bucket contents are entirely concealed. This temporary isolated logic relies on an IAM Condition natively restricting access to a predefined duration (defaulting to 30 minutes, configurable via `startup_timeout_minutes`).
4. The script automatically injects the download commands natively into the VM's OS:
   - **Linux:** Uses `gsutil cp gs://... /path/`
   - **Windows:** Uses PowerShell `& gcloud storage cp gs://... 'C:\path'`
5. Access is completely revoked natively by IAM after the configured timeout elapses, securing the bucket even if the VM is later compromised.

**Setup Requirement:** The Service Account that executes your continuous deployment Cloud Function must have permission to manage IAM policies on the target bucket (e.g., `roles/storage.admin` or `roles/storage.legacyBucketOwner`).

### Sample `config.yaml`

```yaml
zone: "us-central1-a"

# Optional: Number of minutes before the VM's access to startup_files expires natively in IAM. Default is 30.
startup_timeout_minutes: 30

users:
  # Linux (Debian 11) - Recommended for general dev
  - username: "user1"
    instance_name: "dev-vm-user1"
    machine_type: "e2-medium"
    boot_disk_size_gb: 50
    email: "user1@example.com"
    source_image: "projects/debian-cloud/global/images/family/debian-11"
    # Optional: Required if using startup_files
    service_account: "my-vdi-sa@my-gcp-project-id.iam.gserviceaccount.com"
    startup_files:
      - source_gcs_uri: "gs://your-bucket-name/folder/custom-config.sh"
        destination_path: "/etc/custom-config.sh"

  # Linux (Ubuntu 20.04)
  - username: "user2"
    instance_name: "dev-vm-user2"
    machine_type: "e2-standard-2"
    boot_disk_size_gb: 100
    email: "user2@example.com"
    source_image: "projects/ubuntu-os-cloud/global/images/family/ubuntu-2004-lts"

  # Windows Server 2019 - Required for Windows-specific tools
  - username: "user3"
    instance_name: "dev-vm-user3"
    machine_type: "e2-medium"
    boot_disk_size_gb: 50
    email: "user3@example.com"
    source_image: "projects/windows-cloud/global/images/family/windows-2019"
```

### Supported OS Families
*   **Debian 11**: `projects/debian-cloud/global/images/family/debian-11`
*   **Ubuntu 20.04**: `projects/ubuntu-os-cloud/global/images/family/ubuntu-2004-lts`
*   **Windows 2019**: `projects/windows-cloud/global/images/family/windows-2019`


## Usage

1.  **Modify the configuration:**

    *   To create or modify a VM, update the `config/config.yaml` file and upload it to the GCS bucket.
    *   The Cloud Function will be triggered automatically and will create or modify the VM accordingly.

2.  **Generate the Chrome Remote Desktop link:**

    *   Run the `generate_crd_link.py` script to generate the Chrome Remote Desktop link for a user.

        ```
        python scripts/generate_crd_link.py --email user@example.com --instance_name dev-vm-user1
        ```

    *   Open the generated link in Chrome to connect to the VM.

3.  **YubiKey / Smart Card Access:**

    **How it works:**
    *   **Linux**: Uses `xrdp` combined with `pcscd` (PC/SC Smart Card Daemon) to redirect smart cards from the client to the VM.
    *   **Windows**: Uses native RDP smart card redirection. The startup script installs `Gpg4win` and `YubiKey Manager` automatically.

    **RDP Client Setup:**
    1.  **Add PC**: Enter the External IP of your VM.
    2.  **Edit Settings**:
        *   **macOS (Microsoft Remote Desktop)**: Right-click PC > Edit > **Devices & Audio** > Check **Smart Cards**.
        *   **Windows (Remote Desktop Connection)**: Show Options > **Local Resources** > More... > Check **Smart cards**.
    3.  **Connect**: Launch the session.
    4.  **Verify**: Open a terminal/PowerShell inside the VM and run `gpg --card-status`.
