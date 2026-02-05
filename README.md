# Gustav

Gustav an AI-powered Git assistant that helps streamline your development workflow.

## What Gustav Does

- **Smart Commit Messages**: Generate conventional commit messages from your staged changes using AI
- **Pull Request Automation**: Create and update pull requests with AI-generated titles and descriptions
- **Interactive Refinement**: Refine AI-generated content through conversational feedback
- **Activity Reports**: Generate daily/weekly work summaries from your GitHub activity

## Installation

- **Using uv:** `uv tool install git+https://github.com/martintupy/gustav.git`
- **Using pip:** `pip install git+https://github.com/martintupy/gustav.git`

## Quick Start

```bash
# Initialize
gus init

# Verify API connecion
gus status
```

```bash
# Generate commit
gus commit

# Generate pull request
gus pr
```

## Requirements

- Python 3.13+
- Anthropic API key (Claude)
- GitHub Personal Access Token

See [docs/github-token.md](docs/github-token.md) for token setup instructions.

## Troubleshooting

Run `gus status` to verify your configuration and API connections
