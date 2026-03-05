import subprocess
import json
import os
import datetime
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
    latest["checkpoint"] = run(f'curl -sLk -A "{UA}" "https://support.checkpoint.com/results/sk/sk152052" | grep -oE "R[0-9]{{2}}\.[0-9]{{2}}" | head -1')    # FTD
    
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
    # Dynamic subject
    msg["Subject"] = f"🚀 ACTION REQUIRED: {len(mismatches)} Network Appliance Updates Available"
    msg["From"] = f"Network Monitor <{EMAIL_CONFIG['user']}>"
    msg["To"] = EMAIL_CONFIG["to"]

    # Metadata
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hostname = "ubu-01" 

    # 1. HTML Header and Styling
    html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background-color: #f4f7f9; color: #333;">
        <div style="max-width: 650px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border: 1px solid #e1e4e8;">
            <div style="background: linear-gradient(135deg, #004a99 0%, #002d5f 100%); color: white; padding: 30px; text-align: center;">
                <div style="font-size: 40px; margin-bottom: 10px;">🔔</div>
                <h2 style="margin: 0; font-weight: 600; letter-spacing: 0.5px;">Network Update Advisory</h2>
                <p style="margin: 5px 0 0; opacity: 0.8; font-size: 14px;">Outdated firmware detected on critical infrastructure</p>
            </div>
            <div style="padding: 30px;">
                <p style="font-size: 16px; line-height: 1.6;">Hello Admin,</p>
                <p style="font-size: 15px; line-height: 1.6; color: #555;">
                    The automated scan on <strong>{hostname}</strong> has identified versions that are behind the latest vendor releases.
                </p>
                <table style="width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 20px; border: 1px solid #edf2f7; border-radius: 8px; overflow: hidden;">
                    <thead>
                        <tr style="background-color: #f8fafc;">
                            <th style="padding: 15px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b; border-bottom: 2px solid #edf2f7;">Appliance</th>
                            <th style="padding: 15px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b; border-bottom: 2px solid #edf2f7;">Running</th>
                            <th style="padding: 15px; text-align: left; font-size: 12px; text-transform: uppercase; color: #64748b; border-bottom: 2px solid #edf2f7;">Available</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    # 2. Loop through mismatches to add rows
    for m in mismatches:
        html += f"""
                        <tr>
                            <td style="padding: 18px; border-bottom: 1px solid #edf2f7;">
                                <span style="font-weight: 700; color: #1e293b;">{m['vendor'].upper()}</span>
                            </td>
                            <td style="padding: 18px; border-bottom: 1px solid #edf2f7; color: #64748b; font-family: 'Courier New', monospace;">
                                {m['current']}
                            </td>
                            <td style="padding: 18px; border-bottom: 1px solid #edf2f7;">
                                <span style="background-color: #fef3c7; color: #92400e; padding: 6px 12px; border-radius: 20px; font-weight: bold; font-size: 13px; border: 1px solid #fde68a;">
                                    🚀 {m['latest']}
                                </span>
                            </td>
                        </tr>
        """

    # 3. Add the single Footer and close all tags
    html += f"""
                    </tbody>
                </table>
                <div style="margin-top: 30px; padding: 20px; background-color: #f0f7ff; border-radius: 8px; border-left: 4px solid #004a99;">
                    <p style="margin: 0; font-size: 14px; color: #004a99; font-weight: 600;">Next Steps:</p>
                    <ul style="margin: 10px 0 0; padding-left: 20px; font-size: 13px; color: #475569;">
                        <li>Verify compatibility in the lab environment.</li>
                        <li>Download updates from official vendor portals.</li>
                    </ul>
                </div>
            </div>
            <div style="background-color: #f8fafc; padding: 20px; text-align: center; border-top: 1px solid #edf2f7;">
                <p style="margin: 0; font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;">
                    Scan completed at {now} | Source: {hostname}
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    # 4. Attach ONCE and send
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
