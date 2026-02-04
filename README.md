# Gustav

Gustav an AI-powered Git assistant that helps streamline your development workflow.

## What Gustav Does

- **Smart Commit Messages**: Generate conventional commit messages from your staged changes using AI
- **Pull Request Automation**: Create and update pull requests with AI-generated titles and descriptions
- **Interactive Refinement**: Refine AI-generated content through conversational feedback
- **Activity Reports**: Generate daily/weekly work summaries from your GitHub activity

## Quick Start

```bash
# Install
uv tool install -e .

# Initialize
gus init

# Generate commit message
gus commit

# Create or update PR
gus pr

# View work report
gus report
```

## Requirements

- Python 3.13+
- Anthropic API key (Claude)
- GitHub Personal Access Token

See [docs/github-token.md](docs/github-token.md) for token setup instructions.

## Troubleshooting

Run `gus status` to verify your configuration and API connections
