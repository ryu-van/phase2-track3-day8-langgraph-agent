"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

import os
from pydantic import BaseModel, Field
from .llm import get_llm
from .state import AgentState, make_event, ApprovalDecision


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── TODO(student): implement ALL nodes below ────────────────────────


class IntentClassification(BaseModel):
    route: str = Field(
        description="The classified route. Must be one of: 'simple', 'tool', 'missing_info', 'risky', 'error'."
    )
    risk_level: str = Field(
        description="The risk level. Must be 'high' if the route is 'risky', and 'low' otherwise."
    )


class Evaluation(BaseModel):
    evaluation_result: str = Field(
        description="Must be 'needs_retry' if the latest tool result indicates a failure, timeout, or error. Must be 'success' if the tool successfully retrieved data."
    )


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM."""
    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentClassification)
    query = state.get("query", "")

    system_prompt = """You are an expert customer support classifier.
Analyze the user's query and classify it into exactly one of these categories:
- 'risky': Actions with side effects, such as refunds, account deletions, sending confirmation emails, cancellations, or destructive modifications.
- 'tool': Information lookups, such as order status lookup, tracking number lookup, search queries, or database searches.
- 'missing_info': Vague, short, or incomplete queries lacking actionable context (e.g. "Can you fix it?", "it's broken").
- 'error': Reports of system failures, timeouts, crashes, service unavailable messages, or error codes.
- 'simple': General questions, greetings, or help requests that can be answered directly without tools or side effects (e.g. "How do I reset my password?").

Priority order (if multiple apply, pick the highest priority):
risky > tool > missing_info > error > simple

Also evaluate the risk level:
- Set risk_level to 'high' if the route is 'risky'.
- Set risk_level to 'low' for all other routes.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query}
    ]
    classification = structured_llm.invoke(messages)
    route = classification.route
    risk_level = classification.risk_level

    return {
        "route": route,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"classified query as {route} (risk: {risk_level})")]
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call. Simulate transient failures for error-route scenarios."""
    attempt = state.get("attempt", 0)
    route = state.get("route")

    if route == "risky":
        approval = state.get("approval")
        is_approved = False
        if approval:
            if hasattr(approval, "decision"):
                is_approved = (approval.decision == "approve")
            elif isinstance(approval, dict):
                is_approved = (approval.get("decision") == "approve") or approval.get("approved", False)
        if not is_approved:
            raise ValueError("Security violation: attempt to execute risky action without approval.")

    if route == "error" and attempt < 2:
        result = "ERROR: Transient tool connection timeout (attempt < 2)."
    else:
        result = f"Mock tool execution successful for query: {state.get('query')}. Retrieved data: Order/Account ID 12345 active."

    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", f"Executed mock tool. Result: {result}")]
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate."""
    tool_results = state.get("tool_results", [])
    latest_result = tool_results[-1] if tool_results else ""

    llm = get_llm()
    structured_llm = llm.with_structured_output(Evaluation)

    system_prompt = """You are an LLM-as-judge evaluator.
Evaluate the latest tool execution result and decide if it was successful or if it encountered a transient error that needs a retry.
Respond with 'needs_retry' if there is any indication of an error, timeout, crash, or failure.
Respond with 'success' if the tool executed successfully and returned the requested information.
"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Latest Tool Result: {latest_result}"}
    ]
    evaluation = structured_llm.invoke(messages)
    eval_res = evaluation.evaluation_result

    return {
        "evaluation_result": eval_res,
        "events": [make_event("evaluate", "completed", f"Evaluated tool result: {eval_res}")]
    }


def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM."""
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")

    context = f"Query: {query}\n"
    if tool_results:
        context += f"Tool Results: {tool_results}\n"
    if approval:
        context += f"Approval: {approval}\n"

    system_prompt = """You are a helpful customer support agent.
Generate a polite, clear, and accurate final response to the user's query based ONLY on the provided context (including tool results and approval status if present).
If a tool result contains an error, state that we encountered a problem but try to be as helpful as possible.
If approval was rejected, explain politely why we couldn't proceed.
"""
    llm = get_llm()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context}
    ]
    response = llm.invoke(messages)
    final_answer = response.content

    return {
        "final_answer": final_answer,
        "events": [make_event("answer", "completed", "Generated final answer")]
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating."""
    query = state.get("query", "")

    system_prompt = """You are a customer support agent.
The user query is vague or missing key information.
Generate a specific, polite question to ask the user to clarify what they need.
Do not make assumptions or hallucinate details. Just ask them to clarify what they want to fix or what issue they are experiencing.
"""
    llm = get_llm()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Vague Query: {query}"}
    ]
    response = llm.invoke(messages)
    question = response.content

    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", f"Clarification requested: {question[:40]}")]
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval."""
    query = state.get("query", "")
    proposed_action = f"Proceed with risky operation (refund/account deletion/etc.) as requested: '{query}'."

    return {
        "proposed_action": proposed_action,
        "events": [make_event("risky_action", "completed", "Prepared risky action details")]
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step."""
    if os.getenv("LANGGRAPH_INTERRUPT") == "true":
        from langgraph.types import interrupt
        decision_data = interrupt({"proposed_action": state.get("proposed_action")})

        if isinstance(decision_data, dict):
            decision = ApprovalDecision(
                decision=decision_data.get("decision", "approve"),
                approved=decision_data.get("approved", True) if "approved" in decision_data else (decision_data.get("decision") == "approve"),
                edited_query=decision_data.get("edited_query"),
                reviewer=decision_data.get("reviewer", "human-reviewer"),
                comment=decision_data.get("comment", "")
            )
        elif isinstance(decision_data, ApprovalDecision):
            decision = decision_data
        else:
            decision = ApprovalDecision(decision="reject", approved=False, reviewer="system-fallback", comment=str(decision_data))
    else:
        decision = ApprovalDecision(decision="approve", approved=True, reviewer="mock-reviewer", comment="Auto-approved in mock mode")

    update = {
        "approval": decision,
        "events": [make_event("approval", "completed", f"Approval check: decision={decision.decision}")]
    }
    if decision.decision == "edit" and decision.edited_query:
        update["query"] = decision.edited_query

    return update


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt."""
    current_attempt = state.get("attempt", 0)
    new_attempt = current_attempt + 1
    err_msg = f"Attempt {new_attempt} failed due to transient failure."

    return {
        "attempt": new_attempt,
        "errors": [err_msg],
        "events": [make_event("retry", "completed", f"Incremented attempt to {new_attempt}")]
    }


def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded."""
    final_answer = "We are sorry, but we encountered repeated system issues while processing your request. Please try again later or contact our human support team directly."
    return {
        "final_answer": final_answer,
        "events": [make_event("dead_letter", "completed", "Escalated to dead letter")]
    }


def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event."""
    return {
        "events": [make_event("finalize", "completed", "workflow finished")]
    }
