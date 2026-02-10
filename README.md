# My Sports Tracker (Streamlit)

A focused sports dashboard that tracks only:

- Pittsburgh Penguins
- Pittsburgh Steelers
- Men's Tennis Singles (Grand Slams only)
- Formula 1 (Mercedes)
- LA Lakers

## Features

- Scores + upcoming schedule
- News feed
- Live playoff odds feature where applicable (via The Odds API)

## Local Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Free Hosting on Streamlit Community Cloud

1. Push this project to a GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and sign in.
3. Click **New app** and select your repo/branch.
4. Set **Main file path** to `app.py`.
5. (Optional but recommended for live odds): add a secret in app settings:

```toml
ODDS_API_KEY = "your_api_key_here"
```

6. Deploy.

## Notes

- Scores/schedules/news use ESPN public endpoints.
- Playoff/championship odds appear only when sportsbooks expose relevant markets.
- For tennis tracker, events are filtered to Grand Slam tournaments only.
