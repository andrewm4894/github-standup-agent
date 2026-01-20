# Example Standups

Copy this file to `~/.config/standup-agent/examples.md` and customize with your own examples.

```bash
cp examples.example.md ~/.config/standup-agent/examples.md
standup config --edit-examples
```

The AI uses these examples as "few-shot prompts" to match your preferred tone, format, and level of detail.

NOTE: For Slack, use short link labels like `<url|pr>`, `<url|issue>` for readability.

---

## Example 1 - Backend Engineer

Did:
- merged api rate limiting implementation - pr
- pr to fix null pointer in auth middleware - also added better error logging - pr
- added docs to runbook about manual cache invalidation in prod - pr
- refactored config loader to support env-specific overrides - pr
- bugfix for lazy loading that was breaking cold starts - pr, thread

Will Do:
- once rate limiting pr is deployed will monitor metrics and adjust thresholds
- get feature flag system running in staging and verify events are flowing
- follow up on open support tickets

---

## Example 2 - Full Stack Engineer

Did:
- some new dashboard charts for user analytics - load times, top features used
- merged react sdk update for error tracking - pr
- added prometheus metrics for background job processing - pr
- deep dive on why deploy was stuck - learned about config caching - thread in dev
- eval criteria pr should be ready for review - pr
- added demo video in pr description showing the new flow

Will Do:
- if analytics pr gets approved will deploy to staging in morning
- next steps on getting new feature out of beta
- review teammate's pr for the settings redesign

---

## Example 3 - Product Engineer

Did:
- merge pricing tier update (PR)
- refine onboarding flow approach based on user feedback (thread)
- implement form validation (PR)
- iterate on BYOK integration

Will do:
- finish BYOK integration
- connect billing to payment gateway
- implement usage tracking
- fix timezone display bug
- support tasks as they come up

---

## Example 4 - Tech Lead

Did:
- new hire onboarding session + 1:1 + weekly sync
- PR reviews
- interview panel for senior role
- discussion around team priorities (context)
- continued work on query optimization - still debugging cache misses (draft)

Will do:
- prep quarterly planning docs
- sdk documentation updates
- review architecture proposal (context)
- set up monitoring alerts for new service (context)
