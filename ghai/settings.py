import subprocess
from pathlib import Path
from typing import Self

import keyring
import yaml
from pydantic import BaseModel, SecretStr, field_validator, model_validator

APP_NAME = "ghai"
SETTINGS_DIR = Path.home() / ".config" / APP_NAME
SETTINGS_FILE = SETTINGS_DIR / "config.yaml"

KEYRING_ANTHROPIC_KEY = "ANTHROPIC_API_KEY"
KEYRING_GITHUB_TOKEN = "GITHUB_TOKEN"


def get_git_config(key: str) -> str | None:
    result = subprocess.run(
        ["git", "config", "--global", key],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


class AnthropicSettings(BaseModel):
    api_key: SecretStr
    api_url: str = "https://api.anthropic.com/v1/messages"
    api_version: str = "2023-06-01"
    model: str = "claude-sonnet-4-20250514"
    timeout: int = 30


class GitHubSettings(BaseModel):
    token: SecretStr
    api_url: str = "https://api.github.com"
    api_version: str = "2022-11-28"


class GitSettings(BaseModel):
    user_email: str | None = None
    user_name: str | None = None


class Settings(BaseModel):
    emails: list[str] = []
    repos: list[str] = []
    anthropic: AnthropicSettings
    github: GitHubSettings
    git: GitSettings = GitSettings()

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one email is required")
        return v

    @model_validator(mode="after")
    def validate_repos_format(self) -> Self:
        for repo in self.repos:
            if "/" not in repo:
                raise ValueError(f"Invalid repo format '{repo}'. Expected 'owner/repo'")
        return self


def load_settings() -> Settings:
    if not SETTINGS_FILE.exists():
        raise FileNotFoundError(f"Settings file not found at {SETTINGS_FILE}. Run 'ghai init' first.")

    with open(SETTINGS_FILE) as f:
        data = yaml.safe_load(f) or {}

    anthropic_api_key = keyring.get_password(APP_NAME, KEYRING_ANTHROPIC_KEY)
    if not anthropic_api_key:
        raise ValueError("Anthropic API key not found in keychain. Run 'ghai init' first.")

    github_token = keyring.get_password(APP_NAME, KEYRING_GITHUB_TOKEN)
    if not github_token:
        raise ValueError("GitHub token not found in keychain. Run 'ghai init' first.")

    anthropic_data = data.get("anthropic") or {}
    github_data = data.get("github") or {}
    git_data = data.get("git") or {}

    git_data.setdefault("user_email", get_git_config("user.email"))
    git_data.setdefault("user_name", get_git_config("user.name"))

    return Settings(
        emails=data.get("emails", []),
        repos=data.get("repos", []),
        anthropic=AnthropicSettings(api_key=SecretStr(anthropic_api_key), **anthropic_data),
        github=GitHubSettings(token=SecretStr(github_token), **github_data),
        git=GitSettings(**git_data),
    )


def settings_exist() -> bool:
    return SETTINGS_FILE.exists()


def anthropic_key_exists() -> bool:
    return keyring.get_password(APP_NAME, KEYRING_ANTHROPIC_KEY) is not None


def github_token_exists() -> bool:
    return keyring.get_password(APP_NAME, KEYRING_GITHUB_TOKEN) is not None


def save_config_file(emails: list[str], repos: list[str]) -> None:
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    data = {"emails": emails, "repos": repos}
    with open(SETTINGS_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def save_anthropic_key(api_key: str) -> None:
    keyring.set_password(APP_NAME, KEYRING_ANTHROPIC_KEY, api_key)


def save_github_token(token: str) -> None:
    keyring.set_password(APP_NAME, KEYRING_GITHUB_TOKEN, token)
