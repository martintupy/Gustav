from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, **kwargs: str) -> str:
    prompt_file = PROMPTS_DIR / f"{name}.md"
    template = prompt_file.read_text()
    return template.format(**kwargs)
