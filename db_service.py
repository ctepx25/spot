import os
import sqlite3
import logging

logger = logging.getLogger(__name__)

def get_connection(db_path):
    """
    Establishes and returns an SQLite database connection.
    Ensures the parent directory exists.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return sqlite3.connect(db_path)

def init_db(db_path):
    """
    Initializes the SQLite database and creates the messages table if it doesn't exist.
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        dateTime TEXT NOT NULL,
        unixTime INTEGER NOT NULL,
        altitude REAL,
        messageType TEXT,
        messageContent TEXT,
        batteryState TEXT,
        messengerId TEXT,
        messengerName TEXT,
        modelId TEXT
    );
    """
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_query)
            conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def save_messages(db_path, messages):
    """
    Saves a list of message dictionaries into the database.
    Ignores messages that already exist (based on 'id').
    Returns the number of newly inserted messages.
    """
    insert_query = """
    INSERT OR IGNORE INTO messages (
        id, latitude, longitude, dateTime, unixTime, altitude,
        messageType, messageContent, batteryState, messengerId, messengerName, modelId
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    new_inserts = 0
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            # Construct tuples for batch insertion
            records = []
            for msg in messages:
                records.append((
                    msg.get('id'),
                    msg.get('latitude'),
                    msg.get('longitude'),
                    msg.get('dateTime'),
                    msg.get('unixTime'),
                    msg.get('altitude'),
                    msg.get('messageType'),
                    msg.get('messageContent'),
                    msg.get('batteryState'),
                    msg.get('messengerId'),
                    msg.get('messengerName'),
                    msg.get('modelId')
                ))
            
            cursor.executemany(insert_query, records)
            conn.commit()
            new_inserts = cursor.rowcount
            # sqlite cursor.rowcount for executemany might not always reflect exact new insertions
            # accurately depending on version or INSERT OR IGNORE behavior, but is generally useful.
        return new_inserts
    except Exception as e:
        logger.error(f"Error saving messages to database: {e}")
        return 0

def get_all_messages(db_path):
    """
    Retrieves all messages stored in the database, ordered by unixTime ascending.
    """
    query = "SELECT * FROM messages ORDER BY unixTime ASC;"
    try:
        with get_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}")
        return []

def message_exists(db_path, msg_id):
    """
    Checks if a message ID already exists in the database.
    """
    query = "SELECT 1 FROM messages WHERE id = ? LIMIT 1;"
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (msg_id,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking message existence: {e}")
        return False

def get_last_message(db_path):
    """
    Gets the chronologically last message stored in the database.
    """
    query = "SELECT * FROM messages ORDER BY unixTime DESC LIMIT 1;"
    try:
        with get_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving last message: {e}")
        return None
