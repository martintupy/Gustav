import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ghai.clients.claude import ClaudeClient
from ghai.clients.git import GitClient
from ghai.clients.github import GitHubClient
from ghai.prompts.loader import load_prompt
from ghai.settings import Settings

console = Console()


def generate_commit_message(claude: ClaudeClient, diff_stat: str, diff: str, files_content: str) -> str:
    prompt = load_prompt("commit_message", diff_stat=diff_stat, diff=diff, files_content=files_content)
    return claude.ask(prompt, max_tokens=256)


def generate_pr_description(claude: ClaudeClient, commits: str, diff_stat: str, diff: str, files_content: str) -> str:
    prompt = load_prompt("pr_description", commits=commits, diff_stat=diff_stat, diff=diff, files_content=files_content)
    return claude.ask(prompt, max_tokens=512)


def update_pr_description(
    claude: ClaudeClient, existing_description: str, commits: str, diff_stat: str, diff: str, files_content: str
) -> str:
    prompt = load_prompt(
        "pr_description_update",
        existing_description=existing_description,
        commits=commits,
        diff_stat=diff_stat,
        diff=diff,
        files_content=files_content,
    )
    return claude.ask(prompt, max_tokens=512)


def generate_pr_title(claude: ClaudeClient, existing_title: str, commits: str, diff_stat: str) -> str:
    prompt = load_prompt("pr_title", existing_title=existing_title, commits=commits, diff_stat=diff_stat)
    return claude.ask(prompt, max_tokens=128)


def collect_files_content(git: GitClient, files: list[str], from_head: bool = False) -> str:
    content_parts = []
    for file in files:
        file_content = git.get_file_content_from_head(file) if from_head else git.get_file_content_from_index(file)
        if file_content is not None:
            content_parts.append(f'<file path="{file}">\n{file_content}\n</file>')
    return "\n\n".join(content_parts)


@click.command()
@click.pass_obj
def pull_request(settings: Settings):
    """Generate commit message and create/update PR"""
    claude = ClaudeClient(settings.anthropic)
    git = GitClient()
    github = GitHubClient(settings.github)

    branch = git.get_current_branch()

    if branch in ("main", "master"):
        raise click.ClickException("Create a feature branch first. You're on main/master.")

    repo = git.get_remote_repo()
    if not repo:
        raise click.ClickException("Could not determine repository from git remote")

    staged_files = git.get_staged_files()

    if not staged_files:
        console.print("[yellow]No staged changes. Stage files with 'git add' first.[/yellow]")
        return

    with console.status("[bold blue]Generating commit message..."):
        diff_stat = git.get_staged_diff_stat()
        diff = git.get_staged_diff()
        files_content = collect_files_content(git, staged_files, from_head=False)
        commit_msg = generate_commit_message(claude, diff_stat, diff, files_content)

    console.print()
    console.print(Panel(commit_msg, title="Commit Message", border_style="cyan"))
    console.print()

    choice = Prompt.ask("Commit?", choices=["y", "n", "e"], default="y")

    if choice == "n":
        console.print("[dim]Aborted.[/dim]")
        return
    elif choice == "e":
        edited_msg = click.edit(commit_msg)
        if edited_msg is None:
            console.print("[dim]Aborted.[/dim]")
            return
        commit_msg = edited_msg.strip()

    git.commit(commit_msg)
    console.print("[green]Committed.[/green]")

    with console.status(f"[bold blue]Pushing '{branch}'..."):
        git.push(branch)
    console.print(f"[green]Pushed '{branch}'.[/green]")

    pr_data = github.get_pr(repo, branch)

    if pr_data:
        pr_number = pr_data["number"]
        existing_title = pr_data.get("title", "")
        existing_body = pr_data.get("body", "")

        console.print(f"\n[bold]Updating existing PR #{pr_number}...[/bold]")

        with console.status("[bold blue]Generating PR description..."):
            commits = git.get_branch_commits()
            diff_stat = git.get_branch_diff_stat()
            diff = git.get_branch_diff()
            changed_files = git.get_branch_changed_files()
            files_content = collect_files_content(git, changed_files, from_head=True)

            description = update_pr_description(claude, existing_body, commits, diff_stat, diff, files_content)
            title = generate_pr_title(claude, existing_title, commits, diff_stat)

        console.print()
        console.print(Panel(description, title="PR Description", border_style="cyan"))
        console.print(f"[bold]Title:[/bold] {title}")
        console.print()

        choice = Prompt.ask("Update PR?", choices=["y", "n", "e"], default="y")

        if choice == "n":
            console.print("[dim]PR unchanged.[/dim]")
            return
        elif choice == "e":
            edited_desc = click.edit(description)
            if edited_desc is None:
                console.print("[dim]Aborted.[/dim]")
                return
            description = edited_desc.strip()

        github.update_pr(repo, pr_number, title, description)
        console.print(f"[green]PR #{pr_number} updated.[/green]")

    else:
        console.print("\n[bold]Creating new PR...[/bold]")

        with console.status("[bold blue]Generating PR description..."):
            commits = git.get_branch_commits()
            diff_stat = git.get_branch_diff_stat()
            diff = git.get_branch_diff()
            changed_files = git.get_branch_changed_files()
            files_content = collect_files_content(git, changed_files, from_head=True)

            description = generate_pr_description(claude, commits, diff_stat, diff, files_content)

        title = commit_msg

        console.print()
        console.print(Panel(description, title="PR Description", border_style="cyan"))
        console.print(f"[bold]Title:[/bold] {title}")
        console.print()

        choice = Prompt.ask("Create PR?", choices=["y", "n", "e", "w"], default="y")

        if choice == "n":
            console.print("[dim]Cancelled.[/dim]")
            return
        elif choice == "e":
            edited_desc = click.edit(description)
            if edited_desc is None:
                console.print("[dim]Aborted.[/dim]")
                return
            description = edited_desc.strip()
        elif choice == "w":
            console.print("[dim]Opening in browser...[/dim]")

        pr_url = github.create_pr(repo, branch, title, description)
        console.print(f"[green]PR created: {pr_url}[/green]")
