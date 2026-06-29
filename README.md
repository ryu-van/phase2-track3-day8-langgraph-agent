# LangGraph Support-Ticket Agent Lab

A completed, production-ready LangGraph orchestration agent designed to process customer support tickets. The agent features state management, conditional routing, retry loops, a strict security guard for sensitive operations, persistence checkpointers, and a premium **Interactive Web UI Sandbox**.

---

## 🏗️ Architecture & Nodes Workflow

The orchestration agent consists of **11 distinct nodes** mapped via state-based conditional routing:

```
[START] ──> intake ──> classify
                         │
                         ├── [simple] ───────> answer ─────────────────────────┐
                         ├── [tool] ─────────> tool ──> evaluate ──> [success]─┤
                         │                       ^          │                  │
                         │                       │          └── [needs_retry]  │
                         │                       │                  │          │
                         │                       └─────────────── retry        │
                         │                                          │          │
                         │                                   [max_attempts]    │
                         │                                          v          │
                         │                                     dead_letter     │
                         │                                          │          │
                         ├── [missing_info] ─> clarify ────────────────────────┼──> finalize ──> [END]
                         ├── [risky] ────────> risky_action ──> approval       │
                         │                                         │           │
                         │                                   [approved]        │
                         │                                         v           │
                         │                                       tool          │
                         │                                         │           │
                         │                                   [rejected]        │
                         │                                         v           │
                         │                                      clarify        │
                         │                                         │           │
                         │                                   [edited]          │
                         │                                         v           │
                         │                                      intake         │
                         └── [error] ────────> retry ──────────────────────────┘
```

### Nodes Definition:
1. **`intake`**: Normalizes user input and structures initial conversation history.
2. **`classify`**: Uses LLM structured output (`.with_structured_output()`) to categorize tickets.
3. **`tool`**: Executes requested backend operations (features transient error simulation).
4. **`evaluate`**: Judges tool results quality using an LLM-as-a-judge model.
5. **`answer`**: Generates grounded, polite responses using LLM based on context.
6. **`clarify`**: Asks specific questions when queries are vague.
7. **`risky_action`**: Formulates proposed description for sensitive actions (refunds/account deletions).
8. **`approval`**: Interrupts thread execution via `interrupt()` for human action review.
9. **`retry`**: Tracks and increments execution attempts, handling transient issues.
10. **`dead_letter`**: Logs critical failures when max attempts are reached.
11. **`finalize`**: Emits audit trace reports and concludes the execution.

---

## 🖥️ Interactive Web UI Sandbox

We built a beautiful, glassmorphic **Live Sandbox Dashboard** to test and verify the graph and its human-in-the-loop paths.

### Features
* **Live Sandbox Editor**: Submit custom ticket queries and watch the execution path update in real-time.
* **Test Scenarios Drawer**: One-click running for all 7 pre-defined scenarios (`S01` to `S07`).
* **Visual Graph Flow Trace**: Chronological visualization of active, completed, and paused nodes.
* **Review Required Panel**: When execution reaches a risky action, a warning panel prompts the reviewer to choose **Approve**, **Reject**, or **Edit Query** (which resumes the workflow with the modified text).
* **State & Log Inspectors**: Click on any node inside the path to view its specific state writes, or inspect the full state JSON snapshot.

### Launching the Dashboard:
Ensure dependencies are installed and `.env` has your API key configured:

```bash
# 1. Run directly on the host:
python -m langgraph_agent_lab.cli serve --port 8000

# 2. Run inside the Docker container:
docker run -p 8000:8000 --env-file .env -v "${PWD}/outputs:/app/outputs" -v "${PWD}/reports:/app/reports" langgraph-agent-lab python -m langgraph_agent_lab.cli serve --host 0.0.0.0 --port 8000
```
Then open `http://localhost:8000` in your web browser.

---

## 📦 Docker Container Setup

The application is fully containerized. To build and run validation scenarios inside the container:

```bash
# Build the optimized image
docker build -t langgraph-agent-lab .

# Run grading scenarios and output reports
docker run --env-file .env -v "${PWD}/outputs:/app/outputs" -v "${PWD}/reports:/app/reports" langgraph-agent-lab
```

---

## 🧪 Local Testing & Grading

You can run validation tests and compile the local lab report:

```bash
# Install local package in editable mode
pip install -e .

# Run pytest unit tests
pytest

# Execute CLI scenarios and generate metrics/reports
python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json

# Validate generated metrics.json file
python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json
```

---

## 📁 Key File Locations

* **FastAPI Server & Frontend**: `src/langgraph_agent_lab/web.py` & `src/langgraph_agent_lab/dashboard.html`
* **Graph Definition**: `src/langgraph_agent_lab/graph.py`
* **Node Actions**: `src/langgraph_agent_lab/nodes.py`
* **Routing Rules**: `src/langgraph_agent_lab/routing.py`
* **State Schema**: `src/langgraph_agent_lab/state.py`
* **Lab Report**: `reports/lab_report.md`
