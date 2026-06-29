"""Routing functions for conditional edges.

Each function takes AgentState and returns a string — the name of the next node.
These strings MUST match node names registered in graph.py.
"""

from __future__ import annotations

from .state import AgentState


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node."""
    r = state.get("route")
    mapping = {
        "simple": "answer",
        "tool": "tool",
        "missing_info": "clarify",
        "risky": "risky_action",
        "error": "retry"
    }
    return mapping.get(r, "answer")


def route_after_evaluate(state: AgentState) -> str:
    """Decide if tool result is satisfactory or needs retry."""
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry the tool or give up."""
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    if attempt < max_attempts:
        return "tool"
    return "dead_letter"


def route_after_approval(state: AgentState) -> str:
    """Route based on human approval decision."""
    approval = state.get("approval")
    decision = "approve"
    if approval:
        if hasattr(approval, "decision"):
            decision = approval.decision
        elif isinstance(approval, dict):
            decision = approval.get("decision")
            if not decision:
                is_approved = approval.get("approved", False)
                decision = "approve" if is_approved else "reject"
        else:
            is_approved = getattr(approval, "approved", False)
            decision = "approve" if is_approved else "reject"

    if decision == "approve":
        return "tool"
    elif decision == "edit":
        return "intake"
    else:
        return "clarify"
