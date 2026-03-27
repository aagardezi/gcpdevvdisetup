import yaml
import os
import datetime
from google.cloud import compute_v1
from google.cloud import storage

def apply_time_bound_iam(project_id, bucket_name, service_account, instance_name, objects, timeout_minutes=30):
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    policy = bucket.get_iam_policy(requested_policy_version=3)

    # Dynamic expiration window from config
    expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_minutes)
    expiration_str = expiration.strftime('%Y-%m-%dT%H:%M:%SZ')

    # Construct strict explicit resource.name conditions mapping explicitly to each file.
    object_conditions = []
    for obj_name in objects:
        object_conditions.append(f"resource.name == 'projects/_/buckets/{bucket_name}/objects/{obj_name}'")
    
    # Example output: request.time < ... && (resource.name == 'projects/.../objects/a' || resource.name == 'projects/.../objects/b')
    obj_expr = " || ".join(object_conditions)
    full_expr = f"request.time < timestamp('{expiration_str}') && ({obj_expr})"

    # Add IAM condition
    policy.bindings.append(
        {
            "role": "roles/storage.objectViewer",
            "members": {f"serviceAccount:{service_account}"},
            "condition": {
                "title": f"TempInit",
                "description": f"Auto-expiring explicit access for VM initialization ({instance_name})",
                "expression": full_expr,
            }
        }
    )
    # Ensure version is 3 to enable conditions
    policy.version = 3
    bucket.set_iam_policy(policy)

def create_instance(project_id, zone, instance_name, machine_type, boot_disk_size_gb, startup_script, source_image, windows_startup_script, service_account=None, startup_files=None, timeout_minutes=30):
    compute_client = compute_v1.InstancesClient()
    machine_type_uri = f"zones/{zone}/machineTypes/{machine_type}"

    boot_disk = {
        "initialize_params": {
            "source_image": source_image,
            "disk_size_gb": boot_disk_size_gb,
        },
        "auto_delete": True,
        "boot": True,
    }

    if startup_files and not service_account:
        raise ValueError(f"service_account must be provided in config for user {instance_name} if startup_files is used.")

    from collections import defaultdict

    if startup_files and service_account:
        buckets_to_objects = defaultdict(list)
        linux_downloads = "\n# --- Begin Injected GCS Downloads ---\n"
        windows_downloads = "\n# --- Begin Injected GCS Downloads ---\n"

        for file_config in startup_files:
            gcs_uri = file_config["source_gcs_uri"]
            dest_path = file_config["destination_path"]

            if gcs_uri.startswith("gs://"):
                parts = gcs_uri.split("/", 3)
                if len(parts) >= 4:
                    bucket_name = parts[2]
                    object_name = parts[3]
                    buckets_to_objects[bucket_name].append(object_name)

            # Apply standard file permissions
            linux_downloads += f"gsutil cp {gcs_uri} {dest_path}\nchmod 644 {dest_path} || true\n"
            windows_downloads += f"& gcloud storage cp {gcs_uri} '{dest_path}'\n"

        linux_downloads += "# --- End Injected GCS Downloads ---\n\n"
        windows_downloads += "# --- End Injected GCS Downloads ---\n\n"

        for bucket, objects in buckets_to_objects.items():
            apply_time_bound_iam(project_id, bucket, service_account, instance_name, objects, timeout_minutes)

        if "#!/bin/bash" in startup_script:
            startup_script = startup_script.replace("#!/bin/bash", "#!/bin/bash" + linux_downloads, 1)
        else:
            startup_script = linux_downloads + startup_script

        if "#Requires -RunAsAdministrator" in windows_startup_script:
            windows_startup_script = windows_startup_script.replace("#Requires -RunAsAdministrator", "#Requires -RunAsAdministrator" + windows_downloads, 1)
        else:
            windows_startup_script = windows_downloads + windows_startup_script

    # Select the startup script based on the OS
    if 'windows' in source_image.lower():
        metadata_key = 'windows-startup-script-ps1'
        metadata_value = windows_startup_script
    else:
        metadata_key = 'startup-script'
        metadata_value = startup_script

    instance = {
        "name": instance_name,
        "machine_type": machine_type_uri,
        "disks": [boot_disk],
        "network_interfaces": [
            {
                "network": "global/networks/default",
                "access_configs": [
                    {"name": "External NAT", "type": "ONE_TO_ONE_NAT"}
                ],
            }
        ],
        "metadata": {
            "items": [
                {
                    "key": metadata_key,
                    "value": metadata_value
                }
            ]
        }
    }

    if service_account:
        instance["service_accounts"] = [
            {
                "email": service_account,
                "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
            }
        ]

    operation = compute_client.insert(project=project_id, zone=zone, instance_resource=instance)
    return operation.result()

