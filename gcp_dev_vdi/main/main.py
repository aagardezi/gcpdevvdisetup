import yaml
import os
from google.cloud import compute_v1

def create_instance(project_id, zone, instance_name, machine_type, boot_disk_size_gb, startup_script, source_image, windows_startup_script):
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

    operation = compute_client.insert(project=project_id, zone=zone, instance_resource=instance)
    return operation.result()

def main(event, context):
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    project_id = os.environ.get('GCP_PROJECT')
    if not project_id:
        raise ValueError("GCP_PROJECT environment variable not set")

    zone = config["zone"]

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
            project_id,
            zone,
            user["instance_name"],
            user["machine_type"],
            user["boot_disk_size_gb"],
            startup_script,
            user["source_image"],
            windows_startup_script
        )

if __name__ == "__main__":
    main(None, None)
