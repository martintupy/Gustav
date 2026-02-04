from collections.abc import Callable

import click
from rich.console import Console
from rich.prompt import Prompt

from gustav.settings import (
    SETTINGS_FILE,
    anthropic_key_exists,
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
    """Initialize gustav configuration"""
    if settings_exist():
        overwrite = Prompt.ask(
            f"[yellow]Settings already exist at {SETTINGS_FILE}. Overwrite?[/yellow]",
            choices=["y", "n"],
            default="n",
        )
        if overwrite != "y":
            console.print("[dim]Aborted.[/dim]")
            return

    console.print("[bold]Setting up gustav configuration[/bold]\n")

    prompt_for_secret("Anthropic API key", anthropic_key_exists(), save_anthropic_key)

    console.print("\n[dim]GitHub token requires scopes: repo, read:org[/dim]")
    prompt_for_secret("GitHub token", github_token_exists(), save_github_token)

    console.print("\n[dim]Enter GitHub organizations to track (empty line to finish):[/dim]")
    orgs: list[str] = []
    while True:
        org = Prompt.ask("  Organization", default="")
        if not org:
            break
        orgs.append(org)

    save_config_file(orgs)
    console.print(f"\n[green]Settings saved to {SETTINGS_FILE}[/green]")
