import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import streamlit as st

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ODDS_BASE = "https://api.the-odds-api.com/v4"

TRACKING_CONFIG = {
    "pittsburgh_penguins": {
        "label": "Pittsburgh Penguins",
        "sport": "hockey",
        "league": "nhl",
        "team_name": "Pittsburgh Penguins",
        "odds_sport_key": "icehockey_nhl",
    },
    "pittsburgh_steelers": {
        "label": "Pittsburgh Steelers",
        "sport": "football",
        "league": "nfl",
        "team_name": "Pittsburgh Steelers",
        "odds_sport_key": "americanfootball_nfl",
    },
    "la_lakers": {
        "label": "LA Lakers",
        "sport": "basketball",
        "league": "nba",
        "team_name": "Los Angeles Lakers",
        "odds_sport_key": "basketball_nba",
    },
    "ny_knicks": {
        "label": "NY Knicks",
        "sport": "basketball",
        "league": "nba",
        "team_name": "New York Knicks",
        "odds_sport_key": "basketball_nba",
    },
    "f1_mercedes": {
        "label": "Formula 1 (Mercedes)",
        "sport": "racing",
        "league": "f1",
        "team_name": "Mercedes",
        "odds_sport_key": "formula1",
    },
    "mens_tennis_slams": {
        "label": "Men's Tennis Singles (Grand Slams)",
        "sport": "tennis",
        "league": "atp",
        "team_name": None,
        "odds_sport_key": None,
    },
}

GRAND_SLAM_KEYS = [
    "australian open",
    "french open",
    "roland garros",
    "wimbledon",
    "us open",
]


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

    candidates = (
        data.get("sports", [{}])[0]
        .get("leagues", [{}])[0]
        .get("teams", [])
    )

    target = team_name.lower()
    for item in candidates:
        team = item.get("team", {})
        names = [
            team.get("displayName", ""),
            team.get("name", ""),
            team.get("shortDisplayName", ""),
            team.get("abbreviation", ""),
        ]
        joined = " ".join(names).lower()
        if target in joined or joined in target:
            return team.get("id")
    return None


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

    return {
        "Date/Time": local_time,
        "Matchup": f"{away} @ {home}",
        "Score": score,
        "Status": status,
    }


def filter_team_events(events: List[Dict[str, Any]], team_name: Optional[str]) -> List[Dict[str, Any]]:
    if not team_name:
        return events
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


