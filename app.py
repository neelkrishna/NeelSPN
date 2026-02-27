import os
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# --- Configuration & Constants ---
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ODDS_BASE = "https://api.the-odds-api.com/v4"

TRACKING_CONFIG = {
    "pittsburgh_penguins": {
        "label": "🐧 Penguins",
        "sport": "hockey",
        "league": "nhl",
        "team_name": "Pittsburgh Penguins",
        "odds_sport_key": "icehockey_nhl",
        "accent": "#FFB81C"  # Pittsburgh Gold
    },
    "pittsburgh_steelers": {
        "label": "🏈 Steelers",
        "sport": "football",
        "league": "nfl",
        "team_name": "Pittsburgh Steelers",
        "odds_sport_key": "americanfootball_nfl",
        "accent": "#FFB81C"
    },
    "la_lakers": {
        "label": "🏀 Lakers",
        "sport": "basketball",
        "league": "nba",
        "team_name": "Los Angeles Lakers",
        "odds_sport_key": "basketball_nba",
        "accent": "#552583" # Lakers Purple
    },
    "ny_knicks": {
        "label": "🏀 Knicks",
        "sport": "basketball",
        "league": "nba",
        "team_name": "New York Knicks",
        "odds_sport_key": "basketball_nba",
        "accent": "#F58426" # Knicks Orange
    },
    "f1_mercedes": {
        "label": "🏎️ Mercedes F1",
        "sport": "racing",
        "league": "f1",
        "team_name": "Mercedes",
        "odds_sport_key": "formula1",
        "accent": "#00A19B" # Petronas Green
    },
    "mens_tennis_slams": {
        "label": "🎾 Grand Slams",
        "sport": "tennis",
        "league": "atp",
        "team_name": None,
        "odds_sport_key": None,
        "accent": "#A3CC00" # Tennis Green
    },
}

GRAND_SLAM_KEYS = ["australian open", "french open", "roland garros", "wimbledon", "us open"]

# --- Custom CSS for Styling & Animations ---
def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Montserrat:wght@700;900&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3 {
        font-family: 'Montserrat', sans-serif;
        letter-spacing: -0.02em;
    }

    .stApp {
        background-color: #0E1117;
    }

    /* Card styling */
    .metric-card {
        background-color: #1E2129;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #FF4B4B;
    }

    /* Fade-in animation */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .animate-in {
        animation: fadeIn 0.6s ease-out forwards;
    }

    /* Custom Header */
    .main-header {
        font-size: 3rem;
        font-weight: 900;
        background: linear-gradient(90deg, #FF4B4B, #FF8C00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }

    /* Metric overrides */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #FFFFFF;
    }

    [data-testid="stMetricDelta"] {
        font-weight: 600;
    }

    /* News Item Styling */
    .news-item {
        padding: 12px;
        border-bottom: 1px solid #30363D;
        transition: background-color 0.2s ease;
    }
    .news-item:hover {
        background-color: #262730;
    }
    .news-link {
        text-decoration: none !important;
        color: #FAFAFA !important;
        font-weight: 600;
        font-size: 1.05rem;
    }
    .news-meta {
        font-size: 0.85rem;
        color: #8B949E;
        margin-top: 4px;
    }

    /* Sidebar tweaks */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }

    /* Tab styling */
    button[data-baseweb="tab"] {
        font-weight: 600;
        font-size: 1rem;
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #FF4B4B !important;
        border-bottom-color: #FF4B4B !important;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #0E1117;
    }
    ::-webkit-scrollbar-thumb {
        background: #30363D;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #484F58;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Data Fetching Logic (Cached) ---

@st.cache_data(ttl=120)
def fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        res = requests.get(url, params=params, timeout=15)
        res.raise_for_status()
        return res.json()
    except requests.RequestException:
        return {}

@st.cache_data(ttl=3600)
def get_team_id(sport: str, league: str, team_name: str) -> Optional[str]:
    url = f"{ESPN_BASE}/{sport}/{league}/teams"
    data = fetch_json(url)
    candidates = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    target = team_name.lower()
    for item in candidates:
        team = item.get("team", {})
        names = [team.get("displayName", ""), team.get("name", ""), team.get("shortDisplayName", ""), team.get("abbreviation", "")]
        joined = " ".join(names).lower()
        if target in joined or joined in target:
            return team.get("id")
    return None

@st.cache_data(ttl=180)
def get_events_in_window(sport: str, league: str, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    date_range = f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    data = fetch_json(url, params={"dates": date_range, "limit": 200})
    return data.get("events", [])

# --- Utility Functions ---

def _normalize_team_name(name: str) -> str:
    cleaned = "".join(ch for ch in (name or "").lower() if ch.isalnum() or ch.isspace())
    return " ".join(cleaned.split())

def _make_matchup_key(away: str, home: str, iso_datetime: Optional[str]) -> str:
    try:
        dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00")) if iso_datetime else None
        date_key = dt.date().isoformat() if dt else ""
    except Exception:
        date_key = ""
    return f"{_normalize_team_name(away)}|{_normalize_team_name(home)}|{date_key}"

def build_matchup_key_from_espn_event(event: Dict[str, Any]) -> str:
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])
    if len(competitors) >= 2:
        away_obj = next((c for c in competitors if c.get("homeAway") == "away"), competitors[0])
        home_obj = next((c for c in competitors if c.get("homeAway") == "home"), competitors[1])
        away = away_obj.get("team", {}).get("displayName", "")
        home = home_obj.get("team", {}).get("displayName", "")
    else:
        away = competitors[0].get("team", {}).get("displayName", "") if competitors else ""
        home = ""
    iso_date = event.get("date")
    return _make_matchup_key(away, home, iso_date)

