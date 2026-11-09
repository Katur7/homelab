---
name: goldfish-review
description: Perform an isolated zero-context Goldfish audit on a milestone plan.md. Red-teams the plan against repo rules, security invariants, Traefik v3 syntax, and rollback feasibility. Use when reviewing milestone plans, preparing for milestone implementation, or when asked for a "goldfish review".
---

# /goldfish-review — Elephant-Goldfish Milestone Auditor

Spawn an isolated, zero-context **Goldfish** subagent to independently audit and red-team a milestone `plan.md` before implementation begins.

The Goldfish evaluates whether `plan.md` is complete, safe, and unambiguous **purely from the written text and repository contracts**, without inheriting conversational bias, unstated assumptions, or sycophancy from earlier brainstorming.

---

## Workflow Overview

```
Elephant (Main Thread) 
  └─► Spawns Goldfish Subagent (Clean Context)
        ├─► Audits specs/XX-<name>/plan.md
        ├─► Checks against AI_INSTRUCTIONS.md, ARCHITECTURE.md, QUIRKS.md
        └─► Returns Structured Audit Report
Elephant 
  └─► Patches plan.md & requests user sign-off
```

---

## Step 1 — Identify Target Plan

1. If a path was provided as an argument (e.g., `/goldfish-review specs/31-example/plan.md`), use it.
2. If omitted, find the latest milestone folder in `specs/`:
   ```bash
   ls -d specs/*/ | sort -V | tail -n 1
   ```
   Target `plan.md` in that folder.
3. Verify that `plan.md` exists. If not, inform the user that a draft plan must be created first (Elephant drafting phase).

---

## Step 2 — Dispatch the Goldfish Subagent

Call `invoke_subagent` to spawn a fresh subagent session.

> [!IMPORTANT]
> Do NOT pass any chat history, conversational justifications, or background reasoning to the subagent prompt. The subagent must evaluate the plan with **zero memory** of the preceding conversation.

### Subagent Invocation Specification

* **TypeName:** `research` (or `self` with read permissions)
* **Role:** `Goldfish Plan Auditor`
* **Prompt Template:**

```text
You are a Goldfish Plan Auditor in an Elephant-Goldfish Model (EGM) workflow.
You have ZERO prior knowledge of the conversation that created this plan.
Your task is to independently red-team and stress-test the following milestone plan:
TARGET PLAN: <absolute path to specs/XX-name/plan.md>

Reference documentation to evaluate against:
- AI_INSTRUCTIONS.md (repo persona, security rules, compose conventions)
- ARCHITECTURE.md (networking, volume standards, domain conventions)
- QUIRKS.md (known service-specific gotchas)
- Target compose files (e.g. services/<service>/compose.yaml)

Evaluate the plan across the following 5 dimensions:

1. Public Repository Security (CRITICAL)
   - Are any real passwords, API tokens, hashed credentials, or private keys written into the plan?
   - Are secrets isolated to .env (gitignored) and referenced via ${VAR}?
   - Are domains compliant with the domain strategy (public: pippinn.me, internal: internal.pippinn.me)?

2. Traefik v3 Label & Routing Accuracy
   - Are backtick syntax rules used for all labels? Example: Host(`service.pippinn.me`)
   - Are required middlewares properly referenced (authelia, crowdsec, security-headers)?
   - Are OIDC bypass paths preserved where required (e.g. Immich /.well-known/immich)?

3. Docker & Compose Syntax & Conventions
   - Are all container images pinned to explicit versions (NEVER :latest)?
   - Are ${VAR} references only used for shell/.env variables (NOT variables defined in env_file)?
   - Are static non-secret values hardcoded in compose.yaml?
   - Are network connections (proxy_traefik, socket-proxy, internal) correct?
   - Are storage volume mappings compliant with ARCHITECTURE.md paths (/mnt/storage/...)?

4. Rollback & Operational Feasibility
   - Are rollback steps concrete and actionable if deployment fails?
   - Is there a validation step (e.g., docker compose config, curl check)?
   - Does this plan impact dependent containers or shared networks?

5. Specification Completeness & Ambiguity
   - Can an engineer or agent execute this milestone SOLELY from plan.md without guessing?
   - Are file paths exact?

Return a structured report categorized by:
- 🔴 BLOCKERS (Must fix before user sign-off / deployment)
- 🟡 RISKS & ASSUMPTIONS (Unclear rollback, edge cases, potential outages)
- 🟢 RECOMMENDATIONS (Clarity, linting, formatting)
- VERDICT: [APPROVED / REVISE_REQUIRED]
```

---

## Step 3 — Process Goldfish Audit Findings

Once the subagent returns its report:

1. **Present the Findings:** Display the structured critique concisely to the user.
2. **Elephant Reconciliation:**
   - If findings include **BLOCKERS** or **RISKS**:
     - Automatically propose updates to `specs/XX-name/plan.md` addressing each valid point.
     - Ask the user for confirmation on any architectural choices that require human decision.
   - If **APPROVED**:
     - Note that `plan.md` has passed the Goldfish audit.
     - Prompt the user for final sign-off to begin the implementation phase.
