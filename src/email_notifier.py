"""
Email notification module for committee review.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from src.config import settings


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
        """Send email notification for new intervention."""
        subject = f"Journal Review Request: {journal_name} - {parameter_name}"
        
        body = f"""
New manual review request submitted for journal evaluation.

Journal: {journal_name}
Evaluation ID: {eval_id}
Parameter: {parameter_name}
Provided Value: {parameter_value}
Issue Description: {issue_description or 'No description provided'}

Please review this intervention in the admin panel:
https://mtu-journal-evaluator.onrender.com/admin/interventions

---
MTU Journal Evaluator
        """.strip()
        
        # Try SMTP if configured
        smtp_host = getattr(settings, 'SMTP_HOST', None) or settings.SMTP_HOST if hasattr(settings, 'SMTP_HOST') else None
        from_email = getattr(settings, 'FROM_EMAIL', None)
        
        # Check if SMTP is configured
        import os
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "0"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("FROM_EMAIL")
        
        if all([smtp_host, smtp_port, smtp_user, smtp_password, from_email]):
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
                
                print(f"[EMAIL SENT] To: {to_email}, Subject: {subject}")
                return True
            except Exception as e:
                print(f"[EMAIL ERROR] Failed to send email: {e}")
                # Fall through to console logging
        
        # Fallback: log to console
        print(f"[EMAIL NOTIFICATION] To: {to_email}")
        print(f"[EMAIL NOTIFICATION] Subject: {subject}")
        print(f"[EMAIL NOTIFICATION] Body:\n{body}")
        print("[EMAIL NOTIFICATION] NOTE: SMTP not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL env vars to send actual emails.")
        
        return False
