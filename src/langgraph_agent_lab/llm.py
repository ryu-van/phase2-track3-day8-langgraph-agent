"""LLM factory helper.

Provides a simple interface to create LLM clients for use in nodes.
Students should use this helper so the lab works with any supported provider.

Usage in nodes:
    from .llm import get_llm
    llm = get_llm()
    response = llm.invoke("Hello")
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
load_dotenv(override=True)
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import BaseModel, Field


class MockChatModel(BaseChatModel):
    """A mock chat model for offline local unit testing without active LLM keys."""
    
    model_name: str = "mock-model"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        user_msg = ""
        for m in reversed(messages):
            m_content = m.content if hasattr(m, "content") else str(m)
            user_msg = m_content
            break
            
        content = "Mock response"
        generation = ChatGeneration(message=AIMessage(content=content))
        return ChatResult(generations=[generation])

    def invoke(self, messages: Any, stop: Optional[List[str]] = None, **kwargs: Any) -> Any:
        user_msg = ""
        for m in reversed(messages):
            if isinstance(m, dict):
                m_content = m.get("content", "")
                m_role = m.get("role", "")
            else:
                m_content = m.content if hasattr(m, "content") else str(m)
                m_role = m.type if hasattr(m, "type") else "user"
            if m_role == "user" or m_role == "human":
                user_msg = m_content
                break

        if "Vague Query" in user_msg:
            content = "Could you please clarify which order or account you are referring to, and describe the exact issue you'd like us to fix?"
        elif "Approval" in user_msg:
            if "approved=False" in user_msg.replace(" ", "") or "approved=false" in user_msg.replace(" ", ""):
                content = "Unfortunately, we cannot proceed with your request as the approval was rejected."
            else:
                content = "We have successfully completed your request. The risky action has been executed and confirmed."
        elif "Tool Results" in user_msg:
            if "ERROR" in user_msg:
                content = "We encountered a temporary timeout error while trying to process your request."
            else:
                content = "We have successfully processed your request using our tools. Your order is active."
        else:
            content = "Here is the support ticket response: reset instructions sent."

        return AIMessage(content=content)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        class StructuredMock:
            def __init__(self, parent: Any, schema: Any):
                self.parent = parent
                self.schema = schema

            def invoke(self, messages: Any, **kwargs: Any) -> Any:
                user_msg = ""
                for m in reversed(messages):
                    if isinstance(m, dict):
                        m_content = m.get("content", "")
                        m_role = m.get("role", "")
                    else:
                        m_content = m.content if hasattr(m, "content") else str(m)
                        m_role = m.type if hasattr(m, "type") else "user"
                    if m_role == "user" or m_role == "human":
                        user_msg = m_content
                        break

                schema_name = self.schema.__name__ if hasattr(self.schema, "__name__") else str(self.schema)

                if "IntentClassification" in schema_name:
                    query_lower = user_msg.lower()
                    route = "simple"
                    risk_level = "low"

                    if "refund" in query_lower or "delete" in query_lower or "cancel" in query_lower:
                        route = "risky"
                        risk_level = "high"
                    elif "lookup" in query_lower or "status" in query_lower or "order" in query_lower:
                        route = "tool"
                    elif "fix it" in query_lower or "can you fix" in query_lower:
                        route = "missing_info"
                    elif "timeout" in query_lower or "failure" in query_lower or "error" in query_lower:
                        route = "error"

                    return self.schema(route=route, risk_level=risk_level)

                elif "Evaluation" in schema_name:
                    query_lower = user_msg.lower()
                    evaluation_result = "success"
                    if "error" in query_lower:
                        evaluation_result = "needs_retry"
                    return self.schema(evaluation_result=evaluation_result)

                return self.schema()

        return StructuredMock(self, schema)

    @property
    def _llm_type(self) -> str:
        return "mock_chat_model"


def get_llm(model: str | None = None, temperature: float = 0.0):
    """Create an LLM client from environment configuration.

    Checks for API keys in this order:
    1. GEMINI_API_KEY → ChatGoogleGenerativeAI
    2. OPENAI_API_KEY → ChatOpenAI
    3. ANTHROPIC_API_KEY → ChatAnthropic

    Override model with the `model` parameter or LLM_MODEL env var.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if gemini_key == "mock" or openai_key == "mock" or anthropic_key == "mock":
        return MockChatModel()

    if gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-google-genai") from exc
        return ChatGoogleGenerativeAI(
            model=model or os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            google_api_key=gemini_key,
            temperature=temperature,
        )

    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-openai") from exc
        base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
        return ChatOpenAI(
            model=model or os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=temperature,
            api_key=openai_key,
            base_url=base_url,
        )

    if anthropic_key:
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError("Install: pip install langchain-anthropic") from exc
        return ChatAnthropic(
            model=model or os.getenv("LLM_MODEL", "claude-sonnet-4-20250514"),
            temperature=temperature,
        )

    raise RuntimeError(
        "No LLM API key found. Set GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY in .env\n"
        "See .env.example for configuration."
    )
