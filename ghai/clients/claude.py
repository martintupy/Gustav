import time

import click
import httpx
from loguru import logger

from ghai.settings import AnthropicSettings

Message = dict[str, str]


class ClaudeClient:
    def __init__(self, settings: AnthropicSettings):
        self.settings = settings

    def ask(self, prompt: str, prompt_name: str, max_tokens: int = 256) -> str:
        messages = [{"role": "user", "content": prompt}]
        return self._request(messages, prompt_name, max_tokens)

    def chat(self, messages: list[Message], prompt_name: str, max_tokens: int = 256) -> str:
        return self._request(messages, prompt_name, max_tokens)

    def _request(self, messages: list[Message], prompt_name: str, max_tokens: int) -> str:
        start = time.perf_counter()
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
                "messages": messages,
            },
            timeout=self.settings.timeout,
        )
        elapsed = time.perf_counter() - start

        data = response.json()
        if "error" in data:
            logger.error(f"Claude API request error: {data['error']}")
            raise click.ClickException(f"Claude API error: {data['error']['message']}")

        logger.debug(
            f"Claude API response [{prompt_name}]: length={len(data['content'][0]['text'])} elapsed={elapsed:.2f}s"
        )
        return data["content"][0]["text"]
