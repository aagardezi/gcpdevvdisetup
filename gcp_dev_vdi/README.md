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

3.  **Configure the project:**

    *   Open `config/config.yaml` and replace the placeholder values with your GCP project ID, zone, and user information.

4.  **Set up a GCS bucket:**

    *   Create a GCS bucket to store the `config.yaml` file.
    *   Upload the `config/config.yaml` file to the GCS bucket.

5.  **Deploy the Cloud Function:**

    *   Deploy the `main.py` script as a Cloud Function that is triggered by changes to the `config.yaml` file in the GCS bucket.

        ```
        gcloud functions deploy gcp-dev-vdi --runtime python39 --trigger-resource your-gcs-bucket-name --trigger-event google.storage.object.finalize
        ```

## Configuration & OS Selection

To configure your VDI VMs, Edit `config/config.yaml`.
You can select the Operating System by changing the `source_image`.

### Sample `config.yaml`

```yaml
zone: "us-central1-a"

users:
  # Linux (Debian 11) - Recommended for general dev
  - username: "user1"
    instance_name: "dev-vm-user1"
    machine_type: "e2-medium"
    boot_disk_size_gb: 50
    email: "user1@example.com"
    source_image: "projects/debian-cloud/global/images/family/debian-11"

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
