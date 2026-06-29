import requests
import logging
from datetime import datetime

from db_service import get_last_message, message_exists, save_messages
from notification_service import send_telegram_notification, format_track_start_message, format_custom_message

logger = logging.getLogger(__name__)

def fetch_feed_data(url):
    """
    Fetches raw JSON data from a SPOT feed URL.
    """
    try:
        logger.info(f"Fetching SPOT feed data from URL: {url}")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        return None
    except ValueError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        return None

def parse_spot_messages(json_data):
    """
    Parses the SPOT feed JSON response and extracts a list of message dictionaries.
    Handles various SPOT API structural quirks (e.g., single message object vs list).
    """
    if not json_data:
        return []

    try:
        # Navigate to the feedMessageResponse section
        response_node = json_data.get("response", {})
        feed_response = response_node.get("feedMessageResponse", {})
        
        # If there are no messages, feedMessageResponse or messages might be empty
        messages_node = feed_response.get("messages")
        if not messages_node:
            logger.info("No messages found in the SPOT response.")
            return []
        
        message_data = messages_node.get("message")
        if not message_data:
            logger.info("No message array/object found in messages node.")
            return []
        
        # SPOT API Quirk: If there's only one message, it might be returned as a dict instead of a list.
        if isinstance(message_data, dict):
            return [message_data]
        elif isinstance(message_data, list):
            return message_data
        else:
            logger.warning(f"Unexpected type for messages: {type(message_data)}")
            return []
            
    except Exception as e:
        logger.error(f"Error parsing SPOT messages: {e}")
        return []

def build_feed_url(feed_id, start_date=None, end_date=None):
    """
    Constructs a SPOT public feed URL using feed_id and optional start/end datetimes.
    Dates should be datetime objects.
    Format required by SPOT: 2026-06-12T00:00:00-0000
    """
    base_url = f"https://api.findmespot.com/spot-main-web/consumer/rest-api/2.0/public/feed/{feed_id}/message.json"
    params = []
    
    if start_date:
        # format: YYYY-MM-DDTHH:MM:SS-0000
        start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S-0000")
        params.append(f"startDate={start_str}")
    if end_date:
        end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S-0000")
        params.append(f"endDate={end_str}")
        
    if params:
        return f"{base_url}?{'&'.join(params)}"
    return base_url

def sync_feed_data(feed_id, start_dt, end_dt, tg_token, tg_chat_id, db_path):
    """
    Fetches raw SPOT feed data, parses it, checks for new messages,
    dispatches Telegram notifications if criteria are met, and saves messages.
    Returns (success, new_count, notifications_sent, error_msg)
    """
    feed_url = build_feed_url(feed_id, start_dt, end_dt)
    raw_json = fetch_feed_data(feed_url)
    
    if not raw_json:
        return False, 0, 0, "Failed to connect or fetch data from SPOT feed endpoint."
        
    parsed_msgs = parse_spot_messages(raw_json)
    if not parsed_msgs:
        return True, 0, 0, "No messages returned in this date range."
        
    # Sort chronologically to process sequences in order
    sorted_msgs = sorted(parsed_msgs, key=lambda x: int(x.get('unixTime', 0)))
    
    # Fetch currently latest message in DB to detect TRACK state transitions
    last_msg = get_last_message(db_path)
    new_count = 0
    notifications_sent = 0
    
    for msg in sorted_msgs:
        msg_id = msg.get('id')
        if not message_exists(db_path, msg_id):
            msg_type = str(msg.get('messageType', '')).upper()
            
            # 1. Check if a new TRACK sequence starts
            if msg_type == 'UNLIMITED-TRACK':
                is_start = False
                if last_msg is None:
                    is_start = True
                elif str(last_msg.get('messageType', '')).upper() != 'UNLIMITED-TRACK':
                    is_start = True
                else:
                    # Prior point was a TRACK, but check if there's a big gap (e.g. > 4 hours)
                    try:
                        last_time = int(last_msg.get('unixTime', 0))
                        curr_time = int(msg.get('unixTime', 0))
                        if curr_time - last_time > 4 * 3600:
                            is_start = True
                    except (ValueError, TypeError):
                        pass
                
                if is_start:
                    notification_text = format_track_start_message(msg)
                    if send_telegram_notification(tg_token, tg_chat_id, notification_text):
                        notifications_sent += 1
                        
            # 2. Check if it's a Custom message
            elif msg_type == 'CUSTOM' or msg.get('showCustomMsg') == 'Y':
                notification_text = format_custom_message(msg)
                if send_telegram_notification(tg_token, tg_chat_id, notification_text):
                    notifications_sent += 1
            
            # Save point to DB and update our last known message state
            save_messages(db_path, [msg])
            last_msg = msg
            new_count += 1
            
    return True, new_count, notifications_sent, None
