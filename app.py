import os
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Ρυθμίσεις από περιβάλλον (θα τις βάλεις στο Render)
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

@app.route('/webhook', methods=['POST'])
def webhook():
    # 1. Παίρνουμε τα δεδομένα από το plugin
    data = request.json
    if not data:
        return jsonify({"error": "no data"}), 400

    # 2. Φτιάχνουμε prompt για το DeepSeek
    prompt = f"""Είσαι σύμβουλος πωλήσεων. Διάβασε τα στοιχεία ανοίγματος email:

?? Email: {data.get('email')}
?? Πελάτης: {data.get('name')}
?? Πακέτο: {data.get('package')}
?? τ.μ.: {data.get('size')}
?? Διεύθυνση: {data.get('address')}, {data.get('city')}, {data.get('zip')}
?? Χρόνος: {data.get('time')}
?? IP: {data.get('ip')}

Δώσε μου **3 συγκεκριμένες ενέργειες** για να κερδίσω αυτόν τον πελάτη. Να είσαι άμεσος, πρακτικός και εμπνευσμένος. Μην γράφεις εισαγωγές. Μόνο τις 3 προτάσεις με αρίθμηση."""

    # 3. Καλούμε το DeepSeek API
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
        response = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        advice = response.json()['choices'][0]['message']['content']
    except Exception as e:
        advice = f"? Σφάλμα AI: {str(e)}"

    # 4. Στέλνουμε τη συμβουλή πίσω στο Telegram
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    msg = f"?? *AI Strategy*\n\n{advice}"
    requests.post(telegram_url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })

    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))