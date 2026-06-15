import telebot
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def send_telegram_notification(token, chat_id, text):
    """
    Sends a formatted Markdown message to a Telegram channel or chat.
    """
    if not token or not chat_id:
        logger.warning("Telegram token or Chat ID is missing. Notification skipped.")
        return False
        
    try:
        # Standardize chat_id to string or integer
        bot = telebot.TeleBot(token)
        # We use parse_mode='Markdown' for nice bold/italic text and inline links
        bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown', disable_web_page_preview=False)
        logger.info("Telegram notification sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False

def format_track_start_message(msg):
    """
    Formats a notification message for a newly started TRACK sequence.
    """
    # Parse timestamp
    unix_time = msg.get('unixTime')
    if unix_time:
        time_str = datetime.fromtimestamp(int(unix_time)).strftime('%Y-%m-%d %H:%M UTC')
    else:
        time_str = msg.get('dateTime', 'Unknown Time')
        
    latitude = msg.get('latitude')
    longitude = msg.get('longitude')
    maps_url = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
    
    text = (
        f"🥾 *New Track Sequence Started!*\n\n"
        f"👤 *Device:* {msg.get('messengerName', 'SPOT Device')}\n"
        f"📅 *Time:* {time_str}\n"
        f"📍 *Location:* [{latitude}, {longitude}]({maps_url})\n"
        f"🏔️ *Altitude:* {msg.get('altitude', 0)} m\n"
        f"🔋 *Battery:* {msg.get('batteryState', 'GOOD')}\n"
        f"📱 *Model:* {msg.get('modelId', 'SPOT')}"
    )
    return text

def format_custom_message(msg):
    """
    Formats a notification message for a custom message.
    """
    unix_time = msg.get('unixTime')
    if unix_time:
        time_str = datetime.fromtimestamp(int(unix_time)).strftime('%Y-%m-%d %H:%M UTC')
    else:
        time_str = msg.get('dateTime', 'Unknown Time')
        
    latitude = msg.get('latitude')
    longitude = msg.get('longitude')
    maps_url = f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
    content = msg.get('messageContent', 'No text provided')
    
    text = (
        f"💬 *New Custom Message Received!*\n\n"
        f"👤 *Device:* {msg.get('messengerName', 'SPOT Device')}\n"
        f"✉️ *Message:* \"_{content}_\"\n"
        f"📅 *Time:* {time_str}\n"
        f"📍 *Location:* [{latitude}, {longitude}]({maps_url})\n"
        f"🔋 *Battery:* {msg.get('batteryState', 'GOOD')}"
    )
    return text
