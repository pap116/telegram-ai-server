# app.py
import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Environment variables (θα οριστούν στο Render)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    if not DEEPSEEK_API_KEY or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return jsonify({"error": "missing keys"}), 500

    prompt = f"""Είσαι σύμβουλος πωλήσεων. Διάβασε τα στοιχεία ανοίγματος email:

Email: {data.get('email')}
Πελάτης: {data.get('name')}
Πακέτο: {data.get('package')}
τ.μ.: {data.get('size')}
Διεύθυνση: {data.get('address')}, {data.get('city')}, {data.get('zip')}
Χρόνος: {data.get('time')}
IP: {data.get('ip')}

Δώσε μου 3 συγκεκριμένες ενέργειες για να κερδίσω αυτόν τον πελάτη. Μην γράφεις εισαγωγές. Μόνο τις 3 προτάσεις με αρίθμηση."""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    try:
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        advice = response.json()['choices'][0]['message']['content']
    except Exception as e:
        advice = f"Σφάλμα AI: {str(e)}"

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    msg = f"🧠 *AI Strategy*\n\n{advice}"
    try:
        requests.post(telegram_url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=5)
    except Exception as e:
        print(f"Telegram error: {e}")

    return jsonify({"status": "ok"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
