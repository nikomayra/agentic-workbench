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
* Hugging Face / Transformers / PyTorch

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

## Phase 7 — Evals + Observability

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

Only now add:

* Redis
* Celery
* Background workers
* Retry policies
* Resume-after-failure
* Live progress via SSE

Persist workflow state so a server restart does not destroy an execution.

**Start here:** Make resumption work manually before adding infrastructure. Persist the current step and each completed result, deliberately stop a run after one step, and add a function that reloads the `WorkflowRun` and continues from the next incomplete step. Once that works, move the coordinator into one Celery task using only the run ID as input; Redis carries queued work, while PostgreSQL remains the durable source of workflow state. SSE is only the live progress channel to the browser—it is not where state lives.

Optional learning exercise: rebuild one workflow using **LangGraph** and compare the approaches. LangGraph's persistence model uses checkpoints specifically to support resumability, human intervention, memory, and fault recovery.

**Minimal tests:** prove resuming a run does not execute an already-completed step twice.

---

## Phase 9 — Productization

Only if the project is still interesting:

* GitHub issue input
* GitHub PR creation
* Reusable workflow templates
* Saved agent configurations
* Model selection
* Team/project profiles
* Dashboard of historical runs
* Deployment
* A polished public README with architecture, setup, screenshots, demo flow, limitations, and resume-ready project highlights

**Start here:** Pick one thin end-to-end integration instead of implementing the entire list. A good first slice is “GitHub issue URL → create workflow run → approved result produces a draft pull request.” Keep GitHub access in a small service/tool boundary, add the minimum token configuration, and document a demo path before adding teams, profiles, or model-selection UI.

At this point decide whether to extract it from `study_box` into its own repository/company idea.

**Resume checkpoint #7 — final main-project update:** Rewrite the final two project bullets and skills keywords around the strongest completed evidence: multi-agent repository workflows, approvals/guardrails, parallel Git isolation, MCP, evals/observability, durable execution, and the deployed GitHub issue-to-draft-PR demo.

---

# 6. Follow-On AI / ML Phase

After the agentic 80%, go one layer deeper.

## A. RAG

Add repository/document knowledge retrieval.

Learn:

* Chunking
* Embeddings
* Vector similarity
* Metadata filtering
* Retrieval quality
* Reranking
* Context construction

Use PostgreSQL + `pgvector` rather than introducing another database.

Compare:

```text
Full-context prompting
vs
RAG
```

Measure retrieval quality rather than assuming RAG helps.

**Start here:** Create a small set of repository questions with known relevant files, store chunks and embeddings in `pgvector`, and measure whether retrieval returns those files. Compare against sending the complete small fixture before wiring retrieval into an agent.

**Resume Checkpoint #8** Built a retrieval-augmented generation pipeline using embeddings, pgvector, metadata filtering, and context retrieval, and evaluated retrieval quality against full-context prompting.

---

## B. Local Hugging Face Model

Run a small open model locally.

Learn:

* Tokenizers
* Tokens
* Model loading
* Generation parameters
* Quantization
* GPU/CPU memory constraints
* Local vs API inference

Give the local model a small role such as:

```text
Task classification
Code-risk classification
Issue categorization
Simple routing
```

**Start here:** Use one standalone script or notebook to load a small model and classify a fixed list of examples. Record accuracy, latency, and memory use before putting the model behind an API or inside the workbench.

**Resume Checkpoint #9** Integrated locally hosted Hugging Face models for lightweight classification/routing tasks, comparing latency, cost, and quality against hosted APIs.
---

## C. Fine-Tuning / LoRA

Fine-tune a small pretrained model for one narrow task.

Example:

> Given an engineering ticket, classify it as frontend/backend/database/infrastructure and estimate risk.

Create a dataset, train, evaluate baseline vs fine-tuned model, and integrate the winner into the workbench.

Hugging Face's PEFT tooling supports parameter-efficient approaches such as LoRA, where a relatively small set of adapter parameters is trained instead of retraining the complete base model.

**Start here:** Build and score a train/validation/test dataset with the untouched base model first. Fine-tune one LoRA adapter only after you have that baseline; otherwise you cannot tell whether training improved anything.

**Resume Checkpoint #10** Fine-tuned a pretrained model with LoRA/PEFT on a task-specific dataset and benchmarked it against the base model before integrating it into the application.

---

## D. Tiny Model From Scratch — Educational

Train one deliberately small transformer from scratch.

The goal is **understanding**, not usefulness.

Learn:

```text
Tokenization
Embeddings
Attention
Forward pass
Loss
Backpropagation
Training loop
Validation
Inference
```

Keep it tiny enough to train locally or cheaply.

Then compare:

```text
Tiny model from scratch
vs
Pretrained model
vs
Fine-tuned pretrained model
```

**Start here:** Keep this separate from the web application. Follow one small PyTorch transformer exercise, train on a tiny text dataset, and be able to explain the tensor flow from token IDs through embeddings and attention to loss before adding features.

That gives you enough depth to intelligently discuss modern ML without pretending to be an ML researcher.

**Resume Checkpoint #11** Implemented and trained a small transformer from scratch to gain hands-on experience with tokenization, attention, training loops, validation, and inference.

---

## E. Model Routing

Final integration:

```text
Cheap/local model → simple classification
Cloud model → complicated planning/reasoning
Specialized fine-tuned model → narrow task
```

Now the project demonstrates both **agent orchestration and practical ML architecture**.

**Start here:** Begin with a deterministic Python router—an `if`/`match` decision based on task type, risk, or size—not another routing agent. Run the same labeled tasks through each candidate model, then write routing rules from measured quality, latency, and cost.

**Resume Checkpoint #12** Built a model-routing layer that selects between local, fine-tuned, and cloud models based on task complexity, latency, cost, and quality requirements.

---

# FINAL RESUME CHECKPOINT — 13

**Resume Checkpoint #13** AI/ML Systems: Built and evaluated agentic workflows, RAG pipelines, local and fine-tuned models, MCP integrations, multi-model routing, and production-style AI observability/guardrails.


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
* Return to FastAPI deployment documentation only when the local workflow is demonstrable.

### Follow-On AI/ML Work

* RAG: [OpenAI retrieval guide](https://developers.openai.com/api/docs/guides/retrieval) and [`pgvector`](https://github.com/pgvector/pgvector).
* Local models: [Transformers quick tour](https://huggingface.co/docs/transformers/quicktour).
* LoRA: [PEFT quick tour](https://huggingface.co/docs/peft/quicktour).
* Tiny transformer: [PyTorch tutorials](https://docs.pytorch.org/tutorials/); keep this educational experiment separate from the workbench.

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
