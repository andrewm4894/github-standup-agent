#!/bin/bash
exec uv run --directory /Users/andrewmaguire/Documents/GitHub/github-standup-agent \
    python -m github_standup_agent.mcp_server
