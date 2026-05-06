import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

if not DEEPSEEK_API_KEY or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("⚠️ Missing environment variables. Server will not send AI advice.")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no data"}), 400

    # Δημιουργία prompt
    prompt = f"""Είσαι σύμβουλος πωλήσεων. Διάβασε τα στοιχεία ανοίγματος email:

Email: {data.get('email')}
Πελάτης: {data.get('name')}
Πακέτο: {data.get('package')}
τ.μ.: {data.get('size')}
Διεύθυνση: {data.get('address')}, {data.get('city')}, {data.get('zip')}
Χρόνος: {data.get('time')}
IP: {data.get('ip')}

Δώσε μου 3 συγκεκριμένες ενέργειες για να κερδίσω αυτόν τον πελάτη. Μην γράφεις εισαγωγές. Μόνο τις 3 προτάσεις με αρίθμηση."""

    # Κλήση DeepSeek
    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7},
            timeout=15
        )
        response.raise_for_status()
        advice = response.json()['choices'][0]['message']['content']
    except Exception as e:
        advice = f"Σφάλμα AI: {str(e)}"

    # Αποστολή στο Telegram
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🧠 *AI Strategy*\n\n{advice}", "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception:
        pass

    return jsonify({"status": "ok"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
