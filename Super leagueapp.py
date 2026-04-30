import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Super League Dashboard", layout="wide")

BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"
LEAGUE_ID = 4415


# -----------------------------
# DATA LOADER
# -----------------------------
@st.cache_data(ttl=3600)
def load_data():

    # ---------------- MATCHES ----------------
    events_url = f"{BASE_URL}/eventsseason.php?id={LEAGUE_ID}&s=2026"
    events = requests.get(events_url).json().get("events", [])

    matches = pd.DataFrame(events)

    if matches.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    matches = matches[[
        "dateEvent",
        "strHomeTeam",
        "strAwayTeam",
        "intHomeScore",
        "intAwayScore",
        "strEvent"
    ]].rename(columns={
        "dateEvent": "date",
        "strHomeTeam": "home",
        "strAwayTeam": "away",
        "intHomeScore": "home_score",
        "intAwayScore": "away_score",
        "strEvent": "match"
    })

    matches["home_score"] = pd.to_numeric(matches["home_score"], errors="coerce")
    matches["away_score"] = pd.to_numeric(matches["away_score"], errors="coerce")

    # winner
    matches["winner"] = matches.apply(
        lambda x: (
            x["home"] if x["home_score"] > x["away_score"]
            else x["away"] if x["away_score"] > x["home_score"]
            else "Draw"
        ),
        axis=1
    )

    # ---------------- TEAMS ----------------
    teams_url = f"{BASE_URL}/lookup_all_teams.php?id={LEAGUE_ID}"
    teams = requests.get(teams_url).json().get("teams", [])

    teams = pd.DataFrame(teams)[[
        "strTeam", "strStadium", "strLocation"
    ]].rename(columns={
        "strTeam": "team",
        "strStadium": "stadium",
        "strLocation": "location"
    })

    # ---------------- PLAYERS ----------------
    players_all = []

    for team in teams["team"]:
        url = f"{BASE_URL}/searchplayers.php?t={team}"
        res = requests.get(url).json().get("player")

        if res:
            for p in res:
                players_all.append({
                    "player": p.get("strPlayer"),
                    "team": p.get("strTeam"),
                    "position": p.get("strPosition"),
                    "nationality": p.get("strNationality")
                })

    players = pd.DataFrame(players_all)

    # ---------------- TRY SCORERS (ESTIMATED MODEL) ----------------
    try_scorers = []

    for _, row in matches.iterrows():
        if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
            continue

        margin = abs(row["home_score"] - row["away_score"])

        try_scorers.append({
            "match": row["match"],
            "team": row["winner"],
            "tries_estimated": max(1, int(margin / 4)),
            "date": row["date"]
        })

    tries = pd.DataFrame(try_scorers)

    # ---------------- TEAM STATS ----------------
    team_points = {}

    for _, row in matches.iterrows():
        if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
            continue

        team_points[row["home"]] = team_points.get(row["home"], {"for": 0, "against": 0})
        team_points[row["away"]] = team_points.get(row["away"], {"for": 0, "against": 0})

        team_points[row["home"]]["for"] += row["home_score"]
        team_points[row["home"]]["against"] += row["away_score"]

        team_points[row["away"]]["for"] += row["away_score"]
        team_points[row["away"]]["against"] += row["home_score"]

    team_stats = pd.DataFrame([
        {
            "team": k,
            "points_for": v["for"],
            "points_against": v["against"],
            "net": v["for"] - v["against"]
        }
        for k, v in team_points.items()
    ])

    return matches, tries, players, teams, team_stats


# -----------------------------
# LOAD DATA
# -----------------------------
matches, tries, players, teams, team_stats = load_data()


# -----------------------------
# UI
# -----------------------------
st.title("🏉 Super League Analytics Dashboard")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Matches",
    "🔥 Attack (Tries)",
    "🛡 Defence",
    "👥 Players"
])


# ---------------- MATCHES ----------------
with tab1:
    st.subheader("Match Results")

    if not matches.empty:
        st.dataframe(matches)
    else:
        st.warning("No match data available")


# ---------------- ATTACK ----------------
with tab2:
    st.subheader("Estimated Try Scorers")

    if not tries.empty:
        st.dataframe(
            tries.sort_values("tries_estimated", ascending=False)
        )
    else:
        st.warning("No try data available")


    st.subheader("Attack Rankings")

    if not team_stats.empty:
        st.dataframe(
            team_stats.sort_values("points_for", ascending=False)
        )


# ---------------- DEFENCE ----------------
with tab3:
    st.subheader("Defensive Rankings")

    if not team_stats.empty:
        st.dataframe(
            team_stats.sort_values("points_against", ascending=True)
        )


# ---------------- PLAYERS ----------------
with tab4:
    st.subheader("Players")

    if not players.empty:
        team_filter = st.selectbox("Filter by team", ["All"] + sorted(players["team"].dropna().unique()))

        if team_filter != "All":
            filtered = players[players["team"] == team_filter]
        else:
            filtered = players

        st.dataframe(filtered)
    else:
        st.warning("No player data available")
