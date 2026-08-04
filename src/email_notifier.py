"""
Email notification module for committee review.
Supports SendGrid HTTPS API as primary, SMTP as fallback.
"""
import os
from typing import Optional
from src.config import settings

try:
    import requests
except Exception:
    requests = None  # type: ignore


class EmailNotifier:
    @staticmethod
    def send_intervention_notification(
        to_email: str,
        journal_name: str,
        parameter_name: str,
        parameter_value: str,
        eval_id: int,
        issue_description: str = ""
    ):
        """Send email notification for new intervention via SendGrid API or SMTP."""
        subject = f"Journal Review Request: {journal_name} - {parameter_name}"
        committee_email = settings.COMMITTEE_EMAIL
        
        body = f"""
New manual review request submitted for journal evaluation.

Journal: {journal_name}
Evaluation ID: {eval_id}
Parameter: {parameter_name}
Provided Value: {parameter_value}
Issue Description: {issue_description or 'No description provided'}

Please review this intervention in the admin panel:
https://mtu-journal-evaluator.onrender.com/admin/interventions

Committee email: {committee_email}

---
MTU Journal Evaluator
        """.strip()
        
        print(f"[EMAIL NOTIFICATION] Preparing email to={to_email}, subject={subject}")
        
        # Try SendGrid HTTPS API first
        sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        from_email = os.getenv("FROM_EMAIL", committee_email)
        
        if sendgrid_api_key and requests:
            try:
                resp = requests.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {sendgrid_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "personalizations": [{
                            "to": [{"email": to_email}],
                            "subject": subject
                        }],
                        "from": {"email": from_email, "name": "MTU Journal Evaluator"},
                        "content": [{
                            "type": "text/plain",
                            "value": body
                        }]
                    },
                    timeout=15
                )
                print(f"[EMAIL - SendGrid] status={resp.status_code}")
                if resp.status_code in (200, 202):
                    print(f"[EMAIL SENT via SendGrid] To: {to_email}, Subject: {subject}")
                    return True
                else:
                    print(f"[EMAIL ERROR - SendGrid] {resp.status_code}: {resp.text[:500]}")
            except Exception as e:
                print(f"[EMAIL ERROR - SendGrid] {e}")
        elif sendgrid_api_key and not requests:
            print("[EMAIL ERROR] requests library not available for SendGrid")
        
        # Fallback to SMTP if SendGrid not configured
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "0"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        
        if all([smtp_host, smtp_port, smtp_user, smtp_password]):
            try:
                msg = MIMEMultipart()
                msg['From'] = from_email
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.send_message(msg)
                
                print(f"[EMAIL SENT via SMTP] To: {to_email}, Subject: {subject}")
                return True
            except Exception as e:
                print(f"[EMAIL ERROR - SMTP] {e}")
        
        # Final fallback: log to console
        print(f"[EMAIL NOTIFICATION] To: {to_email}")
        print(f"[EMAIL NOTIFICATION] Subject: {subject}")
        print(f"[EMAIL NOTIFICATION] Body:\n{body}")
        print("[EMAIL NOTIFICATION] NOTE: No email provider configured.")
        print("  Set SENDGRID_API_KEY + FROM_EMAIL for HTTPS delivery, or")
        print("  SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD for SMTP.")
        
        return False
