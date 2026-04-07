# Architecture Overview

This document provides a high-level overview of the **Bug/Issue Triage OpenEnv** architecture, detailing the interactions between the agent, the server layer, and the core environment logic.

## System Workflow

The following diagram illustrates the flow of a typical triage episode, from initialization to terminal scoring.

```mermaid
flowchart TD
  %% ===========
  %% ACTORS
  %% ===========
  Agent["Agent / Baseline Script"]:::actor

  %% ===========
  %% SERVER LAYER
  %% ===========
  API["FastAPI Server<br/>bugtriage_env/server/app.py"]:::server

  %% ===========
  %% ENV CORE
  %% ===========
  Env["OpenEnv Environment<br/>bugtriage_env/server/bugtriage_env_environment.py"]:::env
  Models["Pydantic Models + Enums<br/>bugtriage_env/models.py"]:::code

  %% ===========
  %% DATA SOURCES
  %% ===========
  Tasks[("tasks/issues_easy.json<br/>issues_medium.json<br/>issues_hard.json")]:::data
  Examples[("examples/sample_issue.json")]:::data

  %% ===========
  %% INTERNAL STATE + GRADING
  %% ===========
  State[("Internal Episode State<br/>(decisions, clarifications,<br/>step_count, cumulative_reward,<br/>truth labels hidden)")]:::state
  Grader["Deterministic Grader<br/>_compute_final_score() -> 0..1<br/>(Security cap rule)"]:::grader

  %% ===========
  %% ENDPOINTS / FLOWS
  %% ===========
  Agent -->|"POST /reset<br/>(TASK_SET=easy|medium|hard)"| API
  API -->|"calls reset()"| Env
  Env --> Models
  Env -->|"load scenario (priority)"| Tasks
  Env -->|"fallback if missing"| Examples
  Env -->|"init episode state"| State
  Env -->|"return Observation"| API
  API -->|"observation"| Agent

  Agent -->|"POST /step(action)"| API
  API -->|"calls step(action)"| Env
  Env -->|"validate + parse action"| Models
  Env -->|"update state<br/>+ shaped reward"| State
  Env -->|"return (observation, reward, done, info)"| API
  API -->|"observation + reward + done + info"| Agent

  %% Terminal scoring
  Env -->|"if done=true<br/>(SubmitTriage/Escalate/max_steps)"| Grader
  Grader -->|"final_score in [0,1]<br/>apply security cap if needed"| Env

  %% Debug state
  Agent -->|"GET /state"| API
  API -->|"calls state()"| Env
  Env -->|"return internal state (debug)"| API
  API -->|"state snapshot"| Agent

  %% ===========
  %% STYLES
  %% ===========
  classDef actor fill:#f3f4f6,stroke:#111827,stroke-width:1px;
  classDef server fill:#e0f2fe,stroke:#0284c7,stroke-width:1px;
  classDef env fill:#dcfce7,stroke:#16a34a,stroke-width:1px;
  classDef code fill:#fef9c3,stroke:#ca8a04,stroke-width:1px;
  classDef data fill:#fae8ff,stroke:#a21caf,stroke-width:1px;
  classDef state fill:#ffe4e6,stroke:#e11d48,stroke-width:1px;
  classDef grader fill:#ede9fe,stroke:#6d28d9,stroke-width:1px;
```

## Component Breakdown

### 1. Agent Layer
The agent interacts with the environment via a RESTful API provided by the FastAPI server. It submits triage actions and receives observations.

### 2. Server Layer (`app.py`)
A lightweight FastAPI wrapper that exposes the environment endpoints (`/reset`, `/step`, `/state`). It ensures that the agent's requests are correctly routed to the core logic.

### 3. Environment Core (`bugtriage_env_environment.py`)
Responsible for managing the lifecycle of an episode. It handles state transitions, action validation using Pydantic models, and interfaces with the grading logic.

### 4. Grading Logic
A deterministic grader ensures fair and consistent evaluation of agent performance. It incorporates security rules (e.g., security caps) to penalize dangerous triage decisions.
