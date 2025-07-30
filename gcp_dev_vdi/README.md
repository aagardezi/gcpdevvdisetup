# GCP Dev VDI Setup

This project automates the deployment and management of development VDI VMs in GCP that can be accessed via Chrome Remote access to the VMs.

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
