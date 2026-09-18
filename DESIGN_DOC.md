# Agentic Workbench — Study & Build Plan

## Goal

Build a reusable **agentic workflow workbench** rather than a one-off demo.

The platform accepts an objective, lets AI agents plan and execute work through tools, validates the results, and exposes the workflow for human review.

The first workflow template will be **Software Engineering**:

> Requirement → plan → implementation → tests → independent review → human approval

Later, the same core could support research, operations, data analysis, product work, etc.

---

# 1. Core Concepts to Learn — the 80%

By the end of the main project, understand and have implemented:

### LLM / Agent Fundamentals

* Model API calls
* Instructions / prompting
* Structured outputs
* Function/tool calling
* Tool schemas and validation
* Agent execution loops
* Context management
* Persistent workflow state

### Agent Orchestration

* Single-agent workflows
* Manager / supervisor pattern
* Agents-as-tools
* Handoffs
* Sequential workflows
* Parallel workers
* Planner → worker → reviewer pattern
* Critic / feedback loops
* Retry and termination rules

### Production Agent Systems

* Human-in-the-loop approval
* Tool permissions / allowlists
* Guardrails
* Sandboxed execution
* Tracing and observability
* Cost / token / latency tracking
* Failure recovery
* Durable / resumable workflows
* Deterministic validation vs LLM judgment
* Agent evals

### Connectivity

* MCP clients and servers
* MCP tools
* MCP resources
* MCP prompts
* External API / repository integrations

OpenAI's current Agents SDK directly exposes agents, tools, handoffs, guardrails, sessions, tracing, human approval, sandboxed agents, and MCP integration, making it a useful first implementation framework rather than requiring us to build every primitive ourselves.

---

# 2. Stack

### Frontend

* React
* TypeScript
* Vite
* Minimal CSS/Tailwind

### Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* PostgreSQL
* OpenAI Agents SDK

### Engineering

* `uv`
* Docker / Docker Compose
* Pytest
* Ruff
* ESLint
* Vitest
* Git

### Add Later

* Redis
* Celery
* MCP Python SDK
* pgvector

**Do not add Redis, Celery, vector databases, Kubernetes, authentication, etc. until a phase actually requires them.**

---

# 3. Initial Folder Structure

```text
agentic_workbench/
├── frontend/
│   └── React / TypeScript app
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   ├── tools/
│   │   ├── workflows/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   └── tests/
│
├── mcp/
│   └── added later
│
├── fixtures/
│   └── sample_repo/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

`fixtures/sample_repo/` should contain a deliberately small application the agents are allowed to inspect and modify.

Do **not** initially point autonomous agents at important repositories.

---

# 4. Core Product Requirements

A user creates a **Workflow Run** containing:

```text
Objective
Target repository
Constraints
Optional context
```

Example:

> Add cancellation support to the reservation API and update tests.

The platform should eventually perform:

```text
User Requirement
      ↓
Planner Agent
      ↓
Structured Plan + Acceptance Criteria
      ↓
Worker Agent(s)
      ↓
Code / Artifacts
      ↓
Deterministic Tests
      ↓
Reviewer Agent
      ↓
Corrections if necessary
      ↓
Human Approval
      ↓
Final Artifact / PR
```

The UI should show:

* Current workflow state
* Generated plan
* Agents involved
* Tool calls
* Test results
* Reviewer findings
* Files / diffs produced
* Errors
* Execution time
* Approximate model cost / usage
* Approval requests

Core persisted objects:

```text
WorkflowRun
AgentRun
StepRun
ToolCall
Artifact
Approval
```

Keep these generic enough that future workflow types do not need a different database architecture.

---

# 5. Development Phases — Breadth First

The goal is **resume/interview breadth early, depth afterward**.

Resume checkpoints are reminders to revise the same one or two project bullets and the skills section as meaningful capabilities are completed. They are not instructions to add one resume bullet per phase, and future work must not be claimed before it is implemented.

## Phase 0 — Scaffolding - DONE

Claude may build this phase for you.

Set up:

* React/Vite frontend
* FastAPI backend
* PostgreSQL
* SQLAlchemy/Alembic
* Docker Compose
* `uv`
* Pytest/Ruff
* ESLint/Vitest
* Environment variables
* `/health`
* Basic DB connection
* Empty frontend → backend API request

**Do not let Claude implement agent/domain logic yet.**

---

## (COMPLETED) Phase 1 — Single-Agent Vertical Slice

Build:

```text
UI objective
   ↓
