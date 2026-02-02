import click
import httpx

from ghai.settings import AnthropicSettings


class ClaudeClient:
    def __init__(self, settings: AnthropicSettings):
        self.settings = settings

    def ask(self, prompt: str, max_tokens: int = 256) -> str:
        response = httpx.post(
            self.settings.api_url,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.settings.api_key.get_secret_value(),
                "anthropic-version": self.settings.api_version,
            },
            json={
                "model": self.settings.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self.settings.timeout,
        )
        data = response.json()
        if "error" in data:
            raise click.ClickException(f"Claude API error: {data['error']['message']}")
        return data["content"][0]["text"]
