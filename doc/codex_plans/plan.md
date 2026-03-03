Below is a **practical “overnight-ready” draft** for your `sps-review` repo that (a) keeps Codex inside the workspace, (b) enables network for Stage 4, (c) supports **Policy 2** (installs only in a dedicated env), and (d) removes most interruption points by combining **workspace-write sandbox + network + execpolicy rules**. Codex config can be scoped to the repo via `.codex/config.toml` (trusted projects only). ([developers.openai.com][1])

I’m giving you four artefacts:

1. `.codex/config.toml` (project-scoped behaviour)
2. `.codex/rules/sps_overnight.rules` (allow/forbid command policy) ([developers.openai.com][2])
3. `AGENTS.md` (runbook constraints for the agent) ([developers.openai.com][3])
4. `.vscode/settings.json` (force Codex to run in WSL from VS Code) ([developers.openai.com][4])

---

## 1) Project config: `.codex/config.toml`

Key choices:

* `sandbox_mode = "workspace-write"` so Codex can edit/run within the repo. ([developers.openai.com][5])
* `network_access = true` so Stage 4 won’t trigger network prompts. ([developers.openai.com][4])
* `approval_policy = "on-request"` is the safest default in the IDE extension; your rules then remove prompts for the commands you explicitly allow. (If you set `"never"`, you must be *very* confident your forbid-rules cover interactive/hanging commands.) ([developers.openai.com][4])
* `web_search = "disabled"` keeps the run deterministic and reduces prompt-injection surface while still allowing outbound network for your API calls. ([developers.openai.com][4])
* `shell_environment_policy.ignore_default_excludes = true` so env vars containing KEY/SECRET/TOKEN are not stripped before your pipeline reads API keys. ([developers.openai.com][6])

```toml
# .codex/config.toml
# Project-scoped Codex settings for overnight, unattended work.
# NOTE: Loaded only when the project is trusted by Codex/VS Code.

model = "gpt-5.2-codex"
approval_policy = "on-request"
sandbox_mode = "workspace-write"

# Avoid non-deterministic web browsing during an overnight run.
web_search = "disabled"

# Enable outbound network in workspace-write sandbox (needed for OpenAI/Gemini calls).
[sandbox_workspace_write]
network_access = true
# Keep defaults for /tmp and $TMPDIR to avoid breaking PDF tooling that uses temp files.
exclude_slash_tmp = false
exclude_tmpdir_env_var = false
writable_roots = []

# Ensure API key env vars survive Codex's default KEY/SECRET/TOKEN filtering.
[shell_environment_policy]
ignore_default_excludes = true

# Optional performance knob: snapshots shell state to speed repeated commands.
[features]
shell_snapshot = true
```

---

## 2) Command policy: `.codex/rules/sps_overnight.rules`

This ruleset is designed around your stated constraints:

* **No `sudo` / no system package managers** (prevents the classic “asks for password at 03:00” failure mode)
* **Installs allowed only via conda/mamba, and only into a named env**: `sps-overnight`
* **No git writes / pushes** overnight
* **Blocks common interactive commands** that can hang the run

Rules use `prefix_rule()` with `allow/prompt/forbidden`. Codex loads rules from Team Config locations including repo `.codex/rules/`. ([developers.openai.com][2])

