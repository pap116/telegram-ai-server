import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

def get_ip_location(ip):
    """Επιστρέφει πόλη και χώρα για μια IP (free ip-api.com)"""
    if not ip or ip.startswith('127.') or ip == '::1':
        return "local"
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
        data = r.json()
        if data.get('status') == 'success':
            return f"{data.get('city', '?')}, {data.get('country', '?')}"
        return "unknown"
    except:
        return "unknown"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    ip = data.get('ip', '')
    location = get_ip_location(ip)
    opens = data.get('opens_count', 1)
    ip_changed = data.get('ip_changed', False)

    prompt = f"""Κάνε ένα σύντομο ψυχογράφημα για πελάτη που άνοιξε email:

- Άνοιξε {opens} φορές
- Τελευταία φορά: {data.get('time')}
- Πακέτο: {data.get('package')}, τ.μ.: {data.get('size')}
- IP: {ip} (τοποθεσία: {location})
- Η IP άλλαξε: {"Ναι" if ip_changed else "Όχι"}

Δώσε 3 γραμμές:
1. Επίπεδο ενδιαφέροντος (χαμηλό/μέτριο/υψηλό) και γιατί
2. Αν δείχνει κινητικότητα (π.χ. άνοιξε από άλλη τοποθεσία)
3. Μία συγκεκριμένη ενέργεια για μένα"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 120
    }
    try:
        resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        advice = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        advice = f"AI error: {str(e)}"

    telegram_msg = f"🧠 *Ψυχογράφημα*\n\n{advice}"
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": telegram_msg, "parse_mode": "Markdown"},
                  timeout=5)

    return jsonify({"status": "ok"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
