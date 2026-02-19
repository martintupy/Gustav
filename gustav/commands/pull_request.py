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

from gustav.cache import get_cache_key, get_cached, set_cached
from gustav.clients.claude import ClaudeClient
from gustav.clients.git import GitClient
from gustav.clients.github import GitHubClient
from gustav.prompts.loader import load_prompt
from gustav.settings import Settings

console = Console()


def is_similar(claude: ClaudeClient, old: str, new: str, context: str = "") -> bool:
    if old == new:
        logger.debug(f"Similarity check ({context}): texts are identical")
        return True

    if not old.strip() or not new.strip():
        return False

    prompt = load_prompt("pr_similarity", text_a=old, text_b=new)
    response = claude.ask(prompt, "pr_similarity", max_tokens=8)
    return response.strip().lower() == "yes"


def unified_diff_text(old: str, new: str) -> Text:
    if old == new:
        return Text(new)

    result = Text()
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff_lines = list(difflib.unified_diff(old_lines, new_lines, n=999))

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
    current_description: str | None,
    panel_title: str,
) -> tuple[str, str]:
    cache_key = get_cache_key(commits, diff_stat, diff, current_description or "")
    cached = get_cached(cache_key)

    if cached:
        console.print("[dim]Using cached result...[/dim]")
        return cached["title"], cached["description"]

    with Live(
        build_loading_panel(panel_title, "Generating changes..."),
        console=console,
        refresh_per_second=10,
        transient=True,
    ) as live:
        changes = generate_pr_changes(claude, commits, diff_stat, diff, files_content)
        live.update(build_loading_panel(panel_title, "Generating summary..."))
        summary = generate_pr_summary(claude, changes)
        live.update(build_loading_panel(panel_title, "Generating title..."))
        title = generate_pr_title(claude, summary)

    generated_description = build_full_description(summary, changes)

    if current_description and existing_title and is_similar(claude, current_description, generated_description):
        console.print("[dim]Description similar.[/dim]")
        return existing_title, current_description

    set_cached(cache_key, {"title": title, "description": generated_description})
    return title, generated_description


def generate_pr_changes(claude: ClaudeClient, commits: str, diff_stat: str, diff: str, files_content: str) -> str:
    prompt = load_prompt("pr_changes", commits=commits, diff_stat=diff_stat, diff=diff, files_content=files_content)
    return claude.ask(prompt, "pr_changes", max_tokens=512).strip()


def generate_pr_summary(claude: ClaudeClient, changes: str) -> str:
    prompt = load_prompt("pr_summary", changes=changes)
    return claude.ask(prompt, "pr_summary", max_tokens=128).strip()


def generate_pr_title(claude: ClaudeClient, summary: str) -> str:
    prompt = load_prompt("pr_title", summary=summary)
    return claude.ask(prompt, "pr_title", max_tokens=128).strip()


def build_full_description(summary: str, changes: str) -> str:
    return f"## Summary\n\n{summary}\n\n## Changes\n\n{changes}"


def extract_summary_from_description(description: str) -> str | None:
    if "## Summary" not in description:
        return None
    after_header = description.split("## Summary", 1)[1]
    before_next = after_header.split("## ", 1)[0]
    return before_next.strip() or None


def refine_pr(claude: ClaudeClient, title: str, description: str, panel_title: str) -> tuple[str, str] | None:
    feedback = Prompt.ask("[dim]How should I change it?[/dim]")
    if not feedback:
        return None

    refine_prompt = load_prompt(
        "pr_refine",
        current_description=description,
        user_feedback=feedback,
    )
    with Live(
        build_loading_panel(panel_title, "Refining description..."),
        console=console,
        refresh_per_second=10,
        transient=True,
    ) as live:
        new_description = claude.chat([{"role": "user", "content": refine_prompt}], "pr_refine", max_tokens=512)
        live.update(build_loading_panel(panel_title, "Updating title..."))
        summary = extract_summary_from_description(new_description)
        new_title = generate_pr_title(claude, summary) if summary else title

    return new_title, new_description


def interactive_pr_loop(
    claude: ClaudeClient,
    title: str,
    description: str,
    panel_title: str,
    existing_title: str | None = None,
    existing_body: str | None = None,
) -> tuple[str, str] | None:
    is_update = existing_title is not None
    no_changes = is_update and title == existing_title and description == existing_body

    while True:
        if is_update:
            display_pr_diff(existing_title, title, existing_body or "", description, panel_title)
        else:
            display_pr_preview(title, description, panel_title)

        if no_changes:
            console.print("[dim](n) cancel  (r) refine[/dim]")
            choice = Prompt.ask("No changes", choices=["n", "r"], default="n")
        else:
            console.print("[dim](y) confirm  (n) cancel  (r) refine[/dim]")
            prompt_text = "Update PR?" if is_update else "Create PR?"
            choice = Prompt.ask(prompt_text, choices=["y", "n", "r"], default="y")

        if choice == "y":
            return title, description
        elif choice == "n":
            console.print("[dim]Cancelled.[/dim]")
            return None
        elif choice == "r":
            refined = refine_pr(claude, title, description, panel_title)
            if refined:
                title, description = refined
                no_changes = False


def collect_files_content(git: GitClient, files: list[str], renamed_files: set[str]) -> str:
    content_parts = []
    for file in files:
        if file in renamed_files:
            continue
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
    renamed_files = git.get_branch_renames(base_branch)
    files_content = collect_files_content(git, changed_files, renamed_files)

    if pr_data:
        pr_number = pr_data["number"]
        pr_url = pr_data.get("url", "")
        existing_title = pr_data.get("title", "")
        existing_body = pr_data.get("body", "") or ""
        panel_title = f"Update Pull Request #{pr_number} - {pr_url}"

        title, description = generate_pr_content_cached(
            claude, commits, diff_stat, diff, files_content, existing_title, existing_body, panel_title
        )

        result = interactive_pr_loop(claude, title, description, panel_title, existing_title, existing_body)
        if not result:
            return

        title, description = result
        github.update_pr(repo, pr_number, title, description)
        console.print(f"[green]PR #{pr_number} updated.[/green]")

    else:
        panel_title = "New Pull Request"

        title, description = generate_pr_content_cached(
            claude, commits, diff_stat, diff, files_content, None, None, panel_title
        )

        result = interactive_pr_loop(claude, title, description, panel_title)
        if not result:
            return

        title, description = result
        pr_url = github.create_pr(repo, branch, title, description, base=base_branch)
        console.print(f"[green]PR created: {pr_url}[/green]")