```python
# .codex/rules/sps_overnight.rules
# Starlark rules for Codex execpolicy (command allow/deny).

# -----------------------
# Hard blocks (never)
# -----------------------
prefix_rule(
    pattern=["sudo"],
    decision="forbidden",
    justification="Overnight run: never use sudo. If a system dep is required, log it and stop.",
)

prefix_rule(pattern=["apt"], decision="forbidden", justification="No system installs overnight (use conda/mamba env only).")
prefix_rule(pattern=["apt-get"], decision="forbidden", justification="No system installs overnight (use conda/mamba env only).")
prefix_rule(pattern=["dpkg"], decision="forbidden", justification="No system installs overnight (use conda/mamba env only).")
prefix_rule(pattern=["snap"], decision="forbidden", justification="No system installs overnight (use conda/mamba env only).")

prefix_rule(pattern=["curl"], decision="forbidden", justification="Avoid arbitrary downloads; use Python libs + pinned deps in env.")
prefix_rule(pattern=["wget"], decision="forbidden", justification="Avoid arbitrary downloads; use Python libs + pinned deps in env.")

# Block editors/pagers that can hang an unattended run.
prefix_rule(pattern=["vim"], decision="forbidden", justification="Interactive editor blocked for overnight runs.")
prefix_rule(pattern=["nano"], decision="forbidden", justification="Interactive editor blocked for overnight runs.")
prefix_rule(pattern=["less"], decision="forbidden", justification="Interactive pager blocked for overnight runs.")
prefix_rule(pattern=["more"], decision="forbidden", justification="Interactive pager blocked for overnight runs.")

# Risky deletes
prefix_rule(pattern=["rm", "-rf"], decision="forbidden", justification="Destructive delete blocked. Use targeted deletes only.")
prefix_rule(pattern=["rm", "-r"], decision="forbidden", justification="Recursive delete blocked. Use targeted deletes only.")

# -----------------------
# Allow: safe inspection / filesystem / text utils
# -----------------------
prefix_rule(pattern=["ls"], decision="allow")
prefix_rule(pattern=["pwd"], decision="allow")
prefix_rule(pattern=["cat"], decision="allow")
prefix_rule(pattern=["head"], decision="allow")
prefix_rule(pattern=["tail"], decision="allow")
prefix_rule(pattern=["wc"], decision="allow")
prefix_rule(pattern=["find"], decision="allow")
prefix_rule(pattern=["rg"], decision="allow")
prefix_rule(pattern=["grep"], decision="allow")
prefix_rule(pattern=["sed"], decision="allow")
prefix_rule(pattern=["awk"], decision="allow")
prefix_rule(pattern=["cut"], decision="allow")
prefix_rule(pattern=["sort"], decision="allow")
prefix_rule(pattern=["uniq"], decision="allow")
prefix_rule(pattern=["tee"], decision="allow")

prefix_rule(pattern=["mkdir"], decision="allow")
prefix_rule(pattern=["cp"], decision="allow")
prefix_rule(pattern=["mv"], decision="allow")
prefix_rule(pattern=["touch"], decision="allow")

# -----------------------
# Allow: read-only git (no network, no history rewriting)
# -----------------------
prefix_rule(pattern=["git", "status"], decision="allow")
prefix_rule(pattern=["git", "diff"], decision="allow")
prefix_rule(pattern=["git", "log"], decision="allow")
prefix_rule(pattern=["git", "show"], decision="allow")
prefix_rule(pattern=["git", "rev-parse"], decision="allow")

# Explicitly forbid write/network git operations.
prefix_rule(pattern=["git", "commit"], decision="forbidden", justification="No commits overnight.")
prefix_rule(pattern=["git", "push"], decision="forbidden", justification="No pushes overnight.")
prefix_rule(pattern=["git", "pull"], decision="forbidden", justification="No pulls overnight.")
prefix_rule(pattern=["git", "fetch"], decision="forbidden", justification="No fetches overnight.")
prefix_rule(pattern=["git", "reset"], decision="forbidden", justification="No history rewriting overnight.")
prefix_rule(pattern=["git", "clean"], decision="forbidden", justification="No destructive clean overnight.")

# -----------------------
# Allow: conda/mamba ONLY within the dedicated env
# -----------------------
# Standardise on env name: sps-overnight
# Encourage using mamba if available.

# mamba install into the dedicated env (two common flag styles)
prefix_rule(pattern=["mamba", "install", "-n", "sps-overnight"], decision="allow")
prefix_rule(pattern=["mamba", "install", "--name", "sps-overnight"], decision="allow")

# conda install into the dedicated env (if you prefer conda over mamba)
prefix_rule(pattern=["conda", "install", "-n", "sps-overnight"], decision="allow")
prefix_rule(pattern=["conda", "install", "--name", "sps-overnight"], decision="allow")

# Run commands inside the env (preferred for reproducibility)
prefix_rule(pattern=["mamba", "run", "-n", "sps-overnight"], decision="allow")
prefix_rule(pattern=["conda", "run", "-n", "sps-overnight"], decision="allow")

# Optional: forbid installs into base or other envs by blocking bare install prefixes
prefix_rule(
    pattern=["mamba", "install"],
    decision="prompt",
    justification="Only install into -n sps-overnight. Add -n sps-overnight and retry.",
)
prefix_rule(
    pattern=["conda", "install"],
    decision="prompt",
    justification="Only install into -n sps-overnight. Add -n sps-overnight and retry.",
)
```

