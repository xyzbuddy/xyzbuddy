#!/usr/bin/env python3
"""Generate static Blue & Black GitHub stats cards (SVG) for a profile README.

Uses only the Python standard library and the GitHub GraphQL API.

Outputs (in --out, default "stats/"):
  overview.svg   - stars, commits, PRs, issues, repos, contributions
  languages.svg  - most used languages (public, non-fork repos you own)
  streak.svg     - total contributions, current streak, longest streak
  activity.svg   - daily contributions over the last 31 days (line graph)
  calendar.svg   - contribution heatmap for the last year

Environment:
  GH_TOKEN  token used for the API (GITHUB_TOKEN in Actions is enough for
            public data; a PAT with read:user adds private contribution counts
            if "Private contributions" is enabled on your profile)
  GH_USER   GitHub username (Actions passes github.repository_owner)

Flags:
  --placeholder   write "waiting for first run" cards (no API calls)
  --demo          write cards from made-up sample data (local preview only)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"

# ---- Theme -----------------------------------------------------------------
BG = "#0D1117"
BORDER = "#1F2A44"
ACCENT = "#2563EB"
ACCENT_LIGHT = "#60A5FA"
TEXT = "#E6EDF3"
MUTED = "#8B949E"
GRID = "#1B2333"
HEAT = ["#161B22", "#0C2D6B", "#1E40AF", "#2563EB", "#60A5FA"]
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"


# ---- API -------------------------------------------------------------------
def gql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-stats",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
            if payload.get("errors"):
                raise RuntimeError(json.dumps(payload["errors"])[:500])
            return payload["data"]
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2:
                raise
            print(f"Request failed ({exc}); retrying...", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("unreachable")


USER_QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    login
    name
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      contributionYears
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 first: 100, after: $cursor) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch(token: str, login: str) -> dict:
    stars = 0
    langs: dict[str, dict] = {}
    cursor = None
    first = None
    while True:
        user = gql(token, USER_QUERY, {"login": login, "cursor": cursor})["user"]
        if user is None:
            raise RuntimeError(f"GitHub user '{login}' not found")
        first = first or user
        repos = user["repositories"]
        for repo in repos["nodes"]:
            stars += repo["stargazerCount"]
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                entry = langs.setdefault(
                    name, {"size": 0, "color": edge["node"]["color"] or ACCENT}
                )
                entry["size"] += edge["size"]
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]

    # All-time daily contributions and commit totals, one year at a time.
    days: dict[str, int] = {}
    commits = 0
    for year in sorted(first["contributionsCollection"]["contributionYears"]):
        coll = gql(
            token,
            YEAR_QUERY,
            {
                "login": login,
                "from": f"{year}-01-01T00:00:00Z",
                "to": f"{year}-12-31T23:59:59Z",
            },
        )["user"]["contributionsCollection"]
        commits += coll["totalCommitContributions"]
        for week in coll["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days[day["date"]] = day["contributionCount"]

    cal = first["contributionsCollection"]["contributionCalendar"]
    return {
        "login": first["login"],
        "name": first["name"] or first["login"],
        "stars": stars,
        "commits": commits,
        "prs": first["pullRequests"]["totalCount"],
        "issues": first["issues"]["totalCount"],
        "repos": first["repositories"]["totalCount"],
        "year_total": cal["totalContributions"],
        "calendar": [
            [(d["date"], d["contributionCount"]) for d in w["contributionDays"]]
            for w in cal["weeks"]
        ],
        "days": days,
        "languages": langs,
    }


def demo_data() -> dict:
    rnd = random.Random(7)
    today = dt.date.today()
    days = {}
    for i in range(500):
        d = today - dt.timedelta(days=i)
        days[d.isoformat()] = 0 if rnd.random() < 0.3 else rnd.randint(1, 14)
    for i in range(9):  # guarantee a visible current streak
        days[(today - dt.timedelta(days=i)).isoformat()] = rnd.randint(1, 9)
    start = today - dt.timedelta(days=364 + (today.weekday() + 1) % 7)
    calendar, week = [], []
    d = start
    while d <= today:
        week.append((d.isoformat(), days.get(d.isoformat(), 0)))
        if len(week) == 7:
            calendar.append(week)
            week = []
        d += dt.timedelta(days=1)
    if week:
        calendar.append(week)
    return {
        "login": "demo-user",
        "name": "Demo User",
        "stars": 42,
        "commits": 1234,
        "prs": 56,
        "issues": 18,
        "repos": 27,
        "year_total": sum(c for w in calendar for _, c in w),
        "calendar": calendar,
        "days": days,
        "languages": {
            "JavaScript": {"size": 420000, "color": "#f1e05a"},
            "Python": {"size": 310000, "color": "#3572A5"},
            "C++": {"size": 190000, "color": "#f34b7d"},
            "Java": {"size": 120000, "color": "#b07219"},
            "PHP": {"size": 80000, "color": "#4F5D95"},
            "CSS": {"size": 60000, "color": "#563d7c"},
            "HTML": {"size": 40000, "color": "#e34c26"},
            "Kotlin": {"size": 20000, "color": "#A97BFF"},
            "C": {"size": 9000, "color": "#555555"},
        },
    }


# ---- Helpers ---------------------------------------------------------------
def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return f"{n:,}"


def short_date(iso: str, with_year: bool = True) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}" if with_year else f"{d:%b} {d.day}"


def card(width: int, height: int, title: str, body: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">\n'
        f"<title>{escape(label)}</title>\n"
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{BG}" stroke="{BORDER}"/>\n'
        f'<rect x="25" y="22" width="4" height="18" rx="2" fill="{ACCENT}"/>\n'
        f'<text x="37" y="37" font-family="{FONT}" font-size="17" font-weight="600" '
        f'fill="{ACCENT_LIGHT}">{escape(title)}</text>\n'
        f"{body}\n</svg>\n"
    )


def t(x, y, s, size=13, fill=TEXT, weight=400, anchor="start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(str(s))}</text>'
    )


# ---- Streak math -----------------------------------------------------------
def streaks(days: dict[str, int]) -> dict:
    if not days:
        return {"total": 0, "cur": 0, "cur_range": None, "best": 0, "best_range": None,
                "first": None}
    dates = sorted(days)
    total = sum(days.values())
    first_active = next((d for d in dates if days[d] > 0), None)

    best = run = 0
    best_range = None
    run_start = None
    for d in dates:
        if days[d] > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > best:
                best, best_range = run, (run_start, d)
        else:
            run = 0

    # Current streak: counts back from the latest day; an empty "today"
    # does not break it (the day is not over yet).
    idx = len(dates) - 1
    if days[dates[idx]] == 0:
        idx -= 1
    cur = 0
    end = dates[idx] if idx >= 0 else None
    start = None
    while idx >= 0 and days[dates[idx]] > 0:
        cur += 1
        start = dates[idx]
        idx -= 1
    return {
        "total": total,
        "first": first_active,
        "cur": cur,
        "cur_range": (start, end) if cur else None,
        "best": best,
        "best_range": best_range,
    }


# ---- Cards -----------------------------------------------------------------
def overview_svg(data: dict) -> str:
    rows = [
        ("Total stars earned", data["stars"]),
        ("Total commits", data["commits"]),
        ("Pull requests", data["prs"]),
        ("Issues", data["issues"]),
        ("Public repositories", data["repos"]),
        ("Contributions (last year)", data["year_total"]),
    ]
    parts = []
    for i, (label, value) in enumerate(rows):
        y = 74 + i * 22
        parts.append(f'<circle cx="31" cy="{y - 4}" r="3" fill="{ACCENT}"/>')
        parts.append(t(44, y, label, 13, MUTED))
        parts.append(t(300, y, fmt(value), 13, TEXT, 600, "end"))
    # Contributions ring on the right
    cx, cy, r = 400, 115, 48
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{GRID}" stroke-width="8"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ACCENT}" stroke-width="8"/>')
    parts.append(t(cx, cy + 2, fmt(data["commits"]), 20, TEXT, 700, "middle"))
    parts.append(t(cx, cy + 20, "commits", 11, MUTED, 400, "middle"))
    title = f"{data['name']}'s GitHub Stats"
    return card(495, 210, title, "\n".join(parts),
                f"GitHub stats for {data['login']}: {data['stars']} stars, "
                f"{data['commits']} commits, {data['prs']} pull requests, "
                f"{data['issues']} issues, {data['repos']} public repositories")


def languages_svg(data: dict) -> str:
    langs = sorted(data["languages"].items(), key=lambda kv: kv[1]["size"], reverse=True)
    total = sum(v["size"] for _, v in langs) or 1
    top = langs[:8]
    parts = []
    if not top:
        parts.append(t(25, 110, "No language data in public repositories yet.", 13, MUTED))
    else:
        # stacked bar
        x, bar_w = 25.0, 445.0
        parts.append(f'<clipPath id="bar"><rect x="25" y="58" width="{bar_w}" height="10" rx="5"/></clipPath>')
        segs = []
        for name, v in top:
            w = bar_w * v["size"] / total
            segs.append(f'<rect x="{x:.2f}" y="58" width="{w:.2f}" height="10" fill="{v["color"]}"/>')
            x += w
        parts.append(f'<rect x="25" y="58" width="{bar_w}" height="10" rx="5" fill="{GRID}"/>')
        parts.append('<g clip-path="url(#bar)">' + "".join(segs) + "</g>")
        for i, (name, v) in enumerate(top):
            col, row = i % 2, i // 2
            x0, y0 = 25 + col * 230, 98 + row * 26
            pct = 100 * v["size"] / total
            parts.append(f'<circle cx="{x0 + 5}" cy="{y0 - 4}" r="5" fill="{v["color"]}"/>')
            parts.append(t(x0 + 17, y0, name, 13, TEXT))
            parts.append(t(x0 + 205, y0, f"{pct:.1f}%", 12, MUTED, 400, "end"))
    summary = ", ".join(f"{n} {100 * v['size'] / total:.1f}%" for n, v in top) or "none"
    return card(495, 210, "Most Used Languages", "\n".join(parts),
                f"Most used languages: {summary}")


def streak_svg(data: dict) -> str:
    s = streaks(data["days"])
    w, h = 990, 190
    cols = [165, 495, 825]
    parts = [
        f'<line x1="330" y1="65" x2="330" y2="165" stroke="{BORDER}"/>',
        f'<line x1="660" y1="65" x2="660" y2="165" stroke="{BORDER}"/>',
    ]
    first = short_date(s["first"]) + " – Present" if s["first"] else "No contributions yet"
    parts += [
        t(cols[0], 110, fmt(s["total"]), 30, TEXT, 700, "middle"),
        t(cols[0], 138, "Total Contributions", 14, ACCENT_LIGHT, 600, "middle"),
        t(cols[0], 160, first, 12, MUTED, 400, "middle"),
    ]
    # current streak with ring
    parts.append(f'<circle cx="{cols[1]}" cy="102" r="34" fill="none" stroke="{ACCENT}" stroke-width="5"/>')
    parts.append(t(cols[1], 112, s["cur"], 28, TEXT, 700, "middle"))
    parts.append(t(cols[1], 156, "Current Streak", 14, ACCENT_LIGHT, 600, "middle"))
    if s["cur_range"]:
        a, b = s["cur_range"]
        rng = short_date(a, False) if a == b else f"{short_date(a, False)} – {short_date(b, False)}"
    else:
        rng = "Start a streak today"
    parts.append(t(cols[1], 175, rng, 12, MUTED, 400, "middle"))
    parts += [
        t(cols[2], 110, s["best"], 30, TEXT, 700, "middle"),
        t(cols[2], 138, "Longest Streak", 14, ACCENT_LIGHT, 600, "middle"),
    ]
    if s["best_range"]:
        a, b = s["best_range"]
        parts.append(t(cols[2], 160, f"{short_date(a)} – {short_date(b)}", 12, MUTED, 400, "middle"))
    unit = "day" if s["cur"] == 1 else "days"
    return card(w, h, "Contribution Streak", "\n".join(parts),
                f"Total contributions {s['total']}, current streak {s['cur']} {unit}, "
                f"longest streak {s['best']} days")


def activity_svg(data: dict) -> str:
    days = data["days"]
    last = max(days) if days else dt.date.today().isoformat()
    end = dt.date.fromisoformat(last)
    series = [((end - dt.timedelta(days=30 - i)).isoformat()) for i in range(31)]
    vals = [days.get(d, 0) for d in series]
    w, h = 990, 320
    left, right, top, bottom = 60, 960, 70, 270
    vmax = max(max(vals), 4)
    step = max(1, -(-vmax // 4))  # ceil(vmax/4)
    vmax = step * 4
    sx = lambda i: left + (right - left) * i / 30
    sy = lambda v: bottom - (bottom - top) * v / vmax
    parts = []
    for k in range(5):
        y = sy(step * k)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(t(left - 10, y + 4, step * k, 11, MUTED, 400, "end"))
    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
    area = f"{left},{bottom} {pts} {right},{bottom}"
    parts.append(f'<polygon points="{area}" fill="{ACCENT}" fill-opacity="0.18"/>')
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="2.5" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
    for i, v in enumerate(vals):
        parts.append(f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="3.5" fill="{BG}" '
                     f'stroke="{ACCENT_LIGHT}" stroke-width="2"/>')
        if i % 5 == 0 or i == 30:
            parts.append(t(sx(i), bottom + 20, short_date(series[i], False), 11, MUTED, 400, "middle"))
    parts.append(t(right, 37, f"{sum(vals)} contributions in the last 31 days", 12, MUTED, 400, "end"))
    return card(w, h, "Contribution Activity", "\n".join(parts),
                f"Line graph of daily contributions from {series[0]} to {series[-1]}, "
                f"{sum(vals)} in total")


def calendar_svg(data: dict) -> str:
    weeks = data["calendar"][-53:]
    counts = sorted(c for w in weeks for _, c in w if c > 0)

    def level(c: int) -> int:
        if c == 0 or not counts:
            return 0
        q = [counts[int(len(counts) * p) - 1] if int(len(counts) * p) else counts[0]
             for p in (0.25, 0.5, 0.75)]
        return 1 + sum(c > x for x in q)

    cell, gap = 13.5, 3.5
    left, top = 60, 78
    w, h = 990, 250
    parts = []
    last_month = None
    for wi, week in enumerate(weeks):
        x = left + wi * (cell + gap)
        for date, c in week:
            wd = (dt.date.fromisoformat(date).weekday() + 1) % 7  # Sunday = 0
            y = top + wd * (cell + gap)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" '
                         f'fill="{HEAT[level(c)]}"><title>{c} on {date}</title></rect>')
        month = dt.date.fromisoformat(week[0][0]).strftime("%b")
        if month != last_month and wi < len(weeks) - 2:
            parts.append(t(x, top - 10, month, 11, MUTED))
            last_month = month
    for wd, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        parts.append(t(left - 10, top + wd * (cell + gap) + 11, name, 11, MUTED, 400, "end"))
    right_edge = left + 53 * (cell + gap) - gap
    lx = right_edge - 5 * (cell + gap) - 32
    ly = top + 7 * (cell + gap) + 12
    parts.append(t(lx - 8, ly + 11, "Less", 11, MUTED, 400, "end"))
    for i, colour in enumerate(HEAT):
        parts.append(f'<rect x="{lx + i * (cell + gap):.1f}" y="{ly}" width="{cell}" height="{cell}" '
                     f'rx="3" fill="{colour}"/>')
    parts.append(t(lx + 5 * (cell + gap) + 4, ly + 11, "More", 11, MUTED))
    parts.append(t(left, ly + 11, f"{fmt(data['year_total'])} contributions in the last year",
                   12, MUTED))
    return card(w, h, "Contribution Calendar", "\n".join(parts),
                f"Contribution heatmap: {data['year_total']} contributions in the last year")


def placeholder_svg(width: int, height: int, title: str) -> str:
    body = "\n".join([
        t(width / 2, height / 2 + 8, "Waiting for the first update", 15, TEXT, 600, "middle"),
        t(width / 2, height / 2 + 30,
          "Run the “Update GitHub stats” workflow in the Actions tab.", 12, MUTED, 400, "middle"),
    ])
    return card(width, height, title, body, f"{title}: not generated yet")


CARDS = {
    "overview.svg": (overview_svg, 495, 210, "GitHub Stats"),
    "languages.svg": (languages_svg, 495, 210, "Most Used Languages"),
    "streak.svg": (streak_svg, 990, 190, "Contribution Streak"),
    "activity.svg": (activity_svg, 990, 320, "Contribution Activity"),
    "calendar.svg": (calendar_svg, 990, 250, "Contribution Calendar"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="stats")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--placeholder", action="store_true")
    mode.add_argument("--demo", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    if args.placeholder:
        rendered = {f: placeholder_svg(w, h, title) for f, (_, w, h, title) in CARDS.items()}
    else:
        if args.demo:
            data = demo_data()
        else:
            token = os.environ.get("GH_TOKEN", "").strip()
            login = os.environ.get("GH_USER", "").strip()
            if not token or not login:
                print("GH_TOKEN and GH_USER must be set", file=sys.stderr)
                return 2
            data = fetch(token, login)
        rendered = {f: fn(data) for f, (fn, *_rest) in CARDS.items()}

    for name, svg in rendered.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        print(f"wrote {os.path.join(args.out, name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
