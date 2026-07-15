# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Agent 팩토리."""

from strands import Agent
from strands.models import BedrockModel
from strands.session import SessionManager

from backend.runtime.agent.tools.github import GitHubConfig, GitHubTools


def agent_factory(session_manager: SessionManager, github_config: GitHubConfig, model: BedrockModel) -> Agent:
    """GitHub 도구를 사용하는 에이전트를 생성한다."""
    github_tools = GitHubTools(config=github_config)

    return Agent(
        system_prompt="You are a helpful assistant with access to GitHub.",
        model=model,
        session_manager=session_manager,
        tools=[github_tools.get_github_user, github_tools.list_github_repos],
    )
