from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table

from ghai.clients.claude import ClaudeClient
from ghai.clients.github import GitHubClient
from ghai.prompts.loader import load_prompt
from ghai.settings import Settings

console = Console()


@click.command()
@click.pass_obj
def report(settings: Settings):
    """Generate a daily work report from GitHub commits"""
    claude = ClaudeClient(settings.anthropic)
    github = GitHubClient(settings.github)
    since = datetime.now() - timedelta(days=7)

    commits_by_day = github.fetch_commits_by_day(settings.repos, settings.emails, since)

    if not commits_by_day:
        console.print("[yellow]No commits found in the last 7 days.[/yellow]")
        return

    sorted_days = sorted(commits_by_day.keys(), reverse=True)

    table = Table(title="Weekly Report (last 7 days)", show_header=True, header_style="bold cyan")
    table.add_column("Date", style="bold")
    table.add_column("Summary")

    with console.status("[bold blue]Generating summaries with Claude...") as status:
        for day in sorted_days:
            day_dt = datetime.strptime(day, "%Y-%m-%d")
            day_name = day_dt.strftime("%A")
            commits = commits_by_day[day]
            commits_text = "\n".join(f"- {c}" for c in commits)

            status.update(f"[bold blue]Summarizing {day}...")

            prompt = load_prompt("daily_summary", commits=commits_text)
            summary = claude.ask(prompt)
            table.add_row(f"{day} ({day_name})", summary)

    console.print()
    console.print(table)
    console.print()
