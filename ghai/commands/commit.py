import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ghai.clients.claude import ClaudeClient
from ghai.clients.git import GitClient
from ghai.prompts.loader import load_prompt
from ghai.settings import Settings

console = Console()


def build_commit_prompt(diff_stat: str, diff: str, files_content: str) -> str:
    return load_prompt("commit_message", diff_stat=diff_stat, diff=diff, files_content=files_content)


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

    prompt = build_commit_prompt(diff_stat, diff, files_content)
    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

    with console.status("[bold blue]Generating commit message..."):
        commit_msg = claude.chat(messages, max_tokens=256)

    while True:
        console.print()
        console.print(Panel(commit_msg, title="Commit Message", border_style="cyan"))
        console.print()
        console.print("[dim](y) accept  (n) cancel  (e) edit manually  (r) refine with feedback[/dim]")

        choice = Prompt.ask("Commit?", choices=["y", "n", "e", "r"], default="y")

        if choice == "y":
            break
        elif choice == "n":
            console.print("[dim]Cancelled.[/dim]")
            return
        elif choice == "e":
            edited_msg = click.edit(commit_msg, extension=".txt")
            if edited_msg is None:
                console.print("[yellow]Editor returned no changes. Use 'r' to refine with feedback instead.[/yellow]")
                continue
            commit_msg = edited_msg.strip()
            break
        elif choice == "r":
            feedback = Prompt.ask("[dim]How should I change it?[/dim]")
            if not feedback:
                continue
            messages.append({"role": "assistant", "content": commit_msg})
            messages.append({"role": "user", "content": feedback})
            with console.status("[bold blue]Refining commit message..."):
                commit_msg = claude.chat(messages, max_tokens=256)

    git.commit(commit_msg)
    console.print("[green]Committed.[/green]")

    if push:
        branch = git.get_current_branch()
        with console.status(f"[bold blue]Pushing '{branch}'..."):
            git.push(branch)
        console.print(f"[green]Pushed '{branch}'.[/green]")
