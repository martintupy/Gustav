# GitHub Token Setup

gus requires a GitHub Personal Access Token (PAT) with specific permissions to function properly.

## Option 1: Classic Token (Recommended)

Classic tokens work across all orgs you're a member of.

### Required Scopes

| Scope | Purpose |
|-------|---------|
| `repo` | Access private repositories for PR creation and commit operations |
| `read:org` | Access organization repos for the `report` command |

### Creating a Classic Token

1. Go to [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Set a descriptive name (e.g., "gus CLI")
4. Select the required scopes:
   - [x] `repo` (Full control of private repositories)
   - [x] `read:org` (Read org and team membership)
5. Click "Generate token"
6. Copy the token and run `gus init` to save it

## Option 2: Fine-Grained Token

Fine-grained tokens require explicit org access configuration.

### Creating a Fine-Grained Token

1. Go to [GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click "Generate new token"
3. Set a descriptive name (e.g., "gus CLI")
4. **Resource owner**: Select your organization (e.g., `Dius-ai`), NOT your personal account
5. **Repository access**: Select "All repositories"
6. **Permissions > Repository permissions**:
   - Contents: Read and write
   - Metadata: Read
   - Pull requests: Read and write
7. Click "Generate token"
8. Copy the token and run `gus init` to save it

**Note:** Fine-grained tokens only work for the selected resource owner. To access multiple orgs, use a classic token instead.

## Token Storage

The token is stored securely in your system keychain (macOS Keychain, Windows Credential Manager, or Linux Secret Service).

## Troubleshooting

### Report command shows no company/org activity

If `gus report` only shows personal repos:

**For classic tokens:**
- Ensure your token has the `read:org` scope
- Regenerate the token with the correct scopes

**For fine-grained tokens:**
- Ensure the resource owner is set to your organization
- Ensure repository access includes org repos

### Permission denied errors

If you see "Resource not accessible by integration":
- The token is missing required scopes/permissions
- For fine-grained tokens: check the resource owner setting
