from pathlib import Path
import altair as alt
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

        /* Card Styling for Results - Adapts to Light/Dark Mode */
        .result-card {
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            padding: 1rem 1.2rem;
            border-radius: 8px;
            border-left: 5px solid #2ecc71;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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

def sort_results_newest_first(results):
    if "Date of Match" not in results.columns:
        return results

    return (
        results.assign(_match_date=pd.to_datetime(results["Date of Match"], dayfirst=True, errors="coerce"))
        .sort_values("_match_date", ascending=False, na_position="last", kind="stable")
        .drop(columns="_match_date")
    )

def build_advanced_stats(emerald_standings, shamrock_standings, results):
    start_date = pd.Timestamp("2026-10-05")
    today = pd.Timestamp.today().normalize()
    week_starts = pd.date_range(start=start_date, end=max(today, start_date), freq="W-MON")
    division_standings = {
        "Emerald": emerald_standings,
        "Shamrock": shamrock_standings,
    }
    required_columns = {
        "Select your Box League Division",
        "Winning Team",
        "Losing Team",
        "Winning Team Score (Games won)",
        "Losing Team Score (Games won)",
    }
    matches_by_division = {}

    if required_columns.issubset(results.columns):
        for division, standings in division_standings.items():
            if "Team" not in standings.columns:
                matches_by_division[division] = pd.DataFrame()
                continue

            teams = standings["Team"].dropna().astype(str).str.strip()
            teams = {team for team in teams if team}
            division_results = results[
                results["Select your Box League Division"]
                .astype("string")
                .str.contains(division, case=False, na=False, regex=False)
            ].copy()
            division_results["_winner"] = division_results["Winning Team"].astype("string").str.strip()
            division_results["_loser"] = division_results["Losing Team"].astype("string").str.strip()
            division_results["_winning_games"] = pd.to_numeric(
                division_results["Winning Team Score (Games won)"], errors="coerce"
            )
            division_results["_losing_games"] = pd.to_numeric(
                division_results["Losing Team Score (Games won)"], errors="coerce"
            )
            division_results = division_results[
                division_results["_winner"].isin(teams)
                & division_results["_loser"].isin(teams)
                & division_results["_winning_games"].notna()
                & division_results["_losing_games"].notna()
            ].copy()
            division_results["_margin"] = (
                division_results["_winning_games"] - division_results["_losing_games"]
            )
            division_results["_match_date"] = pd.to_datetime(
                division_results["Date of Match"], dayfirst=True, errors="coerce"
            ) if "Date of Match" in division_results.columns else pd.NaT
            matches_by_division[division] = division_results

    else:
        matches_by_division = {division: pd.DataFrame() for division in division_standings}

    margin_rows = []
    weekly_match_averages = {}
    completion_rows = []
    total_completed_pairings = 0
    total_possible_pairings = 0
    total_margins = []

    for division, standings in division_standings.items():
        division_matches = matches_by_division[division]
        margins = division_matches["_margin"] if "_margin" in division_matches else pd.Series(dtype=float)
        total_margins.extend(margins.tolist())
        margin_rows.append({
            "Division": division,
            "Average winning margin (games)": margins.mean(),
        })

        if not division_matches.empty:
            weekly_matches = division_matches[
                division_matches["_match_date"].ge(start_date)
                & division_matches["_match_date"].le(today)
            ].copy()
            if not weekly_matches.empty:
                weekly_matches["_week"] = (
                    weekly_matches["_match_date"].dt.to_period("W-SUN").dt.start_time
                )
                weekly_counts = weekly_matches.groupby("_week").size()
            else:
                weekly_counts = pd.Series(dtype=int)
        else:
            weekly_counts = pd.Series(dtype=int)
        weekly_match_averages[division] = (
            weekly_counts.reindex(week_starts, fill_value=0).sum() / len(week_starts)
        )

        if "Team" in standings.columns:
            teams = standings["Team"].dropna().astype(str).str.strip()
            teams = {team for team in teams if team}
            possible_pairings = len(teams) * (len(teams) - 1) // 2
        else:
            teams = set()
            possible_pairings = 0

        completed_pairings = set()
        if not division_matches.empty:
            completed_pairings = {
                frozenset((row["_winner"], row["_loser"]))
                for _, row in division_matches.iterrows()
                if row["_winner"] != row["_loser"]
            }
        completed_count = len(completed_pairings)
        total_completed_pairings += completed_count
        total_possible_pairings += possible_pairings
        completion_rows.append({
            "Division": division,
            "Games played (%)": (
                completed_count / possible_pairings * 100 if possible_pairings else 0
            ),
        })

    margin_rows.append({
        "Division": "Overall",
        "Average winning margin (games)": (
            sum(total_margins) / len(total_margins) if total_margins else float("nan")
        ),
    })
    weekly_match_averages["Overall"] = (
        weekly_match_averages["Emerald"] + weekly_match_averages["Shamrock"]
    )
    completion_rows.append({
        "Division": "Overall",
        "Games played (%)": (
            total_completed_pairings / total_possible_pairings * 100
            if total_possible_pairings else 0
        ),
    })

    return {
        "average_margin": pd.DataFrame(margin_rows).set_index("Division"),
        "average_matches_per_week": pd.DataFrame.from_dict(
            weekly_match_averages, orient="index", columns=["Average matches per week"]
        ).rename_axis("Division"),
        "completion": pd.DataFrame(completion_rows).set_index("Division"),
    }

def division_bar_chart(data, value_column, y_title, value_format, suffix=""):
    division_order = ["Emerald", "Shamrock", "Overall"]
    chart_data = data.reindex(division_order).reset_index()
    chart_data["Label"] = chart_data[value_column].map(
        lambda value: f"{value:.1f}{suffix}" if pd.notna(value) else "N/A"
    )

    bars = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X("Division:N", sort=division_order, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f"{value_column}:Q", title=y_title),
        color=alt.Color(
            "Division:N",
            scale=alt.Scale(
                domain=division_order,
                range=["#2ecc71", "#1b4d3e", "#808080"],
            ),
            legend=None,
        ),
        tooltip=[
            alt.Tooltip("Division:N"),
            alt.Tooltip(f"{value_column}:Q", title=y_title, format=value_format),
        ],
    )
    labels = alt.Chart(chart_data).mark_text(dy=-8).encode(
        x=alt.X("Division:N", sort=division_order),
        y=alt.Y(f"{value_column}:Q"),
        text=alt.Text("Label:N"),
    )
    return (bars + labels).properties(height=320)