def summarize_odds_for_event(odds_event: Dict[str, Any]) -> Dict[str, str]:
    home = odds_event.get("home_team", "")
    away = odds_event.get("away_team", "")
    best_home_ml, best_away_ml, best_spread, best_total = None, None, None, None

    for book in odds_event.get("bookmakers", []):
        for market in book.get("markets", []):
            key, outcomes = market.get("key"), market.get("outcomes", [])
            if key == "h2h":
                for o in outcomes:
                    name, price = o.get("name"), o.get("price")
                    if price is None: continue
                    if name == home: best_home_ml = price
                    elif name == away: best_away_ml = price
            elif key == "spreads":
                for o in outcomes:
                    if o.get("name") == home:
                        point, price = o.get("point"), o.get("price")
                        if price is not None: best_spread = (point, price)
            elif key == "totals":
                for o in outcomes:
                    if str(o.get("name", "")).lower().startswith("over"):
                        point, price = o.get("point"), o.get("price")
                        if price is not None: best_total = (point, price)

    summary: Dict[str, str] = {}
    if best_home_ml is not None and best_away_ml is not None:
        summary["moneyline"] = f"{best_away_ml:+} / {best_home_ml:+}"
    if best_spread is not None:
        summary["spread"] = f"{best_spread[0]:+g} ({best_spread[1]:+})"
    if best_total is not None:
        summary["total"] = f"O/U {best_total[0]} ({best_total[1]:+})"
    return summary

@st.cache_data(ttl=120)
def get_event_odds_map(odds_sport_key: str, api_key: str) -> Dict[str, Dict[str, str]]:
    url = f"{ODDS_BASE}/sports/{odds_sport_key}/odds"
    params = {"apiKey": api_key, "regions": "us", "markets": "h2h,spreads,totals", "oddsFormat": "american"}
    data = fetch_json(url, params=params)
    if not isinstance(data, list): return {}
    out: Dict[str, Dict[str, str]] = {}
    for event in data:
        key = _make_matchup_key(event.get("away_team", ""), event.get("home_team", ""), event.get("commence_time"))
        summary = summarize_odds_for_event(event)
        if summary: out[key] = summary
    return out

def format_event_row(event: Dict[str, Any]) -> Dict[str, Any]:
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])
    if len(competitors) < 2:
        away = competitors[0].get("team", {}).get("displayName", "TBD") if competitors else "TBD"
        home = "TBD"
        score = "-"
    else:
        away_obj = next((c for c in competitors if c.get("homeAway") == "away"), competitors[0])
        home_obj = next((c for c in competitors if c.get("homeAway") == "home"), competitors[1])
        away = away_obj.get("team", {}).get("displayName", "Away")
        home = home_obj.get("team", {}).get("displayName", "Home")
        away_score = away_obj.get("score", "")
        home_score = home_obj.get("score", "")
        score = f"{away_score}-{home_score}" if away_score or home_score else "-"

    iso_date = event.get("date")
    dt_utc = datetime.fromisoformat(iso_date.replace("Z", "+00:00")) if iso_date else None
    local_time = dt_utc.astimezone().strftime("%Y-%m-%d %I:%M %p") if dt_utc else "-"
    status = competition.get("status", {}).get("type", {}).get("description") or event.get("status", {}).get("type", {}).get("description", "")

    return {"Date/Time": local_time, "Matchup": f"{away} @ {home}", "Score": score, "Status": status}