POST /runs
   ↓
Planner agent
   ↓
Structured plan
   ↓
Postgres
   ↓
Display plan in UI
```

Learn:

* Model invocation
* Agent loop
* Structured output
* Pydantic schemas
* Persistence
* Basic tracing

**Resume checkpoint #1:** AI-agent application + structured agent workflows.

---

## (COMPLETED) Phase 2 — Tools

Give the agent safe read-only tools:

```text
list_files()
read_file()
search_code()
git_status()
run_tests()
```

Agent should inspect `fixtures/sample_repo/` and answer questions or generate an implementation plan based on the actual repository.

**Start here:** These are ordinary Python functions exposed to the model with `@function_tool`; they are not a special agent filesystem. Use `pathlib` for listing/reading files and Python's `subprocess` module to run fixed commands such as `rg`, `git status`, and `pytest`. Keep the repository root and commands under application control—the model may provide a path or search query, but never an arbitrary shell command. Build and test each private Python helper directly before registering its small decorated wrapper with the agent.

Learn:

* Function calling
* Tool schemas
* Tool-result context
* Permission boundaries
* Error handling

---

## (COMPLETED) Phase 3 — Multi-Agent Workflow

Introduce:

```text
Planner
   ↓
Implementer
   ↓
Tests
   ↓
Reviewer
```

Reviewer receives:

* Requirement
* Acceptance criteria
* Diff
* Test output

Reviewer returns structured:

```text
PASS
or
CHANGES_REQUIRED
```

Allow **one repair cycle** initially.

**Start here:** First orchestrate this in normal Python rather than asking one agent to manage everything. One coordinator function should call the planner, give its structured plan to an implementer, run the fixed test tool, and then give the requirement, diff, and test output to a reviewer. This phase also needs one narrowly scoped write/apply-patch tool that can modify only the disposable `fixtures/sample_repo/`; Phase 4 will put human approval in front of that same capability. Implement the one-repair limit as an ordinary counter or loop in Python so termination is deterministic.

Learn:

* Agents-as-tools
* Handoffs
* Context boundaries
* Critic patterns
* Termination rules

**Minimal tests:** prove a failed review triggers at most one repair, and a passed review stops immediately.

**Resume checkpoint #2:** Multi-agent planner → implementer → reviewer orchestration, repository tool/function calling, deterministic testing, and bounded repair loops.

---

## (COMPLETED) Phase 4 — Human Approval + Guardrails

Before dangerous actions such as:

```text
write_file
execute_shell
git_commit
```

require explicit approval.

Add:

* Tool allowlist
* Command restrictions
* Timeouts
* Maximum agent turns
* Maximum repair loops
* Failure states

Learn:

* Human-in-the-loop
* Guardrails
* Security boundaries
* Agent autonomy vs control

The Agents SDK supports guardrails around inputs, outputs, and function-tool execution, including approval-oriented patterns.

**Start here:** Gate one capability first: the fixture-only write/apply-patch tool from Phase 3. When it is requested, save a pending `Approval`, stop or pause the workflow, show the request in the UI, and resume only after an approve/reject API call. Keep permission checks, path restrictions, command allowlists, timeouts, and loop limits in Python; a prompt asking the model to behave safely is not an authorization boundary.

**Minimal tests:** prove rejected approval never invokes the write tool.

**Resume checkpoint #3:** Human-in-the-loop approvals, resumable agent state, guardrails, scoped tool permissions, and deterministic execution limits.

---

## (COMPLETED) Phase 5 — Parallel Agents

Start with one integrated, user-approved plan. The planner may propose generic workstreams containing a task, intended paths, acceptance criteria, and any shared contracts. The deterministic coordinator accepts a simple, plausibly independent decomposition or falls back to one worker.

```text
Approved plan
├── Workstream A → Worker A → isolated Git worktree A
└── Workstream B → Worker B → isolated Git worktree B
```

Application code generates UUID worker/branch names, binds each worker's repository tools to its complete worktree as the trusted root, and runs workers concurrently with `asyncio.TaskGroup`. Intended paths are coordination guidance rather than a perfect prediction of every file the implementation may need.

After workers finish:

```text
Coordinator commits and merges worker branches
→ conflicts are resolved in an integration worktree
→ combined tests run
→ reviewer evaluates the merged result
→ human approval
→ generated worktrees and branches are cleaned up
```

Git lifecycle, merge order, tests, limits, and cleanup remain deterministic application responsibilities. Agents handle work requiring judgment: planning, implementation, semantic review, and conflict repair.

**Start here:** The read-only isolation smoke path is complete: choose parallel or single-worker execution, create UUID worktrees, bind read-only workers, collect concurrent reports, and always clean up. Next, bind the remaining repository/editing tools to each trusted root, commit worker results, and add the integration worktree flow.

Learn:

* Parallel orchestration
* Git worktrees
* Structured task partitioning and single-worker fallback
* Trusted-root tool binding
* Textual and semantic conflict handling
* Context and run-state isolation
* Deterministic integration and cleanup

**Minimal tests:** prove the parallel decision falls back when decomposition is unsafe; workers receive different worktree paths; cleanup removes generated worktrees/branches; and combined tests run only against the integration worktree.

**Resume checkpoint #4:** Parallel agent orchestration, isolated Git worktrees, dynamically scoped repository tools, deterministic single-worker fallback, integration testing, and conflict handling.

---

## (COMPLETED) Phase 6 — MCP

Convert several custom repository tools into your own MCP server.

Expose a representative set:

```text
Tools:
- list_files
- read_file
- search_repo
- run_tests
- git_diff
- git_status

