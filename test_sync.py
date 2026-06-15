import os
from datetime import datetime
from db_service import init_db, save_messages, get_all_messages
from feed_service import build_feed_url, fetch_feed_data, parse_spot_messages

def run_test():
    print("🚀 Starting SPOT Tracker Integration Test...")
    
    # Use a separate test database file
    test_db = os.path.join("data", "test_tracking.db")
    
    # 1. Initialize DB
    print(f"Initializing test database at {test_db}...")
    init_db(test_db)
    assert os.path.exists(test_db), "Database file should exist after initialization."
    print("✅ Database initialized successfully.")
    
    # 2. Build Feed URL
    feed_id = "0FOq6U5ICzOEL4qCqbM8YrAOqUzP8uGUp"
    start_dt = datetime(2026, 6, 12, 0, 0, 0)
    end_dt = datetime(2026, 6, 13, 0, 0, 0)
    
    url = build_feed_url(feed_id, start_dt, end_dt)
    print(f"Built feed URL: {url}")
    assert "startDate=2026-06-12T00:00:00-0000" in url, "Start date format mismatch."
    assert "endDate=2026-06-13T00:00:00-0000" in url, "End date format mismatch."
    print("✅ Feed URL constructed correctly.")
    
    # 3. Fetch Data
    print("Fetching data from SPOT API...")
    raw_json = fetch_feed_data(url)
    assert raw_json is not None, "Failed to fetch JSON data from SPOT API."
    print("✅ Successfully fetched JSON data.")
    
    # 4. Parse Messages
    print("Parsing SPOT messages...")
    messages = parse_spot_messages(raw_json)
    print(f"Found {len(messages)} messages.")
    assert len(messages) > 0, "Parsed messages list should not be empty."
    print("✅ Messages parsed successfully.")
    
    # 5. Save Messages to Database
    print("Saving messages to SQLite...")
    inserted_count = save_messages(test_db, messages)
    print(f"Messages processing complete. Rowcount/updates indicated: {inserted_count}")
    
    # 6. Retrieve and Validate Messages
    print("Reading back messages from database...")
    retrieved = get_all_messages(test_db)
    print(f"Retrieved {len(retrieved)} messages from DB.")
    assert len(retrieved) == len(messages), f"Number of retrieved messages ({len(retrieved)}) should match parsed ({len(messages)})."
    
    # Check fields of the first message
    first_msg = retrieved[0]
    required_fields = ['id', 'latitude', 'longitude', 'dateTime', 'unixTime']
    for field in required_fields:
        assert first_msg.get(field) is not None, f"Field '{field}' should not be None."
        
    print(f"First parsed message details:")
    print(f"  ID: {first_msg['id']}")
    print(f"  Time: {first_msg['dateTime']}")
    print(f"  Coordinates: {first_msg['latitude']}, {first_msg['longitude']}")
    print(f"  Battery: {first_msg['batteryState']}")
    print(f"  Type: {first_msg['messageType']}")
    
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
    
    # Clean up test database
    if os.path.exists(test_db):
        os.remove(test_db)
        print("🗑️ Test database cleaned up.")

if __name__ == "__main__":
    run_test()
