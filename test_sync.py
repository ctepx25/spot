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
    
    print("\n🎉 ALL DATABASE INTEGRATION TESTS PASSED SUCCESSFULLY!")
    
    # Clean up test database
    if os.path.exists(test_db):
        os.remove(test_db)
        print("🗑️ Test database cleaned up.")

def test_app_map_and_proxy_config():
    print("\n🧪 Verifying Flask ProxyFix middleware and Cartodb Positron map rendering...")
    from app import app
    from werkzeug.middleware.proxy_fix import ProxyFix
    
    # 1. Verify ProxyFix middleware is applied
    assert isinstance(app.wsgi_app, ProxyFix), "Flask app.wsgi_app should be wrapped with ProxyFix middleware."
    print("✅ Verified: ProxyFix is successfully applied to Flask app.wsgi_app.")

    # 2. Verify Flask detects proxy headers using test client
    with app.test_client() as client:
        @app.route("/_test_proxy_headers")
        def _test_proxy_headers():
            from flask import request
            return {"scheme": request.scheme, "host": request.host}
            
        response = client.get("/_test_proxy_headers", headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "my-secure-proxy.com"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data["scheme"] == "https", f"Flask should detect HTTPS from X-Forwarded-Proto. Got: {data['scheme']}"
        assert data["host"] == "my-secure-proxy.com", f"Flask should detect Host from X-Forwarded-Host. Got: {data['host']}"
    print("✅ Verified: Flask correctly handles forwarded proxy headers through ProxyFix.")

    # 3. Verify Map tile layers are generated with HTTPS-secured Cartodb Positron
    with app.test_client() as client:
        # Request the index page which renders the map
        response = client.get("/")
        assert response.status_code == 200, "Index route should respond with 200 OK."
        html_content = response.get_data(as_text=True)
        
        # Check that Cartodb Positron tile URL is present in the rendered HTML
        assert "basemaps.cartocdn.com/light_all" in html_content, "Map HTML should render Cartodb Positron basemap tiles URL."
        # Ensure it is secure HTTPS URL
        assert "https://" in html_content, "Cartodb Positron tiles should use HTTPS URL scheme."
    print("✅ Verified: Map renders with secure HTTPS Cartodb Positron tile URLs.")

if __name__ == "__main__":
    run_test()
    test_app_map_and_proxy_config()
