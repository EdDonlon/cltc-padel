from pathlib import Path
import pandas as pd
import streamlit as st

# Configure the page layout to use wide mode for full width tables
st.set_page_config(
    page_title="Charleville LTC Padel Box League",
    page_icon="🎾",
    layout="wide",
)

# --- CUSTOM CSS FOR POLISHED UI ---
st.markdown(
    """
    <style>
        /* Main App Background & Font Styling */
        .stApp {
            background-color: #f8f9fa;
        }

        /* Custom Header Banner with Court Background Image */
        .header-container {
            background: linear-gradient(rgba(27, 77, 62, 0.88), rgba(46, 204, 113, 0.88)), 
                        url('https://images.unsplash.com/photo-1709587825099-f6f07e5337af?q=80&w=3131&auto=format&fit=crop');
            background-size: cover;
            background-position: center;
            padding: 2.5rem 2rem;
            border-radius: 10px;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .header-container h1 {
            color: white !important;
            margin-bottom: 0.2rem;
        }
        .header-container p {
            color: #e8f5e9 !important;
            font-size: 1.1rem;
        }

        /* Card Styling for Results */
        .result-card {
            background-color: white;
            padding: 1rem 1.2rem;
            border-radius: 8px;
            border-left: 5px solid #2ecc71;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 0.8rem;
            font-size: 1rem;
        }
        
    </style>
    """,
    unsafe_allow_html=True,
)

# Google Sheet Export URL configuration
SHEET_ID = "1x-tP2lFaBGqMcWXN4QIErGF02FD3HZFD_IH4U32eiDU"
EMERALD_GID = "1522007513"
SHAMROCK_GID = "954276068"

@st.cache_data(ttl=60)
def load_league_data(gid):
    csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    df = pd.read_csv(csv_url, skiprows=1)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    # Add spacing padding to the Team column values to force a wider column fit natively
    if "Team" in df.columns:
        df["Team"] = df["Team"].astype(str) + "    "
        
    return df

@st.cache_data(ttl=60)
def load_results_data():
    try:
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Results"
        df = pd.read_csv(csv_url)
        return df
    except Exception:
        return pd.DataFrame()

# Styling function to highlight top 2 playoff spots & shade Total Points grey
def style_league_table(df):
    def apply_styles(row):
        styles = [''] * len(row)
        try:
            pos = int(row.iloc[0])
            if pos <= 2:
                for i in range(len(row)):
                    styles[i] = 'background-color: rgba(46, 204, 113, 0.25); font-weight: bold;'
        except Exception:
            pass
        return styles

    styled = df.style.apply(apply_styles, axis=1)
    
    # Shade the 'Total Points' column in grey to emphasize importance
    if "Total Points" in df.columns:
        styled = styled.set_properties(
            subset=["Total Points"], 
            props="background-color: #e0e0e0; font-weight: bold; color: #000000;"
        )
        
    return styled

# Styled Header Banner
st.markdown(
    """
    <div class="header-container">
        <h1>Charleville LTC Padel Box League</h1>
        <p>Live standings, results, and official league rules. Sep-Nov 2026.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    emerald_df = load_league_data(EMERALD_GID)
    shamrock_df = load_league_data(SHAMROCK_GID)
    results_df = load_results_data()

    # Create 3 top-level tabs
    tab_emerald, tab_shamrock, tab_rules = st.tabs([
        "🟢 Emerald Division", 
        "☘️ Shamrock Division", 
        "📖 League Rules"
    ])

    with tab_emerald:
        # Optional: Add logo if file exists (e.g., emerald_logo.png in project directory)
        #if Path("images/Emerald Logo.jpg").exists():
        #    st.image("images/Emerald Logo.jpg", width=120)
            
        st.subheader("Emerald Division Standings")
        st.markdown("*(Top 2 teams qualify for the semi-finals!)*")
        st.dataframe(
            style_league_table(emerald_df), 
            use_container_width=True, 
            hide_index=True
        )
        
        st.markdown("---")
        st.subheader("🏆 Emerald Division Results")
        if not results_df.empty and "Select your Box League Division" in results_df.columns:
            em_results = results_df[results_df["Select your Box League Division"].str.contains("Emerald", na=False)]
            if not em_results.empty:
                for _, row in em_results.iterrows():
                    winner = row.get("Winning Team", "")
                    loser = row.get("Losing Team", "")
                    w_score = row.get("Winning Team Score (Games won)", "")
                    l_score = row.get("Losing Team Score (Games won)", "")
                    date = row.get("Date of Match", "")
                    st.markdown(
                        f"""
                        <div class="result-card">
                            📅 <b>{date}</b> &nbsp;|&nbsp; 🏆 <b>{winner}</b> ({w_score}) vs. {loser} ({l_score})
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("No results recorded for the Emerald Division yet.")
        else:
            st.info("No results recorded yet.")

    with tab_shamrock:
        # Optional: Add logo if file exists (e.g., shamrock_logo.png in project directory)
        if Path("shamrock_logo.png").exists():
            st.image("shamrock_logo.png", width=120)
            
        st.subheader("Shamrock Division Standings")
        st.markdown("*(Top 2 teams qualify for the semi-finals!)*")
        st.dataframe(
            style_league_table(shamrock_df), 
            use_container_width=True, 
            hide_index=True,
        )
        
        st.markdown("---")
        st.subheader("🏆 Shamrock Division Results")
        if not results_df.empty and "Select your Box League Division" in results_df.columns:
            sh_results = results_df[results_df["Select your Box League Division"].str.contains("Shamrock", na=False)]
            if not sh_results.empty:
                for _, row in sh_results.iterrows():
                    winner = row.get("Winning Team", "")
                    loser = row.get("Losing Team", "")
                    w_score = row.get("Winning Team Score (Games won)", "")
                    l_score = row.get("Losing Team Score (Games won)", "")
                    date = row.get("Date of Match", "")
                    st.markdown(
                        f"""
                        <div class="result-card">
                            📅 <b>{date}</b> &nbsp;|&nbsp; 🏆 <b>{winner}</b> ({w_score}) vs. {loser} ({l_score})
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            else:
                st.info("No results recorded for the Shamrock Division yet.")
        else:
            st.info("No results recorded yet.")

    with tab_rules:
        st.subheader("Charleville LTC Padel Box League Rules")
        try:
            with open("rules.md", "r", encoding="utf-8") as f:
                rules_markdown = f.read()
            st.markdown(rules_markdown)
        except FileNotFoundError:
            st.error("rules.md file not found. Please create it in your project root.")

except Exception as e:
    st.error(f"Could not load league tables: {e}")
    st.info("Ensure that your Google Sheet is shared with 'Anyone with the link can view'.")