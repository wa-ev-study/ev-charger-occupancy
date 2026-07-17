"""
send_report.py  -  Email the day's Excel report to the recipients.

Sends through Gmail using an App Password (free). Credentials come from
environment variables set as GitHub Secrets:
    GMAIL_ADDRESS        the project Gmail address (sender)
    GMAIL_APP_PASSWORD   a 16-character Google App Password

If credentials are missing it prints a notice and exits 0 (so dry runs without
secrets don't fail the workflow).
"""

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
TZ = ZoneInfo(CONFIG["project"]["timezone"])
REPORTS = ROOT / "data" / "reports"


def latest_report():
    files = sorted(REPORTS.glob("EV_Bellevue_Report_*.xlsx"))
    return files[-1] if files else None


def md_to_text(md):
    out = []
    for ln in md.splitlines():
        ln = ln.replace("**", "").replace("`", "")
        if ln.startswith("# "):
            ln = ln[2:]
        elif ln.startswith("## "):
            ln = ln[3:].upper()
        elif ln.startswith("- "):
            ln = "  - " + ln[2:]
        out.append(ln)
    return "\n".join(out)


def main():
    if not CONFIG.get("email", {}).get("enabled"):
        print("Email disabled in config."); return
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not sender or not app_pw:
        print("No GMAIL_ADDRESS / GMAIL_APP_PASSWORD set — skipping send "
              "(expected in a dry run without secrets).")
        return

    report = latest_report()
    if not report:
        print("No report file to send."); return
    body_md = (REPORTS / "_email_body.md")
    body = md_to_text(body_md.read_text()) if body_md.exists() else "See attached report."

    recipients = CONFIG["email"]["recipients"]
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    subject = f"{CONFIG['email']['subject_prefix']} — {today}"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(report.read_bytes(), maintype="application",
                       subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       filename=report.name)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_pw)
        server.send_message(msg)
    print(f"Emailed {report.name} to {', '.join(recipients)}")


if __name__ == "__main__":
    main()
