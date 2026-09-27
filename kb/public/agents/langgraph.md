---
topic: agents/langgraph
priority: P3
applies_to: "LangGraph (Python `langgraph` package, MIT licence); docs retrieved 2026-09-26"
retrieved_utc: 2026-09-27
sources: [S-bivxzhtv, S-thsymqx6, S-pxkxmmn5, S-5pmoh6xp, S-j54mtzby, S-dir5xyqr, S-6buofrld, S-43xr27dp, S-woho7bmc, S-ujkfhzif, S-bygurlbr]
status: complete
---

# LangGraph

## Summary
- **LangGraph** is LangChain's low-level, open-source orchestration framework (`pip install
  langgraph`, package `langgraph`, **MIT** licence, latest seen `1.2.12`) for building durable,
  stateful, multi-actor agent workflows as graphs. [DOC S-6buofrld]
- A workflow is a **`StateGraph`**: a shared **state** schema (TypedDict, dataclass or Pydantic
  model), **nodes** (functions that read/update state), and **edges** (fixed or conditional) that
  decide which node runs next; execution uses a Pregel-style message-passing model in discrete
  **super-steps**, and the graph must be **`.compile()`**d before use. [DOC S-bivxzhtv]
- **Checkpointers** (`InMemorySaver`, `SqliteSaver`/`AsyncSqliteSaver`, `PostgresSaver`/
  `AsyncPostgresSaver`) persist a **thread**'s state after each super-step, giving short-term
  memory, fault tolerance, "time travel" and **human-in-the-loop** pauses via `interrupt()` /
  `Command(resume=...)`. [DOC S-thsymqx6, S-j54mtzby, S-pxkxmmn5]
- MCP tools are wired into LangChain/LangGraph agents through `langchain[mcp]`
  (successor to the older separate `langchain-mcp-adapters` package as of v1.4.0). [DOC S-dir5xyqr]
- **LangGraph Platform** was rebranded **LangSmith Deployment**: a managed service for running
  LangGraph agents in production (durable execution, state, streaming, a Studio IDE), separate from
  the open-source `langgraph` framework itself. [DOC S-43xr27dp] Deployment needs the paid Plus plan or
  above, and self-hosting needs an Enterprise plan and its licence key (details under Facts).
  [DOC S-woho7bmc, S-ujkfhzif]

## Facts

### Package, graph construction
- Install: `pip install langgraph` or `uv add langgraph`; licence **MIT**; latest version observed
  on PyPI (2026-09-26): `1.2.12`. [DOC S-6buofrld]
- `StateGraph` state can be a `TypedDict`, `dataclass`, or Pydantic `BaseModel`; separate input and
  output schemas can be declared alongside the internal schema. [DOC S-bivxzhtv]
- **Reducers**: annotate a state field with `Annotated[type, reducer_fn]` (e.g. `operator.add`) so a
  node's returned update is merged into existing state instead of the default behaviour, which
  replaces the field's value outright. [DOC S-bivxzhtv]
- Edges: `add_edge()` for a fixed transition, `add_conditional_edges()` with a routing function for
  dynamic branching. `START` and `END` are virtual nodes marking entry and termination. [DOC S-bivxzhtv]
- **`Command`**: a node return value that combines a state `update` with routing (`goto`) in one
  object. **`Send`**: returned from a conditional edge to invoke a node once per item, each call with
  its own input state, for map-reduce-style fan-out. [DOC S-bivxzhtv]
- The graph **must** be compiled with `.compile()` before invocation; compilation validates the
  graph structure and wires in runtime settings such as the checkpointer. [DOC S-bivxzhtv]

### Checkpointers and threads
- `InMemorySaver` (`from langgraph.checkpoint.memory import InMemorySaver`, ships with the
  `langgraph-checkpoint` dependency) stores checkpoints in RAM only — lost on process restart; for
  experimentation, not production. [DOC S-j54mtzby, S-thsymqx6]
- `SqliteSaver` / `AsyncSqliteSaver` live in the separate **`langgraph-checkpoint-sqlite`** package;
  local file-based storage, intended for development. [DOC S-j54mtzby, S-thsymqx6]
- `PostgresSaver` / `AsyncPostgresSaver` live in the separate **`langgraph-checkpoint-postgres`**
  package; production-grade, used in LangSmith itself. Construct with
  `PostgresSaver.from_conn_string("postgresql://...")` and call `.setup()` once to create the
  checkpoint schema before first use. [DOC S-j54mtzby]
- A **`thread_id`** (in `config={"configurable": {"thread_id": ...}}`) is required for a
  checkpointer to save or resume state; it must stay under 255 characters to avoid database errors
  with `PostgresSaver`. Reusing a `thread_id` resumes that thread's latest checkpoint; a new value
  starts a fresh thread with empty state. [DOC S-thsymqx6, S-pxkxmmn5]
- **`checkpoint_ns`** (checkpoint namespace) is the empty string `""` for the parent graph and
  `"<node_name>:<uuid>"` for a subgraph, nesting as `"outer:uuid|inner:uuid"` for nested subgraphs —
  relevant when troubleshooting subgraph state isolation. [DOC S-j54mtzby]
- State inspection/editing: `get_state(config)` returns the latest checkpoint as a `StateSnapshot`;
  `update_state(config, values)` writes a new checkpoint with edited values; `get_state_history(config)`
  returns the thread's checkpoints newest-first — the basis for "time travel" (replaying or forking
  from an earlier checkpoint). [DOC S-j54mtzby]
- Checkpointers distinguish short-term, **thread-scoped** memory (checkpoints) from long-term,
  **cross-thread** memory (a separate `store` abstraction, for data shared across threads). [DOC S-thsymqx6]

### Interrupts and human-in-the-loop
- `interrupt(payload)` pauses graph execution at that point in a node and surfaces `payload`
  (must be JSON-serializable) to the caller; it requires a checkpointer and a `thread_id` in config
  to work. [DOC S-pxkxmmn5]
- Resuming: invoke the graph again with `Command(resume=<value>)`; `<value>` becomes the return
  value of the paused `interrupt()` call inside the node. [DOC S-pxkxmmn5]
- Documented human-in-the-loop patterns: approval before a critical/irreversible action (e.g. an
  API call or a destructive tool), review-and-edit of an LLM output before it proceeds, explicit
  tool-call approval before execution, and re-prompting on invalid input. [DOC S-pxkxmmn5]
- Correctness rules for `interrupt()`: do not wrap the call in a bare `try/except` (that swallows
  the internal exception the pause relies on); keep the order of `interrupt()` calls within a node
  consistent across resumes; place side effects *after* the `interrupt()` call, not before it
  (they would otherwise re-run on resume); avoid `while True` loops containing `interrupt()` — use
  conditional edges for repeated pauses instead. [DOC S-pxkxmmn5]

### Durable execution and streaming
- Durability is set per graph execution call (`durability=`) with three modes: `"exit"` (persists
  only when execution exits: success, error, or a human-in-the-loop interrupt — best performance, no
  recovery from a mid-run crash), `"async"` (persists asynchronously while the next step executes —
  small risk of lost checkpoints on a crash), and `"sync"` (persists synchronously before the next
  step starts — highest durability, some performance overhead). [DOC S-j54mtzby]
- `.stream()` / `.astream()` accept a `stream_mode`, either a single string or a list of modes:
  `values` (full state after each step), `updates` (per-node state updates after each step; multiple
  updates in one super-step stream separately), `messages` (LLM token, metadata tuples),
  `custom` (arbitrary data emitted from a node via `get_stream_writer`), `checkpoints` and `tasks`
  (checkpoint/task start-finish events; both require a checkpointer), and `debug` (combines
  `checkpoints` and `tasks` with extra metadata). [DOC S-5pmoh6xp]
- With multiple `stream_mode`s and `version="v2"`, every streamed chunk is a `StreamPart` dict with
  `type`, `ns`, and `data` fields; consumers should branch on `chunk["type"]` rather than unpacking
  a fixed tuple shape. [DOC S-5pmoh6xp]

### MCP integration
- LangChain/LangGraph agents call MCP tools via the `langchain[mcp]` extra
  (`pip install 'langchain[mcp]'` / `uv add 'langchain[mcp]'`); this is the current path as of
  LangChain v1.4.0, replacing the previously separate `langchain-mcp-adapters` package. [DOC S-dir5xyqr]
- Migration from `langchain-mcp-adapters`: uninstall it and install `langchain[mcp]>=1.4.0`; the
  `langchain.mcp` namespace is beta and raises `LangChainBetaWarning` on import. `MultiServerMCPClient`
  becomes `MCPAdapter` (an async context manager with `list_tools()`), and helpers are renamed, e.g.
  `convert_mcp_tool_to_langchain_tool` to `as_langchain_tool`. [DOC S-bygurlbr]
- The MCP adapter infers transport automatically from the target passed to it: an HTTP/HTTPS URL
  is reached over **streamable HTTP**; a script path is launched as a **subprocess over stdio**;
  an in-process **FastMCP** server instance is connected in-memory (no subprocess or socket); or a
  pre-built transport object can be passed directly. [DOC S-dir5xyqr]

### LangGraph Platform / LangSmith Deployment
- LangGraph itself is the open-source framework; **LangSmith Deployment** (the current name,
  rebranded from "LangGraph Platform") is LangChain's managed service for running LangGraph agents
  in production, offering one-click deployment with durable execution, state and streaming, plus a
  **Studio** IDE for visual debugging. [DOC S-43xr27dp]
- LangSmith pricing (read 2026-09-27): Developer $0 for one seat with up to 5k base traces a month;
  Plus $39 per seat per month with up to 10k base traces, access to Deployment and one free small
  serverless deployment; Enterprise custom-priced with self-hosted and hybrid deployment options.
  [DOC S-woho7bmc]
- Self-hosted LangSmith Deployment requires an Enterprise plan and the LangSmith licence key delivered
  with it. [DOC S-ujkfhzif]

## Reference
- Cross-link: `agents/microsoft-agent-framework.md` — Microsoft Agent Framework's own typed
  `Workflow` graph model, checkpointing, and `ctx.request_info()` human-in-the-loop pattern are the
  closest analogue to LangGraph's `StateGraph` + `interrupt()`/`Command(resume=...)`; see that
  article's Summary and "Human-in-the-loop (HITL)" fact for the comparison. A back-link line has
  been added to `agents/microsoft-agent-framework.md`'s Reference section.
- `claude/agent-sdk.md` — for the Claude Agent SDK's own agent-loop and tool-approval model, to
  compare with LangGraph's graph-based orchestration.
- `mcp/tools.md` — the MCP-level human-in-the-loop expectation (servers/clients SHOULD keep a
  human able to deny tool invocations), which LangGraph's `interrupt()` pattern can implement
  at the application layer.

## Examples

Graph with a **human-approval interrupt before a device-wipe tool call**, using a Postgres
checkpointer:

- SNIPPET: a `StateGraph` that pauses with `interrupt()` for reviewer approval before a device-wipe
  node, persisted with `PostgresSaver` and resumed with `Command(resume=...)`; context: LangGraph,
  `langgraph-checkpoint-postgres`; checked: no [DER S-bivxzhtv, S-thsymqx6, S-pxkxmmn5, S-j54mtzby:
  StateGraph/compile, checkpointer persistence, interrupt()/Command(resume=...), and
  PostgresSaver.from_conn_string()/.setup() each documented separately, composed here into one
  example]
```python
import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt


