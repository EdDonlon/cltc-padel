from html import escape
from itertools import combinations
from pathlib import Path
import altair as alt
import numpy as np
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

def filter_results_by_team(results, division_data, key):
    if "Team" not in division_data.columns or not {"Winning Team", "Losing Team"}.issubset(results.columns):
        return results, "All"

    teams = (
        division_data["Team"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    teams = teams[teams.ne("")].drop_duplicates().tolist()
    selected_team = st.selectbox("Filter results by team", ["All", *teams], key=key)

    if selected_team != "All":
        winners = results["Winning Team"].fillna("").astype(str).str.strip()
        losers = results["Losing Team"].fillna("").astype(str).str.strip()
        results = results[winners.eq(selected_team) | losers.eq(selected_team)]

    return results, selected_team

def parse_news_posts(news_markdown):
    posts = []
    current_title = None
    current_body = []

    for line in news_markdown.splitlines():
        if line.startswith("## "):
            if current_title:
                posts.append((current_title, "\n".join(current_body).strip()))
            current_title = line[3:].strip()
            current_body = []
        elif current_title:
            current_body.append(line)

    if current_title:
        posts.append((current_title, "\n".join(current_body).strip()))

    return posts

def estimate_playoff_probabilities(standings, results, division_name, simulations=10_000):
    if "Team" not in standings.columns:
        return pd.DataFrame(columns=["Team", "Playoff probability"])

    teams = standings["Team"].dropna().astype(str).str.strip()
    teams = list(dict.fromkeys(team for team in teams if team))
    team_count = len(teams)
    if not team_count:
        return pd.DataFrame(columns=["Team", "Playoff probability"])

    team_indexes = {team: index for index, team in enumerate(teams)}
    if "Total Points" in standings.columns:
        points_by_team = (
            standings.assign(_team=standings["Team"].astype(str).str.strip())
            .drop_duplicates("_team")
            .set_index("_team")["Total Points"]
        )
        current_points = pd.to_numeric(points_by_team.reindex(teams), errors="coerce").fillna(0).to_numpy()
    else:
        current_points = np.zeros(team_count)

    columns = {
        "Select your Box League Division",
        "Winning Team",
        "Losing Team",
        "Winning Team Score (Games won)",
        "Losing Team Score (Games won)",
    }
    valid_results = pd.DataFrame()
    if columns.issubset(results.columns):
        valid_results = results[
            results["Select your Box League Division"]
            .astype("string")
            .str.contains(division_name, case=False, na=False, regex=False)
        ].copy()
        valid_results["_winner"] = valid_results["Winning Team"].astype("string").str.strip()
        valid_results["_loser"] = valid_results["Losing Team"].astype("string").str.strip()
        valid_results["_winning_games"] = pd.to_numeric(
            valid_results["Winning Team Score (Games won)"], errors="coerce"
        )
        valid_results["_losing_games"] = pd.to_numeric(
            valid_results["Losing Team Score (Games won)"], errors="coerce"
        )
        valid_results = valid_results[
            valid_results["_winner"].isin(teams)
            & valid_results["_loser"].isin(teams)
            & valid_results["_winner"].ne(valid_results["_loser"])
            & valid_results["_winning_games"].ge(0)
            & valid_results["_losing_games"].ge(0)
        ]

    games_won = np.zeros(team_count)
    games_played = np.zeros(team_count)
    played_pairings = set()
    for _, match in valid_results.iterrows():
        winner = team_indexes[match["_winner"]]
        loser = team_indexes[match["_loser"]]
        winner_games = match["_winning_games"]
        loser_games = match["_losing_games"]
        if pd.isna(winner_games) or pd.isna(loser_games):
            continue
        games_won[winner] += winner_games
        games_won[loser] += loser_games
        games_played[winner] += winner_games + loser_games
        games_played[loser] += winner_games + loser_games
        played_pairings.add(frozenset((winner, loser)))

    # Smooth small samples toward an even game split; unplayed teams start at 50%.
    game_win_rates = (games_won + 8.5) / (games_played + 17)
    rng = np.random.default_rng(20261012 if division_name == "Emerald" else 20261013)
    final_points = np.tile(current_points, (simulations, 1))

    for team_a, team_b in combinations(range(team_count), 2):
        if frozenset((team_a, team_b)) in played_pairings:
            continue

        probability_a_wins_game = game_win_rates[team_a] / (
            game_win_rates[team_a] + game_win_rates[team_b]
        )
        games_a = rng.binomial(17, probability_a_wins_game, size=simulations)
        games_b = 17 - games_a
        final_points[:, team_a] += games_a + (games_a > games_b) * 2
        final_points[:, team_b] += games_b + (games_b > games_a) * 2

    playoff_slots = min(2, team_count)
    cutoff = np.partition(final_points, -playoff_slots, axis=1)[:, -playoff_slots]
    above_cutoff = final_points > cutoff[:, np.newaxis]
    tied_at_cutoff = final_points == cutoff[:, np.newaxis]
    slots_left = playoff_slots - above_cutoff.sum(axis=1)
    tie_count = tied_at_cutoff.sum(axis=1)
    playoff_shares = above_cutoff + tied_at_cutoff * (
        slots_left / tie_count
    )[:, np.newaxis]
    probabilities = playoff_shares.mean(axis=0)

    return (
        pd.DataFrame({"Team": teams, "Playoff probability": probabilities})
        .sort_values("Playoff probability", ascending=False, kind="stable")
        .reset_index(drop=True)
    )

def build_advanced_stats(emerald_standings, shamrock_standings, results):
    start_date = pd.Timestamp("2026-10-05")
    today = pd.Timestamp.today().normalize()
    current_week_start = today - pd.Timedelta(days=today.weekday())
    week_starts = pd.date_range(
        start=start_date,
        end=current_week_start - pd.Timedelta(days=7),
        freq="W-MON",
    )
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
                & division_matches["_match_date"].lt(current_week_start)
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
            if len(week_starts)
            else float("nan")
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
    def team_label(team):
        return escape(str(team), quote=True).replace("&amp;", "&amp;<br>")

    table_header_style = (
        "padding: 0.5rem; text-align: left; vertical-align: top; "
        "border: 1px solid rgba(128, 128, 128, 0.25); "
        "background-color: rgba(128, 128, 128, 0.08);"
    )
    cell_style = "padding: 0.5rem; border: 1px solid rgba(128, 128, 128, 0.25);"
    headers = "".join(
        f'<th style="{table_header_style}">{team_label(team)}</th>'
        for team in table.columns
    )
    rows = []
    for team, values in table.iterrows():
        cells = []
        for opponent, value in values.items():
            background = (
                "background-color: rgba(128, 128, 128, 0.35);"
                if team == opponent
                else ""
            )
            cells.append(
                f'<td style="{cell_style} {background}">{escape(str(value), quote=True)}</td>'
            )
        rows.append(
            f'<tr><th style="{table_header_style}">{team_label(team)}</th>{"".join(cells)}</tr>'
        )

    return (
        '<div style="overflow-x: auto;"><table style="width: 100%; '
        'border-collapse: collapse; font-size: 0.85rem;">'
        f'<thead><tr><th style="{table_header_style}">Pairing</th>{headers}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )

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
    tab_emerald, tab_shamrock, tab_playoffs, tab_stats, tab_news, tab_rules = st.tabs([
        "🟢 Emerald Division", 
        "☘️ Shamrock Division",
        "🏆 Playoffs",
        "📊 Advanced stats",
        "📰 News",
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
                em_results, selected_team = filter_results_by_team(
                    em_results, emerald_df, "emerald_results_team_filter"
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
                    st.info(f"No results found for {selected_team}.")
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
            st.markdown(
                style_head_to_head_table(emerald_head_to_head),
                unsafe_allow_html=True,
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
                sh_results, selected_team = filter_results_by_team(
                    sh_results, shamrock_df, "shamrock_results_team_filter"
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
                    st.info(f"No results found for {selected_team}.")
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
            st.markdown(
                style_head_to_head_table(shamrock_head_to_head),
                unsafe_allow_html=True,
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
            "Weekly match averages use completed Monday-to-Sunday weeks from October 5."
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
        st.caption("Average matches recorded per completed calendar week since October 5.")
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

        st.markdown("### Playoff probability")
        st.caption(
            "Estimated top-two chances from 10,000 simulations of the remaining round-robin matches. "
            "Current league points are retained; future 17-game match scores use each team's "
            "recorded game-win rate, smoothed toward 50%. Teams with no results use the 50% baseline. "
            "Tied positions at the cutoff share the available playoff probability."
        )
        emerald_probabilities = estimate_playoff_probabilities(
            emerald_df, results_df, "Emerald"
        )
        shamrock_probabilities = estimate_playoff_probabilities(
            shamrock_df, results_df, "Shamrock"
        )
        emerald_column, shamrock_column = st.columns(2)
        with emerald_column:
            st.markdown("#### Emerald Division")
            st.dataframe(
                emerald_probabilities,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Playoff probability": st.column_config.NumberColumn(
                        "Playoff probability",
                        format="percent",
                    )
                },
            )
        with shamrock_column:
            st.markdown("#### Shamrock Division")
            st.dataframe(
                shamrock_probabilities,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Playoff probability": st.column_config.NumberColumn(
                        "Playoff probability",
                        format="percent",
                    )
                },
            )

    with tab_news:
        st.subheader("League News")
        try:
            news_markdown = Path("news.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            st.error("news.md file not found. Please create it in your project root.")
        else:
            news_posts = parse_news_posts(news_markdown)
            if not news_posts:
                st.info(
                    "No news posts yet. Add posts to news.md using a level-two heading "
                    "(## Post title), then write the post content in Markdown. "
                    "List the newest post first."
                )
            for title, body in news_posts:
                with st.container(border=True):
                    st.markdown(f"### {title}")
                    if body:
                        st.markdown(body)

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
    <div style="display: flex; justify-content: center; box-shadow: none;">
        <video width="250" autoplay loop muted playsinline style="background: transparent; box-shadow: none; border: none; outline: none; filter: none;">
            <source src="{giphy_mp4_url}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
    </div>
"""

st.markdown(video_html, unsafe_allow_html=True)