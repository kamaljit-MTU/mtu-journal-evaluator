"""
Telegram notification module for committee review.
"""
import os
from typing import Optional
from src.config import settings

try:
    import requests
except Exception:
    requests = None  # type: ignore


class TelegramNotifier:
    @staticmethod
    def send_intervention_notification(
        chat_id: str,
        journal_name: str,
        parameter_name: str,
        parameter_value: str,
        eval_id: int,
        issue_description: str = ""
    ):
        """Send Telegram notification for new intervention."""
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            print("[TELEGRAM] No bot token configured. Set TELEGRAM_BOT_TOKEN env var.")
            return False
        
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

Committee email: {settings.COMMITTEE_EMAIL}

---
MTU Journal Evaluator
        """.strip()
        
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": f"*{subject}*\n\n{body}",
                    "parse_mode": "Markdown"
                },
                timeout=15
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                print(f"[TELEGRAM SENT] chat_id={chat_id}, subject={subject}")
                return True
            else:
                print(f"[TELEGRAM ERROR] {resp.status_code}: {resp.text[:300]}")
                return False
        except Exception as e:
            print(f"[TELEGRAM ERROR] {e}")
            return False