class WipeState(TypedDict):
    device_id: str
    log: Annotated[list[str], operator.add]


def request_wipe_approval(state: WipeState) -> WipeState:
    decision = interrupt(
        {
            "action": "wipe_device",
            "device_id": state["device_id"],
            "message": f"Approve remote wipe of {state['device_id']}?",
        }
    )
    if decision != "approve":
        return {"log": ["wipe denied by reviewer"]}
    return {"log": ["wipe approved by reviewer"]}


def wipe_device(state: WipeState) -> WipeState:
    # side effect only after the interrupt/approval above has been resolved
    return {"log": [f"wipeDevice() called for {state['device_id']}"]}


def route_after_approval(state: WipeState) -> str:
    return END if state["log"][-1].startswith("wipe denied") else "wipe_device"


builder = StateGraph(WipeState)
builder.add_node("request_wipe_approval", request_wipe_approval)
builder.add_node("wipe_device", wipe_device)
builder.add_edge(START, "request_wipe_approval")
builder.add_conditional_edges(
    "request_wipe_approval", route_after_approval, ["wipe_device", END]
)
builder.add_edge("wipe_device", END)

# placeholder DSN: real deployments use a secrets manager, never a literal password
DSN = "postgresql://kb:***@db.corp.example.com/agents"
with PostgresSaver.from_conn_string(DSN) as checkpointer:
    checkpointer.setup()  # one-time: creates the checkpoint schema
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "wipe-PL-LT-00123"}}
    graph.invoke({"device_id": "PL-LT-00123", "log": []}, config=config)

    # ... later, once a reviewer has approved out of band ...
    graph.invoke(Command(resume="approve"), config=config)
```