@st.cache_data(ttl=180)
def get_events_in_window(sport: str, league: str, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    date_range = f"{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}"
    url = f"{ESPN_BASE}/{sport}/{league}/scoreboard"
    data = fetch_json(url, params={"dates": date_range, "limit": 200})
    return data.get("events", [])


def _normalize_team_name(name: str) -> str:
    """Normalize team names so ESPN and The Odds API can line up."""
    cleaned = "".join(ch for ch in (name or "").lower() if ch.isalnum() or ch.isspace())
    return " ".join(cleaned.split())


def _make_matchup_key(away: str, home: str, iso_datetime: Optional[str]) -> str:
    """Build a stable key for a matchup on a given date."""
    try:
        dt = datetime.fromisoformat(iso_datetime.replace("Z", "+00:00")) if iso_datetime else None
        date_key = dt.date().isoformat() if dt else ""
    except Exception:
        date_key = ""
    return f"{_normalize_team_name(away)}|{_normalize_team_name(home)}|{date_key}"


def build_matchup_key_from_espn_event(event: Dict[str, Any]) -> str:
    """Create a matchup key from an ESPN scoreboard event."""
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
    """Reduce a The Odds API event into simple display strings."""
    home = odds_event.get("home_team", "")
    away = odds_event.get("away_team", "")

    best_home_ml = None
    best_away_ml = None
    best_spread = None
    best_total = None

    for book in odds_event.get("bookmakers", []):
        for market in book.get("markets", []):
            key = market.get("key")
            outcomes = market.get("outcomes", [])

            if key == "h2h":
                for o in outcomes:
                    name = o.get("name")
                    price = o.get("price")
                    if price is None:
                        continue
                    if name == home and best_home_ml is None:
                        best_home_ml = price
                    elif name == away and best_away_ml is None:
                        best_away_ml = price

            elif key == "spreads":
                for o in outcomes:
                    if o.get("name") == home:
                        point = o.get("point")
                        price = o.get("price")
                        if price is None:
                            continue
                        if best_spread is None:
                            best_spread = (point, price)

            elif key == "totals":
                for o in outcomes:
                    # Prefer the Over leg for a simple summary
                    if str(o.get("name", "")).lower().startswith("over"):
                        point = o.get("point")
                        price = o.get("price")
                        if price is None:
                            continue
                        if best_total is None:
                            best_total = (point, price)

    summary: Dict[str, str] = {}

    if best_home_ml is not None or best_away_ml is not None:
        if best_home_ml is not None and best_away_ml is not None:
            summary["moneyline"] = f"{away} {best_away_ml:+} / {home} {best_home_ml:+}"
        elif best_home_ml is not None:
            summary["moneyline"] = f"{home} {best_home_ml:+}"
        elif best_away_ml is not None:
            summary["moneyline"] = f"{away} {best_away_ml:+}"

    if best_spread is not None:
        point, price = best_spread
        if isinstance(point, (int, float)):
            summary["spread"] = f"{home} {point:+g} ({price:+})"
        else:
            summary["spread"] = f"{home} {point} ({price:+})"

    if best_total is not None:
        point, price = best_total
        summary["total"] = f"O/U {point} (O {price:+})"

    return summary


@st.cache_data(ttl=120)
def get_event_odds_map(odds_sport_key: str, api_key: str) -> Dict[str, Dict[str, str]]:
    """
    Fetch per-game odds from The Odds API and index them by matchup key.

    We request standard game markets (moneyline, spreads, totals) and then
    collapse to simple display strings.
    """
    url = f"{ODDS_BASE}/sports/{odds_sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }
    data = fetch_json(url, params=params)
    if not isinstance(data, list):
        return {}

    out: Dict[str, Dict[str, str]] = {}
    for event in data:
        away = event.get("away_team", "")
        home = event.get("home_team", "")
        commence_time = event.get("commence_time")
        key = _make_matchup_key(away, home, commence_time)
        summary = summarize_odds_for_event(event)
        if summary:
            out[key] = summary
    return out


@st.cache_data(ttl=300)
def get_news(sport: str, league: str, team_id: Optional[str]) -> List[Dict[str, str]]:
    if team_id:
        url = f"{ESPN_BASE}/{sport}/{league}/teams/{team_id}/news"
    else:
        url = f"{ESPN_BASE}/{sport}/{league}/news"

    data = fetch_json(url)
    articles = data.get("articles", [])
    news = []
    for a in articles[:8]:
        links = a.get("links", {}).get("web", {})
        news.append(
            {
                "headline": a.get("headline", "Untitled"),
                "published": a.get("published", "")[:10],
                "source": (a.get("source") or "ESPN"),
                "url": links.get("href", ""),
            }
        )
    return news


@st.cache_data(ttl=120)
def get_live_odds(team_name: str, odds_sport_key: Optional[str], api_key: Optional[str]) -> Dict[str, str]:
    if not odds_sport_key:
        return {"status": "Not applicable"}
    if not api_key:
        return {"status": "Missing API key"}

    url = f"{ODDS_BASE}/sports/{odds_sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "outrights",
        "oddsFormat": "american",
    }
    data = fetch_json(url, params=params)
    if not isinstance(data, list):
        return {"status": "Unavailable"}

    target = team_name.lower()
    best_playoff = None
    best_title = None

    for event in data:
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    name = str(outcome.get("name", "")).lower()
                    desc = str(outcome.get("description", "")).lower()
                    price = outcome.get("price")
                    if not price:
                        continue
                    if target in name:
                        if "playoff" in desc or "make playoffs" in desc:
                            if best_playoff is None:
                                best_playoff = price
                        if "champion" in desc or "win" in desc or "title" in desc or market.get("key") == "outrights":
                            if best_title is None:
                                best_title = price

    if best_playoff is None and best_title is None:
        return {"status": "No market found"}

    result = {"status": "OK"}
    if best_playoff is not None:
        result["playoff_market"] = f"{best_playoff:+}"
    if best_title is not None:
        result["championship_market"] = f"{best_title:+}"
    return result


