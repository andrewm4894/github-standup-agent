# Example Standups

These are real examples from the team. Match this tone, format, and level of detail.

---

## Andy's Example

Did:
- docs pr about how to verify your deployments to encode my learnings from stuck plugin server deploy - <https://github.com/PostHog/runbooks/pull/340|runbooks#340>
- pr to ensure $ai_error_normalized is always set when expected - means can also see unknown error message errors in error tab naturally to dig into them - <https://github.com/PostHog/posthog/pull/45100|posthog#45100>
- add docs to temporal runbook about manually registering schedule in prod - <https://github.com/PostHog/runbooks/pull/341|runbooks#341>
- clean up some temporal schedule names for clustering stuff to have llma-trace-* prefix - <https://github.com/PostHog/posthog/commit/abc1234|commit>, <https://github.com/PostHog/posthog/commit/def5678|commit>
- bugfix to lazy import umap for clustering workflow as was breaking deploy - <https://github.com/PostHog/posthog/pull/45050|posthog#45050>, thread

Will Do:
- on monday morning will merge pr4 for clustering frontend and make sure all working as expected
- get trace summarization and clustering temporal workflows actually running away in project 2 and generating the events the clustering ui needs

---

## Andy's Example 2

Did:
- some new charts on go/llma-dash - spinner timings, top 50 orgs looked at trace
- will clean up as PH just randomly adds insights wherever it wants when adding to a dashboard
- merged js sdk for llma / error tracking - pr
- added some prom metrics for nodejs ai processing stuff - pr
- deep dive on why my code not deployed - learned some stuff - thread in dev
- adding allows_na option to evals pr should be ready for review - pr
- added demo video in pr desc showing why needed
- got posthog mcp running in claude and did some dogfooding of it vs PH AI

Will Do:
- if get clustering pr3 merged then will manually register both temporal workflows in prod in morning and watch them running
- i renamed the hourly summarization one so think need to maybe reregister it
- next steps in getting errors tab out of beta assuming plugin server stuff adding the $ai_error_normalized prop as expected
- follow up on some support tickets im assigned as waiting on
- one or two open prs in js for bug fixes i need review on

---

## Carlos's Example

Did:
- Merge costs update (PR)
- Refine playground + evals approach in regards to the gateway (thread)
- Implement playground rate limiting (PR)
- Iterate on playground BYOK

Will do:
- Finish playground BYOK
- Connect LLMA evals BYOK to LLM Gateway
- Implement live eval editor
- Fix eval language mismatch bug
- Support tasks as they come up

---

## Radu's Example

Did:
- Richard onboarding session + 1 on 1 + weekly sync
- PR reviews
- PM Superday interview
- Discussion around internal "ad" (context)
- Continued work on the query caching, but not working as I want it yet (draft)

Will do:
- Prep offsite schedule
- Prompt management SDK work
- Review docs examples for wizard (context)
- Create a workflow to send emails to churners (context)
- Add access control to LLMA (context)
