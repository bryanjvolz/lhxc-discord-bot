import sqlite3
import json

DB_FILE = 'discord_bot.db'

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    """Creates the necessary tables in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create a table for saved events (global per user)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            UNIQUE(user_id, event_id)
        )
    ''')

    # Create a table for server configurations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS server_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL UNIQUE,
            notification_channel_id INTEGER,
            notification_mode TEXT DEFAULT 'periodic',
            digest_time TEXT DEFAULT '08:00'
        )
    ''')

    # Add columns if they don't exist (for migration purposes)
    cursor.execute("PRAGMA table_info(server_configs)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'notification_mode' not in columns:
        cursor.execute("ALTER TABLE server_configs ADD COLUMN notification_mode TEXT DEFAULT 'periodic'")
    if 'digest_time' not in columns:
        cursor.execute("ALTER TABLE server_configs ADD COLUMN digest_time TEXT DEFAULT '08:00'")

    # Create a table for posted events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posted_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            last_updated TEXT NOT NULL,
            UNIQUE(event_id, guild_id)
        )
    ''')

    # Create a table for user configurations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            timezone TEXT
        )
    ''')

    # Create a table for digest events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS digest_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            event_data TEXT NOT NULL,
            UNIQUE(guild_id, event_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            notification_date TEXT NOT NULL,
            UNIQUE(user_id, event_id, notification_date)
        )
    ''')

    conn.commit()
    conn.close()

def set_notification_channel(guild_id, channel_id):
    """Sets the notification channel for a server."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO server_configs (guild_id, notification_channel_id) VALUES (?, ?) "
                   "ON CONFLICT(guild_id) DO UPDATE SET notification_channel_id = excluded.notification_channel_id",
                   (guild_id, channel_id))
    conn.commit()
    conn.close()

def set_user_timezone(user_id, timezone):
    """Sets the timezone for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_configs (user_id, timezone) VALUES (?, ?)",
                   (user_id, timezone))
    conn.commit()
    conn.close()

def get_user_timezone(user_id):
    """Gets the timezone for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timezone FROM user_configs WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['timezone'] if row else None

def save_event(user_id, event_id):
    """Saves an event for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO saved_events (user_id, event_id) VALUES (?, ?)",
                   (user_id, event_id))
    conn.commit()
    conn.close()

def remove_saved_event(user_id, event_id):
    """Removes a saved event for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_events WHERE user_id = ? AND event_id = ?",
                   (user_id, event_id))
    conn.commit()
    conn.close()

def get_saved_events(user_id):
    """Gets all saved event IDs for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT event_id FROM saved_events WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row['event_id'] for row in rows]

def get_all_users_with_saved_events():
    """Gets all user IDs who have saved events."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM saved_events")
    rows = cursor.fetchall()
    conn.close()
    return [row['user_id'] for row in rows]

def has_user_notification(user_id, event_id, notification_date):
    """Checks whether a user notification was sent for an event on a date."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM user_notifications WHERE user_id = ? AND event_id = ? AND notification_date = ?",
        (user_id, event_id, notification_date)
    )
    sent = cursor.fetchone() is not None
    conn.close()
    return sent

def add_user_notification(user_id, event_id, notification_date):
    """Records a successfully sent user notification."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO user_notifications (user_id, event_id, notification_date) VALUES (?, ?, ?)",
        (user_id, event_id, notification_date)
    )
    conn.commit()
    conn.close()

def get_all_saved_events_with_users():
    """Gets all saved events with the users who saved them."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT event_id, user_id FROM saved_events ORDER BY event_id")
    rows = cursor.fetchall()
    conn.close()

    events = {}
    for row in rows:
        event_id = row['event_id']
        user_id = row['user_id']
        if event_id not in events:
            events[event_id] = []
        events[event_id].append(user_id)
    return events

def get_posted_event(event_id, guild_id):
    """Gets a posted event from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT last_updated FROM posted_events WHERE event_id = ? AND guild_id = ?", (event_id, guild_id))
    row = cursor.fetchone()
    conn.close()
    return row['last_updated'] if row else None

def add_posted_event(event_id, guild_id, last_updated):
    """Adds a posted event to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO posted_events (event_id, guild_id, last_updated) VALUES (?, ?, ?)",
                   (event_id, guild_id, last_updated))
    conn.commit()
    conn.close()

def get_all_notification_channels():
    """Gets all notification channel IDs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT guild_id, notification_channel_id FROM server_configs WHERE notification_channel_id IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()
    return {row['guild_id']: row['notification_channel_id'] for row in rows}

def set_notification_mode(guild_id, mode):
    """Sets the notification mode for a server (periodic or digest)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO server_configs (guild_id, notification_mode) VALUES (?, ?) "
                   "ON CONFLICT(guild_id) DO UPDATE SET notification_mode = excluded.notification_mode",
                   (guild_id, mode))
    conn.commit()
    conn.close()

def get_notification_settings(guild_id):
    """Gets the notification settings (mode and digest time) for a server."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT notification_mode, digest_time FROM server_configs WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {'notification_mode': 'periodic', 'digest_time': '08:00'}

def set_digest_time(guild_id, digest_time):
    """Sets the daily digest time for a server."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO server_configs (guild_id, digest_time) VALUES (?, ?) "
                   "ON CONFLICT(guild_id) DO UPDATE SET digest_time = excluded.digest_time",
                   (guild_id, digest_time))
    conn.commit()
    conn.close()

def add_digest_event(guild_id, event_id, event_data):
    """Adds an event to the digest queue for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO digest_events (guild_id, event_id, event_data) VALUES (?, ?, ?)",
                   (guild_id, event_id, json.dumps(event_data)))
    conn.commit()
    conn.close()

def get_digest_events(guild_id):
    """Retrieves all events in the digest queue for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT event_data FROM digest_events WHERE guild_id = ?", (guild_id,))
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row['event_data']) for row in rows]

def clear_digest_events(guild_id):
    """Clears all events from the digest queue for a specific guild."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM digest_events WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()

def clear_saved_events(user_id):
    """Clears all saved events for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_events WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()
