import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'email_analytics.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS email_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                name TEXT,
                package TEXT,
                size REAL,
                open_count INTEGER,
                ip_changed INTEGER,
                timestamp TEXT NOT NULL,
                analysis_text TEXT NOT NULL,
                score INTEGER,
                reminder_count INTEGER DEFAULT 0,
                last_reminder_time TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_email ON email_analytics (email)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON email_analytics (timestamp)')
        conn.commit()

def save_analysis(email, name, package, size, open_count, ip_changed, analysis_text, score):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO email_analytics 
            (email, name, package, size, open_count, ip_changed, timestamp, analysis_text, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (email, name, package, size, open_count, ip_changed, datetime.now().isoformat(), analysis_text, score))
        conn.commit()

def get_latest_analysis(email=None):
    """Επιστρέφει την πιο πρόσφατη ανάλυση για ένα email ή όλες αν email=None"""
    with get_db() as conn:
        if email:
            cur = conn.execute('''
                SELECT * FROM email_analytics 
                WHERE email = ? 
                ORDER BY timestamp DESC LIMIT 1
            ''', (email,))
        else:
            cur = conn.execute('''
                SELECT * FROM email_analytics 
                ORDER BY timestamp DESC LIMIT 1
            ''')
        row = cur.fetchone()
        return dict(row) if row else None

def get_all_recent_analyses(days=30):
    """Επιστρέφει όλες τις αναλύσεις των τελευταίων `days` ημερών"""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db() as conn:
        cur = conn.execute('''
            SELECT * FROM email_analytics 
            WHERE timestamp > ? 
            ORDER BY timestamp DESC
        ''', (cutoff,))
        return [dict(row) for row in cur.fetchall()]

def cleanup_old_analyses(months=6):
    """Διαγράφει εγγραφές παλαιότερες από `months` μήνες"""
    cutoff = (datetime.now() - timedelta(days=months*30)).isoformat()
    with get_db() as conn:
        conn.execute('DELETE FROM email_analytics WHERE timestamp < ?', (cutoff,))
        conn.commit()
        return conn.total_changes

def update_reminder_info(email, reminder_count, last_reminder_time):
    with get_db() as conn:
        conn.execute('''
            UPDATE email_analytics 
            SET reminder_count = ?, last_reminder_time = ?
            WHERE email = ? AND timestamp = (
                SELECT MAX(timestamp) FROM email_analytics WHERE email = ?
            )
        ''', (reminder_count, last_reminder_time, email, email))
        conn.commit()
