import subprocess
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

STATE_FILE = "prev_versions.json"

EMAIL_CONFIG = {
    "to": "ngetachew277@gmail.com",
    "user": "ngetachew277@gmail.com",
    "pass": "hxvuijrkimqtsatr",
    "smtp": "smtp.gmail.com",
    "port": 587
}

# Installed versions in your environment
current_versions = {
    "dnac": "2.3.7.7",
    "ise": "3.5",
    "ftd": "7.4.2.1",
    "checkpoint": "R82"
}

def run(cmd):
    """Run shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

def scrape_latest():
    """Scrape the latest versions from vendor websites."""
    latest = {}

    latest["ise"] = run(
        'curl -s "https://www.cisco.com/c/en/us/support/security/identity-services-engine/products-release-notes-list.html" | grep -o "Release 3\\.5" | head -1 | sed "s/Release //"'
    )

    latest["dnac"] = run(
        'curl -s https://www.cisco.com/c/en/us/td/docs/cloud-systems-management/network-automation-and-management/catalyst-center/2-3-7/release_notes/b_cisco_catalyst_center_237_release_notes.html | grep -oE "Release 2\\.3\\.7\\.[0-9]+" | awk \'{print $2}\' | sort -Vr | head -1'
    )

    latest["checkpoint"] = run(
        'curl -s "https://support.checkpoint.com/results/sk/sk152052" | grep -o "R82\\.10" | head -1'
    )

    latest["ftd"] = run(
        'curl -s "https://www.cisco.com/c/en/us/support/security/firepower-ngfw/products-release-notes-list.html" | grep -oE "Release 7\\.[0-9]\\.[0-9](\\.[0-9])?" | head -1 | awk \'{print $2}\''
    )

    return latest

def load_prev():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}

def save_prev(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)

def send_alert(mismatches):
    msg = MIMEMultipart()
    msg["Subject"] = "🚨 Version Update Detected"
    body = "<h3>Version Mismatch Detected</h3><ul>"
    for m in mismatches:
        body += f"<li>{m['vendor'].upper()} : Installed {m['current']} → Latest {m['latest']}</li>"
    body += "</ul>"
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP(EMAIL_CONFIG["smtp"], EMAIL_CONFIG["port"]) as server:
        server.starttls()
        server.login(EMAIL_CONFIG["user"], EMAIL_CONFIG["pass"])
        server.sendmail(EMAIL_CONFIG["user"], EMAIL_CONFIG["to"], msg.as_string())
    print("Alert sent.")

def main():
    prev = load_prev()  # Load previous scrape (empty on first run)
    latest = scrape_latest()

    mismatches = []

    if not prev:
        # First run: compare current vs latest
        for vendor in latest:
            if latest[vendor] != current_versions.get(vendor):
                mismatches.append({
                    "vendor": vendor,
                    "current": current_versions.get(vendor),
                    "latest": latest[vendor]
                })
    else:
        # Subsequent runs: check if latest changed from prev
        for vendor in latest:
            if latest[vendor] != prev.get(vendor):
                # Only alert if current != latest
                if latest[vendor] != current_versions.get(vendor):
                    mismatches.append({
                        "vendor": vendor,
                        "current": current_versions.get(vendor),
                        "latest": latest[vendor]
                    })

    if mismatches:
        send_alert(mismatches)
    else:
        print("No updates detected.")

    # Always update prev for next run
    save_prev(latest)
    print("Prev versions updated for next run.")

if __name__ == "__main__":
    main()
