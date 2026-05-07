import os
import requests
import re
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
WP_API_TOKEN = os.environ.get('WP_API_TOKEN', '')

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

def get_ip_location(ip):
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
    first_open_time_str = data.get('first_open_time', '')

    # Υπολογισμός ωρών από το πρώτο άνοιγμα
    hours_since_first_open = 0
    if first_open_time_str:
        try:
            first_open = datetime.strptime(first_open_time_str, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            hours_since_first_open = (now - first_open).total_seconds() / 3600.0
        except:
            pass

    # Νέο prompt με 6 γραμμές (πλούσιο)
    prompt = f"""Είσαι σύμβουλος πωλήσεων διακόσμησης και Φημισμένος και Ταλαντούχος Interior Designer. Ανάλυσε συμπεριφορά πελάτη. Στοιχεία:

- Ανοίγματα email: {opens} φορές
- Τελευταία ώρα: {data.get('time')}
- Πακέτο: {data.get('package')}, τ.μ.: {data.get('size')}
- IP: {ip} (περιοχή: {location})
- Η IP άλλαξε: {"ΝΑΙ (κινητικότητα)" if ip_changed else "ΟΧΙ (σταθερή)"}

Απάντησε ΜΟΝΟ με 6 γραμμές, ακριβώς όπως φαίνονται παρακάτω. Κράτα τη γλώσσα φιλική, επαγγελματική, χωρίς υπερβολές.

1. Πιθανότητα κλεισίματος (1-10): [X/10] - (μία σύντομη εξήγηση)
2. Συναισθηματική κατάσταση: (π.χ. "προσεκτικός", "ενθουσιώδης", "αναβλητικός")
3. Πρόταση επόμενης επαφής: (π.χ. "τηλέφωνο αύριο 10-12", "email με έκπτωση", "περιμένετε 2 ημέρες")
4. Ιδανικό μήνυμα που θα του στείλεις (αυτούσιο, σε ευθεία ομιλία, μέχρι 15 λέξεις)
5. Εκτίμηση budget/οικονομικής άνεσης: (π.χ. "Υψηλή (Luxury)", "Μεσαία (Basic)", "Χαμηλή")
6. Συγκεκριμένη ενέργεια για μένα ΤΩΡΑ: (π.χ. "πάρε τον τηλέφωνο αμέσως", "στείλε email με link για ραντεβού")

Μην γράψεις τίποτα άλλο, ούτε εισαγωγές."""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 350    # αυξημένο για να χωράνε οι 6 γραμμές
    }
    try:
        resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        advice = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        advice = f"AI error: {str(e)}"

    # Εξαγωγή βαθμολογίας από την 1η γραμμή (ίδια λογική)
    try:
        score_match = re.search(r'\(1-10\):\s*(\d+)/10', advice)
        score = int(score_match.group(1)) if score_match else 0
    except:
        score = 0

    # Αποστολή ανάλυσης στο Telegram (πάντα)
    telegram_msg = f"🎯 *Ανάλυση Πώλησης*\n\n{advice}"
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": telegram_msg, "parse_mode": "Markdown"},
                  timeout=5)

    # === ΑΠΟΦΑΣΗ ΑΠΟΣΤΟΛΗΣ REMINDER (score>6 και 24 ώρες από το πρώτο άνοιγμα) ===
    if score > 6 and hours_since_first_open >= 24:
        wp_endpoint = "https://10deco.gr/wp-json/deco/v1/send-reminder"
        reminder_data = {
            "email": data.get('email'),
            "name": data.get('name'),
            "package": data.get('package'),
            "size": data.get('size'),
            "score": score,
            "address": data.get('address'),
            "city": data.get('city'),
            "zip": data.get('zip')
        }
        try:
            requests.post(wp_endpoint, json=reminder_data,
                         headers={"Content-Type": "application/json", "X-API-Token": WP_API_TOKEN},
                         timeout=3)
        except Exception as e:
            print(f"Reminder error: {e}")
    # ==========================================================

    return jsonify({"status": "ok"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/')
def index():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
