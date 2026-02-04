from collections import defaultdict
from datetime import datetime

import click
import httpx
from loguru import logger
from rich.console import Console

from gustav.settings import GitHubSettings

console = Console()


class GitHubClient:
    def __init__(self, settings: GitHubSettings):
        self.settings = settings
        self.headers = {
            "Authorization": f"Bearer {settings.token.get_secret_value()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.api_version,
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        url = f"{self.settings.api_url}/{endpoint.lstrip('/')}"
        logger.debug(f"GitHub API: {method} {url}")
        if json:
            logger.debug(f"Request body: {json}")
        response = httpx.request(
            method,
            url,
            headers=self.headers,
            json=json,
            params=params,
            timeout=30,
            follow_redirects=True,
        )
        logger.debug(f"Response: {response.status_code}")
        if response.status_code >= 400:
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
        return response

    def _get_paginated(self, endpoint: str, params: dict | None = None) -> list:
        results = []
        params = params.copy() if params else {}
        params["per_page"] = 100
        page = 1

        while True:
            params["page"] = page
            response = self._request("GET", endpoint, params=params)
            if response.status_code != 200:
                break

            data = response.json()
            if isinstance(data, list):
                if not data:
                    break
                results.extend(data)
                page += 1
            else:
                results.append(data)
                break

        return results

    def get_pr(self, repo: str, branch: str) -> dict | None:
        owner = repo.split("/")[0]
        response = self._request(
            "GET",
            f"repos/{repo}/pulls",
            params={"head": f"{owner}:{branch}"},
        )
        if response.status_code != 200:
            return None

        prs = response.json()
        if not prs:
            return None

        pr = prs[0]
        return {
            "number": pr["number"],
            "title": pr.get("title", ""),
            "body": pr.get("body", ""),
            "url": pr.get("html_url", ""),
        }

    def create_pr(self, repo: str, branch: str, title: str, body: str, base: str = "main") -> str:
        response = self._request(
            "POST",
            f"repos/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": branch,
                "base": base,
            },
        )

        if response.status_code == 404:
            raise click.ClickException(
                f"Repository '{repo}' not found. Check that your GitHub token has access to this repo."
            )
        if response.status_code in (301, 302):
            location = response.headers.get("Location", "")
            raise click.ClickException(
                f"Repository '{repo}' has been moved. Update your git remote: git remote set-url origin {location}"
            )
        if response.status_code not in (200, 201):
            error_data = (
                response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            )
            error = error_data.get("message", response.text)
            raise click.ClickException(f"Failed to create PR: {error}")

        return response.json().get("html_url", "")

    def update_pr(self, repo: str, pr_number: int, title: str, body: str) -> None:
        response = self._request(
            "PATCH",
            f"repos/{repo}/pulls/{pr_number}",
            json={"title": title, "body": body},
        )

        if response.status_code == 404:
            raise click.ClickException(
                f"Repository '{repo}' or PR #{pr_number} not found. "
                "Check that your GitHub token has access to this repo."
            )
        if response.status_code != 200:
            error = response.json().get("message", response.text)
            raise click.ClickException(f"Failed to edit PR: {error}")

    def get_default_branch(self, repo: str) -> str:
        response = self._request("GET", f"repos/{repo}")
        if response.status_code == 404:
            raise click.ClickException(
                f"Repository '{repo}' not found. Check that your GitHub token has access to this repo."
            )
        if response.status_code != 200:
            return "main"
        return response.json().get("default_branch", "main")

    def get_branches(self, repo: str) -> list[str]:
        branches_data = self._get_paginated(f"repos/{repo}/branches")
        return [b["name"] for b in branches_data] if branches_data else ["main"]

    def get_commits(
        self,
        repo: str,
        branch: str,
        since: datetime | None = None,
    ) -> list[dict]:
        params = {"sha": branch}
        if since:
            params["since"] = since.strftime("%Y-%m-%dT00:00:00Z")
        return self._get_paginated(f"repos/{repo}/commits", params=params)

    def get_authenticated_user(self) -> str:
        response = self._request("GET", "user")
        if response.status_code != 200:
            raise click.ClickException("Failed to get authenticated user. Check your GitHub token.")
        return response.json().get("login", "")

    def get_user_orgs(self) -> list[str]:
        orgs_data = self._get_paginated("user/orgs")
        return [org.get("login", "") for org in orgs_data if org.get("login")]

    def get_user_events(self, username: str, since: datetime) -> list[dict]:
        events = self._get_paginated(f"users/{username}/events")
        logger.debug(f"Fetched {len(events)} total events for {username}")

        filtered = []
        repos_seen: set[str] = set()
        for event in events:
            created_at = event.get("created_at", "")
            repo_name = event.get("repo", {}).get("name", "")
            repos_seen.add(repo_name)
            if created_at:
                event_date = datetime.strptime(created_at[:10], "%Y-%m-%d")
                if event_date >= since:
                    filtered.append(event)

        logger.debug(f"Repos in events: {sorted(repos_seen)}")
        logger.debug(f"Filtered to {len(filtered)} events since {since.strftime('%Y-%m-%d')}")
        return filtered

    def get_org_repos(self, org: str) -> list[str]:
        repos = self._get_paginated(f"orgs/{org}/repos", params={"type": "all"})
        return [r.get("full_name", "") for r in repos if r.get("full_name")]

    def get_repo_commits(self, repo: str, author: str, since: datetime) -> list[dict]:
        params = {"author": author, "since": since.strftime("%Y-%m-%dT00:00:00Z")}
        return self._get_paginated(f"repos/{repo}/commits", params=params)

    def fetch_org_commits(self, org: str, username: str, since: datetime) -> dict[str, list[str]]:
        logger.debug(f"Fetching repos from {org}")
        repos = self.get_org_repos(org)
        logger.debug(f"Found {len(repos)} repos in {org}")

        commits_by_day: dict[str, list[str]] = defaultdict(list)

        for repo in repos:
            commits = self.get_repo_commits(repo, username, since)
            for commit in commits:
                date_str = commit.get("commit", {}).get("author", {}).get("date", "")
                message = commit.get("commit", {}).get("message", "").split("\n")[0]

                if date_str:
                    day = date_str.split("T")[0]
                    commits_by_day[day].append(f"[{repo}] Pushed: {message}")

        logger.debug(f"Found {sum(len(v) for v in commits_by_day.values())} commits in {org}")
        return dict(commits_by_day)

    def fetch_activity_by_day(self, username: str, orgs: list[str], since: datetime) -> dict[str, list[str]]:
        activity_by_day: dict[str, list[str]] = defaultdict(list)

        with console.status("[bold blue]Fetching activity from GitHub...") as status:
            status.update("[bold blue]Fetching personal events...")
            events = self.get_user_events(username, since)

            for org in orgs:
                status.update(f"[bold blue]Fetching commits from {org}...")
                org_commits = self.fetch_org_commits(org, username, since)
                for day, commits in org_commits.items():
                    activity_by_day[day].extend(commits)

            for event in events:
                event_type = event.get("type", "")
                repo_name = event.get("repo", {}).get("name", "")
                created_at = event.get("created_at", "")
                payload = event.get("payload", {})

                if not created_at:
                    continue

                day = created_at.split("T")[0]

                if event_type == "PushEvent":
                    commits = payload.get("commits", [])
                    for commit in commits:
                        msg = commit.get("message", "").split("\n")[0]
                        activity_by_day[day].append(f"[{repo_name}] Pushed: {msg}")

                elif event_type == "PullRequestEvent":
                    action = payload.get("action", "")
                    pr = payload.get("pull_request", {})
                    title = pr.get("title", "")
                    activity_by_day[day].append(f"[{repo_name}] PR {action}: {title}")

                elif event_type == "PullRequestReviewEvent":
                    action = payload.get("action", "")
                    pr = payload.get("pull_request", {})
                    title = pr.get("title", "")
                    activity_by_day[day].append(f"[{repo_name}] Reviewed PR: {title}")

                elif event_type == "IssueCommentEvent":
                    issue = payload.get("issue", {})
                    title = issue.get("title", "")
                    activity_by_day[day].append(f"[{repo_name}] Commented on: {title}")

                elif event_type == "IssuesEvent":
                    action = payload.get("action", "")
                    issue = payload.get("issue", {})
                    title = issue.get("title", "")
                    activity_by_day[day].append(f"[{repo_name}] Issue {action}: {title}")

                elif event_type == "CreateEvent":
                    ref_type = payload.get("ref_type", "")
                    ref = payload.get("ref", "")
                    if ref:
                        activity_by_day[day].append(f"[{repo_name}] Created {ref_type}: {ref}")

        return dict(activity_by_day)
