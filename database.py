import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional

class Database:
  def __init__(self, db_name: str = "scheduled_messages.db"):
    """
    Initialize database connection 
    """
    self.db_name = db_name
    self.init_database()

  def init_database(self):
    """
    create table if it doesn't exist
    """ 
    conn = sqlite3.connect(self.db_name)
    cursor = conn.cursor()

    cursor.execute('''
      CREATE TABLE IF NOT EXISTS scheduled_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        message_content TEXT NOT NULL,
        scheduled_time TIMESTAMP NOT NULL,
        author_id TEXT NOT NULL,
        sent INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
      ''')

    conn.commit()
    conn.close()
    print(f"Database initialized and table created successfully in {self.db_name}")

  def add_scheduled_message(self, channel_id: str, message_content: str, scheduled_time: datetime, author_id: str) -> int:
    """
    return id of new scheduled message
    """
    conn = sqlite3.connect(self.db_name)
    cursor = conn.cursor()

    cursor.execute('''
      INSERT INTO scheduled_messages (channel_id, message_content, scheduled_time, author_id)
      VALUES (?, ?, ?, ?)
      ''', (channel_id, message_content, scheduled_time, author_id))
    
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id

  def get_due_messages(self, current_time: datetime) -> List[Tuple]:
    """
    get all current and previous scheduled messages that are due to be sent
    return list of tuples (id, channel_id, message_content, scheduled_time, author_id)
    """
    conn = sqlite3.connect(self.db_name)
    cursor = conn.cursor()

    cursor.execute('''
      SELECT id, channel_id, message_content, scheduled_time, author_id
      FROM scheduled_messages
      WHERE scheduled_time <= ? AND sent = 0
      ORDER BY scheduled_time ASC
    ''', (current_time,))

    messages = cursor.fetchall()
    conn.close()

    return messages

  def mark_message_as_sent(self, message_id: int):
    """
    mark a scheduled message as sent
    """
    conn = sqlite3.connect(self.db_name)
    cursor = conn.cursor()
    cursor.execute('''
      UPDATE scheduled_messages
      SET sent = 1
      WHERE id = ?
    ''', (message_id,))

    conn.commit()
    conn.close()

  def get_pending_messages(self) -> List[Tuple]:
    """
    get all pending scheduled messages
    """
    conn = sqlite3.connect(self.db_name)
    cursor = conn.cursor()
    cursor.execute('''
      SELECT id, channel_id, message_content, scheduled_time, author_id
      FROM scheduled_messages
      WHERE sent = 0
      ORDER BY scheduled_time ASC
    ''')

    messages = cursor.fetchall()
    conn.close()
    return messages

  def delete_message(self, message_id: int) -> bool:
    """
    delete a scheduled message
    True if successful, False otherwise
    """
    conn = sqlite3.connect(self.db_name)
    cursor = conn.cursor()
    cursor.execute('''
      DELETE FROM scheduled_messages
      WHERE id = ?
    ''', (message_id,))

    rows_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_deleted > 0

