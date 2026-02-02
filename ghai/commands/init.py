from collections.abc import Callable

import click
from rich.console import Console
from rich.prompt import Prompt

from ghai.settings import (
    SETTINGS_FILE,
    anthropic_key_exists,
    get_git_config,
    github_token_exists,
    save_anthropic_key,
    save_config_file,
    save_github_token,
    settings_exist,
)

console = Console()


def prompt_for_secret(name: str, exists: bool, save_fn: Callable[[str], None]) -> None:
    if exists:
        update = Prompt.ask(
            f"[dim]{name} already configured. Update?[/dim]",
            choices=["y", "n"],
            default="n",
        )
        if update != "y":
            return
        value = Prompt.ask(f"[dim]{name}[/dim]", password=True)
    else:
        value = Prompt.ask(f"[dim]{name}[/dim]", password=True)
        if not value:
            raise click.ClickException(f"{name} is required.")
    save_fn(value)
    console.print(f"[green]{name} saved to system keychain.[/green]")


@click.command()
def init():
    """Initialize ghai configuration"""
    if settings_exist():
        overwrite = Prompt.ask(
            f"[yellow]Settings already exist at {SETTINGS_FILE}. Overwrite?[/yellow]",
            choices=["y", "n"],
            default="n",
        )
        if overwrite != "y":
            console.print("[dim]Aborted.[/dim]")
            return

    console.print("[bold]Setting up ghai configuration[/bold]\n")

    prompt_for_secret("Anthropic API key", anthropic_key_exists(), save_anthropic_key)
    prompt_for_secret("GitHub token", github_token_exists(), save_github_token)

    git_email = get_git_config("user.email")
    console.print("\n[dim]Enter your git email addresses (one per line, empty line to finish):[/dim]")
    emails = []
    while True:
        default = git_email if not emails and git_email else ""
        email = Prompt.ask("  Email", default=default)
        if not email:
            break
        emails.append(email)
        git_email = None

    if not emails:
        raise click.ClickException("At least one email is required.")

    console.print("\n[dim]Enter GitHub repos to track (format: owner/repo, empty line to finish):[/dim]")
    repos = []
    while True:
        repo = Prompt.ask("  Repo", default="")
        if not repo:
            break
        if "/" not in repo:
            console.print("[red]Invalid format. Use 'owner/repo'.[/red]")
            continue
        repos.append(repo)

    save_config_file(emails, repos)
    console.print(f"\n[green]Settings saved to {SETTINGS_FILE}[/green]")
