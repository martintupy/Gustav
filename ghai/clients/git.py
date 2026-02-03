import re
import subprocess

import click
from loguru import logger


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

    def _get_base_ref(self, base: str = "main") -> str | None:
        for ref in [f"origin/{base}", base, "origin/master", "master"]:
            result = self._run("rev-parse", "--verify", ref, check=False)
            if result.returncode == 0:
                return ref
        return None

    def get_branch_diff(self, base: str = "main") -> str:
        base_ref = self._get_base_ref(base)
        logger.debug(f"get_branch_diff: base={base}, base_ref={base_ref}")
        if base_ref:
            result = self._run("diff", f"{base_ref}...HEAD", check=False)
            logger.debug(f"diff {base_ref}...HEAD returned {len(result.stdout)} chars")
            if result.returncode == 0:
                return result.stdout
        result = self._run("diff", "--root", "HEAD", check=False)
        return result.stdout if result.returncode == 0 else ""

    def get_branch_diff_stat(self, base: str = "main") -> str:
        base_ref = self._get_base_ref(base)
        if base_ref:
            result = self._run("diff", f"{base_ref}...HEAD", "--stat", check=False)
            if result.returncode == 0:
                return result.stdout
        result = self._run("diff", "--root", "HEAD", "--stat", check=False)
        return result.stdout if result.returncode == 0 else ""

    def get_branch_commits(self, base: str = "main") -> str:
        base_ref = self._get_base_ref(base)
        if base_ref:
            result = self._run("log", f"{base_ref}..HEAD", "--oneline", check=False)
            if result.returncode == 0:
                return result.stdout
        result = self._run("log", "--oneline", check=False)
        return result.stdout if result.returncode == 0 else ""

    def get_branch_changed_files(self, base: str = "main") -> list[str]:
        base_ref = self._get_base_ref(base)
        if base_ref:
            result = self._run("diff", f"{base_ref}...HEAD", "--name-only", check=False)
            if result.returncode == 0:
                return [f for f in result.stdout.strip().split("\n") if f]
        result = self._run("ls-tree", "-r", "--name-only", "HEAD", check=False)
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []

    def commit(self, message: str) -> None:
        self._run("commit", "-m", message)

    def push(self, branch: str) -> None:
        result = self._run("push", "-u", "origin", branch, check=False)
        if result.returncode != 0:
            self._run("push", "origin", branch)

    def branch_exists_on_remote(self, branch: str) -> bool:
        result = self._run("ls-remote", "--heads", "origin", branch, check=False)
        return bool(result.stdout.strip())

    def get_remote_repo(self) -> str | None:
        result = self._run("remote", "get-url", "origin", check=False)
        if result.returncode != 0:
            return None

        url = result.stdout.strip()
        match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
        if match:
            return match.group(1).rstrip("/")
        return None
