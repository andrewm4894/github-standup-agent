"""Tools for fetching items assigned to a user."""

import json
import subprocess
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def list_assigned_items(
    ctx: RunContextWrapper[StandupContext],
    username: Annotated[
        str | None,
        "GitHub username to search for. Defaults to current user.",
    ] = None,
    include_prs: Annotated[bool, "Include assigned PRs"] = True,
    include_issues: Annotated[bool, "Include assigned issues"] = True,
    repo: Annotated[
        str | None,
        "Filter to specific repo (e.g., 'owner/repo'). None for all repos.",
    ] = None,
    limit: Annotated[int, "Maximum number of items to return per type"] = 30,
) -> str:
    """
    Fetch all open items (issues and PRs) assigned to a user.

    Unlike list_prs/list_issues, this has NO date filter - it shows everything
    currently assigned regardless of recent activity. Useful for understanding
    what someone is responsible for or actively working on.
    """
    target_user = username or ctx.context.github_username
    if not target_user:
        return "GitHub username not available. Cannot search assigned items."

    results: dict[str, list[dict[str, Any]]] = {"issues": [], "prs": []}

    # Fetch assigned issues
    if include_issues:
        cmd = [
            "gh",
            "search",
            "issues",
            "--assignee",
            target_user,
            "--state",
            "open",
            "--json",
            "number,title,repository,state,url,labels,updatedAt",
            "--limit",
            str(limit),
        ]
        if repo:
            cmd.extend(["--repo", repo])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and result.stdout.strip():
                results["issues"] = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    # Fetch assigned PRs
    if include_prs:
        cmd = [
            "gh",
            "search",
            "prs",
            "--assignee",
            target_user,
            "--state",
            "open",
            "--json",
            "number,title,repository,state,url,labels,updatedAt,isDraft",
            "--limit",
            str(limit),
        ]
        if repo:
            cmd.extend(["--repo", repo])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and result.stdout.strip():
                results["prs"] = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    total = len(results["issues"]) + len(results["prs"])
    if total == 0:
        return f"No open items assigned to {target_user}."

    # Format output
    lines = [f"Found {total} open item(s) assigned to {target_user}:\n"]

    if results["issues"]:
        lines.append(f"\n📋 **Issues ({len(results['issues'])}):**")
        by_repo: dict[str, list[dict[str, Any]]] = {}
        for issue in results["issues"]:
            repo_name = issue.get("repository", {}).get("nameWithOwner", "unknown")
            if repo_name not in by_repo:
                by_repo[repo_name] = []
            by_repo[repo_name].append(issue)

        for repo_name, issues in by_repo.items():
            lines.append(f"\n  📁 {repo_name}:")
            for issue in issues:
                labels = issue.get("labels", [])
                label_str = ""
                if labels:
                    label_names = [lbl.get("name", "") for lbl in labels[:3]]
                    label_str = f" [{', '.join(label_names)}]"
                lines.append(f"    • #{issue['number']}: {issue['title']}{label_str}")

    if results["prs"]:
        lines.append(f"\n🔀 **Pull Requests ({len(results['prs'])}):**")
        by_repo = {}
        for pr in results["prs"]:
            repo_name = pr.get("repository", {}).get("nameWithOwner", "unknown")
            if repo_name not in by_repo:
                by_repo[repo_name] = []
            by_repo[repo_name].append(pr)

        for repo_name, prs in by_repo.items():
            lines.append(f"\n  📁 {repo_name}:")
            for pr in prs:
                draft = " (DRAFT)" if pr.get("isDraft") else ""
                labels = pr.get("labels", [])
                label_str = ""
                if labels:
                    label_names = [lbl.get("name", "") for lbl in labels[:3]]
                    label_str = f" [{', '.join(label_names)}]"
                lines.append(f"    • #{pr['number']}: {pr['title']}{draft}{label_str}")

    return "\n".join(lines)
