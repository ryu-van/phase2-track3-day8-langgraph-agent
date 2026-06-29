import os
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path

# Force interrupt mode in the web environment
os.environ["LANGGRAPH_INTERRUPT"] = "true"

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph.types import Command

app = FastAPI(title="LangGraph Agent Tester Lab")

# Setup the stateful graph checkpointer
checkpointer = build_checkpointer("memory")
graph = build_graph(checkpointer=checkpointer)

class RunRequest(BaseModel):
    thread_id: str
    query: Optional[str] = None
    decision: Optional[str] = None       # "approve", "reject", "edit"
    edited_query: Optional[str] = None

def get_thread_trace(thread_id: str) -> Dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    history = list(graph.get_state_history(config))
    
    # Sort chronologically (oldest first)
    history.reverse()
    
    trace: List[Dict[str, Any]] = []
    for snapshot in history:
        metadata = snapshot.metadata or {}
        writes = metadata.get("writes", {})
        if writes:
            for node, output in writes.items():
                # We skip showing internal transition states or end nodes in raw logs if empty
                trace.append({
                    "node": node,
                    "values": snapshot.values,
                    "writes": output,
                    "next": list(snapshot.next) if snapshot.next else [],
                    "step": metadata.get("step")
                })
                
    is_interrupted = False
    proposed_action = None
    next_nodes: List[str] = []
    
    latest_snapshot = history[-1] if history else None
    if latest_snapshot:
        next_nodes = list(latest_snapshot.next)
        if next_nodes and "approval" in next_nodes:
            is_interrupted = True
            proposed_action = latest_snapshot.values.get("proposed_action")
            
    return {
        "thread_id": thread_id,
        "is_interrupted": is_interrupted,
        "proposed_action": proposed_action,
        "next_nodes": next_nodes,
        "state": latest_snapshot.values if latest_snapshot else {},
        "trace": trace
    }

@app.get("/api/scenarios")
def get_scenarios():
    """Load and return the list of configured scenarios."""
    try:
        scenarios_path = Path("data/sample/scenarios.jsonl")
        if not scenarios_path.exists():
            return []
        scenarios = load_scenarios(scenarios_path)
        return [
            {
                "id": s.id,
                "query": s.query,
                "expected_route": s.expected_route.value,
                "requires_approval": s.requires_approval,
                "tags": s.tags
            }
            for s in scenarios
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/run")
def run_agent(req: RunRequest):
    """Start or resume the agent execution thread."""
    config = {"configurable": {"thread_id": req.thread_id}}
    
    try:
        # Check current status of the thread
        state_history = list(graph.get_state_history(config))
        is_interrupted = False
        if state_history and state_history[0].next:
            if "approval" in state_history[0].next:
                is_interrupted = True

        # 1. If we are currently interrupted and received a decision, resume
        if is_interrupted and req.decision:
            # Reconstruct the decision payload for the approval node
            # The node converts this dict into an ApprovalDecision object
            decision_payload = {
                "decision": req.decision,
                "approved": req.decision == "approve",
                "edited_query": req.edited_query,
                "reviewer": "web-interactive-user",
                "comment": f"Resumed via Web UI with decision: {req.decision}"
            }
            # Resume execution
            graph.invoke(Command(resume=decision_payload), config=config)
            
        # 2. Otherwise, start a new run
        elif req.query:
            initial_input = {
                "query": req.query,
                "thread_id": req.thread_id,
                "attempt": 0,
                "max_attempts": 3,
                "risk_level": "normal"
            }
            graph.invoke(initial_input, config=config)
        else:
            raise HTTPException(status_code=400, detail="Missing either 'query' (to start) or 'decision' (to resume).")
            
        return get_thread_trace(req.thread_id)
        
    except Exception as exc:
        # Return state trace even on failure to inspect error logs
        trace_data = get_thread_trace(req.thread_id)
        trace_data["error"] = str(exc)
        return trace_data

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serve the single-page testing dashboard."""
    html_file = Path(__file__).parent / "dashboard.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
        
    # Fallback template if file isn't created yet
    return "<h3>Dashboard HTML file is missing or building...</h3>"