Resources:
- README

Prompts:
- review_change
```

Planner, decomposer, and reviewer repository inspection goes through MCP. Workers
retain directly bound tools because each worker operates within a different Git
worktree, while deterministic coordinator operations remain ordinary Python.

MCP defines a client/server interface around three especially important server primitives: **tools, resources, and prompts**.

**Start here:** Do not redesign the repository tools. Move one existing helper—preferably `search_code`—behind a tiny local MCP server, verify it with an MCP client or inspector, and then replace the agent's direct Python import with an MCP connection. A tool performs an action, a resource exposes readable data, and a prompt is a reusable prompt template; implement one of each only after the first tool call works end to end.

**Resume checkpoint #5:** MCP server/client development and agent integration using tools, resources, and reusable prompts.

**Minimal tests:** make one real MCP tool call and repeat the repository-escape test through MCP.

---

## (COMPLETED) Phase 7 — Evals + Observability

Create 10–20 repeatable tasks against the sample repository.

Measure:

```text
Task success
Tests passed
Reviewer findings
Human corrections required
Tokens
Cost
Latency
Number of agent turns
```

Compare:

```text
Single agent
vs
Planner + worker
vs
Planner + worker + reviewer
```

This is where you find out whether your fancy architecture actually helps.

**Start here:** An eval is a repeatable input plus an explicit way to judge the result. Begin with a JSON or Python list of five objectives containing expected files, required test outcomes, and any forbidden behavior; run the same cases against each agent configuration and save one result row per case. Use deterministic checks such as test exit codes and referenced file paths before adding an LLM judge. Inspect traces while debugging individual failures, then aggregate success rate, latency, turns, and token usage.

Tracing should make model turns, tool calls, handoffs, and guardrail behavior inspectable rather than treating the system as a black box.

**Resume checkpoint #6:** Agent evaluation, tracing, reliability measurement, and cost/latency benchmarking across workflow architectures.

**Minimal tests:** prove the eval harness scores one known pass and one known failure correctly.

---

## Phase 8 — Durable Execution

Move long workflows out of the HTTP request while keeping PostgreSQL—not Redis—as the durable source of truth.

**Manual durability checkpoint — complete:** `CoordinatorExecution` already round-trips through JSON in `WorkflowRun.agent_state`, and a focused test proves that reloading a paused execution resumes only pending work rather than replaying completed work.

Finish the phase with one narrow architecture:

```text
FastAPI command → enqueue run_id → Celery worker
                                  ↓
                         load state from Postgres
                                  ↓
                       advance until pause/terminal
                                  ↓
                         persist state to Postgres

