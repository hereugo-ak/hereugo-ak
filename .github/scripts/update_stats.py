#!/usr/bin/env python3
"""Refresh the profile README's contribution statistics from GitHub GraphQL."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

README = Path(__file__).resolve().parents[2] / "README.md"
GRAPHQL_URL = "https://api.github.com/graphql"
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
    }
  }
}
"""


def github_contributions(login: str, start: datetime, end: datetime) -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")

    payload = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "login": login,
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": end.isoformat().replace("+00:00", "Z"),
            },
        }
    ).encode("utf-8")
    request = Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "hereugo-ak-profile-stats",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        body = json.load(response)

    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"], separators=(",", ":")))

    try:
        return int(
            body["data"]["user"]["contributionsCollection"]
            ["contributionCalendar"]["totalContributions"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Unexpected GitHub response: {body}") from exc


def github_followers(login: str) -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")

    request = Request(
        f"https://api.github.com/users/{login}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hereugo-ak-profile-stats",
        },
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        body = json.load(response)

    try:
        return int(body["followers"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Unexpected GitHub profile response: {body}") from exc


def build_stats_block(rolling: int, year_total: int, year: int, updated: str) -> str:
    return f"""<!-- STATS:START -->
<table>
<tr>
<td align=\"center\" width=\"50%\">
<h2>{rolling}</h2>
<sub><b>CONTRIBUTIONS IN THE LAST YEAR</b></sub><br>
<sub>GitHub's rolling 12-month count</sub>
</td>
<td align=\"center\" width=\"50%\">
<h2>{year_total}</h2>
<sub><b>CONTRIBUTIONS IN {year}</b></sub><br>
<sub>live calendar total · updated {updated}</sub>
</td>
</tr>
</table>
<!-- STATS:END -->"""


def main() -> None:
    login = os.environ.get("GITHUB_USERNAME", "hereugo-ak")
    now = datetime.now(timezone.utc)
    rolling = github_contributions(login, now - timedelta(days=365), now)
    year_total = github_contributions(login, datetime(now.year, 1, 1, tzinfo=timezone.utc), now)
    month_total = github_contributions(login, datetime(now.year, now.month, 1, tzinfo=timezone.utc), now)
    followers = github_followers(login)
    updated_date = now.strftime("%Y-%m-%d")
    block = build_stats_block(rolling, year_total, now.year, updated_date)

    text = README.read_text(encoding="utf-8")
    pattern = r"<!-- STATS:START -->.*?<!-- STATS:END -->"
    updated, replacements = re.subn(pattern, block, text, count=1, flags=re.DOTALL)
    if replacements != 1:
        raise RuntimeError("README.md must contain exactly one STATS:START/STATS:END block")

    replacements = {
        "__FOLLOWERS__": str(followers),
        "__ROLLING_CONTRIBUTIONS__": str(rolling),
        "__YEAR_CONTRIBUTIONS__": str(year_total),
        "__MONTH_CONTRIBUTIONS__": str(month_total),
        "__YEAR__": str(now.year),
        "__MONTH_NAME__": now.strftime("%B").upper(),
        "__UPDATED_DATE__": updated_date,
    }
    for placeholder, value in replacements.items():
        updated = updated.replace(placeholder, value)

    if updated == text:
        print("Stats are already current")
        return

    README.write_text(updated, encoding="utf-8")
    print(
        f"Updated {README}: followers={followers}, rolling={rolling}, "
        f"year={year_total}, month={month_total}"
    )


if __name__ == "__main__":
    main()