def build_head_to_head_table(division_data, results_data, division_name):
    if "Team" not in division_data.columns:
        return pd.DataFrame()

    teams = division_data["Team"].dropna().astype(str).str.strip()
    teams = [team for team in teams if team]
    table = pd.DataFrame("—", index=teams, columns=teams, dtype=object)
    table.index.name = "Pairing"

    required_columns = {
        "Select your Box League Division",
        "Winning Team",
        "Losing Team",
        "Winning Team Score (Games won)",
        "Losing Team Score (Games won)",
    }
    if not required_columns.issubset(results_data.columns):
        return table

    division_results = results_data[
        results_data["Select your Box League Division"]
        .astype("string")
        .str.contains(division_name, case=False, na=False, regex=False)
    ]
    match_results = {}
    team_set = set(teams)

    for _, result in division_results.iterrows():
        winner = str(result["Winning Team"]).strip()
        loser = str(result["Losing Team"]).strip()
        if winner not in team_set or loser not in team_set:
            continue

        winning_score = result["Winning Team Score (Games won)"]
        losing_score = result["Losing Team Score (Games won)"]
        winning_score = "" if pd.isna(winning_score) else str(winning_score).strip()
        losing_score = "" if pd.isna(losing_score) else str(losing_score).strip()

        match_results.setdefault((winner, loser), []).append(
            f"W {winning_score}-{losing_score}"
        )
        match_results.setdefault((loser, winner), []).append(
            f"L {losing_score}-{winning_score}"
        )

    for (team, opponent), results in match_results.items():
        table.at[team, opponent] = "; ".join(results)

    return table

def style_head_to_head_table(table):
    def style_diagonal(row):
        return [
            "background-color: rgba(128, 128, 128, 0.35)" if row.name == column else ""
            for column in table.columns
        ]

    return table.style.apply(style_diagonal, axis=1)

def team_at_position(standings, position):
    if "Position" not in standings.columns or "Team" not in standings.columns:
        return "TBD"

    positions = pd.to_numeric(standings["Position"], errors="coerce")
    teams = standings.loc[positions == position, "Team"]
    if teams.empty or pd.isna(teams.iloc[0]) or not str(teams.iloc[0]).strip():
        return "TBD"

    return str(teams.iloc[0]).strip()

