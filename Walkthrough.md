# Access & YubiKey Verification Walkthrough

This guide explains how to access your GCP VDI VM and verify YubiKey smart card usage.

> [!IMPORTANT]
> **Use RDP for YubiKey**: Chrome Remote Desktop (CRD) on Linux does **not** support smart card redirection. You must use an RDP client to use your YubiKey for GPG/SSH operations. Use CRD for general low-latency access.

## Prerequisites

1.  **YubiKey**: Inserted into your local machine.
2.  **RDP Client** (for YubiKey):
    - **macOS**: [Microsoft Remote Desktop](https://apps.apple.com/us/app/microsoft-remote-desktop/id1295203466?mt=12)
    - **Windows**: Remote Desktop Connection.
3.  **Chrome Browser** (for Chrome Remote Desktop).

## Method 1: RDP (Required for YubiKey)

### 1. Configure RDP Client

You must explicitly enable smart card redirection.

**Microsoft Remote Desktop (macOS):**

1.  Add PC: `YOUR_VM_EXTERNAL_IP`.
2.  Right-click -> **Edit**.
3.  **Devices & Audio** -> Check **Smart Cards**.
4.  Save.

**Windows Remote Desktop:**

1.  **Show Options** -> **Local Resources** -> **More...**
2.  Check **Smart cards**.
3.  **OK** -> **Connect**.

### 2. Connect & Verify

1.  Connect to the VM via RDP.
2.  Open a **Terminal**.
3.  Run:
    ```bash
    gpg --card-status
    ```
4.  **Success**: You see your YubiKey details (Reader: Yubico...).
    **Failure**: "OpenPGP card not available" (Check RDP settings or restart `gpg-agent`).

### 3. Decrypt a File

1.  Run: `gpg --decrypt secret.txt.gpg`
2.  Enter PIN if prompted.

## Method 2: Windows VM (RDP Required for YubiKey)

Windows VMs also require RDP for smart card redirection.

### 1. Prerequisites

- **Gpg4win**: Installed automatically by the startup script.
- **YubiKey Manager**: Installed automatically.

### 2. Connect

1.  Use **Microsoft Remote Desktop** (macOS) or **Remote Desktop Connection** (Windows).
2.  Enable **Smart Cards** in the redirection settings (same as Linux).
3.  Connect to the VM.

### 3. Verify

1.  Open **PowerShell** (not CMD, for better encoding support).
2.  Run:
    ```powershell
    gpg --card-status
    ```
3.  **Success**: You should see the YubiKey details.

## Method 3: Chrome Remote Desktop (General Access)

Use this for general work if you don't need the YubiKey attached.

### 1. Generate Setup Link

On your local machine, run the helper script:

```bash
python scripts/generate_crd_link.py --email your@email.com --instance_name your-vm-name
```

Open the generated URL in Chrome.

### 2. Authorize & Setup

1.  Follow the instructions in the browser to "Set up via SSH".
2.  Copy the command (starts with `DISPLAY= /opt/google/...`).
3.  **SSH** into your VM (or use RDP).
4.  Paste and run the command to register the host.
5.  Set a simplified PIN for CRD access.

### 3. Connect

Go to [remotedesktop.google.com/access](https://remotedesktop.google.com/access) and click your VM to connect.

## Troubleshooting

- **Polkit/Color Profile Prompts in RDP**:
  - The startup script applies a fix to suppress these. If they appear, click Cancel or Authenticate.
- **No Smart Card in RDP**:
  - Verify `pcscd` service: `sudo systemctl status pcscd`.
  - Verify standard user permissions (usually fine, but `plugdev` group might be needed on some OSes).
