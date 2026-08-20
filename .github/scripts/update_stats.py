#!/usr/bin/env python3
"""Refresh contribution metrics from the authenticated GitHub profile calendar.

The profile calendar can include private or restricted contributions that the
repository's default GITHUB_TOKEN cannot see. The workflow therefore requires
GITHUB_PROFILE_TOKEN; without it, the updater exits safely without changing the
README.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

README = Path(__file__).resolve().parents[2] / "README.md"
GRAPHQL_URL = "https://api.github.com/graphql"
QUERY = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
    }
  }
}
"""


def authenticated_year_total(start: datetime, end: datetime) -> int:
    token = os.environ.get("GITHUB_PROFILE_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_PROFILE_TOKEN is required")

    payload = json.dumps(
        {
            "query": QUERY,
            "variables": {
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
            body["data"]["viewer"]["contributionsCollection"]
            ["contributionCalendar"]["totalContributions"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Unexpected GitHub response: {body}") from exc


def build_stats_block(year_total: int, year: int, updated: str) -> str:
    return f"""<!-- STATS:START -->
<table>
<tr>
<td align=\"center\" width=\"50%\">
<h2>{year_total}</h2>
<sub><b>CONTRIBUTIONS IN {year}</b></sub><br>
<sub>GitHub native calendar · updated {updated}</sub>
</td>
<td align=\"center\" width=\"50%\">
<h2>7</h2>
<sub><b>PUBLIC REPOSITORIES</b></sub><br>
<sub>owner-visible public repository count</sub>
</td>
</tr>
</table>
<!-- STATS:END -->"""


def main() -> None:
    token = os.environ.get("GITHUB_PROFILE_TOKEN")
    if not token:
        print("GITHUB_PROFILE_TOKEN is not configured; leaving README unchanged")
        return

    now = datetime.now(timezone.utc)
    year_total = authenticated_year_total(
        datetime(now.year, 1, 1, tzinfo=timezone.utc), now
    )
    updated_date = now.strftime("%Y-%m-%d")
    block = build_stats_block(year_total, now.year, updated_date)
    text = README.read_text(encoding="utf-8")

    updated, replacements = re.subn(
        r"<!-- STATS:START -->.*?<!-- STATS:END -->",
        block,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if replacements != 1:
        raise RuntimeError("README.md must contain exactly one STATS:START/STATS:END block")

    updated = re.sub(
        r"(badge/Contributions-)\d+(-2ea043)",
        rf"\g<1>{year_total}\g<2>",
        updated,
        count=1,
    )
    updated = re.sub(
        r"(?<=;)(?:\d+)\+contributions\+in\+[^;]+",
        f"{year_total}+contributions+in+{now.year}",
        updated,
        count=1,
    )
    updated = re.sub(
        r"\*\*\d+ contributions in [^*]+\.\*\*",
        f"**{year_total} contributions in {now.year}.**",
        updated,
        count=1,
    )
    updated = re.sub(
        r"(<h3>)\d+(</h3>\n<sub><b>CONTRIBUTIONS IN \d+</b>)",
        rf"\g<1>{year_total}\g<2>",
        updated,
        count=1,
    )

    if updated == text:
        print("Stats are already current")
        return

    README.write_text(updated, encoding="utf-8")
    print(f"Updated {README} with {year_total} authenticated contributions in {now.year}")


if __name__ == "__main__":
    main()
