# Briefing: AI, wars and global news

## Setup (about 10 minutes, free)
1. Create a GitHub repository and upload all files in this folder (including `.github`).
2. Settings > Pages > Deploy from branch > `main` / root.
3. Actions > "Update news" > Run workflow. It then runs hourly and creates `news.json`.
4. Open `https://<your-name>.github.io/<repository>/` on your phone and choose
   "Add to Home Screen" (iPhone: Safari; Android: Chrome).

## Daily notification (optional)
1. Install the ntfy app and subscribe to a long, unguessable topic name.
2. Repository Settings > Secrets and variables > Actions: add secret `NTFY_TOPIC` (that name)
   and variable `NEWS_APP_URL` (your app address). Delivery hour: variable `NTFY_HOUR` (UTC, default 6)
   is read from the environment in `collector.py`; add it to the workflow's `env` block to change it.

## Customising
Sources (including the India category), categories and conflict keywords are the lists at the top of `collector.py`.
Test locally: `python collector.py && python -m http.server` and open http://localhost:8000.
Note: free GitHub Pages repositories are public, so `news.json` is public as well.