**Important:** after adding rules, restart Codex so it reloads them. ([developers.openai.com][2])
You can also test how a command will be treated with `codex execpolicy check`. ([developers.openai.com][2])

---

## 3) Agent runbook: `AGENTS.md` (repo root)

This is where you encode your workflow constraints so Codex does not “get clever” in unhelpful ways. Codex automatically loads AGENTS guidance from the repo root down to the working directory. ([developers.openai.com][3])

```md
# AGENTS.md — sps-review overnight runbook

## Non-negotiable constraints
- Stay inside this repo. Do not read/write outside the workspace.
- Never use sudo or system package managers (apt/apt-get/dpkg/snap). If a system dep is required: write it to the log and stop.
- Do not use interactive tools (vim/nano/less/more).
- Do not commit or push. Git is read-only (status/diff/log/show only).
- All outputs must be written under `results/overnight/` (create if missing).
- Maintain a single reference table linking artefacts:
  - `results/overnight/artefact_manifest.tsv` (one row per paper_id/source_id; columns are paths to artefacts)
- Maintain a rolling log:
  - `results/overnight/LOG.md` (append-only, timestamped)

## Dependency policy (Policy 2)
- You may install missing dependencies ONLY into conda env `sps-overnight`.
- Prefer mamba if available.
- Never install into base.
- If a dependency cannot be installed via conda/mamba/pip without sudo: log and stop.

## Workflow goal (high level)
1) Text extraction QC (sample-based report + recommendations)
2) Source categorisation (iterative calibration, then full corpus)
3) Case-series splitting (validate vs manual set, then process all relevant sources)
4) LangExtract examples + model comparison (OpenAI vs Gemini), with evidence-linked outputs

## Stopping conditions
- If any step requires sudo / system installs: stop after writing a clear "BLOCKED" section in LOG.md.
- If accuracy thresholds are not met in a calibration stage: iterate locally within that stage; do not proceed to full-corpus runs.
```

---

## 4) VS Code: force Codex to run inside WSL

This avoids accidental Windows-native execution (different sandbox semantics). Add this either globally or repo-local. The Codex security guide explicitly documents this setting. ([developers.openai.com][4])

```json
// .vscode/settings.json
{
  "chatgpt.runCodexInWindowsSubsystemForLinux": true
}
```

---

## How you use this in practice (minimal friction)

1. Create/activate your dedicated env once (manually), e.g. `sps-overnight`.
2. Trust the workspace in VS Code (so `.codex/config.toml` is honoured). ([developers.openai.com][1])
3. Restart VS Code (or the Codex extension) after adding `.codex/rules/…`. ([developers.openai.com][2])
4. Run in **Agent** mode (not “Full Access”); your config already enables network in workspace-write, so Stage 4 should not prompt for network. ([developers.openai.com][7])

---

If you paste one example of the *specific* permission prompt that currently interrupts you (the exact text), I’ll tighten the ruleset so that particular class of escalation either (a) becomes auto-allowed safely, or (b) becomes auto-blocked with a clean “log-and-stop” behaviour.

[1]: https://developers.openai.com/codex/config-basic/ "Config basics"
[2]: https://developers.openai.com/codex/rules/ "Rules"
[3]: https://developers.openai.com/codex/guides/agents-md/?utm_source=chatgpt.com "Custom instructions with AGENTS.md"
[4]: https://developers.openai.com/codex/security/ "Security"
[5]: https://developers.openai.com/codex/config-sample/ "Sample Configuration"
[6]: https://developers.openai.com/codex/config-reference/ "Configuration Reference"
[7]: https://developers.openai.com/codex/ide/features "Codex IDE extension features"