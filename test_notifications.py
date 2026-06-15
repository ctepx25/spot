import os
from datetime import datetime
from db_service import init_db, save_messages, message_exists, get_last_message
from notification_service import format_track_start_message, format_custom_message

def test_notification_conditions():
    print("🧪 Starting Automated Notification Logic Unit Tests...")
    
    test_db = os.path.join("data", "test_notifications.db")
    if os.path.exists(test_db):
        os.remove(test_db)
        
    init_db(test_db)
    
    # Define a series of mock messages chronologically
    # Message 1: Custom message at 09:00 AM
    msg_custom = {
        'id': 1001,
        'latitude': 32.12345,
        'longitude': 34.56789,
        'dateTime': "2026-06-12T09:00:00+0000",
        'unixTime': 1781254800, # 1781254800 is June 12, 2026, 09:00:00 UTC
        'altitude': 100,
        'messageType': 'CUSTOM',
        'messageContent': 'Setting off on the hike now!',
        'batteryState': 'GOOD',
        'messengerId': 'SPOT_001',
        'messengerName': 'Hiker Andrey',
        'modelId': 'SPOT4'
    }
    
    # Message 2: First TRACK point at 09:10 AM (Starts a new TRACK sequence because prior msg was CUSTOM)
    msg_track_1 = {
        'id': 1002,
        'latitude': 32.12450,
        'longitude': 34.56810,
        'dateTime': "2026-06-12T09:10:00+0000",
        'unixTime': 1781255400, # + 10 mins
        'altitude': 110,
        'messageType': 'TRACK',
        'messageContent': '',
        'batteryState': 'GOOD',
        'messengerId': 'SPOT_001',
        'messengerName': 'Hiker Andrey',
        'modelId': 'SPOT4'
    }
    
    # Message 3: Second TRACK point at 09:20 AM (Should NOT trigger start, since it's only 10 mins after track_1)
    msg_track_2 = {
        'id': 1003,
        'latitude': 32.12560,
        'longitude': 34.56830,
        'dateTime': "2026-06-12T09:20:00+0000",
        'unixTime': 1781256000, # + 10 mins
        'altitude': 120,
        'messageType': 'TRACK',
        'messageContent': '',
        'batteryState': 'GOOD',
        'messengerId': 'SPOT_001',
        'messengerName': 'Hiker Andrey',
        'modelId': 'SPOT4'
    }
    
    # Message 4: Third TRACK point at 03:00 PM (Should trigger start because gap is > 5 hours)
    msg_track_3 = {
        'id': 1004,
        'latitude': 32.15000,
        'longitude': 34.59000,
        'dateTime': "2026-06-12T15:00:00+0000",
        'unixTime': 1781276400, # + 5 hours 40 mins
        'altitude': 250,
        'messageType': 'TRACK',
        'messageContent': '',
        'batteryState': 'GOOD',
        'messengerId': 'SPOT_001',
        'messengerName': 'Hiker Andrey',
        'modelId': 'SPOT4'
    }
    
    # --- Execute and Validate Sequence ---
    last_msg = get_last_message(test_db)
    assert last_msg is None, "Last message should initially be None."
    
    # 1. Process Custom Message
    print("Testing Custom Message notification trigger...")
    is_custom_triggered = (msg_custom['messageType'] == 'CUSTOM')
    assert is_custom_triggered, "Should detect CUSTOM type correctly."
    custom_text = format_custom_message(msg_custom)
    assert "Setting off on the hike now!" in custom_text, "Content formatting mismatch."
    assert "Hiker Andrey" in custom_text, "Device name missing."
    print("✅ Custom Message formatting verified.")
    save_messages(test_db, [msg_custom])
    last_msg = msg_custom
    
    # 2. Process Track 1
    print("Testing Track 1 Sequence Start trigger...")
    is_track = (msg_track_1['messageType'] == 'TRACK')
    assert is_track, "Should detect TRACK type correctly."
    
    is_start = False
    if last_msg is None:
        is_start = True
    elif last_msg.get('messageType') != 'TRACK':
        is_start = True # Yes, because last_msg is CUSTOM!
        
    assert is_start is True, "Track 1 should trigger a start sequence because previous message was not TRACK."
    track_1_text = format_track_start_message(msg_track_1)
    assert "New Track Sequence Started!" in track_1_text, "Track start banner mismatch."
    print("✅ Track 1 Sequence Start trigger verified.")
    save_messages(test_db, [msg_track_1])
    last_msg = msg_track_1
    
    # 3. Process Track 2
    print("Testing Track 2 (Same sequence) suppression...")
    is_track = (msg_track_2['messageType'] == 'TRACK')
    is_start = False
    if last_msg is None:
        is_start = True
    elif last_msg.get('messageType') != 'TRACK':
        is_start = True
    else:
        # Check time gap (> 4 hours)
        gap = int(msg_track_2['unixTime']) - int(last_msg['unixTime'])
        if gap > 4 * 3600:
            is_start = True
            
    assert is_start is False, "Track 2 should NOT trigger a start sequence because it's in the same short TRACK sequence."
    print("✅ Track 2 sequence suppression verified (no duplicate alerts).")
    save_messages(test_db, [msg_track_2])
    last_msg = msg_track_2
    
    # 4. Process Track 3
    print("Testing Track 3 (Large gap) Sequence Start trigger...")
    is_track = (msg_track_3['messageType'] == 'TRACK')
    is_start = False
    if last_msg is None:
        is_start = True
    elif last_msg.get('messageType') != 'TRACK':
        is_start = True
    else:
        # Check time gap (> 4 hours)
        gap = int(msg_track_3['unixTime']) - int(last_msg['unixTime'])
        if gap > 4 * 3600:
            is_start = True
            
    assert is_start is True, "Track 3 should trigger a new start sequence because of the big time gap (> 4 hours)."
    track_3_text = format_track_start_message(msg_track_3)
    assert "New Track Sequence Started!" in track_3_text
    print("✅ Track 3 (Large gap) Start trigger verified.")
    save_messages(test_db, [msg_track_3])
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)
        
    print("\n🎉 ALL NOTIFICATION UNIT TESTS PASSED!")

if __name__ == "__main__":
    test_notification_conditions()
