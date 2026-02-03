import click
from prompt_toolkit import prompt as pt_prompt
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner

from ghai.cache import get_cache_key, get_cached, set_cached
from ghai.clients.claude import ClaudeClient
from ghai.clients.git import GitClient
from ghai.prompts.loader import load_prompt
from ghai.settings import Settings

console = Console()

PANEL_TITLE = "Commit Message"


def build_loading_panel(status: str) -> Panel:
    content = Group(Spinner("dots", text=f" {status}", style="bold blue"))
    return Panel(content, title=PANEL_TITLE, border_style="cyan")


def build_commit_prompt(diff_stat: str, diff: str, files_content: str) -> str:
    return load_prompt("commit_message", diff_stat=diff_stat, diff=diff, files_content=files_content)


def generate_commit_message_cached(claude: ClaudeClient, diff_stat: str, diff: str, files_content: str) -> str:
    cache_key = get_cache_key("commit", diff_stat, diff)
    cached = get_cached(cache_key)

    if cached:
        console.print("[dim]Using cached result...[/dim]")
        return cached["message"]

    prompt = build_commit_prompt(diff_stat, diff, files_content)
    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

    with Live(build_loading_panel("Generating..."), console=console, refresh_per_second=10, transient=True):
        commit_msg = claude.chat(messages, max_tokens=256)

    set_cached(cache_key, {"message": commit_msg})
    return commit_msg


def collect_files_content(git: GitClient, files: list[str]) -> str:
    content_parts = []
    for file in files:
        file_content = git.get_file_content_from_index(file)
        if file_content is not None:
            content_parts.append(f'<file path="{file}">\n{file_content}\n</file>')
    return "\n\n".join(content_parts)


@click.command()
@click.option("--push", "-p", is_flag=True, help="Push after committing")
@click.pass_obj
def commit(settings: Settings, push: bool):
    """Generate commit message and commit staged changes"""
    claude = ClaudeClient(settings.anthropic)
    git = GitClient()

    staged_files = git.get_staged_files()

    if not staged_files:
        console.print("[yellow]No staged changes. Stage files with 'git add' first.[/yellow]")
        return

    diff_stat = git.get_staged_diff_stat()
    diff = git.get_staged_diff()
    files_content = collect_files_content(git, staged_files)

    commit_msg = generate_commit_message_cached(claude, diff_stat, diff, files_content)

    prompt = build_commit_prompt(diff_stat, diff, files_content)
    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

    while True:
        console.print(Panel(commit_msg, title=PANEL_TITLE, border_style="cyan"))
        console.print("[dim](y) confirm  (n) cancel  (e) edit  (r) refine[/dim]")

        choice = Prompt.ask("Confirm?", choices=["y", "n", "e", "r"], default="y")

        if choice == "y":
            break
        elif choice == "n":
            console.print("[dim]Cancelled.[/dim]")
            return
        elif choice == "e":
            edited_msg = pt_prompt("Edit message: ", default=commit_msg)
            if edited_msg:
                commit_msg = edited_msg.strip()
            break
        elif choice == "r":
            feedback = Prompt.ask("[dim]How should I change it?[/dim]")
            if not feedback:
                continue
            messages.append({"role": "assistant", "content": commit_msg})
            messages.append({"role": "user", "content": feedback})
            with Live(build_loading_panel("Refining..."), console=console, refresh_per_second=10, transient=True):
                commit_msg = claude.chat(messages, max_tokens=256)

    git.commit(commit_msg)
    console.print("[green]Committed.[/green]")

    if push:
        branch = git.get_current_branch()
        with console.status(f"[bold blue]Pushing '{branch}'..."):
            git.push(branch)
        console.print(f"[green]Pushed '{branch}'.[/green]")
