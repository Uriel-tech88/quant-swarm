#!/usr/bin/env python3
"""
Telegram Token Expiry Reminder
Sends a message to Telegram 7 days before GitHub PAT expires.
Usage: python telegram_reminder.py
Requires: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.
"""
import os, requests, datetime

def send_reminder(days_left, token_start="ghp_..."):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ MISSING: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars first.")
        return False

    message = (
        f"⚠️ QUANT SWARM ALERT\n"
        f"Your GitHub PAT ({token_start}) expires in {days_left} days!\n"
        f"Renew at: github.com/settings/tokens\n"
        f"Repo: Uriel-tech88/quant-swarm\n"
        f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        if resp.status_code == 200:
            print(f"✓ Telegram reminder sent ({days_left} days left)")
            return True
        else:
            print(f"✗ Telegram error: {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ Telegram send failed: {e}")
        return False

def check_expiry():
    """Calculate days until GitHub PAT expiry and remind if within threshold."""
    expiry = datetime.date(2026, 11, 11)  # PAT expiry: Wed, Nov 11 2026
    today = datetime.date.today()
    days_left = (expiry - today).days

    if days_left <= 7:
        print(f"⚠️ PAT expires in {days_left} days — sending reminder")
        send_reminder(days_left)
    else:
        print(f"✓ PAT has {days_left} days left — no reminder needed yet")

if __name__ == "__main__":
    check_expiry()
