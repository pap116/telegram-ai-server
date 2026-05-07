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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reminders_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                stage INTEGER NOT NULL,
                sent_time TEXT NOT NULL
            )
        ''')
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

def get_recent_events(limit=10):
    with get_db() as conn:
        cur = conn.execute('''
            SELECT email, name, package, size, open_count, score, timestamp
            FROM email_analytics 
            ORDER BY timestamp DESC LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cur.fetchall()]

def get_client_stats(email):
    with get_db() as conn:
        cur = conn.execute('''
            SELECT open_count, score, name, package, size, timestamp 
            FROM email_analytics 
            WHERE email = ? 
            ORDER BY timestamp DESC LIMIT 1
        ''', (email,))
        latest = cur.fetchone()
        if not latest:
            return None
        cur2 = conn.execute('SELECT COUNT(*) as cnt FROM email_analytics WHERE email = ?', (email,))
        cnt = cur2.fetchone()['cnt']
        cur3 = conn.execute('SELECT timestamp FROM email_analytics WHERE email = ? ORDER BY timestamp ASC LIMIT 1', (email,))
        first = cur3.fetchone()
        return {
            'email': email,
            'name': latest['name'],
            'package': latest['package'],
            'size': latest['size'],
            'total_opens': latest['open_count'],
            'event_count': cnt,
            'first_open': first['timestamp'] if first else None,
            'last_open': latest['timestamp'],
            'latest_score': latest['score']
        }

def get_all_clients_stats():
    with get_db() as conn:
        cur = conn.execute('''
            SELECT a1.*
            FROM email_analytics a1
            INNER JOIN (
                SELECT email, MAX(timestamp) as max_ts
                FROM email_analytics
                GROUP BY email
            ) a2 ON a1.email = a2.email AND a1.timestamp = a2.max_ts
            ORDER BY a1.timestamp DESC
        ''')
        rows = cur.fetchall()
        return [dict(row) for row in rows]

def cleanup_old_analyses(months=6):
    cutoff = (datetime.now() - timedelta(days=months*30)).isoformat()
    with get_db() as conn:
        conn.execute('DELETE FROM email_analytics WHERE timestamp < ?', (cutoff,))
        conn.execute('DELETE FROM reminders_sent WHERE sent_time < ?', (cutoff,))
        conn.commit()
        return conn.total_changes

def save_reminder(email, stage):
    with get_db() as conn:
        conn.execute('''
            INSERT INTO reminders_sent (email, stage, sent_time)
            VALUES (?, ?, ?)
        ''', (email, stage, datetime.now().isoformat()))
        conn.commit()

def get_reminder_count(email):
    with get_db() as conn:
        cur = conn.execute('SELECT COUNT(*) as cnt FROM reminders_sent WHERE email = ?', (email,))
        return cur.fetchone()['cnt']
