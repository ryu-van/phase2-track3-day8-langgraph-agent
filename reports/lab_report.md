# Day 08 Lab Report

## 1. Team / student

- Name: 2A202600725-Nguyễn Văn Duy
- Repo/commit: local-run
- Date: 2026-06-29

## 2. Architecture

The support-ticket orchestration workflow is implemented using LangGraph.
It consists of 11 nodes linked via fixed and conditional edges:
1. `intake`: Normalizes the user query.
2. `classify`: Uses LLM with structured output to map intent into 5 predefined categories.
3. `tool`: Mock api execution with transient error simulation.
4. `evaluate`: Evaluates tool outputs (LLM-as-judge).
5. `answer`: Grounded response generation using LLM.
6. `clarify`: Requests additional details when query lacks context.
7. `risky_action`: Prepares sensitive operations (refund/deletion) for approval.
8. `approval`: Pauses graph execution using `interrupt()` if HITL is enabled, otherwise mock approves.
9. `retry`: Increments retry counter and saves error logs.
10. `dead_letter`: Handles terminal failures after max retries are reached.
11. `finalize`: Audits and logs completion event.

## 3. State schema

State is stored inside `AgentState` TypedDict. Key fields are annotated as follows:

| Field | Reducer | Why |
|---|---|---|
| messages | append | audit conversation/events |
| route | overwrite | current classified route |
| risk_level | overwrite | current query risk level |
| attempt | overwrite | track current retry attempts |
| max_attempts | overwrite | define attempt boundary |
| final_answer | overwrite | stores final user response |
| evaluation_result | overwrite | drives retry loop gate |
| pending_question | overwrite | stores clarification question |
| proposed_action | overwrite | stores details of risky operation |
| approval | overwrite | stores HITL approval decision |
| tool_results | append | history of tool outputs |
| errors | append | history of errors encountered |
| events | append | history of graph execution steps |

## 4. Scenario results

Summarized performance statistics:
- **Total Scenarios**: 7
- **Success Rate**: 100.00%
- **Average Nodes Visited**: 6.57
- **Total Retries**: 4
- **Total Interrupts**: 2

### Detailed Metrics:

| Scenario | Expected route | Actual route | Success | Retries | Interrupts | Approval Result |
|---|---|---|---:|---:|---:|---:|
| S01_simple | simple | simple | Yes | 0 | 0 | N/A |
| S02_tool | tool | tool | Yes | 0 | 0 | N/A |
| S03_missing | missing_info | missing_info | Yes | 0 | 0 | N/A |
| S04_risky | risky | risky | Yes | 0 | 1 | approve |
| S05_error | error | error | Yes | 3 | 0 | N/A |
| S06_delete | risky | risky | Yes | 0 | 1 | approve |
| S07_dead_letter | error | error | Yes | 1 | 0 | N/A |


## 5. Failure analysis

1. **Transient Tool/API Failures**:
   - Simulated under the `error` route. The tool node raises a mock `ERROR` for the first two attempts. The `evaluate` node (using LLM-as-judge) detects the error and routes the state to the `retry` node. The `route_after_retry` checks if the attempt limit has been reached. If `attempt < max_attempts`, it loops back to the `tool` node; otherwise, it branches to `dead_letter` to avoid infinite loops.
2. **Risky Actions Without Human Approval**:
   - Queries with side effects (like refunds or deletes) are routed to `risky_action` and then to the `approval` node. If `LANGGRAPH_INTERRUPT` is enabled, the graph interrupts and halts execution. If resumes are rejected, the route falls back to `clarify` (instead of `tool`), ensuring no destructive actions occur without consent.

## 6. Persistence / recovery evidence

We implemented `SqliteSaver` in `persistence.py`. It establishes a connection to `checkpoints.db` and configures it to run in WAL journal mode. State persistence allows resuming aborted workflows (e.g. from an interrupt or crash) using the configured `thread_id` and the checkpointer.

## 7. Extension work

- **SQLite Checkpointer**: Implemented SQLite-based persistence that supports connection objects and WAL mode in `persistence.py`.
- **LLM-as-Judge Evaluation**: Implemented an LLM structured evaluator in `evaluate_node` to determine tool execution status.

## 8. Improvement plan

If we had one more day, we would:
1. Build a Streamlit UI to review pending tasks and trigger resumes dynamically.
2. Build parallel fan-out tool calling using `Send()` to run multiple lookups simultaneously.
