import click
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule

from ghai.clients.claude import ClaudeClient
from ghai.clients.git import GitClient
from ghai.clients.github import GitHubClient
from ghai.prompts.loader import load_prompt
from ghai.settings import Settings

console = Console()


def display_pr_preview(title: str, description: str) -> None:
    content = Group(title, Rule(style="dim"), Markdown(description))
    console.print()
    console.print(Panel(content, title="Pull Request", border_style="cyan"))
    console.print()


def build_pr_description_prompt(commits: str, diff_stat: str, diff: str, files_content: str) -> str:
    return load_prompt("pr_description", commits=commits, diff_stat=diff_stat, diff=diff, files_content=files_content)


def generate_pr_title(claude: ClaudeClient, commits: str, diff_stat: str) -> str:
    prompt = load_prompt("pr_title", commits=commits, diff_stat=diff_stat)
    return claude.ask(prompt, max_tokens=128)


def collect_files_content(git: GitClient, files: list[str]) -> str:
    content_parts = []
    for file in files:
        file_content = git.get_file_content_from_head(file)
        if file_content is not None:
            content_parts.append(f'<file path="{file}">\n{file_content}\n</file>')
    return "\n\n".join(content_parts)


@click.command()
@click.pass_obj
def pull_request(settings: Settings):
    """Create or update pull request"""
    claude = ClaudeClient(settings.anthropic)
    git = GitClient()
    github = GitHubClient(settings.github)

    branch = git.get_current_branch()

    repo = git.get_remote_repo()
    if not repo:
        raise click.ClickException("Could not determine repository from git remote")

    base_branch = github.get_default_branch(repo)

    if branch == base_branch:
        raise click.ClickException(f"Create a feature branch first. You're on '{base_branch}'.")

    if not git.branch_exists_on_remote(branch):
        with console.status(f"[bold blue]Pushing '{branch}'..."):
            git.push(branch)
        console.print(f"[green]Pushed '{branch}' branch.[/green]")

    pr_data = github.get_pr(repo, branch)

    commits = git.get_branch_commits(base_branch)
    diff_stat = git.get_branch_diff_stat(base_branch)
    diff = git.get_branch_diff(base_branch)
    changed_files = git.get_branch_changed_files(base_branch)
    files_content = collect_files_content(git, changed_files)

    if not commits.strip() and not diff.strip():
        raise click.ClickException(
            f"No commits or changes found compared to '{base_branch}'. "
            f"Make sure your branch has commits that differ from '{base_branch}'."
        )

    if pr_data:
        pr_number = pr_data["number"]
        existing_body = pr_data.get("body", "")

        console.print(f"\n[bold]Updating existing PR #{pr_number}...[/bold]")

        prompt = load_prompt(
            "pr_description_update",
            existing_description=existing_body,
            commits=commits,
            diff_stat=diff_stat,
            diff=diff,
            files_content=files_content,
        )
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        with console.status("[bold blue]Generating PR title..."):
            title = generate_pr_title(claude, commits, diff_stat)
        with console.status("[bold blue]Generating PR description..."):
            description = claude.chat(messages, max_tokens=512)

        while True:
            display_pr_preview(title, description)
            console.print("[dim](y) update  (n) cancel  (r) refine with feedback[/dim]")

            choice = Prompt.ask("Update PR?", choices=["y", "n", "r"], default="y")

            if choice == "y":
                break
            elif choice == "n":
                console.print("[dim]Cancelled.[/dim]")
                return
            elif choice == "r":
                feedback = Prompt.ask("[dim]How should I change it?[/dim]")
                if not feedback:
                    continue
                messages.append({"role": "assistant", "content": description})
                messages.append({"role": "user", "content": feedback})
                with console.status("[bold blue]Refining PR description..."):
                    description = claude.chat(messages, max_tokens=512)

        github.update_pr(repo, pr_number, title, description)
        console.print(f"[green]PR #{pr_number} updated.[/green]")

    else:
        prompt = build_pr_description_prompt(commits, diff_stat, diff, files_content)
        messages = [{"role": "user", "content": prompt}]

        with console.status("[bold blue]Generating PR title..."):
            title = generate_pr_title(claude, commits, diff_stat)
        with console.status("[bold blue]Generating PR description..."):
            description = claude.chat(messages, max_tokens=512)

        while True:
            display_pr_preview(title, description)
            console.print("[dim](y) create  (n) cancel  (r) refine with feedback[/dim]")

            choice = Prompt.ask("Create PR?", choices=["y", "n", "r"], default="y")

            if choice == "y":
                break
            elif choice == "n":
                console.print("[dim]Cancelled.[/dim]")
                return
            elif choice == "r":
                feedback = Prompt.ask("[dim]How should I change it?[/dim]")
                if not feedback:
                    continue
                messages.append({"role": "assistant", "content": description})
                messages.append({"role": "user", "content": feedback})
                with console.status("[bold blue]Refining PR description..."):
                    description = claude.chat(messages, max_tokens=512)

        pr_url = github.create_pr(repo, branch, title, description, base=base_branch)
        console.print(f"[green]PR created: {pr_url}[/green]")
