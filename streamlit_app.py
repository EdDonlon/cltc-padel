from pathlib import Path
import pandas as pd
import streamlit as st

# Configure the page layout to use wide mode for full width tables
st.set_page_config(
    page_title="Charleville LTC Padel Box League",
    page_icon="🎾",
    layout="wide",
)

st.title("🎾 Charleville LTC Padel Box League")
st.markdown("Live standings and league tables pulled directly from the official Google Sheet.")

# Google Sheet Export URL configuration
SHEET_ID = "1x-tP2lFaBGqMcWXN4QIErGF02FD3HZFD_IH4U32eiDU"
EMERALD_GID = "1522007513"
SHAMROCK_GID = "1753177685"  # GID for Shamrock Division tab

@st.cache_data(ttl=60)
def load_league_data(gid):
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    # skiprows=2 skips the title rows so row 3 becomes the clean column headers
    df = pd.read_csv(csv_url, skiprows=2)
    # Drop completely empty columns or unnamed index artifacts if any exist
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    return df

try:
    # Use tabs for clean division switching
    tab_emerald, tab_shamrock = st.tabs(["🟢 Emerald Division", "☘️ Shamrock Division"])

    with tab_emerald:
        st.subheader("Emerald Division Standings")
        emerald_df = load_league_data(EMERALD_GID)
        st.dataframe(
            emerald_df, 
            use_container_width=True, 
            hide_index=True
        )

    with tab_shamrock:
        st.subheader("Shamrock Division Standings")
        shamrock_df = load_league_data(SHAMROCK_GID)
        st.dataframe(
            shamrock_df, 
            use_container_width=True, 
            hide_index=True
        )

except Exception as e:
    st.error(f"Could not load league tables: {e}")
    st.info("Ensure that your Google Sheet is shared with 'Anyone with the link can view'.")

# Sidebar quick links
st.sidebar.markdown("### Quick Links")
st.sidebar.markdown("[📊 View Full Google Sheet](https://docs.google.com/spreadsheets/d/1x-tP2lFaBGqMcWXN4QIErGF02FD3HZFD_IH4U32eiDU/edit?resourcekey=&gid=1522007513)")