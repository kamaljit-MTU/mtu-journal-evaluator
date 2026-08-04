"""
Email notification module for committee review.
Supports Brevo HTTPS API as primary, SMTP as fallback.
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from src.config import settings
import requests


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
        """Send email notification for new intervention via Brevo API or SMTP."""
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
        
        # Try Brevo HTTPS API first
        brevo_api_key = os.getenv("BREVO_API_KEY")
        from_email = os.getenv("FROM_EMAIL", settings.COMMITTEE_EMAIL)
        
        if brevo_api_key and from_email:
            try:
                resp = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "api-key": brevo_api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    json={
                        "sender": {
                            "name": "MTU Journal Evaluator",
                            "email": from_email
                        },
                        "to": [{"email": to_email}],
                        "subject": subject,
                        "textContent": body
                    },
                    timeout=15
                )
                if resp.status_code in (200, 201):
                    print(f"[EMAIL SENT via Brevo] To: {to_email}, Subject: {subject}")
                    return True
                else:
                    print(f"[EMAIL ERROR - Brevo] {resp.status_code}: {resp.text[:300]}")
            except Exception as e:
                print(f"[EMAIL ERROR - Brevo] {e}")
        
        # Fallback to SMTP if Brevo not configured
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "0"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        
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
                
                print(f"[EMAIL SENT via SMTP] To: {to_email}, Subject: {subject}")
                return True
            except Exception as e:
                print(f"[EMAIL ERROR - SMTP] {e}")
        
        # Fallback: log to console
        print(f"[EMAIL NOTIFICATION] To: {to_email}")
        print(f"[EMAIL NOTIFICATION] Subject: {subject}")
        print(f"[EMAIL NOTIFICATION] Body:\n{body}")
        print("[EMAIL NOTIFICATION] NOTE: No email provider configured.")
        print("  Set BREVO_API_KEY + FROM_EMAIL for HTTPS delivery, or")
        print("  SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD for SMTP.")
        
        return False
