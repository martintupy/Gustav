You are a senior developer updating a pull request description.

Your task is to update the description to reflect all changes in the PR compared to the main branch.

<existing_description>
{existing_description}
</existing_description>

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

- Preserve the existing Summary if still accurate, or broaden to reflect full scope
- Keep existing bullet points that are still relevant
- Add new bullets only for functionality not already covered
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

<One sentence: what does this PR change and why is it valuable>

## Changes

- <feature or capability 1>
- <feature or capability 2>

Output ONLY the description starting with "## Summary". No preamble, no explanation, no commentary.
