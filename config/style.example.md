# Standup Style Guide

## Format
- Use "Did:" and "Will Do:" sections (NOT "Yesterday/Today" or "Recently/Next")
- No "Blockers" section unless explicitly needed - mention blockers inline if relevant
- Keep everything as bullet points with `-`

## Content Style
- Be concise but include enough context for team visibility
- Reference PRs, threads, tickets, and contexts with ` - pr`, ` - thread`, ` - context` suffixes
- Include specific project names, tools, and technical details
- Mention collaboration with team members when relevant
- Use casual/technical tone - not overly formal

## Bullet Point Patterns
- Start with action verb in lowercase (merged, added, fixed, refactored, working on)
- Include what was done AND why/outcome when notable
- Group related items conceptually
- Link to relevant discussions/threads for context

## Linking Guidelines
- **Always link PRs, commits, issues, and threads with actual URLs** - never just say "- pr" or "(commit)" without the link
- Use Slack link format: `<https://github.com/org/repo/pull/123|repo#123>` for PRs
- Use Slack link format: `<https://github.com/org/repo/commit/abc123|commit>` for commits
- Group multiple related links: `(commit, commit)` or `(pr, pr)` with each linked
- If a commit doesn't have a PR yet, still link to the commit directly

## Examples of Good Bullets
- "merged js sdk for llma / error tracking - <https://github.com/PostHog/posthog/pull/123|posthog#123>"
- "tweaked provider timeout config - <https://github.com/PostHog/posthog/commit/abc123|commit>"
- "deep dive on why my code not deployed - learned some stuff - thread in dev"
- "clean up temporal schedule names - <https://github.com/PostHog/posthog/pull/456|pr>, <https://github.com/PostHog/posthog/pull/457|pr>"
- "if get clustering pr3 merged then will manually register both temporal workflows in prod"

## What to Include
- PRs merged/opened/reviewed
- Notable code changes and their purpose
- Debugging sessions and learnings
- Cross-team collaboration
- Specific next steps with conditional context (e.g., "if X then Y")

## What to Skip
- Routine meetings unless notable outcome
- Minor housekeeping unless significant
- Excessive detail on standard work
