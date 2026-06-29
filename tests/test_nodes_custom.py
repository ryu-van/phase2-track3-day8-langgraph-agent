import pytest
from langgraph_agent_lab.nodes import tool_node, approval_node
from langgraph_agent_lab.state import ApprovalDecision


def test_tool_node_security_guard_unapproved():
    # Attempt to execute risky action without any approval object
    state = {
        "route": "risky",
        "attempt": 0,
        "query": "Delete user account",
        "approval": None,
    }
    with pytest.raises(ValueError, match="Security violation: attempt to execute risky action without approval."):
        tool_node(state)


def test_tool_node_security_guard_rejected():
    # Attempt to execute risky action with rejected approval decision
    state = {
        "route": "risky",
        "attempt": 0,
        "query": "Delete user account",
        "approval": ApprovalDecision(decision="reject", approved=False),
    }
    with pytest.raises(ValueError, match="Security violation: attempt to execute risky action without approval."):
        tool_node(state)


def test_tool_node_security_guard_approved():
    # Success case with approved decision
    state = {
        "route": "risky",
        "attempt": 0,
        "query": "Delete user account",
        "approval": ApprovalDecision(decision="approve", approved=True),
    }
    res = tool_node(state)
    assert "Mock tool execution successful" in res["tool_results"][0]


def test_approval_node_edit_decision(monkeypatch):
    # Setup state for approval node
    state = {
        "proposed_action": "Refund $50",
        "query": "Refund $50",
    }
    
    # Mock environment to simulate human interaction via interrupt
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    
    # We will mock the interrupt function call inside nodes.py
    # approval_node does: from langgraph.types import interrupt
    # Let's mock it inside langgraph.types or direct import in nodes
    import langgraph.types
    monkeypatch.setattr(langgraph.types, "interrupt", lambda payload: {"decision": "edit", "edited_query": "Refund $20", "comment": "Reduce amount"})
    
    res = approval_node(state)
    assert res["approval"].decision == "edit"
    assert res["approval"].edited_query == "Refund $20"
    assert res["query"] == "Refund $20"
