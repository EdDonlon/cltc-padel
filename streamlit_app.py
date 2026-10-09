from pathlib import Path
import pandas as pd
import streamlit as st

# Set the title and favicon that appear in the browser's tab bar.
st.set_page_config(
    page_title="Charleville LTC Padel Box League",
    page_icon="🌍",
)

st.title("🎾 Charleville LTC Padel Box League")
st.markdown("Live standings and league tables pulled directly from the official Google Sheet.")

# Google Sheet Export URL configuration
# Sheet ID extracted from your link: 1x-tP2lFaBGqMcWXN4QIErGF02FD3HZFD_IH4U32eiDU
# GID for Emerald Division: 1522007513 (you can add other GIDs if you have multiple tabs)
SHEET_ID = "1x-tP2lFaBGqMcWXN4QIErGF02FD3HZFD_IH4U32eiDU"
EMERALD_GID = "1522007513"

@st.cache_data(ttl=60)  # Cache data for 1 minute to avoid hitting rate limits
def load_league_data(gid):
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    # Read CSV, skipping initial metadata rows if needed depending on sheet structure
    df = pd.read_csv(csv_url)
    return df

try:
    st.subheader("Emerald Division")
    emerald_df = load_league_data(EMERALD_GID)
    
    # Display the table interactively
    st.dataframe(emerald_df, use_container_width=True, hide_index=True)

    # Optional: Add tabs or selectors if you have more divisions (e.g., Shamrock Division)
    # SHAMROCK_GID = "your_other_gid_here"
    
except Exception as e:
    st.error(f"Could not load league tables: {e}")
    st.info("Ensure that your Google Sheet is shared with 'Anyone with the link can view' so the app can read it.")

# Add a sidebar helper or link back to the entry form/rules
st.sidebar.markdown("### Quick Links")
st.sidebar.markdown("[📊 View Full Google Sheet](https://docs.google.com/spreadsheets/d/1x-tP2lFaBGqMcWXN4QIErGF02FD3HZFD_IH4U32eiDU/edit?resourcekey=&gid=1522007513)")