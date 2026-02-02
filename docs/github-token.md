# GitHub Token Setup

## Fine-grained Token (Recommended)

1. Go to https://github.com/settings/personal-access-tokens/new
2. Set token name and expiration
3. Select repository access (specific repos or all)
4. Set permissions:
   - **Contents**: Read-only
   - **Pull requests**: Read and write
   - **Metadata**: Read-only (auto-selected)
5. Generate and copy token

## Classic Token

1. Go to https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `read:user`
4. Generate and copy token
