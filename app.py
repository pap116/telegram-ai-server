import os
import requests
import re
from datetime import datetime
from flask import Flask, request, jsonify

# Εισαγωγή συναρτήσεων βάσης
from analytics_db import init_db, save_analysis, get_latest_analysis, get_recent_events, get_client_stats, get_all_clients_stats, cleanup_old_analyses, save_reminder, get_reminder_count

app = Flask(__name__)

# Environment variables
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
WP_API_TOKEN = os.environ.get('WP_API_TOKEN', '')

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# Αρχικοποίηση βάσης και εκκαθάριση παλαιών εγγραφών
init_db()
cleanup_old_analyses(months=6)

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

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Telegram send error: {e}")

# ========== WEBHOOK ΑΠΟ ΤΟ PLUGIN (tracking ανοιγμάτων) ==========
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

    # Υπολογισμός ωρών από το πρώτο άνοιγμα (για reminder delay)
    hours_since_first_open = 0
    if first_open_time_str:
        try:
            first_open = datetime.strptime(first_open_time_str, '%Y-%m-%d %H:%M:%S')
            now = datetime.now()
            hours_since_first_open = (now - first_open).total_seconds() / 3600.0
        except:
            pass

    # Prompt ανάλυσης (6 γραμμές)
    prompt = f"""Είσαι σύμβουλος πωλήσεων διακόσμησης. Ανάλυσε συμπεριφορά πελάτη. Στοιχεία:

- Ανοίγματα email: {opens} φορές
- Τελευταία ώρα: {data.get('time')}
- Πακέτο: {data.get('package')}, τ.μ.: {data.get('size')}
- IP: {ip} (περιοχή: {location})
- Η IP άλλαξε: {"ΝΑΙ (κινητικότητα)" if ip_changed else "ΟΧΙ (σταθερή)"}

Απάντησε ΜΟΝΟ με 6 γραμμές, ακριβώς όπως φαίνονται παρακάτω.

1. Πιθανότητα κλεισίματος (1-10): [X/10] - (μία σύντομη εξήγηση)
2. Συναισθηματική κατάσταση: (π.χ. "προσεκτικός", "ενθουσιώδης")
3. Πρόταση επόμενης επαφής: (π.χ. "τηλέφωνο αύριο 10-12", "email με έκπτωση")
4. Ιδανικό μήνυμα που θα του στείλεις (αυτούσιο, σε ευθεία ομιλία, μέχρι 15 λέξεις)
5. Εκτίμηση budget/οικονομικής άνεσης: (π.χ. "Υψηλή (Luxury)", "Μεσαία (Basic)")
6. Συγκεκριμένη ενέργεια για μένα ΤΩΡΑ: (π.χ. "πάρε τον τηλέφωνο αμέσως")

Μην γράψεις τίποτα άλλο."""

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 450   # Αυξημένο για να μην κόβονται οι απαντήσεις
    }
    try:
        resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        advice = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        advice = f"AI error: {str(e)}"

    # Εξαγωγή βαθμολογίας
    try:
        score_match = re.search(r'\(1-10\):\s*(\d+)/10', advice)
        score = int(score_match.group(1)) if score_match else 0
    except:
        score = 0

    # Αποθήκευση ανάλυσης στη βάση
    save_analysis(
        email=data.get('email'),
        name=data.get('name'),
        package=data.get('package'),
        size=data.get('size'),
        open_count=opens,
        ip_changed=1 if ip_changed else 0,
        analysis_text=advice,
        score=score
    )

    # Αποστολή ανάλυσης στον admin (Telegram)
    telegram_msg = f"🎯 *Ανάλυση Πώλησης*\n\n{advice}"
    send_telegram_message(TELEGRAM_CHAT_ID, telegram_msg)

    # Απόφαση αποστολής reminder (score>6 και μετά από 24 ώρες)
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

    return jsonify({"status": "ok"})

# ========== WEBHOOK ΓΙΑ ΣΥΝΟΜΙΛΙΑ ΜΕ ΤΟ BOT (admin μόνο) ==========
@app.route('/webhook_telegram', methods=['POST'])
def telegram_webhook():
    update = request.get_json()
    if not update or 'message' not in update:
        return jsonify({"status": "ok"}), 200

    message = update['message']
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()

    if not text:
        return jsonify({"status": "ok"}), 200

    # Μόνο ο admin (εσύ) μπορεί να συνομιλεί
    if str(chat_id) != str(TELEGRAM_CHAT_ID):
        return jsonify({"status": "ok"}), 200

    # Δημιουργία context από τη βάση
    context_lines = []

    # Πρόσφατα γεγονότα (5 τελευταία ανοίγματα)
    recent = get_recent_events(limit=5)
    if recent:
        context_lines.append("📌 *Πρόσφατες δραστηριότητες:*")
        for ev in recent:
            context_lines.append(f"• {ev['name']} ({ev['email']}) – {ev['package']}, {ev['size']} τ.μ. – σκορ {ev['score']} – άνοιξε {ev['open_count']} φορές")

    # Τελευταία ανάλυση γενικά
    latest = get_latest_analysis()
    if latest:
        context_lines.append(f"\n📊 *Τελευταία ανάλυση:*\n{latest['analysis_text']}")

    context = "\n".join(context_lines) if context_lines else ""

    # Αν το μήνυμα περιέχει email, προσθέτουμε στατιστικά για εκείνον τον πελάτη
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if email_match:
        email = email_match.group(0)
        stats = get_client_stats(email)
        if stats:
            context += f"\n\n📈 *Στατιστικά για {stats['name']} ({email}):*\n"
            context += f"• Σύνολο ανοιγμάτων: {stats['total_opens']}\n"
            context += f"• Πρώτο άνοιγμα: {stats['first_open']}\n"
            context += f"• Τελευταίο σκορ: {stats['latest_score']}\n"

    prompt = f"""Είσαι ο βοηθός του Παντελή, ιδιοκτήτη της 10deco. Ο Παντελής σε ρωτάει κάτι. Εσύ:

- Απευθύνεσαι σε αυτόν με το μικρό του όνομα "Παντελή".
- **Χρησιμοποιείς ΜΟΝΟ τα δεδομένα που σου δίνονται παρακάτω.** Δεν επινοείς πελάτες, ανοίγματα, ή καμπάνιες.
- Απαντάς με βάση αυτά τα πραγματικά δεδομένα. Αν δεν υπάρχει πληροφορία, λες "Δεν έχω αυτή την πληροφορία".
- Δίνεις συμβουλές μόνο για πωλήσεις, διακόσμηση, ή διαχείριση πελατών.
- Κρατάς τις απαντήσεις σύντομες (2-3 προτάσεις), εκτός αν ζητηθεί αναλυτική απάντηση.

{context}

Μήνυμα του Παντελή: {text}"""

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 400
    }
    try:
        resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        reply = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        reply = f"Σφάλμα: {str(e)}"

    send_telegram_message(chat_id, reply)
    return jsonify({"status": "ok"}), 200

# ========== ΒΟΗΘΗΤΙΚΑ ENDPOINTS ==========
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/')
def index():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
