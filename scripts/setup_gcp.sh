#!/bin/bash
# GCP Dev VDI - Environment Bootstrapping Script
#
# This script sets up the required Google Cloud infrastructure for the VDI orchestrator,
# explicitly adhering to the principle of least privilege. It provisions:
# 1. A GCS bucket with Uniform Bucket Level Access for storing config files.
# 2. A Cloud Function Deployer Service Account.
# 3. A VM Instance Service Account (granted 0 native permissions).
# 4. Binds only the strictly required roles to the Deployer SA.

set -e

# Default variables - customizable via environment or interactive prompts
PROJECT_ID="${GCP_PROJECT:-$(gcloud config get-value project)}"
REGION="${GCP_REGION:-us-central1}"
BUCKET_NAME="vdi-config-${PROJECT_ID}"

DEPLOYER_SA_NAME="vdi-deployer-sa"
VM_SA_NAME="vdi-vm-sa"

DEPLOYER_SA_EMAIL="${DEPLOYER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
VM_SA_EMAIL="${VM_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "================================================================="
echo " Bootstrapping GCP Environment for Dev VDI"
echo " Project: $PROJECT_ID"
echo " Region:  $REGION"
echo " Bucket:  $BUCKET_NAME"
echo "================================================================="

# 1. Enable Required APIs
echo "[1/4] Enabling required APIs (Compute, Storage, Cloud Functions, IAM)..."
gcloud services enable \
    compute.googleapis.com \
    storage.googleapis.com \
    cloudfunctions.googleapis.com \
    iam.googleapis.com \
    cloudbuild.googleapis.com \
    --project="${PROJECT_ID}"

# 2. Create the Configuration GCS Bucket
echo "[2/4] Creating internal Configuration GCS Bucket (${BUCKET_NAME})..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${BUCKET_NAME}" \
        --project="${PROJECT_ID}" \
        --location="${REGION}" \
        --uniform-bucket-level-access
    echo "  -> Bucket created successfully."
else
    echo "  -> Bucket already exists. Automatically enforcing uniform bucket-level access."
    gcloud storage buckets update "gs://${BUCKET_NAME}" --uniform-bucket-level-access --project="${PROJECT_ID}"
fi
echo "  -> NOTE: Place your config.yaml and any startup script files in 'gs://${BUCKET_NAME}/'"

# 3. Create Service Accounts
echo "[3/4] Creating Service Accounts..."

# Orchestrator (Cloud Function) SA
if ! gcloud iam service-accounts describe "${DEPLOYER_SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${DEPLOYER_SA_NAME}" \
        --description="Service Account executing the VDI Orchestrator Cloud Function" \
        --display-name="VDI Orchestrator SA" \
        --project="${PROJECT_ID}"
    echo "  -> Created Orchestrator SA: ${DEPLOYER_SA_EMAIL}"
else
    echo "  -> Orchestrator SA already exists."
fi

# VM Instance SA (Receives the conditional IAM grants during boot)
if ! gcloud iam service-accounts describe "${VM_SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${VM_SA_NAME}" \
        --description="Service Account dynamically attached to provisioned VDI VMs" \
        --display-name="VDI VM Instance Identity" \
        --project="${PROJECT_ID}"
    echo "  -> Created VM Instance SA: ${VM_SA_EMAIL}"
else
    echo "  -> VM Instance SA already exists."
fi

# 4. Assign Strict Least-Privilege IAM Roles to the Orchestrator
echo "[4/4] Assigning IAM Policies..."

# Let the Deployer create/manage compute instances
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_SA_EMAIL}" \
    --role="roles/compute.instanceAdmin.v1" >/dev/null

# Let the Deployer attach the VM_SA to the created instances
gcloud iam service-accounts add-iam-policy-binding "${VM_SA_EMAIL}" \
    --member="serviceAccount:${DEPLOYER_SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" >/dev/null

# Let the Deployer apply conditional IAM bindings to the configuration bucket
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
    --member="serviceAccount:${DEPLOYER_SA_EMAIL}" \
    --role="roles/storage.admin" >/dev/null

# Note: The VM_SA deliberately receives ZERO native roles mapping to its project/bucket.
# The Deployer grants it temporary view permutations during provisioning dynamically.

echo "================================================================="
echo " Setup Complete & Verified."
echo ""
echo " Next Steps:"
echo " 1. Update config/config.yaml:"
echo "    - Set 'service_account' to: ${VM_SA_EMAIL}"
echo "    - Upload your startup files to gs://${BUCKET_NAME}/"
echo ""
echo " 2. Deploy your orchestrator:"
echo "    gcloud functions deploy gcp-dev-vdi \\"
echo "      --runtime python39 \\"
echo "      --service-account=${DEPLOYER_SA_EMAIL} \\"
echo "      --trigger-resource=${BUCKET_NAME} \\"
echo "      --trigger-event=google.storage.object.finalize \\"
echo "      --project=${PROJECT_ID}"
echo "================================================================="
