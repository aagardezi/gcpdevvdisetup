import argparse
import urllib.parse

def generate_crd_link(email, instance_name):
    base_url = "https://remotedesktop.google.com/access/session"
    params = {
        "user_email": email,
        "host_name": instance_name,
        "auth_code": "",  # This will be filled in by the user
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--instance_name", required=True)
    args = parser.parse_args()

    link = generate_crd_link(args.email, args.instance_name)
    print(f"Chrome Remote Desktop link: {link}")
