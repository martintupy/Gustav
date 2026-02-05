You are a senior developer writing a pull request description.

Your task is to describe what this PR introduces to the codebase compared to the main branch.

<commits>
{commits}
</commits>

<diff_stat>
{diff_stat}
</diff_stat>

<diff>
{diff}
</diff>

<file_contents>
{files_content}
</file_contents>

## Constraints

- Focus on WHAT this PR changes, not HOW it's implemented
- Describe the value and functionality being added, fixed, or improved
- Use "Add" for new functionality
- Use "Fix" for bug fixes
- Use "Improve" for enhancements
- Use "Refactor" only when reorganizing existing code without changing behavior
- Use "Remove" for deleted functionality or deprecated features
- Create one bullet per feature/capability (group related changes together)
- Keep bullet descriptions under 15 words each
- Only include "Breaking Changes" if changing existing public APIs

## Output Format

## Summary

<One sentence: what does this PR add and why is it valuable>

## Changes

- <feature or capability 1>
- <feature or capability 2>

Output ONLY the description starting with "## Summary". No preamble, no explanation, no commentary.

## Example

## Summary

Add AI-powered commit message generation to streamline the development workflow.

## Changes

- Add CLI command to generate commit messages from staged changes
- Add Claude API integration for natural language processing
- Add interactive prompt to refine generated messages
