"""Tool for fetching cross-repository activity via GraphQL."""

import json
import subprocess
from typing import Annotated

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext

ACTIVITY_QUERY = """
query($username: String!) {
  user(login: $username) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""


@function_tool
def get_activity_summary(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int, "Number of days to summarize"] = 7,
) -> str:
    """
    Get a summary of GitHub activity across all repositories.

    Uses GraphQL to fetch contribution statistics including commits,
    PRs, reviews, and issues.
    """
    username = ctx.context.github_username

    if not username:
        return "GitHub username not available. Cannot fetch activity summary."

    try:
        result = subprocess.run(
            [
                "gh", "api", "graphql",
                "-f", f"query={ACTIVITY_QUERY}",
                "-F", f"username={username}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return f"Error fetching activity: {result.stderr}"

        data = json.loads(result.stdout)
        user_data = data.get("data", {}).get("user", {})
        contributions = user_data.get("contributionsCollection", {})

        if not contributions:
            return "No contribution data available."

        # Get recent days from calendar
        calendar = contributions.get("contributionCalendar", {})
        weeks = calendar.get("weeks", [])

        # Flatten and get recent days
        all_days = []
        for week in weeks:
            all_days.extend(week.get("contributionDays", []))

        recent_days = all_days[-days_back:] if all_days else []
        recent_total = sum(d.get("contributionCount", 0) for d in recent_days)

        # Format summary
        lines = [
            "📊 GitHub Activity Summary\n",
            f"Total contributions (this year): {calendar.get('totalContributions', 0)}",
            f"Contributions (last {days_back} days): {recent_total}\n",
            "Breakdown (this year):",
            f"  • Commits: {contributions.get('totalCommitContributions', 0)}",
            f"  • Pull Requests: {contributions.get('totalPullRequestContributions', 0)}",
            f"  • PR Reviews: {contributions.get('totalPullRequestReviewContributions', 0)}",
            f"  • Issues: {contributions.get('totalIssueContributions', 0)}",
        ]

        if recent_days:
            lines.append("\nRecent activity:")
            for day in recent_days[-7:]:  # Last 7 days max
                count = day.get("contributionCount", 0)
                date = day.get("date", "")
                bar = "█" * min(count, 10)
                lines.append(f"  {date}: {bar} ({count})")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "Timeout while fetching activity summary."
    except json.JSONDecodeError:
        return "Error parsing activity data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."
