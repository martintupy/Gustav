import click
import httpx
import keyring
from rich.console import Console
from rich.table import Table

from ghai.settings import (
    APP_NAME,
    KEYRING_ANTHROPIC_KEY,
    KEYRING_GITHUB_TOKEN,
    SETTINGS_FILE,
    anthropic_key_exists,
    get_git_config,
    github_token_exists,
    settings_exist,
)

console = Console()


def test_anthropic_api() -> str:
    api_key = keyring.get_password(APP_NAME, KEYRING_ANTHROPIC_KEY)
    if not api_key:
        return "[dim]Skipped (no key)[/dim]"
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            },
            timeout=10,
        )
        if response.status_code == 200:
            return "[green]OK[/green]"
        return f"[red]Error {response.status_code}[/red]"
    except httpx.RequestError as e:
        return f"[red]{e}[/red]"


def test_github_api() -> str:
    token = keyring.get_password(APP_NAME, KEYRING_GITHUB_TOKEN)
    if not token:
        return "[dim]Skipped (no token)[/dim]"
    try:
        response = httpx.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        if response.status_code == 200:
            username = response.json().get("login", "unknown")
            return f"[green]OK[/green] ({username})"
        return f"[red]Error {response.status_code}[/red]"
    except httpx.RequestError as e:
        return f"[red]{e}[/red]"


@click.command()
@click.option("--test", is_flag=True, help="Test API connections")
def status(test: bool):
    """Show configuration status"""
    table = Table(title="ghai Configuration Status", show_header=False)
    table.add_column("Key", style="dim")
    table.add_column("Value")

    table.add_row("Config file", str(SETTINGS_FILE))
    table.add_row("Config exists", "[green]Yes[/green]" if settings_exist() else "[red]No[/red]")
    table.add_row("Anthropic API key", "[green]Set[/green]" if anthropic_key_exists() else "[red]Not set[/red]")
    table.add_row("GitHub token", "[green]Set[/green]" if github_token_exists() else "[red]Not set[/red]")
    table.add_row("Git user.email", get_git_config("user.email") or "[dim]Not set[/dim]")
    table.add_row("Git user.name", get_git_config("user.name") or "[dim]Not set[/dim]")

    if test:
        table.add_row("Anthropic API", test_anthropic_api())
        table.add_row("GitHub API", test_github_api())

    console.print(table)

    if settings_exist():
        import yaml

        with open(SETTINGS_FILE) as f:
            data = yaml.safe_load(f) or {}

        console.print()
        emails = data.get("emails", [])
        if emails:
            console.print(f"[bold]Emails:[/bold] {', '.join(emails)}")
        else:
            console.print("[bold]Emails:[/bold] [red]None configured[/red]")

        repos = data.get("repos", [])
        if repos:
            console.print(f"[bold]Repos:[/bold] {', '.join(repos)}")
        else:
            console.print("[bold]Repos:[/bold] [dim]None configured[/dim]")
