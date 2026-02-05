from collections.abc import Callable

import click
from rich.console import Console
from rich.prompt import Prompt

from gustav.settings import (
    SETTINGS_FILE,
    anthropic_key_exists,
    github_token_exists,
    save_anthropic_key,
    save_github_token,
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
    """Initialize gustav"""
    console.print("[bold]Initializing Gustav[/bold]")
    prompt_for_secret("Anthropic API key", anthropic_key_exists(), save_anthropic_key)
    prompt_for_secret("GitHub token", github_token_exists(), save_github_token)
