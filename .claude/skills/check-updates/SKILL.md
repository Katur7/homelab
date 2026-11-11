---
name: check-updates
description: Check WUD for pending container updates, summarise release notes, select updates upfront, apply in batch, and automatically commit.
allowed-tools: WebFetch, WebSearch, Read, AskUserQuestion, invoke_subagent, run_command
---

# /check-updates — WUD Container Update Review

Check What's Up Docker for pending container updates, summarise release notes using a cheap model subagent (`flash` / `flash_lite`), highlight breaking changes, batch-prompt for all updates upfront, apply them unattended, and automatically commit.

---

## Workflow Overview

```
1. Run `python3 scripts/check-updates.py --json`
   └── Returns structured container updates with changelog text and metadata
2. For each container:
   ├── LinuxServer rebuild-only (`is_linuxserver_rebuild_only: true`):
   │   └── Output one-line note directly (skip LLM subagent)
   └── Normal update (`is_linuxserver_rebuild_only: false`):
       └── Invoke cheap subagent (`Model: "flash"`) to analyze changelogs
3. Render all container update cards upfront
4. Batch-prompt user with `AskUserQuestion` to select updates upfront
5. Apply all selected updates unattended (pull, up -d, verify health)
6. Automatically commit compose.yaml changes to git without asking
```

---

## Step 1 — Collect Update Data

Execute the helper script to query WUD, resolve repositories, and package raw changelogs:

```bash
python3 scripts/check-updates.py --json
```

- If the output is empty (`[]`) or reports no updates, inform the user: `"No updates available."` and finish.
- If an error occurs (e.g. WUD unreachable), stop and report the error clearly.

Each item in the JSON array contains:
- `name` — container name
- `image` — Docker image reference
- `local_version` — current version
- `remote_version` — target version
- `semver_diff` — `major` / `minor` / `patch` / `prerelease`
- `compose_file` — path to compose.yaml
- `is_linuxserver_rebuild_only` — boolean (`true` if only `ls###` base image bumped)
- `release_urls` — list of release URLs / blog URLs
- `raw_content` — raw release changelog / cleaned announcement text
- `note` — optional note (e.g. rebuild note or fetch warning)

---

## Step 2 — Summarise Releases & Detect Breaking Changes

### Fast-path: LinuxServer Rebuild-Only

If `is_linuxserver_rebuild_only` is `true`:
**Do not invoke an LLM subagent.** Render the note directly:

```markdown
## [<name>]  <local_version> → <remote_version>  (<semver_diff>)
Compose file: `<compose_file>`

*<note>*
```

Proceed directly to Step 3 for this container.

### Subagent Analysis: App Updates & Upstream Changelogs

If `is_linuxserver_rebuild_only` is `false`:
Delegate release notes analysis to a lightweight subagent (`Model: "flash"` or `"flash_lite"`).

If multiple containers require LLM analysis, invoke subagents concurrently in a single `invoke_subagent` call to minimize turn latency.

#### Subagent Invocation Specification

- **Tool:** `invoke_subagent`
- **Subagents array:**
  - `TypeName`: `"research"` (or `"self"`)
  - `Role`: `"Release Notes Analyst"`
  - `Model`: `"flash"`
  - `Prompt`:
    ```text
    You are an expert homelab systems administrator reviewing software release notes.
    Target container: {name} ({local_version} -> {remote_version}, {semver_diff})
    Release URLs: {release_urls}

    Review the following raw release notes / announcement:
    """
    {raw_content}
    """

    Produce a concise, well-structured analysis in the following format:
    ### Summary
    - 2-3 most important new capabilities, fixes, or improvements.

    ⚠️ BREAKING CHANGES & MIGRATIONS
    - High-impact backward-incompatible changes (config syntax, database migrations, UI/naming overhauls, removed features).
    - Deprecated options affecting common deployments.
    - Required manual steps before or after updating.
    Ignore obscure edge cases, minor third-party platform fixes (unless core to the app), or routine dependency bumps.
    If no breaking changes exist, omit the ⚠️ BREAKING CHANGES section entirely.
    ```

