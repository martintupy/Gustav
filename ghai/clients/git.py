import re
import subprocess

import click


class GitClient:
    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            raise click.ClickException(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result

    def get_current_branch(self) -> str:
        result = self._run("branch", "--show-current")
        return result.stdout.strip()

    def get_staged_files(self) -> list[str]:
        result = self._run("diff", "--cached", "--name-only")
        return [f for f in result.stdout.strip().split("\n") if f]

    def get_staged_diff(self) -> str:
        result = self._run("diff", "--cached")
        return result.stdout

    def get_staged_diff_stat(self) -> str:
        result = self._run("diff", "--cached", "--stat")
        return result.stdout

    def get_file_content_from_index(self, file: str) -> str | None:
        result = self._run("cat-file", "-e", f":{file}", check=False)
        if result.returncode != 0:
            return None
        result = self._run("show", f":{file}")
        return result.stdout

    def get_file_content_from_head(self, file: str) -> str | None:
        result = self._run("cat-file", "-e", f"HEAD:{file}", check=False)
        if result.returncode != 0:
            return None
        result = self._run("show", f"HEAD:{file}")
        return result.stdout

    def get_branch_diff(self, base: str = "main") -> str:
        for remote_base in [f"origin/{base}", base]:
            result = self._run("diff", f"{remote_base}...HEAD", check=False)
            if result.returncode == 0:
                return result.stdout
        return ""

    def get_branch_diff_stat(self, base: str = "main") -> str:
        for remote_base in [f"origin/{base}", base]:
            result = self._run("diff", f"{remote_base}...HEAD", "--stat", check=False)
            if result.returncode == 0:
                return result.stdout
        return ""

    def get_branch_commits(self, base: str = "main") -> str:
        for remote_base in [f"origin/{base}", base]:
            result = self._run("log", f"{remote_base}..HEAD", "--oneline", check=False)
            if result.returncode == 0:
                return result.stdout
        return ""

    def get_branch_changed_files(self, base: str = "main") -> list[str]:
        for remote_base in [f"origin/{base}", base]:
            result = self._run("diff", f"{remote_base}...HEAD", "--name-only", check=False)
            if result.returncode == 0:
                return [f for f in result.stdout.strip().split("\n") if f]
        return []

    def commit(self, message: str) -> None:
        self._run("commit", "-m", message)

    def push(self, branch: str) -> None:
        result = self._run("push", "-u", "origin", branch, check=False)
        if result.returncode != 0:
            self._run("push", "origin", branch)

    def get_remote_repo(self) -> str | None:
        result = self._run("remote", "get-url", "origin", check=False)
        if result.returncode != 0:
            return None

        url = result.stdout.strip()
        match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
        if match:
            return match.group(1).rstrip("/")
        return None
