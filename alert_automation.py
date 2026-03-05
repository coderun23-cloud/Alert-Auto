import subprocess
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuration
STATE_FILE = "prev_versions.json"
EMAIL_CONFIG = {
    "to": "ngetachew277@gmail.com",
    "user": "ngetachew277@gmail.com",
    "pass": "hxvuijrkimqtsatr",
    "smtp": "smtp.gmail.com",
    "port": 587
}

# Source of Truth
current_versions = {
    "dnac": "2.3.7.7",
    "ise": "3.4",
    "ftd": "7.3.2.1",
    "checkpoint": "R81"
}

def run(cmd):
    """Executes bash commands with a retry mechanism for network stability."""
    for _ in range(2): # Try twice if the first one fails
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, executable='/bin/bash', timeout=30)
            output = result.stdout.strip()
            if output: return output
        except Exception:
            continue
    return ""

def scrape_latest():
    """Scrape versions using browser headers to bypass blocks."""
    latest = {}
    # Modern browser User-Agent
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

    # ISE
    latest["ise"] = run(rf"""curl -sL -A "{ua}" "https://www.cisco.com/c/en/us/support/security/identity-services-engine/products-release-notes-list.html" | grep -o "Release 3\.5" | head -1 | sed 's/Release //'""")
    
    # DNAC
    latest["dnac"] = run(rf"""curl -sL -A "{ua}" "https://www.cisco.com/c/en/us/td/docs/cloud-systems-management/network-automation-and-management/catalyst-center/2-3-7/release_notes/b_cisco_catalyst_center_237_release_notes.html" | grep -oE "Release 2\.3\.7\.[0-9]+" | awk '{{print $2}}' | sort -Vr | head -1""")
    
    # CHECKPOINT - Improved to be more resilient
    latest["checkpoint"] = run(rf"""curl -sL -k -A "{ua}" "https://support.checkpoint.com/results/sk/sk152052" | grep -o "R82\.10" | head -1""")
    
    # FTD
    latest["ftd"] = run(rf"""curl -sLk -A "{ua}" "https://www.cisco.com/c/en/us/td/docs/security/secure-firewall/release-notes/threat-defense/770/threat-defense-release-notes-77.html" | grep -oE "7\.[0-9]\.[0-9]+" | sort -V | tail -1""")

    return {k: (v if v else "Not Found") for k, v in latest.items()}

def load_prev():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_prev(data):
    with open(STATE_FILE, "w") as f: json.dump(data, f, indent=4)

def send_alert(mismatches):
    msg = MIMEMultipart()
    msg["Subject"] = "🚨 Network Software Update Alert"
    msg["From"] = f"Network Admin <{EMAIL_CONFIG['user']}>"
    msg["To"] = EMAIL_CONFIG["to"]

    html = f"""
    <html>
    <body style="font-family: Arial; padding: 20px; background-color: #f4f4f4;">
        <div style="max-width: 600px; margin: auto; background: white; border: 1px solid #ddd; border-radius: 12px; overflow: hidden;">
            <div style="background-color: #004a99; color: white; padding: 25px; text-align: center;">
                <h2 style="margin: 0;">Updates Detected</h2>
            </div>
            <div style="padding: 25px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background-color: #f8f9fa; border-bottom: 2px solid #eee;">
                        <th style="padding: 12px; text-align: left;">VENDOR</th>
                        <th style="padding: 12px; text-align: left;">INSTALLED</th>
                        <th style="padding: 12px; text-align: left;">AVAILABLE</th>
                    </tr>
    """
    for m in mismatches:
        html += f"""
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 15px;"><strong>{m['vendor'].upper()}</strong></td>
                        <td style="padding: 15px;">{m['current']}</td>
                        <td style="padding: 15px;"><span style="background-color: #ffd700; padding: 5px 10px; border-radius: 4px; font-weight: bold;">{m['latest']}</span></td>
                    </tr>
        """
    html += "</table></div></div></body></html>"
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(EMAIL_CONFIG["smtp"], EMAIL_CONFIG["port"]) as server:
        server.starttls()
        server.login(EMAIL_CONFIG["user"], EMAIL_CONFIG["pass"])
        server.sendmail(EMAIL_CONFIG["user"], EMAIL_CONFIG["to"], msg.as_string())

def main():
    print("Checking versions...")
    prev_json = load_prev()
    latest_web = scrape_latest()
    mismatches = []

    for vendor, web_ver in latest_web.items():
        local_ver = current_versions.get(vendor)
        json_ver = prev_json.get(vendor)

        if web_ver == "Not Found":
            continue

        # Alert if:
        # 1. Web is different from your code (current_versions)
        # AND
        # 2. Web is different from the last time we alerted (prev_json)
        if web_ver != local_ver and web_ver != json_ver:
            mismatches.append({"vendor": vendor, "current": local_ver, "latest": web_ver})

    if mismatches:
        send_alert(mismatches)
        print("Alert sent.")
    else:
        print("No new changes to report.")

    save_prev(latest_web)
    print(f"Current State: {latest_web}")

if __name__ == "__main__":
    main()
