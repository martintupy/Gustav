import difflib

import click
from loguru import logger
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text

from ghai.cache import get_cache_key, get_cached, set_cached
from ghai.clients.claude import ClaudeClient
from ghai.clients.git import GitClient
from ghai.clients.github import GitHubClient
from ghai.prompts.loader import load_prompt
from ghai.settings import Settings

console = Console()


def is_similar(claude: ClaudeClient, old: str, new: str, context: str = "") -> bool:
    if old == new:
        logger.debug(f"Similarity check ({context}): texts are identical")
        return True

    if not old.strip() or not new.strip():
        logger.debug(f"Similarity check ({context}): one text is empty")
        return False

    prompt = load_prompt("pr_description_similarity", text_a=old, text_b=new)
    response = claude.ask(prompt, "pr_description_similarity", max_tokens=8)
    result = response.strip().lower() == "yes"

    logger.debug(f"Similarity check ({context}): Claude response='{response.strip()}', similar={result}")
    return result


def unified_diff_text(old: str, new: str) -> Text:
    result = Text()
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff_lines = list(difflib.unified_diff(old_lines, new_lines, n=3))

    if not diff_lines:
        return Text(new)

    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        elif line.startswith("-"):
            result.append(line[1:] + "\n", style="red strike")
        elif line.startswith("+"):
            result.append(line[1:] + "\n", style="green")
        elif line.startswith(" "):
            result.append(line[1:] + "\n")

    if not result.plain.strip():
        return Text(new)

    return result


def display_pr_preview(title: str, description: str, panel_title: str = "Pull Request") -> None:
    content = Group(title, Rule(style="dim"), description)
    console.print(Panel(content, title=panel_title, border_style="cyan"))


def display_pr_diff(
    old_title: str,
    new_title: str,
    old_description: str,
    new_description: str,
    panel_title: str,
) -> None:
    if old_title != new_title:
        title_text = Text()
        title_text.append(old_title, style="red strike")
        title_text.append("\n")
        title_text.append(new_title, style="green")
    else:
        title_text = Text(new_title)

    if old_description != new_description:
        desc_diff = unified_diff_text(old_description, new_description)
    else:
        desc_diff = Text(new_description)

    content = Group(title_text, Rule(style="dim"), desc_diff)
    console.print(Panel(content, title=panel_title, border_style="cyan"))


def build_loading_panel(panel_title: str, status: str) -> Panel:
    content = Group(Spinner("dots", text=f" {status}", style="bold blue"))
    return Panel(content, title=panel_title, border_style="cyan")


def generate_pr_content_cached(
    claude: ClaudeClient,
    commits: str,
    diff_stat: str,
    diff: str,
    files_content: str,
    existing_title: str | None,
    existing_body: str | None,
    panel_title: str,
) -> tuple[str, str]:
    cache_key = get_cache_key(commits, diff_stat, diff, existing_body or "")
    cached = get_cached(cache_key)

    if cached:
        console.print("[dim]Using cached result...[/dim]")
        return cached["title"], cached["description"]

    if existing_body is not None:
        prompt = load_prompt(
            "pr_description_update",
            existing_description=existing_body,
            commits=commits,
            diff_stat=diff_stat,
            diff=diff,
            files_content=files_content,
        )
    else:
        prompt = build_pr_description_prompt(commits, diff_stat, diff, files_content)

    messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

    with Live(
        build_loading_panel(panel_title, "Generating title..."),
        console=console,
        refresh_per_second=10,
        transient=True,
    ) as live:
        generated_title = generate_pr_title(claude, commits, diff_stat)
        live.update(build_loading_panel(panel_title, "Generating description..."))
        generated_description = claude.chat(messages, "pr_description", max_tokens=512)

    title = generated_title
    description = generated_description

    if existing_title and is_similar(claude, existing_title, generated_title, "title"):
        title = existing_title
        console.print("[dim]Title unchanged (similar)[/dim]")

    if existing_body and is_similar(claude, existing_body, generated_description, "description"):
        description = existing_body
        console.print("[dim]Description unchanged (similar)[/dim]")

    set_cached(cache_key, {"title": title, "description": description})
    return title, description


def build_pr_description_prompt(commits: str, diff_stat: str, diff: str, files_content: str) -> str:
    return load_prompt("pr_description", commits=commits, diff_stat=diff_stat, diff=diff, files_content=files_content)


def generate_pr_title(claude: ClaudeClient, commits: str, diff_stat: str) -> str:
    prompt = load_prompt("pr_title", commits=commits, diff_stat=diff_stat)
    return claude.ask(prompt, "pr_title", max_tokens=128)


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

    needs_push = not git.branch_exists_on_remote(branch) or git.has_unpushed_commits(branch)
    if needs_push:
        with console.status(f"[bold blue]Pushing '{branch}'..."):
            git.push(branch)
        console.print(f"[green]Pushed '{branch}'.[/green]")

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
        pr_url = pr_data.get("url", "")
        existing_title = pr_data.get("title", "")
        existing_body = pr_data.get("body", "") or ""
        panel_title = f"Update Pull Request #{pr_number} - {pr_url}"

        title, description = generate_pr_content_cached(
            claude, commits, diff_stat, diff, files_content, existing_title, existing_body, panel_title
        )

        no_changes = title == existing_title and description == existing_body

        prompt = load_prompt(
            "pr_description_update",
            existing_description=existing_body,
            commits=commits,
            diff_stat=diff_stat,
            diff=diff,
            files_content=files_content,
        )
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        while True:
            display_pr_diff(existing_title, title, existing_body, description, panel_title)

            if no_changes:
                console.print("[dim](n) cancel  (r) refine[/dim]")
                choice = Prompt.ask("No changes", choices=["n", "r"], default="n")
            else:
                console.print("[dim](y) confirm  (n) cancel  (r) refine[/dim]")
                choice = Prompt.ask("Confirm?", choices=["y", "n", "r"], default="y")

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
                with Live(
                    build_loading_panel(panel_title, "Refining description..."),
                    console=console,
                    refresh_per_second=10,
                    transient=True,
                ):
                    description = claude.chat(messages, "pr_description_refine", max_tokens=512)
                no_changes = False

        github.update_pr(repo, pr_number, title, description)
        console.print(f"[green]PR #{pr_number} updated.[/green]")

    else:
        panel_title = "New Pull Request"

        title, description = generate_pr_content_cached(
            claude, commits, diff_stat, diff, files_content, None, None, panel_title
        )

        prompt = build_pr_description_prompt(commits, diff_stat, diff, files_content)
        messages = [{"role": "user", "content": prompt}]

        while True:
            display_pr_preview(title, description, panel_title)
            console.print("[dim](y) confirm  (n) cancel  (r) refine[/dim]")

            choice = Prompt.ask("Confirm?", choices=["y", "n", "r"], default="y")

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
                with Live(
                    build_loading_panel(panel_title, "Refining description..."),
                    console=console,
                    refresh_per_second=10,
                    transient=True,
                ):
                    description = claude.chat(messages, "pr_description_refine", max_tokens=512)

        pr_url = github.create_pr(repo, branch, title, description, base=base_branch)
        console.print(f"[green]PR created: {pr_url}[/green]")