# Styling function to highlight top 2 playoff spots & shade Total Points column safely for themes
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
    
    # Shade the 'Total Points' column using Streamlit conditional / neutral fallback colors
    if "Total Points" in df.columns:
        styled = styled.set_properties(
            subset=["Total Points"], 
            props="background-color: rgba(128, 128, 128, 0.2); font-weight: bold;"
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

    # Create top-level tabs
    tab_emerald, tab_shamrock, tab_playoffs, tab_stats, tab_rules = st.tabs([
        "🟢 Emerald Division", 
        "☘️ Shamrock Division",
        "🏆 Playoffs",
        "📊 Advanced stats",
        "📖 League Rules"
    ])

    with tab_emerald:
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
            em_results = sort_results_newest_first(
                results_df[results_df["Select your Box League Division"].str.contains("Emerald", na=False)]
            )
            if not em_results.empty:
                with st.container(height=270):
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

        st.markdown("---")
        st.subheader("Emerald Division Head-to-Head Results")
        st.caption("Each cell shows the row pairing's results against the column pairing. Grey cells are self-matchups.")
        emerald_head_to_head = build_head_to_head_table(emerald_df, results_df, "Emerald")
        if emerald_head_to_head.empty:
            st.info("Pairing data is not available for the Emerald Division.")
        else:
            st.dataframe(
                style_head_to_head_table(emerald_head_to_head),
                use_container_width=True,
            )

    with tab_shamrock:
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
            sh_results = sort_results_newest_first(
                results_df[results_df["Select your Box League Division"].str.contains("Shamrock", na=False)]
            )
            if not sh_results.empty:
                with st.container(height=270):
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

        st.markdown("---")
        st.subheader("Shamrock Division Head-to-Head Results")
        st.caption("Each cell shows the row pairing's results against the column pairing. Grey cells are self-matchups.")
        shamrock_head_to_head = build_head_to_head_table(shamrock_df, results_df, "Shamrock")
        if shamrock_head_to_head.empty:
            st.info("Pairing data is not available for the Shamrock Division.")
        else:
            st.dataframe(
                style_head_to_head_table(shamrock_head_to_head),
                use_container_width=True,
            )

    with tab_playoffs:
        st.subheader("Semi-final & Final Bracket")
        st.caption("Projected from the current division standings. Qualifiers update as standings change.")

        emerald_first = team_at_position(emerald_df, 1)
        emerald_second = team_at_position(emerald_df, 2)
        shamrock_first = team_at_position(shamrock_df, 1)
        shamrock_second = team_at_position(shamrock_df, 2)

        semi_finals, final = st.columns(2)
        with semi_finals:
            st.markdown("### Semi-finals")
            with st.container(border=True):
                st.caption("Semi-final 1 · 2nd Emerald vs 1st Shamrock")
                st.write(emerald_second)
                st.markdown("**vs**")
                st.write(shamrock_first)
            with st.container(border=True):
                st.caption("Semi-final 2 · 1st Emerald vs 2nd Shamrock")
                st.write(emerald_first)
                st.markdown("**vs**")
                st.write(shamrock_second)

        with final:
            st.markdown("### Final")
            with st.container(border=True):
                st.caption("Winner of Semi-final 1")
                st.write("Winner of Semi-final 1")
                st.markdown("**vs**")
                st.caption("Winner of Semi-final 2")
                st.write("Winner of Semi-final 2")
                st.divider()
                st.write("🏆 Champion: TBD")

    with tab_stats:
        st.subheader("Advanced stats")
        st.caption(
            "Statistics use valid results matched to teams in the current standings. "
            "Weekly match averages use Monday-to-Sunday weeks from October 5, including the current week."
        )
        stats = build_advanced_stats(emerald_df, shamrock_df, results_df)

        st.markdown("### Average winning margin")
        st.caption("Average difference between the winner's and loser's game scores.")
        st.altair_chart(
            division_bar_chart(
                stats["average_margin"],
                "Average winning margin (games)",
                "Average margin (games)",
                ".1f",
            ),
            use_container_width=True,
        )

        st.markdown("### Average matches played per week")
        st.caption("Average matches recorded per calendar week since October 5, including the current week.")
        st.altair_chart(
            division_bar_chart(
                stats["average_matches_per_week"],
                "Average matches per week",
                "Average matches per week",
                ".1f",
            ),
            use_container_width=True,
        )

        st.markdown("### Round-robin pairings completed")
        st.caption(
            "Percentage of unique pairings played out of all possible pairings "
            "within each division; overall is weighted by each division's schedule size."
        )
        st.altair_chart(
            division_bar_chart(
                stats["completion"],
                "Games played (%)",
                "Pairings completed (%)",
                ".1f",
                suffix="%",
            ),
            use_container_width=True,
        )

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

# Direct MP4 link from Giphy's CDN for this sticker
giphy_mp4_url = "https://media.giphy.com/media/j0YrtFmQoUs2u2Lgv3/giphy.mp4"

# HTML5 video embed configured for background/sticker looping
video_html = f"""
    <div style="display: flex; justify-content: center;">
        <video width="300" autoplay loop muted playsinline style="background: transparent;">
            <source src="{giphy_mp4_url}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
    </div>
"""

st.markdown(video_html, unsafe_allow_html=True)