#### Fallback Guardrail
If subagent invocation fails, times out, or `raw_content` is empty:
Fall back to displaying the `release_urls` and noting the `semver_diff` so the user is never blocked from updating.

---

## Step 3 — Render Container Update Cards

Present all container update cards upfront so the user can review all changes before deciding.

For each container:

```markdown
## [<name>]  <local_version> → <remote_version>  (<semver_diff>)
Compose file: `<compose_file>`

### Releases covered
- [<tag>](<url>)
...

### Summary
- <Key change 1>
- <Key change 2>

⚠️ BREAKING CHANGES
- <Specific breaking change or migration note>
```

If no breaking changes were identified and `semver_diff` is not `major`, omit the `⚠️ BREAKING CHANGES` header.

---

## Step 4 — Batch Prompt for Updates Upfront

After rendering all container cards, prompt the user in a single interaction to select which updates to apply so the entire batch runs unattended.

Use `AskUserQuestion` (or native `ask_question`):

- **If multiple containers have updates:**
  Use multi-select (`is_multi_select: true`):
  - Question: `Select which container updates to apply:`
  - Options: list all available container updates, e.g.:
    - `[<name1>] <local_version> → <remote_version> (<semver_diff>)`
    - `[<name2>] <local_version> → <remote_version> (<semver_diff>)`
- **If only one container has an update:**
  - Question: `Update [<name>] from <local_version> to <remote_version>?`
  - Options: `["Yes — apply update", "No — skip"]`

If the user selects no updates or skips, report `"No updates selected."` and finish.

---

## Step 5 — Apply Selected Updates

Process all chosen containers sequentially without waiting for further user input:

For each selected container:

1. **Locate the compose file:**
   Path is available in `compose_file`.

2. **Detect where the version is stored:**
   Read the `image:` line in the compose file:
   - **Hardcoded tag** (e.g. `image: ghcr.io/mealie-recipes/mealie:v3.13.1`) → edit that line in `compose.yaml` directly.
   - **Env var substitution** (e.g. `image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-v2.6.1}`) → update the variable in the stack's `.env` file instead. **Never commit `.env` files.**

3. **Pull new images:**
   ```bash
   docker compose -f <compose_file> pull
   ```

4. **Recreate updated containers:**
   ```bash
   docker compose -f <compose_file> up -d
   ```
   Coupled services (e.g. immich-server + immich-machine-learning sharing `${IMMICH_VERSION}`) are recreated automatically.

5. **Verify:**
   ```bash
   docker inspect <name> --format '{{.State.Status}} {{.State.Health.Status}}'
   ```
   - If a health check is configured: wait up to 30 seconds for `healthy`. Report clearly if it does not reach healthy.
   - If no health check: `running` is sufficient.

If an individual container update fails or fails to become healthy, report the error clearly and proceed with the remaining selected containers.

---

## Step 6 — Automatically Commit & Summary

Do **not** ask for permission to commit. Automatically commit all compose changes to git once the updates are finished:

1. **Check git status:**
   Verify modified files using `git status --porcelain`.
   - Stage modified compose files only (e.g. `git add services/*/compose.yaml` or specific `compose_file` paths).
   - **Never stage or commit `.env` files.**

2. **Commit changes:**
   If any compose files were updated, commit using the standard repo format:
   ```bash
   git commit -m "Update containers: <name1>, <name2>..." -m "- <name1>: <local1> → <remote1>
   - <name2>: <local2> → <remote2>"
   ```
   *(For a single container, use `Update container: <name> <local> → <remote>`)*

3. **Render Final Summary:**
   Provide a completion summary:
   - Updated containers and their health/running status
   - Git commit SHA and commit message (or note if only `.env` was updated, explaining `.env` files are gitignored)
   - Any failed updates or warnings