def filter_team_events(events: List[Dict[str, Any]], team_name: Optional[str]) -> List[Dict[str, Any]]:
    if not team_name: return events
    filtered = []
    target = team_name.lower()
    for e in events:
        competitors = e.get("competitions", [{}])[0].get("competitors", [])
        names = [c.get("team", {}).get("displayName", "").lower() for c in competitors]
        if any(target in n or n in target for n in names):
            filtered.append(e)
    return filtered

def filter_grand_slams(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for e in events:
        name = (e.get("name") or "").lower()
        short_name = (e.get("shortName") or "").lower()
        if any(k in name or k in short_name for k in GRAND_SLAM_KEYS):
            out.append(e)
    return out

# --- Rendering Components ---

def render_header():
    st.markdown('<div class="main-header">NeelSPN</div>', unsafe_allow_html=True)
    st.markdown('<p style="color: #8B949E; font-size: 1.1rem; margin-bottom: 2rem;">Personalized Sports Tracker Dashboard</p>', unsafe_allow_html=True)

def render_scores_and_schedule(cfg: Dict[str, Any]):
    st.subheader("Recent Scores & Schedule")
    now = datetime.now(timezone.utc)
    past_start, future_end = now - timedelta(days=7), now + timedelta(days=14)

    events = get_events_in_window(cfg["sport"], cfg["league"], past_start, future_end)
    if cfg["team_name"] is None and "mens_tennis_slams" in cfg["label"].lower():
        events = filter_grand_slams(events)
    events = filter_team_events(events, cfg["team_name"])

    if not events:
        st.info("No recent or upcoming events found.")
        return

    odds_map, api_key = {}, st.secrets.get("ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
    if api_key and cfg["odds_sport_key"]:
        odds_map = get_event_odds_map(cfg["odds_sport_key"], api_key)

    rows = []
    for e in events:
        row = format_event_row(e)
        if odds_map:
            matchup_key = build_matchup_key_from_espn_event(e)
            summary = odds_map.get(matchup_key)
            if summary:
                row["Moneyline"] = summary.get("moneyline", "-")
                row["Spread"] = summary.get("spread", "-")
                row["Total"] = summary.get("total", "-")
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_news(cfg: Dict[str, Any]):
    st.subheader("Latest Headlines")
    team_id = get_team_id(cfg["sport"], cfg["league"], cfg["team_name"]) if cfg["team_name"] else None
    
    articles = []
    if team_id:
        url = f"{ESPN_BASE}/{cfg['sport']}/{cfg['league']}/teams/{team_id}/news"
        data = fetch_json(url)
        articles = data.get("articles", [])

    # Fallback to league-wide news if team news is empty or not requested
    if not articles:
        league_url = f"{ESPN_BASE}/{cfg['sport']}/{cfg['league']}/news"
        data = fetch_json(league_url)
        articles = data.get("articles", [])
    
    if not articles:
        st.info("No news headlines available at the moment.")
        return

    for a in articles[:6]:
        links = a.get("links", {}).get("web", {})
        headline = a.get("headline", "Untitled")
        source = a.get("source") or "ESPN"
        published = a.get("published", "")[:10]
        href = links.get("href", "#")
        
        st.markdown(f"""
        <div class="news-item">
            <a href="{href}" class="news-link" target="_blank">{headline}</a>
            <div class="news-meta">{source} • {published}</div>
        </div>
        """, unsafe_allow_html=True)

def render_odds_summary(cfg: Dict[str, Any]):
    st.subheader("Market Outlook")
    if not cfg["odds_sport_key"]:
        st.info("hi cam")
        return

    api_key = st.secrets.get("ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
    if not api_key:
        st.info("hi cam")
        return

    # For simplicity, we'll use the existing logic but style it
    # Redefining briefly for completeness in one file or reuse
    odds = get_live_odds_internal(cfg["team_name"], cfg["odds_sport_key"], api_key)
    
    if odds.get("status") != "OK":
        st.info("hi cam")
        return

    col1, col2 = st.columns(2)
    if "playoff_market" in odds:
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Playoff Probability", odds["playoff_market"])
            st.markdown('</div>', unsafe_allow_html=True)
    if "championship_market" in odds:
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Championship Odds", odds["championship_market"])
            st.markdown('</div>', unsafe_allow_html=True)

def get_live_odds_internal(team_name: str, odds_sport_key: str, api_key: str) -> Dict[str, Any]:
    url = f"{ODDS_BASE}/sports/{odds_sport_key}/odds"
    params = {"apiKey": api_key, "regions": "us", "markets": "outrights", "oddsFormat": "american"}
    data = fetch_json(url, params=params)
    if not isinstance(data, list): return {"status": "Unavailable"}

    target = _normalize_team_name(team_name)
    best_playoff, best_title = None, None
    for event in data:
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    name, desc = _normalize_team_name(outcome.get("name", "")), str(outcome.get("description", "")).lower()
                    price = outcome.get("price")
                    if not price: continue
                    # Fuzzy match: target in name or name in target
                    if target in name or name in target:
                        if "playoff" in desc or "make playoffs" in desc:
                            if best_playoff is None: best_playoff = price
                        if "champion" in desc or "win" in desc or "title" in desc or market.get("key") == "outrights":
                            if best_title is None: best_title = price
    
    if best_playoff is None and best_title is None: return {"status": "No market found"}
    res = {"status": "OK"}
    if best_playoff is not None: res["playoff_market"] = f"{best_playoff:+}"
    if best_title is not None: res["championship_market"] = f"{best_title:+}"
    return res

# --- Main App ---

def main():
    st.set_page_config(page_title="NeelSPN | Dashboard", page_icon="🏟️", layout="wide")
    inject_custom_css()
    
    with st.sidebar:
        st.markdown(f'<div style="text-align: center; margin-bottom: 20px;">'
                    f'<span style="font-size: 5rem;">🏟️</span>'
                    f'</div>', unsafe_allow_html=True)
        st.header("Settings")
        st.info("Tracking 6 major interests across NHL, NFL, NBA, F1, and Tennis.")
        
        st.divider()
        st.subheader("Data Feeds")
        st.caption("• ESPN Core API")
        st.caption("• The Odds API v4")
        st.caption("• Real-time updates every 2-3 mins")

    render_header()

    tab_labels = [cfg["label"] for cfg in TRACKING_CONFIG.values()]
    tabs = st.tabs(tab_labels)

    for i, (key, cfg) in enumerate(TRACKING_CONFIG.items()):
        with tabs[i]:
            st.markdown('<div class="animate-in">', unsafe_allow_html=True)
            
            # Layout for each tab
            col_main, col_side = st.columns([2, 1])
            
            with col_main:
                render_scores_and_schedule(cfg)
                st.markdown("<br>", unsafe_allow_html=True)
                render_news(cfg)
            
            with col_side:
                render_odds_summary(cfg)
                if key == "f1_mercedes":
                    # Re-use existing F1 logic or simplify
                    render_f1_context()
            
            st.markdown('</div>', unsafe_allow_html=True)

def render_f1_context():
    url = f"{ESPN_BASE}/racing/f1/standings"
    data = fetch_json(url)
    standings = data.get("children", [])
    matched = None
    for group in standings:
        entries = group.get("standings", {}).get("entries", [])
        for e in entries:
            team = e.get("team", {})
            if "mercedes" in (team.get("displayName", "").lower() + " " + team.get("shortDisplayName", "").lower()):
                stats = e.get("stats", [])
                points = next((s.get("displayValue") for s in stats if s.get("name", "").lower() == "points"), "-")
                rank = next((s.get("displayValue") for s in stats if s.get("name", "").lower() in ["rank", "position"]), "-")
                matched = {"team": team.get("displayName", "Mercedes"), "points": points, "rank": rank}
                break
    if matched:
        st.subheader("Constructor Standings")
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.metric("Current Rank", matched["rank"])
        c2.metric("Total Points", matched["points"])
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