Postgres status/events → SSE → React dashboard
```

Build:

* A background entry point that accepts only `run_id`, loads the run, advances it, and persists the next pause or terminal state
* Celery with Redis as the queue transport
* Idempotent retry/claim behavior so the same run is not advanced twice concurrently
* SSE for live status updates; reconnecting clients must be able to rebuild the current view from PostgreSQL

**Minimal tests:** keep the no-replay checkpoint; add one task-level test proving a retried/duplicate task does not repeat completed work.

**Resume checkpoint #7:** Durable, resumable agent workflows using PostgreSQL checkpoints, Redis/Celery background execution, idempotent retries, and SSE progress updates.

---

## Phase 9 — Productization

Finish the project as a credible, reusable engineering demo—not a startup product.

### 1. Replace the fixture-only production path

Keep `fixtures/sample_repo/` for tests and evals, but remove `SAMPLE_REPOSITORY_ROOT` from normal workflow execution. Introduce an application-owned repository target/workspace boundary containing at least the source URL or approved local development path, base branch, and allowlisted test command. Clone or copy each run into a managed workspace and pass that workspace explicitly through planning, workers, MCP, tests, and cleanup.

This makes the workflow usable against different repositories without letting the model choose arbitrary filesystem roots or shell commands.

### 2. Add one GitHub flow

```text
GitHub issue URL
→ managed repository checkout
→ existing plan/work/approval workflow
→ human final approval
→ pushed branch + draft pull request
```

Keep GitHub API/authentication logic behind one small service boundary. Do not add profiles, teams, workflow-template builders, or a general model-selection UI.

### 3. Add professional finishing evidence

* GitHub Actions for backend tests/Ruff and frontend lint/test/build
* A focused frontend polish pass using established components such as shadcn/ui
* UI coverage for workflow status, plan, approvals, tests/diff, errors, and final result
* A public README with architecture, setup, screenshot, demo flow, evaluation results, and honest limitations

AI assistance is appropriate for visual/component boilerplate. Personally verify the state flow, loading/error behavior, responsive layout, accessibility basics, and every backend action exposed by the UI.

**Stop condition:** one repository can enter through GitHub, complete the durable workflow, and produce a human-approved draft PR while CI passes. Then stop building and publish it.

**Resume checkpoint #8 — final main-project update:** Rewrite the final two project bullets and skills keywords around the strongest completed evidence: multi-agent repository workflows, approvals/guardrails, parallel Git isolation, MCP, evals/observability, durable background execution, CI, and a GitHub issue-to-draft-PR demo.

---

# 6. Optional Phase 10 — Measured AI Depth

Do not start this phase until the Phase 9 stop condition is met. Neither item is required for the main project.

### RAG, only if repository scale demonstrates a retrieval problem

Use PostgreSQL + `pgvector` to retrieve repository/document chunks. Build a small question set with known relevant files and compare retrieval quality, workflow success, cost, and latency against the existing search/read-tool approach. Keep RAG only if it measurably improves results.

### Model routing, only if Phase 7 provides a useful quality/cost split

Use deterministic application logic—not another agent—to select a cheaper or stronger model based on task type or risk. Evaluate the same cases before and after routing. Existing model-routing work from another project is already valid experience; duplicating it here is optional.

**Resume checkpoint #9 — optional:** Evaluated retrieval and/or model-routing strategies against explicit quality, latency, and cost baselines rather than adding AI infrastructure without evidence.

Local Hugging Face inference, LoRA fine-tuning, and a tiny transformer from scratch are separate learning projects, not extensions of this workbench.


# 7. Rules for Studying Without Falling Back Into AI Dependency

Before asking AI for implementation help:

1. Write what you think the system should do.
2. Identify the layer where the problem exists.
3. Read the relevant official documentation.
4. Try something yourself.
5. Inspect the error.
6. Only then ask for help.

When asking AI:

```text
Here is my mental model:
Here is what I tried:
Here is what happened:
Explain what I misunderstand. Do not implement it for me.
```

Exceptions:

* Boilerplate
* Dependency setup
* Environment issues
* Syntax you already conceptually understand

Those are not worth suffering over.

---

# 8. Important Gotchas

* Start with **one agent**. Add agents only when the workflow proves a reason for them.
* Tests outrank reviewer-agent opinions.
* Do not let agents execute unrestricted shell commands.
* Never give autonomous agents important credentials.
* Limit loops. Agents can happily argue with each other forever.
* Persist structured state; do not make the conversation transcript your database.
* Keep prompts short and responsibilities narrow.
* Measure cost and latency from the beginning.
* Do not add RAG because “AI apps need RAG.”
* Do not add microservices because “agents sound distributed.”
* Do not optimize framework architecture before the workflow works.
* Keep a `LEARNINGS.md` where you explain concepts in your own words after implementing them.

---

# 9. Phase-Specific Documentation When Stuck

Do not read all of this in advance. Open only the phase you are implementing, read enough to identify the next mechanism, and return to the code.

### Phases 0–1 — One Agent and Structured Output

* [OpenAI Agents SDK quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart) — defining and running an agent, adding a function tool, and inspecting traces.
* [FastAPI tutorial](https://fastapi.tiangolo.com/tutorial/) and [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) — HTTP and application data boundaries.

### Phase 2 — Repository Tools

* [Python `pathlib`](https://docs.python.org/3/library/pathlib.html) — safe path construction and file access.
* [Python `subprocess`](https://docs.python.org/3/library/subprocess.html) — running fixed external commands and capturing exit codes/stdout/stderr.
* [`git status`](https://git-scm.com/docs/git-status) and [ripgrep guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md) — the programs behind `git_status()` and `search_code()`.
* Re-read the function-tool example in the [Agents SDK quickstart](https://developers.openai.com/api/docs/guides/agents/quickstart); your Python function is the capability boundary.

### Phase 3 — Multiple Agents and a Repair Loop

* [Agents SDK orchestration and handoffs](https://developers.openai.com/api/docs/guides/agents/orchestration) — code-driven orchestration, agents-as-tools, and handoffs.
* Search the Python docs for `for`/`while` loops and `async` functions only if the coordinator mechanics themselves are unfamiliar. The repair limit belongs in ordinary application code.

### Phase 4 — Approval and Safety Boundaries

* [Agents SDK guardrails and human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals) — guardrails, tool approval, and resuming after review.
* [Agents SDK sandbox agents](https://developers.openai.com/api/docs/guides/agents/sandboxes) — isolation for code execution. Do this after the fixture-only permission checks work.

### Phase 5 — Parallel Workers

* [Python `asyncio` task groups](https://docs.python.org/3/library/asyncio-task.html#task-groups) — running independent async work and waiting for the group.
* [`git worktree`](https://git-scm.com/docs/git-worktree) — isolated working directories attached to one repository.
* [Agents SDK orchestration](https://developers.openai.com/api/docs/guides/agents/orchestration) — deciding when orchestration belongs in application code, agents-as-tools, or handoffs.

### Phase 6 — MCP

* [OpenAI MCP and connectors guide](https://developers.openai.com/api/docs/guides/tools-connectors-mcp) — connecting models/agents to MCP servers.
* [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture) and [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — client/server roles and implementing tools, resources, and prompts.

### Phase 7 — Evals and Observability

* [Evaluate agent workflows](https://developers.openai.com/api/docs/guides/agent-evals) — repeatable datasets and evaluation approaches.
* [Agents SDK integrations and observability](https://developers.openai.com/api/docs/guides/agents/integrations-observability) — traces and external observability integrations.

### Phase 8 — Durable Execution

* [Celery first steps](https://docs.celeryq.dev/en/stable/getting-started/first-steps-with-celery.html) — moving long work out of the request/response process.
* [Redis documentation](https://redis.io/docs/latest/) — use as Celery infrastructure here, not as the canonical workflow database.
* Read LangGraph persistence/HITL documentation only for the optional comparison after your own resume-from-database flow works.

### Phase 9 — Productization

* [GitHub REST issues](https://docs.github.com/en/rest/issues/issues) and [pull requests](https://docs.github.com/en/rest/pulls/pulls) — one practical external integration.
* [GitHub Actions for Python](https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python) — run the existing backend and frontend checks in CI.
* [shadcn/ui](https://ui.shadcn.com/docs) — optional component source for the final dashboard polish pass.

### Optional Phase 10 — Measured AI Depth

* RAG: [OpenAI retrieval guide](https://developers.openai.com/api/docs/guides/retrieval) and [`pgvector`](https://github.com/pgvector/pgvector).
* Model routing: reuse the Phase 7 harness to compare quality, latency, and cost before writing routing rules.

The Agents SDK quickstart progresses from a first agent to tools, multiple agents/handoffs, and tracing, which maps well to the early sequence here.

---

# Definition of “Main Project Done”

The main agentic project is successful when a user can:

```text
Submit engineering objective
→ Agent inspects repository
→ Planner generates acceptance criteria
→ Worker makes changes
→ Tests run
→ Reviewer independently evaluates result
→ Failed review triggers limited repair
→ Human approves final change
→ Every important action is persisted and traceable
```

Once that works reliably, **stop**.

Everything after that is depth, experimentation, or potential product development—not required to claim meaningful agentic-AI experience.
