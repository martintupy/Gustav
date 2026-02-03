from collections import defaultdict
from datetime import datetime

import click
import httpx
from loguru import logger
from rich.console import Console

from ghai.settings import GitHubSettings

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

        if response.status_code not in (200, 201):
            error = response.json().get("message", response.text)
            raise click.ClickException(f"Failed to create PR: {error}")

        return response.json().get("html_url", "")

    def update_pr(self, repo: str, pr_number: int, title: str, body: str) -> None:
        response = self._request(
            "PATCH",
            f"repos/{repo}/pulls/{pr_number}",
            json={"title": title, "body": body},
        )

        if response.status_code != 200:
            error = response.json().get("message", response.text)
            raise click.ClickException(f"Failed to edit PR: {error}")

    def get_default_branch(self, repo: str) -> str:
        response = self._request("GET", f"repos/{repo}")
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

    def fetch_commits_by_day(
        self,
        repos: list[str],
        emails: list[str],
        since: datetime,
    ) -> dict[str, list[str]]:
        commits_by_day = defaultdict(list)
        seen_shas = set()

        with console.status("[bold blue]Fetching commits from GitHub...") as status:
            for repo in repos:
                status.update(f"[bold blue]Fetching branches from {repo}...")
                branches = self.get_branches(repo)

                for branch in branches:
                    status.update(f"[bold blue]Fetching {repo}@{branch}...")
                    commits = self.get_commits(repo, branch, since)

                    for commit in commits:
                        sha = commit.get("sha", "")
                        if sha in seen_shas:
                            continue

                        author_email = commit.get("commit", {}).get("author", {}).get("email", "")
                        if author_email not in emails:
                            continue

                        seen_shas.add(sha)
                        date_str = commit.get("commit", {}).get("author", {}).get("date", "")
                        if date_str:
                            day = date_str.split("T")[0]
                            message = commit.get("commit", {}).get("message", "").split("\n")[0]
                            commits_by_day[day].append(message)

        return dict(commits_by_day)
