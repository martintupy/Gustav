import click
import httpx
import keyring
from loguru import logger
from rich.console import Console
from rich.table import Table

from gustav.settings import (
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
        org_name = None
        try:
            logger.debug("Fetching Anthropic organization info")
            org_response = httpx.get(
                "https://api.anthropic.com/v1/organizations/me",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10,
            )
            logger.debug(f"Anthropic organization endpoint status: {org_response.status_code}")
            if org_response.status_code == 200:
                org_data = org_response.json()
                org_name = org_data.get("name")
                logger.debug(f"Anthropic organization name: {org_name}")
            elif org_response.status_code == 401:
                logger.debug(
                    "Anthropic organization endpoint requires admin API key (regular API keys cannot access organization info)"
                )
            else:
                logger.debug(f"Anthropic organization endpoint error: {org_response.text}")
        except Exception as e:
            logger.debug(f"Anthropic organization endpoint exception: {e}")

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
            org_id = response.headers.get("anthropic-organization-id")
            if org_name:
                return f"[green]OK[/green] ({org_name})"
            elif org_id:
                logger.debug(f"Anthropic organization ID: {org_id}")
                return f"[green]OK[/green] ({org_id})"
            return "[green]OK[/green]"
        return f"[red]Error {response.status_code}[/red]"
    except httpx.RequestError as e:
        return f"[red]{e}[/red]"


def test_github_api() -> tuple[str, str]:
    token = keyring.get_password(APP_NAME, KEYRING_GITHUB_TOKEN)
    if not token:
        return "[dim]Skipped (no token)[/dim]", ""
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
            scopes_header = response.headers.get("X-OAuth-Scopes", "")
            scopes = [s.strip() for s in scopes_header.split(",")] if scopes_header else []
            return f"[green]OK[/green] ({username})", scopes
        return f"[red]Error {response.status_code}[/red]", ""
    except httpx.RequestError as e:
        return f"[red]{e}[/red]", ""


def check_github_permissions(scopes: list[str]) -> str:
    required = {"repo", "read:org"}
    missing = required - set(scopes)
    if not missing:
        return f"[green]OK[/green] ({', '.join(required)})"
    missing_str = ", ".join(sorted(missing))
    return f"[red]Missing: {missing_str}[/red]"


@click.command()
def status():
    """Show configuration status"""
    table = Table(show_header=False)
    table.add_column("Key", style="dim")
    table.add_column("Value")

    config_status = "[green]OK[/green]" if settings_exist() else "[red]Not found[/red]"
    table.add_row("Config", f"{config_status} ({SETTINGS_FILE})")
    table.add_row("Anthropic API", test_anthropic_api())
    github_status, scopes = test_github_api()
    table.add_row("GitHub API", github_status)
    if scopes:
        table.add_row("GitHub Permissions", check_github_permissions(scopes))
    table.add_row("Git user.email", get_git_config("user.email") or "[dim]Not set[/dim]")
    table.add_row("Git user.name", get_git_config("user.name") or "[dim]Not set[/dim]")

    console.print(table)
