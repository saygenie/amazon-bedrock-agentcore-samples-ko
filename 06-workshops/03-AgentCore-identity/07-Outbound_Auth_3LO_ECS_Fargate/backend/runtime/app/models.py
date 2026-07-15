# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""요청 및 응답 모델."""

from pydantic import BaseModel, Field


class InvocationRequest(BaseModel):
    """Agent invocation request."""

    session_id: str = Field(..., description="Session identifier")
    user_message: str = Field(..., description="User message to the agent")
