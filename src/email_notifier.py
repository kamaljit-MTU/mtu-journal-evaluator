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
        
        # For now, just log the email. Actual SMTP configuration can be added later.
        print(f"[EMAIL NOTIFICATION] To: {to_email}")
        print(f"[EMAIL NOTIFICATION] Subject: {subject}")
        print(f"[EMAIL NOTIFICATION] Body:\n{body}")
        
        # TODO: Add SMTP configuration when email credentials are available
        # SMTP settings would come from environment variables:
        # SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL
        
        return True
