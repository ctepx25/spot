import os
import io
import csv
import logging
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, Response, redirect, url_for

from dotenv import load_dotenv
import folium

from db_service import init_db, save_messages, get_all_messages, message_exists, get_last_message
from feed_service import build_feed_url, fetch_feed_data, parse_spot_messages, sync_feed_data

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SPOT_Flask")

# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- Configuration & Paths ---
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tracking.db")
init_db(DB_PATH)

# Fetch configuration variables from environment
DEFAULT_FEED_ID = "0FOq6U5ICzOEL4qCqbM8YrAOqUzP8uGUp"
feed_id = os.getenv("SPOT_FEED_ID", DEFAULT_FEED_ID)
tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

def get_marker_color(msg_type):
    msg_type = str(msg_type).upper()
    if "OK" in msg_type:
        return "green"
    elif "TRACK" in msg_type:
        return "blue"
    elif "HELP" in msg_type or "SOS" in msg_type:
        return "red"
    else:
        return "orange"

@app.route("/")
@app.route("/spot")
@app.route("/spot/")
def index():
    # Load all records from database
    all_msgs = get_all_messages(DB_PATH)
    
    # Extract unique dates present in the database to help with boundaries
    dates_in_db = sorted(list(set(msg['dateTime'][:10] for msg in all_msgs)))
    
    # Determine maximum date limit (today)
    max_date = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Determine selected date
    selected_date_str = request.args.get("date")
    if not selected_date_str:
        if dates_in_db:
            # Default to the most recent date available in the database
            selected_date_str = dates_in_db[-1]
        else:
            # Database is empty, default to June 12, 2026 (our standard tracking mock date)
            selected_date_str = "2026-06-12"
            
    # Filter messages for the selected date
    filtered_messages = [
        msg for msg in all_msgs 
        if msg['dateTime'].startswith(selected_date_str)
    ]
    # Sort chronologically by unixTime ascending
    filtered_messages.sort(key=lambda x: x['unixTime'])
    
    # 2. Compute metrics
    points_count = len(filtered_messages)
    battery_status = "UNKNOWN"
    last_check_in = "N/A"
    device_name = "SPOT Device"
    model_id = "SPOT"
    map_html = ""
    
    if points_count > 0:
        latest_point = filtered_messages[-1]
        battery_status = latest_point.get('batteryState', 'UNKNOWN').upper()
        
        # Format the ISO datetime to a more friendly string
        try:
            parsed_time = pd_to_datetime = datetime.strptime(latest_point['dateTime'][:19], "%Y-%m-%dT%H:%M:%S")
            last_check_in = parsed_time.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            last_check_in = latest_point['dateTime']
            
        device_name = latest_point.get('messengerName', 'SPOT Device')
        model_id = latest_point.get('modelId', 'SPOT')
        
        # 3. Generate Folium Map centered on the latest point
        center_lat = latest_point['latitude']
        center_lon = latest_point['longitude']
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13, control_scale=True)
        
        # Layers
        folium.TileLayer('openstreetmap').add_to(m)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Esri Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        folium.LayerControl().add_to(m)
        
        # Draw PolyLine connecting points
        coordinates = [(msg['latitude'], msg['longitude']) for msg in filtered_messages]
        if len(coordinates) > 1:
            folium.PolyLine(
                locations=coordinates,
                color="#007bff",
                weight=4,
                opacity=0.8,
                tooltip="Track Path"
            ).add_to(m)
            
        # Add markers
        for idx, row in enumerate(filtered_messages):
            lat, lon = row['latitude'], row['longitude']
            msg_type = row.get('messageType', 'Unknown')
            msg_content = row.get('messageContent', '')
            battery = row.get('batteryState', 'N/A')
            alt = row.get('altitude', 0)
            
            try:
                t = datetime.strptime(row['dateTime'][:19], "%Y-%m-%dT%H:%M:%S")
                time_str = t.strftime('%Y-%m-%d %H:%M UTC')
            except Exception:
                time_str = row['dateTime']
            
            # HTML Popup
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 12px; width: 220px;">
                <h4 style="margin: 0 0 5px 0; color: #1e3d59; border-bottom: 1px solid #ccc; padding-bottom: 3px;">📍 SPOT Check-in</h4>
                <b>Time:</b> {time_str}<br/>
                <b>Lat/Lon:</b> {lat:.5f}, {lon:.5f}<br/>
                <b>Altitude:</b> {alt:.0f} m<br/>
                <b>Type:</b> <span style="font-weight:bold; color:{get_marker_color(msg_type)};">{msg_type}</span><br/>
                <b>Battery:</b> {battery}<br/>
                {"<b>Message:</b> " + msg_content if msg_content else ""}
            </div>
            """
            
            # Prominent default marker for the latest location (safest against CDN font-blocking)
            if idx == len(filtered_messages) - 1:
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"LATEST - {time_str}"
                ).add_to(m)
            else:
                # Beautiful vector-based CircleMarker (renders natively as SVGs with zero external font/CSS requests)
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"Point {row['id']} - {time_str}",
                    color=get_marker_color(msg_type),
                    fill=True,
                    fill_color=get_marker_color(msg_type),
                    fill_opacity=0.8
                ).add_to(m)
                
        # Render map HTML as a sandboxed iframe snippet
        map_html = m._repr_html_()
        
    return render_template(
        "index.html",
        selected_date=selected_date_str,
        max_date=max_date,
        points_count=points_count,
        battery_status=battery_status,
        last_check_in=last_check_in,
        device_name=device_name,
        model_id=model_id,
        map_html=map_html,
        messages=filtered_messages
    )

@app.route("/sync", methods=["POST"])
@app.route("/spot/sync", methods=["POST"])
def sync():
    """
    Manual triggers route to sync data from the SPOT API.
    Uses current day as range.
    """
    try:
        # Determine tracking date boundaries (full day: 00:00 to 23:59)
        # Default to today unless a specific date is requested or inferred
        # For simplicity, we sync for the 24-hour range of today
        today_dt = datetime.now()
        start_dt = datetime.combine(today_dt, datetime.min.time())
        end_dt = datetime.combine(today_dt, datetime.max.time())
        
        success, new_count, notifications_sent, err = sync_feed_data(
            feed_id=feed_id,
            start_dt=start_dt,
            end_dt=end_dt,
            tg_token=tg_token,
            tg_chat_id=tg_chat_id,
            db_path=DB_PATH
        )
        
        if success:
            msg = f"Synced successfully! Added {new_count} points."
            if notifications_sent > 0:
                msg += f" Dispatched {notifications_sent} Telegram alerts."
            return jsonify({"success": True, "message": msg})
        else:
            return jsonify({"success": False, "error": err})
    except Exception as e:
        logger.error(f"Error during manual sync endpoint: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)})

@app.route("/download/<date_str>")
@app.route("/spot/download/<date_str>")
def download_csv(date_str):
    """
    Generates a streamable CSV download file for tracking history on a given date.
    """
    all_msgs = get_all_messages(DB_PATH)
    filtered_messages = [
        msg for msg in all_msgs 
        if msg['dateTime'].startswith(date_str)
    ]
    filtered_messages.sort(key=lambda x: x['unixTime'])
    
    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['id', 'dateTime', 'latitude', 'longitude', 'altitude', 'messageType', 'messageContent', 'batteryState', 'messengerName', 'modelId'])
    
    # Write data rows
    for msg in filtered_messages:
        writer.writerow([
            msg.get('id'),
            msg.get('dateTime'),
            msg.get('latitude'),
            msg.get('longitude'),
            msg.get('altitude'),
            msg.get('messageType'),
            msg.get('messageContent'),
            msg.get('batteryState'),
            msg.get('messengerName'),
            msg.get('modelId')
        ])
        
    output.seek(0)
    
    # Stream the CSV response with proper attachment headers
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=spot_tracking_data_{date_str}.csv"}
    )

if __name__ == "__main__":
    # Expose Flask development server on standard port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
