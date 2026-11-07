# Setup

## 1. Details still to add (optional, any time)

Name, role, intro, LinkedIn, Gmail and Telegram are already filled in. These are kept in
`README.md` inside HTML comments (`<!-- … -->`), so they don't show yet:

| Placeholder | What to put |
|---|---|
| `YOUR_PORTFOLIO_URL` | Full URL incl. `https://` once the site is live |
| `YOUR_WHATSAPP_NUMBER` | International format, digits only (e.g. `8801XXXXXXXXX`) |
| `YOUR_LEETCODE_HANDLE`, `YOUR_CODEFORCES_HANDLE`, `YOUR_CODECHEF_HANDLE`, `YOUR_ATCODER_HANDLE`, `YOUR_HACKERRANK_HANDLE`, `YOUR_TOPH_HANDLE` | Your handle on each site |
| `YOUR_BEECROWD_USER_ID` | The number in your Beecrowd profile URL |

Fill in the value, delete any badge you don't need, then remove the surrounding `<!--` and `-->` lines.
Your GitHub username is **not** needed anywhere: the workflow uses the repository owner automatically.

## 2. Push to your profile repository

The repository must be named exactly like your GitHub username (`USERNAME/USERNAME`) and be public.

```bash
git clone https://github.com/USERNAME/USERNAME.git
# copy README.md, SETUP.md, assets/, stats/, scripts/, .github/ into it
cd USERNAME
git add .
git commit -m "Add profile README"
git push
```

## 3. Allow the workflow to commit

Repository → **Settings → Actions → General → Workflow permissions** → choose **Read and write permissions** → Save.
(The workflow itself asks only for `contents: write`.)

## 4. Run it once

**Actions** tab → **Update GitHub stats** → **Run workflow**. After about a minute the five cards in `stats/` replace the "Waiting for the first update" placeholders. From then on it runs daily at 00:17 UTC and commits only when a card actually changed.

## Optional: include private contributions

With the built-in token the cards use **public** data only. To also count private contributions:

1. On GitHub: **Settings → Public profile → Contributions & activity → Include private contributions on my profile**.
2. Create a token: **Settings → Developer settings → Personal access tokens → Tokens (classic)** with only the `read:user` scope and an expiry date you'll remember to renew.
3. In the profile repo: **Settings → Secrets and variables → Actions → New repository secret**, name `STATS_TOKEN`, paste the token.

Private contributions only add to the counts (calendar, streak, activity, commits). Stars, repositories and languages are always computed from your **public, non-fork** repositories.

## How it works and limitations

- `scripts/generate_stats.py` (Python standard library only) reads the GitHub GraphQL API and writes static SVGs. No third-party stats service is involved, so there are no shared rate limits or outages to worry about.
- Cards refresh **once a day**, not instantly after each push. Run the workflow manually for an immediate update.
- Dates follow GitHub's contribution calendar. A day with no contributions *yet* today does not break the current streak.
- GitHub pauses scheduled workflows in a public repo after 60 days without repository activity. If that happens, re-enable it from the Actions tab.
- Icons come from skillicons.dev and badges from shields.io, so those images depend on those services being up. The SQL icon is a local file because skillicons has no generic SQL icon.
- Preview the card design locally with fake data: `python scripts/generate_stats.py --demo --out preview` (don't commit `preview/`).
