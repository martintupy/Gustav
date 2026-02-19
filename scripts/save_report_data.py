#!/usr/bin/env python3
"""
Standalone script to fetch GitHub activity and save raw data to disk.

Usage:
    python scripts/save_report_data.py [--days N]
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gustav.clients.github import GitHubClient
from gustav.settings import DATA_DIR, load_settings


def save_raw_data(username: str, raw_data: dict) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / f"report_{username}.json"
    output_path.write_text(json.dumps(raw_data, indent=2))
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch GitHub activity and save raw data")
    parser.add_argument("--days", "-d", type=int, default=7, help="Number of days to fetch (default: 7)")
    args = parser.parse_args()

    settings = load_settings()
    github = GitHubClient(settings.github)

    username = github.get_authenticated_user()
    print(f"Fetching activity for {username} (last {args.days} days)...")

    since = datetime.now() - timedelta(days=args.days)
    orgs = github.get_user_orgs()
    _, raw_data = github.fetch_activity_by_day(username, orgs, since)

    output_path = save_raw_data(username, raw_data)
    print(f"Raw data saved to {output_path}")


if __name__ == "__main__":
    main()
