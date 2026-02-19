import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from gustav.cache import get_cached, set_cached
from gustav.clients.claude import ClaudeClient
from gustav.clients.github import GitHubClient
from gustav.prompts.loader import load_prompt
from gustav.settings import DATA_DIR, Settings

console = Console()

PANEL_TITLE = "Report"


def build_loading_panel(status: str) -> Panel:
    content = Group(Spinner("dots", text=f" {status}", style="bold blue"))
    return Panel(content, title=PANEL_TITLE, border_style="cyan")


def get_day_cache_key(day: str, username: str) -> str:
    return f"report_{username}_{day}"


def get_cached_day(day: str, username: str) -> dict | None:
    return get_cached(get_day_cache_key(day, username))


def cache_day(day: str, username: str, activity: list[str], summary: str) -> None:
    set_cached(get_day_cache_key(day, username), {"activity": activity, "summary": summary})


def generate_summary(claude: ClaudeClient, activity: list[str]) -> str:
    activity_text = "\n".join(f"- {a}" for a in activity)
    prompt = load_prompt("report_summary", commits=activity_text)
    return claude.ask(prompt, "report_summary")


def save_raw_data(username: str, raw_data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / f"report_{username}.json"
    output_path.write_text(json.dumps(raw_data, indent=2))
    console.print(f"[dim]Raw data saved to {output_path}[/dim]")


@click.command()
@click.option("--days", "-d", default=7, help="Number of days to include in the report")
@click.option("--csv", "csv_path", default=None, type=click.Path(), help="Export report to CSV file")
@click.pass_obj
def report(settings: Settings, days: int, csv_path: str | None):
    """Generate a daily work report from GitHub activity"""
    claude = ClaudeClient(settings.anthropic)
    github = GitHubClient(settings.github)

    username = github.get_authenticated_user()
    console.print(f"[dim]Fetching activity for {username}...[/dim]")

    today = datetime.now().strftime("%Y-%m-%d")
    target_days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

    cached_results: dict[str, dict] = {}
    days_to_fetch: list[str] = []

    for day in target_days:
        if day == today:
            days_to_fetch.append(day)
        else:
            cached = get_cached_day(day, username)
            if cached:
                cached_results[day] = cached
            else:
                days_to_fetch.append(day)

    activity_by_day: dict[str, list[str]] = {}

    if days_to_fetch:
        earliest_day = min(days_to_fetch)
        since = datetime.strptime(earliest_day, "%Y-%m-%d")
        orgs = github.get_user_orgs()
        fetched, raw_data = github.fetch_activity_by_day(username, orgs, since)
        for day in days_to_fetch:
            if day in fetched:
                activity_by_day[day] = fetched[day]
        save_raw_data(username, raw_data)

    all_days = sorted(set(cached_results.keys()) | set(activity_by_day.keys()), reverse=True)

    if not all_days:
        console.print(f"[yellow]No activity found in the last {days} days.[/yellow]")
        return

    rows: list[tuple[str, str, str]] = []

    for day in all_days:
        day_dt = datetime.strptime(day, "%Y-%m-%d")
        day_name = day_dt.strftime("%A")

        if day in cached_results:
            summary = cached_results[day]["summary"]
        else:
            activity = activity_by_day.get(day, [])
            if not activity:
                continue

            with Live(
                build_loading_panel(f"Summarizing {day}..."), console=console, refresh_per_second=10, transient=True
            ):
                summary = generate_summary(claude, activity)

            cache_day(day, username, activity, summary)

        rows.append((day, day_name, summary))

    if csv_path:
        output = Path(csv_path)
        with output.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Day", "Summary"])
            writer.writerows(rows)
        console.print(f"[dim]Report exported to {output}[/dim]")
    else:
        table = Table(title=f"Work Report (last {days} days)", show_header=True, header_style="bold cyan")
        table.add_column("Date", style="bold")
        table.add_column("Summary")
        for day, day_name, summary in rows:
            table.add_row(f"{day} ({day_name})", summary)
        console.print(table)
