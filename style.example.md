# Standup Style Guide

Copy this file to `~/.config/standup-agent/style.md` and customize it.

```bash
cp style.example.md ~/.config/standup-agent/style.md
standup config --edit-style
```

---

## Format

- Use "Did:" and "Will Do:" sections (NOT "Yesterday/Today" or "Recently/Next")
- No separate "Blockers" section - mention blockers inline if relevant
- Keep everything as bullet points with `-`

## Content Style

- Be concise but include enough context for team visibility
- Reference PRs, threads, tickets with ` - pr`, ` - thread`, ` - ticket` suffixes
- Include specific project names, tools, and technical details
- Mention collaboration with team members when relevant
- Use casual/technical tone - not overly formal

## Bullet Point Patterns

- Start with action verb in lowercase (merged, added, fixed, refactored, working on)
- Include what was done AND why/outcome when notable
- Group related items conceptually
- Link to relevant discussions/threads for context

## Examples of Good Bullets

- "merged authentication sdk update - pr"
- "deep dive on deploy issue - learned about config caching - thread in dev"
- "added metrics for api processing - pr"
- "if feature flag pr gets merged then will enable in staging"
- "docs and next steps for beta rollout"

## What to Include

- PRs merged/opened/reviewed
- Notable code changes and their purpose
- Debugging sessions and learnings
- Cross-team collaboration
- Specific next steps with conditional context

## What to Skip

- Routine meetings unless notable outcome
- Minor housekeeping unless significant
- Excessive detail on standard work
