import click
from rich.console import Console

from gustav.cache import clear_cache
from gustav.settings import CACHE_DIR

console = Console()


@click.command()
@click.option("--clear", is_flag=True, help="Clear all cached data")
def cache(clear: bool):
    """Manage cached data"""
    if clear:
        clear_cache()
        console.print("[green]Cache cleared.[/green]")
        return

    if not CACHE_DIR.exists():
        console.print("[dim]Cache is empty.[/dim]")
        return

    cache_files = list(CACHE_DIR.glob("*.json"))
    if not cache_files:
        console.print("[dim]Cache is empty.[/dim]")
        return

    console.print(f"[dim]Cache location:[/dim] {CACHE_DIR}")
    console.print(f"[dim]Cached entries:[/dim] {len(cache_files)}")