def render_scores_and_schedule(
    label: str,
    sport: str,
    league: str,
    team_name: Optional[str],
    only_grand_slams: bool = False,
    odds_sport_key: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc)
    past_start = now - timedelta(days=7)
    future_end = now + timedelta(days=14)

    events = get_events_in_window(sport, league, past_start, future_end)

    if only_grand_slams:
        events = filter_grand_slams(events)

    events = filter_team_events(events, team_name)

    if not events:
        st.info("No events found in the current window.")
        return

    odds_map: Dict[str, Dict[str, str]] = {}
    if odds_sport_key:
        api_key = st.secrets.get("ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
        if api_key:
            odds_map = get_event_odds_map(odds_sport_key=odds_sport_key, api_key=api_key)
        else:
            st.caption("Add `ODDS_API_KEY` in Streamlit secrets to enable per-game odds.")

    rows: List[Dict[str, Any]] = []
    any_odds = False
    for e in events:
        row = format_event_row(e)
        if odds_map:
            matchup_key = build_matchup_key_from_espn_event(e)
            summary = odds_map.get(matchup_key)
            if summary:
                row["Moneyline Odds"] = summary.get("moneyline", "-")
                row["Spread"] = summary.get("spread", "-")
                row["Total"] = summary.get("total", "-")
                any_odds = True
        rows.append(row)

    frame = pd.DataFrame(rows)

    if any_odds:
        for col in ("Moneyline Odds", "Spread", "Total"):
            if col in frame.columns:
                frame[col] = frame[col].fillna("-")

    st.subheader("Recent Scores + Upcoming Schedule")
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_news(label: str, sport: str, league: str, team_name: Optional[str]) -> None:
    team_id = get_team_id(sport, league, team_name) if team_name else None
    items = get_news(sport, league, team_id)

    st.subheader("News")
    if not items:
        st.info("No news items available right now.")
        return

    for item in items:
        if item["url"]:
            st.markdown(f"- [{item['headline']}]({item['url']}) ({item['source']}, {item['published']})")
        else:
            st.markdown(f"- {item['headline']} ({item['source']}, {item['published']})")


def render_live_odds(label: str, team_name: Optional[str], odds_sport_key: Optional[str]) -> None:
    st.subheader("Live Playoff Odds")

    if not team_name or not odds_sport_key:
        st.caption("Not applicable for this tracker.")
        return

    api_key = None
    try:
        api_key = st.secrets.get("ODDS_API_KEY")
    except Exception:
        pass

    if not api_key:
        api_key = os.getenv("ODDS_API_KEY")

    odds = get_live_odds(team_name=team_name, odds_sport_key=odds_sport_key, api_key=api_key)

    status = odds.get("status")
    if status == "Missing API key":
        st.warning("Add `ODDS_API_KEY` in Streamlit secrets to enable live odds.")
        st.caption("This feature uses The Odds API free tier.")
        return
    if status != "OK":
        st.info("Live playoff/championship odds are not available at the moment for this selection.")
        return

    if "playoff_market" in odds:
        st.metric("To Make Playoffs (best line found)", odds["playoff_market"])
    if "championship_market" in odds:
        st.metric("Championship / Title (best line found)", odds["championship_market"])


def render_f1_constructor_context() -> None:
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
        st.subheader("Constructor Context")
        c1, c2 = st.columns(2)
        c1.metric("Mercedes Rank", matched["rank"])
        c2.metric("Mercedes Points", matched["points"])


def main() -> None:
    st.set_page_config(page_title="My Sports Tracker", page_icon="🏟️", layout="wide")
    st.title("My Sports Tracker")
    st.caption("Tracking only: Penguins, Steelers, Men's Grand Slams, Mercedes F1, LA Lakers, and NY Knicks")

    st.markdown("---")

    tabs = st.tabs([
        TRACKING_CONFIG["pittsburgh_penguins"]["label"],
        TRACKING_CONFIG["pittsburgh_steelers"]["label"],
        TRACKING_CONFIG["mens_tennis_slams"]["label"],
        TRACKING_CONFIG["f1_mercedes"]["label"],
        TRACKING_CONFIG["la_lakers"]["label"],
        TRACKING_CONFIG["ny_knicks"]["label"],
    ])

    tab_keys = [
        "pittsburgh_penguins",
        "pittsburgh_steelers",
        "mens_tennis_slams",
        "f1_mercedes",
        "la_lakers",
        "ny_knicks",
    ]

    for tab, key in zip(tabs, tab_keys):
        cfg = TRACKING_CONFIG[key]
        with tab:
            render_scores_and_schedule(
                label=cfg["label"],
                sport=cfg["sport"],
                league=cfg["league"],
                team_name=cfg["team_name"],
                only_grand_slams=(key == "mens_tennis_slams"),
                odds_sport_key=cfg["odds_sport_key"],
            )

            if key == "f1_mercedes":
                render_f1_constructor_context()

            render_news(
                label=cfg["label"],
                sport=cfg["sport"],
                league=cfg["league"],
                team_name=cfg["team_name"],
            )

            render_live_odds(
                label=cfg["label"],
                team_name=cfg["team_name"],
                odds_sport_key=cfg["odds_sport_key"],
            )

    with st.sidebar:
        st.header("Data Sources")
        st.markdown("- ESPN public APIs (scores, schedules, standings, news)")
        st.markdown("- The Odds API (optional, for live odds)")
        st.markdown("- Refreshes automatically with short cache TTLs")

        st.header("Deploy Free")
        st.markdown("Use Streamlit Community Cloud and connect this repo.")
        st.code("pip install -r requirements.txt\nstreamlit run app.py", language="bash")


if __name__ == "__main__":
    main()
