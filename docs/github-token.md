# GitHub Token Setup

gus requires a GitHub Personal Access Token (PAT) with specific scopes to function properly.

## Required Scopes

| Scope      | Purpose                                                           |
| ---------- | ----------------------------------------------------------------- |
| `repo`     | Access private repositories for PR creation and commit operations |
| `read:org` | Access organization repos for the `report` command                |

## Creating a Token

1. Go to [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Set a descriptive name (e.g., "gus CLI")
4. Select the required scopes:
   - [x] `repo` (Full control of private repositories)
   - [x] `read:org` (Read org and team membership)
5. Click "Generate token"
6. Copy the token and run `gus init` to save it

## Token Storage

The token is stored securely in your system keychain (macOS Keychain, Windows Credential Manager, or Linux Secret Service).
