import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime, date, timedelta
import os
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

from db_service import init_db, save_messages, get_all_messages, message_exists, get_last_message
from feed_service import build_feed_url, fetch_feed_data, parse_spot_messages, sync_feed_data
from notification_service import send_telegram_notification, format_track_start_message, format_custom_message

# Load environment variables from .env file if available
load_dotenv()

# --- Page Config & Styling ---
st.set_page_config(
    page_title="SPOT Live Location Feed Dashboard",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a highly polished, modern aesthetic
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #007bff;
        margin-bottom: 20px;
    }
    .metric-card-low-battery {
        background-color: #fff3cd;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 5px solid #ffc107;
        margin-bottom: 20px;
    }
    .main-title {
        color: #1e3d59;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .subtitle {
        color: #17b978;
        font-size: 1.1rem;
        margin-bottom: 25px;
    }
</style>
""", unsafe_allow_html=True)

# --- Configuration & Paths ---
DB_PATH = os.path.join("data", "tracking.db")

# Initialize database
init_db(DB_PATH)


# --- App Title & Subtitle ---
st.markdown('<h1 class="main-title">📍 SPOT Live Location Feed Dashboard</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Real-time GPS tracking and historical path visualization for SPOT devices.</p>', unsafe_allow_html=True)

# --- Sidebar Configuration ---
st.sidebar.image("https://img.icons8.com/color/96/000000/gps-device.png", width=80)
st.sidebar.title("SPOT Tracker Settings")

# Load SPOT Feed ID securely from environment/.env
feed_id = os.getenv("SPOT_FEED_ID", "0FOq6U5ICzOEL4qCqbM8YrAOqUzP8uGUp")

# Date selection
st.sidebar.subheader("Date Filter")
# Initialize date using the historical example period by default (June 2026)
today = date(2026, 6, 13)
default_date = date(2026, 6, 12)

selected_date = st.sidebar.date_input("Tracking Date", default_date, max_value=today)

# Convert selected date to datetimes (00:00:00 to 23:59:59)
start_dt = datetime.combine(selected_date, datetime.min.time())
end_dt = datetime.combine(selected_date, datetime.max.time())

# Load credentials securely from environment/.env for behind-the-scenes UI triggers
tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

# Auto-refresh selector
refresh_option = st.sidebar.selectbox(
    "🔄 Auto-Refresh Interval",
    options=["Off", "1 Min", "5 Mins", "10 Mins"],
    index=0,
    help="Automatically syncs the SPOT feed and refreshes the map at the chosen interval."
)

# Fetch and Store Action
st.sidebar.subheader("Data Synchronization")
sync_button = st.sidebar.button("🔄 Sync Live Feed Data", use_container_width=True)

# Auto-refresh handler (executes BEFORE database loading to ensure fresh data)
interval_mapping = {
    "1 Min": 60 * 1000,
    "5 Mins": 300 * 1000,
    "10 Mins": 600 * 1000
}

if refresh_option != "Off":
    interval_ms = interval_mapping[refresh_option]
    st_autorefresh(interval=interval_ms, key="spot_map_refresh")
    # Silently fetch latest data in background
    st.toast("Auto-syncing live feed...", icon="🔄")
    sync_feed_data(feed_id, start_dt, end_dt, tg_token, tg_chat_id, db_path=DB_PATH)

if sync_button:
    with st.spinner("Fetching data from SPOT API..."):
        success, new_count, notifications_sent, err = sync_feed_data(feed_id, start_dt, end_dt, tg_token, tg_chat_id, db_path=DB_PATH)
        if success:
            if new_count > 0:
                success_msg = f"Synced successfully! Added {new_count} new tracking points."
                if notifications_sent > 0:
                    success_msg += f" Dispatched {notifications_sent} Telegram alerts."
                st.sidebar.success(success_msg)
            else:
                st.sidebar.info("Sync complete. All points are already stored in the database.")
        else:
            st.sidebar.error(err)
# --- Load Database Records ---
all_msgs = get_all_messages(DB_PATH)

if not all_msgs:
    # If database is completely empty, prompt user to fetch initial dataset
    st.info("👋 Welcome! The local database is currently empty. Click 'Sync Live Feed Data' in the sidebar to populate the tracker.")
    # Initialize df as empty
    df = pd.DataFrame()
else:
    # Convert list of dicts to DataFrame
    df = pd.DataFrame(all_msgs)
    
    # Parse date strings to pandas Datetime
    df['dateTime_parsed'] = pd.to_datetime(df['dateTime'])
    
    # Apply date filters
    df_filtered = df[
        (df['dateTime_parsed'] >= pd.Timestamp(start_dt).tz_localize('UTC')) & 
        (df['dateTime_parsed'] <= pd.Timestamp(end_dt).tz_localize('UTC'))
    ].sort_values(by="unixTime", ascending=True)
    
    if df_filtered.empty:
        st.warning("⚠️ No data available in the selected date range. Try syncing again or adjusting dates.")
    else:
        # --- Metrics Display ---
        latest_point = df_filtered.iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Point Count Metric
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <small style="color: #6c757d; font-weight: 600;">TOTAL PATH POINTS</small>
                <h2 style="margin: 0; color: #1e3d59;">{len(df_filtered)}</h2>
                <small style="color: #17b978;">Filtered dataset</small>
            </div>
            """, unsafe_allow_html=True)
            
        # Battery Status Metric
        with col2:
            battery_status = latest_point.get('batteryState', 'UNKNOWN').upper()
            battery_color = "#28a745" if battery_status == "GOOD" else "#dc3545" if battery_status == "LOW" else "#6c757d"
            battery_card_style = "metric-card-low-battery" if battery_status == "LOW" else "metric-card"
            st.markdown(f"""
            <div class="{battery_card_style}">
                <small style="color: #6c757d; font-weight: 600;">BATTERY STATUS</small>
                <h2 style="margin: 0; color: {battery_color};">{battery_status}</h2>
                <small style="color: #6c757d;">Last device report</small>
            </div>
            """, unsafe_allow_html=True)
            
        # Last Known Location Date/Time
        with col3:
            last_time_str = latest_point['dateTime_parsed'].strftime('%Y-%m-%d %H:%M UTC')
            st.markdown(f"""
            <div class="metric-card">
                <small style="color: #6c757d; font-weight: 600;">LAST CHECK-IN</small>
                <h3 style="margin: 5px 0; color: #1e3d59; font-size: 1.25rem;">{last_time_str}</h3>
                <small style="color: #6c757d;">Device check-in time</small>
            </div>
            """, unsafe_allow_html=True)
            
        # Device details
        with col4:
            messenger_name = latest_point.get('messengerName', 'SPOT Device')
            model_id = latest_point.get('modelId', 'Unknown Model')
            st.markdown(f"""
            <div class="metric-card">
                <small style="color: #6c757d; font-weight: 600;">DEVICE IDENTITY</small>
                <h2 style="margin: 0; color: #1e3d59; font-size: 1.5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{messenger_name}</h2>
                <small style="color: #6c757d;">Model: {model_id}</small>
            </div>
            """, unsafe_allow_html=True)

        # Low Battery Global Warning
        if battery_status == "LOW":
            st.warning(f"⚠️ **Device Alert:** The tracker device battery level is **LOW**. Please replace the batteries soon.")

        # --- Interactive Map & Data Details Layout ---
        st.subheader("🗺️ Live Tracking Map & Path Analysis")
        
        # Create Folium Map centered on the latest point
        center_lat = latest_point['latitude']
        center_lon = latest_point['longitude']
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, control_scale=True)
        
        # Map styling layer options
        folium.TileLayer('openstreetmap').add_to(m)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Esri Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        # Add layer control to change map styles
        folium.LayerControl().add_to(m)
        
        # Add Path (PolyLine) connecting sequential coordinates
        coordinates = list(zip(df_filtered['latitude'], df_filtered['longitude']))
        if len(coordinates) > 1:
            folium.PolyLine(
                locations=coordinates,
                color="#007bff",
                weight=4,
                opacity=0.8,
                tooltip="Tracker Path"
            ).add_to(m)
            
        # Helper function to get color coding by messageType
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
        
        # Plot markers
        for idx, row in df_filtered.iterrows():
            lat, lon = row['latitude'], row['longitude']
            time_str = row['dateTime_parsed'].strftime('%Y-%m-%d %H:%M UTC')
            msg_type = row.get('messageType', 'Unknown')
            msg_content = row.get('messageContent', '')
            battery = row.get('batteryState', 'N/A')
            alt = row.get('altitude', 0)
            
            # Construct beautiful HTML popup content
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 12px; width: 220px;">
                <h4 style="margin: 0 0 5px 0; color: #1e3d59; border-bottom: 1px solid #ccc; padding-bottom: 3px;">📍 SPOT Check-in</h4>
                <b>Time:</b> {time_str}<br/>
                <b>Lat/Lon:</b> {lat:.5f}, {lon:.5f}<br/>
                <b>Altitude:</b> {alt} m<br/>
                <b>Type:</b> <span style="font-weight:bold; color:{get_marker_color(msg_type)};">{msg_type}</span><br/>
                <b>Battery:</b> {battery}<br/>
                {"<b>Message:</b> " + msg_content if msg_content else ""}
            </div>
            """
            
            # If it is the latest point, use a star marker to make it highly prominent!
            if idx == df_filtered.index[-1]:
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"LATEST - {time_str}",
                    icon=folium.Icon(color="red", icon="star", prefix="fa")
                ).add_to(m)
            else:
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"Point {row['id']} - {time_str}",
                    icon=folium.Icon(color=get_marker_color(msg_type), icon="info-sign")
                ).add_to(m)
                
        # Render Folium map in Streamlit
        st_folium(m, height=550, use_container_width=True)
        
        # --- Detailed Data Explorer & Download ---
        st.subheader("📊 Historical Data Records Explorer")
        
        # Filter table option
        all_types = sorted(df_filtered['messageType'].unique())
        selected_types = st.multiselect("Filter data table by Message Type", options=all_types, default=all_types)
        
        table_df = df_filtered[df_filtered['messageType'].isin(selected_types)].copy()
        
        # Display the styled table
        st.dataframe(
            table_df[['id', 'dateTime', 'latitude', 'longitude', 'altitude', 'messageType', 'messageContent', 'batteryState']],
            use_container_width=True,
            hide_index=True
        )
        
        # Enable downloading database dump
        csv_data = table_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Data as CSV",
            data=csv_data,
            file_name=f"spot_tracking_data_{selected_date}.csv",
            mime="text/csv"
        )
