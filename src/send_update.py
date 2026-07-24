"""
send_update.py  -  Send a one-off written status update to the recipients,
attaching the latest report. Uses the same Gmail SMTP path as send_report.py.
"""
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())
REPORTS = ROOT / "data" / "reports"

SUBJECT = "EV Charger Pilot — status update + 7/23 report"

BODY = """Adam & Todd,

A quick written record of where the Bellevue EV charger pilot stands, so we both have it on file.

DATA COLLECTION IS HEALTHY. The system has been polling all ~75 Bellevue public chargers every 30 minutes, 7am-9pm. The first clean full day (Wednesday 7/23) is attached.

7/23 HEADLINE:
- 26 readings across the day (every ~30 min)
- 70 usable chargers (5 were offline all day and excluded)
- Average occupancy: ~26.5%
- ~23% of usable chargers sat completely unused

(Two earlier days were under-sampled due to a technical issue and should not be read as representative — each report flags its own sample count.)

ONE TRANSPARENCY NOTE: the automated nightly emails were interrupted for a few nights. The report-and-send step had been running on an unreliable scheduler that silently skipped. The underlying data was fine the entire time — only the email delivery was affected. That is now fixed: the nightly report + email runs off the reliable collector, so nightly emails resume tonight.

The pilot is extended through 7/31, and nightly reports will arrive automatically each evening.

- Adam
"""


def latest_report():
    files = sorted(REPORTS.glob("EV_Bellevue_Report_*.xlsx"))
    return files[-1] if files else None


def main():
    sender = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    if not sender or not pw:
        print("No GMAIL creds; cannot send."); return
    recipients = CONFIG["email"]["recipients"]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = SUBJECT
    msg.set_content(BODY)

    rep = latest_report()
    if rep:
        msg.add_attachment(rep.read_bytes(), maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           filename=rep.name)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, pw)
        s.send_message(msg)
    print(f"Update emailed to {', '.join(recipients)}"
          + (f" with {rep.name}" if rep else ""))


if __name__ == "__main__":
    main()