def main(event, context):
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    project_id = os.environ.get('GCP_PROJECT')
    if not project_id:
        raise ValueError("GCP_PROJECT environment variable not set")

    zone = config["zone"]
    timeout_minutes = config.get("startup_timeout_minutes", 30)

    startup_script = """
    #!/bin/bash
    # Function to install packages on Debian-based systems
    install_debian() {
        sudo apt-get update
        sudo apt-get install -y xfce4 desktop-base
        sudo apt-get install -y --assume-yes wget
        wget https://dl.google.com/linux/direct/chrome-remote-desktop_current_amd64.deb
        sudo dpkg --install chrome-remote-desktop_current_amd64.deb
        sudo apt-get install -y --assume-yes --fix-broken
        sudo DEBIAN_FRONTEND=noninteractive \
            apt-get install -y xfce4 desktop-base
        
        # Install RDP and Smart Card support
        sudo apt-get install -y xrdp pcscd scdaemon gpg
        sudo systemctl enable pcscd
        sudo systemctl start pcscd
        sudo systemctl enable xrdp
        sudo systemctl start xrdp
        if getent group ssl-cert > /dev/null; then
            sudo adduser xrdp ssl-cert
        fi
        
        sudo bash -c 'echo "exec /etc/X11/Xsession /usr/bin/xfce4-session" > /etc/chrome-remote-desktop-session'
        # Configure xrdp to use xfce4
        # Fix Polkit issues for XRDP (color manager prompts)
        sudo mkdir -p /etc/polkit-1/localauthority/50-local.d
        sudo bash -c 'cat > /etc/polkit-1/localauthority/50-local.d/45-allow-colord.pkla <<EOF
[Allow Colord all Users]
Identity=unix-user:*
Action=org.freedesktop.color-manager.create-device;org.freedesktop.color-manager.create-profile;org.freedesktop.color-manager.delete-device;org.freedesktop.color-manager.delete-profile;org.freedesktop.color-manager.modify-device;org.freedesktop.color-manager.modify-profile
ResultAny=no
ResultInactive=no
ResultActive=yes
EOF'

        # Force XFCE4 for XRDP
        if [ -f /etc/xrdp/startwm.sh ]; then
            sudo cp /etc/xrdp/startwm.sh /etc/xrdp/startwm.sh.bak
            sudo bash -c 'cat > /etc/xrdp/startwm.sh <<EOF
#!/bin/sh
if [ -r /etc/profile ]; then
    . /etc/profile
fi
unset DBUS_SESSION_BUS_ADDRESS
unset XDG_RUNTIME_DIR
test -x /etc/X11/Xsession && exec /etc/X11/Xsession
exec /usr/bin/startxfce4
EOF'
            sudo chmod +x /etc/xrdp/startwm.sh
        fi

        sudo systemctl disable lightdm.service
        sudo systemctl stop lightdm.service
    }

    # Function to install packages on Red Hat-based systems
    install_redhat() {
        sudo yum update -y
        sudo yum groupinstall -y "Xfce"
        sudo yum install -y wget
        wget https://dl.google.com/linux/direct/chrome-remote-desktop_current_x86_64.rpm
        sudo yum install -y chrome-remote-desktop_current_x86_64.rpm
        
        # Install RDP and Smart Card support (EPEL might be needed for xrdp on some RHEL/CentOS versions)
        sudo yum install -y epel-release || true
        sudo yum install -y xrdp pcscd scdaemon gpg
        sudo systemctl enable pcscd
        sudo systemctl start pcscd
        sudo systemctl enable xrdp
        sudo systemctl start xrdp
        
        sudo bash -c 'echo "exec /usr/bin/xfce4-session" > /etc/chrome-remote-desktop-session'
        
        # Configure xrdp to use xfce4
        if [ -f /etc/xrdp/startwm.sh ]; then
            sudo cp /etc/xrdp/startwm.sh /etc/xrdp/startwm.sh.bak
            sudo bash -c 'echo "startxfce4" >> /etc/xrdp/startwm.sh'
        fi
    }

    # Detect the OS and install packages accordingly
    if [ -f /etc/debian_version ]; then
        install_debian
    elif [ -f /etc/redhat-release ]; then
        install_redhat
    else
        echo "Unsupported operating system."
        exit 1
    fi
    """

    windows_startup_script = """
    #Requires -RunAsAdministrator

    # Set up Chocolatey
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

    # Install tools for YubiKey and Development
    choco install -y gpg4win yubikey-manager git googlechrome

    #Downloads the Chrome Remote Desktop Host installer
    $installer_url = "https://dl.google.com/dl/edgedl/chrome-remote-desktop/chromeremotedesktophost.msi"
    $installer_path = "$env:TEMP\chromeremotedesktophost.msi"
    (New-Object System.Net.WebClient).DownloadFile($installer_url, $installer_path)

    #Installs the Chrome Remote Desktop Host
    & msiexec.exe /i $installer_path /quiet /qn /norestart

    #Removes the installer
    Remove-Item $installer_path
    """

    for user in config["users"]:
        create_instance(
            project_id=project_id,
            zone=zone,
            instance_name=user["instance_name"],
            machine_type=user["machine_type"],
            boot_disk_size_gb=user["boot_disk_size_gb"],
            startup_script=startup_script,
            source_image=user["source_image"],
            windows_startup_script=windows_startup_script,
            service_account=user.get("service_account"),
            startup_files=user.get("startup_files"),
            timeout_minutes=timeout_minutes
        )

if __name__ == "__main__":
    main(None, None)
