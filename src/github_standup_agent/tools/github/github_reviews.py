"""Tools for fetching code reviews from GitHub."""

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


def _fetch_review_for_pr(
    pr: dict[str, Any], filter_by: str, target_user: str
) -> dict[str, Any] | None:
    """Fetch review data for a single PR. Returns a review dict or None."""
    repo_name = pr.get("repository", {}).get("nameWithOwner", "")
    pr_number = pr.get("number")

    if not repo_name or not pr_number:
        return None

    try:
        review_result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo_name,
                "--json",
                "reviews,reviewDecision",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if review_result.returncode != 0 or not review_result.stdout.strip():
            return None

        review_data = json.loads(review_result.stdout)
        reviews = review_data.get("reviews", [])
        review_decision = review_data.get("reviewDecision")

        # Filter reviews based on mode
        if filter_by == "given":
            # Only include reviews from the target user
            user_reviews = [
                r
                for r in reviews
                if r.get("author", {}).get("login", "").lower() == target_user.lower()
            ]
            # Exclude self-reviews
            pr_author = pr.get("author", {}).get("login", "")
            if pr_author.lower() == target_user.lower():
                return None
        else:  # received
            # All reviews from others
            user_reviews = [
                r
                for r in reviews
                if r.get("author", {}).get("login", "").lower() != target_user.lower()
            ]

        if not user_reviews:
            return None

        return {
            "pr_number": pr_number,
            "pr_title": pr.get("title", ""),
            "pr_url": pr.get("url", ""),
            "pr_state": pr.get("state", ""),
            "repo": repo_name,
            "pr_author": (
                pr.get("author", {}).get("login", "") if filter_by == "given" else target_user
            ),
            "review_decision": review_decision,
            "reviews": [
                {
                    "reviewer": r.get("author", {}).get("login", "unknown"),
                    "state": r.get("state", "unknown"),
                    "submitted_at": r.get("submittedAt", ""),
                    "body_preview": (r.get("body", "") or "")[:100],
                }
                for r in user_reviews
            ],
        }

    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


@function_tool
def list_reviews(
    ctx: RunContextWrapper[StandupContext],
    filter_by: Annotated[
        Literal["given", "received"],
        "Filter mode: 'given' (reviews you gave on others' PRs), 'received' (reviews on your PRs)",
    ] = "given",
    username: Annotated[
        str | None,
        "GitHub username to search for. Defaults to current user.",
    ] = None,
    days_back: Annotated[int, "Number of days to look back"] = 7,
    repo: Annotated[
        str | None,
        "Filter to specific repo (e.g., 'owner/repo'). None for all repos.",
    ] = None,
    limit: Annotated[int, "Maximum number of PRs to fetch reviews for"] = 30,
) -> str:
    """
    Fetch code review activity with actual review states.

    Returns PRs with their review information including:
    - Review state: APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    - Reviewer names
    - Review timestamps

    filter_by options:
    - 'given': Reviews you submitted on other people's PRs
    - 'received': Reviews others gave on your PRs
    """
    target_user = username or ctx.context.github_username
    if not target_user:
        return "GitHub username not available. Cannot search reviews."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    all_reviews: list[dict[str, Any]] = []

    # Step 1: Find PRs based on filter
    if filter_by == "given":
        # PRs where this user reviewed
        cmd = [
            "gh",
            "search",
            "prs",
            "--reviewed-by",
            target_user,
            f"--updated=>={cutoff_date}",
            "--json",
            "number,title,url,state,repository,author",
            "--limit",
            str(limit),
        ]
    else:  # received
        # User's own PRs that might have reviews
        cmd = [
            "gh",
            "search",
            "prs",
            "--author",
            target_user,
            f"--updated=>={cutoff_date}",
            "--json",
            "number,title,url,state,repository",
            "--limit",
            str(limit),
        ]

    if repo:
        cmd.extend(["--repo", repo])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            if "API rate limit" in result.stderr:
                return "GitHub API rate limit reached. Try again later."
            return f"Error searching PRs: {result.stderr}"

        prs = json.loads(result.stdout) if result.stdout.strip() else []

    except subprocess.TimeoutExpired:
        return "Timeout while searching PRs for reviews."
    except json.JSONDecodeError:
        return "Error parsing PR data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."

    if not prs:
        return f"No PRs found with reviews ({filter_by}) in the last {days_back} days."

    # Step 2: Fetch actual review data for each PR (in parallel)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_fetch_review_for_pr, pr, filter_by, target_user): pr for pr in prs
        }
        for future in as_completed(futures):
            result_item = future.result()
            if result_item is not None:
                all_reviews.append(result_item)

    # Store in context
    ctx.context.collected_reviews = all_reviews

    if not all_reviews:
        return f"No reviews found ({filter_by}) in the last {days_back} days."

    # Group by repository
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for review_item in all_reviews:
        repo_name = review_item.get("repo", "unknown")
        if repo_name not in by_repo:
            by_repo[repo_name] = []
        by_repo[repo_name].append(review_item)

    # Format output
    filter_desc = "given by" if filter_by == "given" else "received by"
    total_reviews = sum(len(r["reviews"]) for r in all_reviews)
    lines = [
        f"Found {total_reviews} review(s) {filter_desc} {target_user} "
        f"across {len(all_reviews)} PR(s) in {len(by_repo)} repo(s):"
    ]

    for repo_name, repo_reviews in by_repo.items():
        lines.append(f"\n{repo_name}:")
        for item in repo_reviews:
            pr_state = item.get("pr_state", "").upper()
            decision = item.get("review_decision", "")
            decision_str = f" [{decision}]" if decision else ""

            # PR author info
            author_info = ""
            if filter_by == "given":
                author_info = f" by @{item.get('pr_author', '')}"

            lines.append(
                f"  #{item['pr_number']} [{pr_state}] {item['pr_title']}{author_info}{decision_str}"
            )

            # Individual reviews
            for review in item.get("reviews", []):
                reviewer = review.get("reviewer", "unknown")
                state = review.get("state", "unknown")
                submitted = review.get("submitted_at", "")[:10]

                reviewer_str = f"@{reviewer}" if filter_by == "received" else "You"
                lines.append(f"    - {reviewer_str}: {state} ({submitted})")

    return "\n".join(lines)
