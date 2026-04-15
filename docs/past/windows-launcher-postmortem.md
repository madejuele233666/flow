# Windows Launcher Postmortem

## Context

This repository is developed day-to-day in WSL, but the HUD frontend is intended to run on Windows.

The launcher work in April 2026 aimed to provide a single Windows desktop entry that would:

- sync `frontend/` and `shared/` from WSL to `D:\files\Ptemp\flow_hud`
- prepare the backend environment inside WSL
- start and stop the WSL backend daemon
- start and stop the Windows frontend process
- expose one operator-facing entrypoint for `start`, `restart`, `stop`, `status`, and `sync`

The first versions looked reasonable but failed repeatedly in real use. The issues were not architectural theory problems. They were environment-bound integration bugs across PowerShell, Windows Python packaging, WSL command invocation, and editable install semantics.

This document records the concrete failures and the principles that came out of them.

## What Actually Broke

### 1. Shell string composition was not robust enough

Passing complex commands directly through `powershell -> wsl.exe -> bash -lc` failed in multiple ways:

- quoting broke when command strings contained shell syntax
- `zsh` globbing and PowerShell interpolation obscured the real error
- failures were hard to reproduce because the command seen by the final shell was not the command we thought we sent

The practical fix was to stop building large inline shell strings and instead:

- write explicit shell scripts to disk
- execute those scripts through WSL
- capture logs from the script itself

Principle: for cross-shell orchestration, prefer "write script, then execute script" over nested command-string interpolation.

### 2. Backend package metadata did not match runtime reality

The backend launcher path exposed two missing runtime dependencies:

- `asyncclick`
- `PyYAML`

These were required at runtime but not declared in [backend/pyproject.toml](/home/madejuele/projects/flow/backend/pyproject.toml).

Principle: if a launcher needs to bootstrap an environment from package metadata alone, the metadata must be treated as production-critical, not optional bookkeeping.

### 3. `python -m flow_engine.daemon` had no real module entrypoint

`flow daemon start` forked a child process using:

```python
python -m flow_engine.daemon
```

But [backend/flow_engine/daemon.py](/home/madejuele/projects/flow/backend/flow_engine/daemon.py) did not execute `run_daemon()` when run as a module. The subprocess started and then exited immediately.

Principle: if a command launches a module with `python -m ...`, that target module must be independently executable. Do not assume another file's `__main__` entrypoint will cover it.

### 4. PowerShell parameter naming caused silent argument loss

The first version of `Invoke-WindowsPython` used a parameter named `Args`.

In PowerShell, `$args` is already a built-in automatic variable. The result was that the function appeared to accept arguments but actually invoked Python with zero effective arguments in the failing path.

This produced misleading behavior around Windows virtual environment creation.

Principle: in PowerShell, do not name custom parameters `Args` or other well-known automatic variable names.

### 5. Editable local path dependencies were not portable enough

The frontend package metadata includes a local file dependency on `../shared`.

On Windows, `pip install -e "frontend[gui]"` resolved that dependency incorrectly in the copied workspace and looked for:

- `D:\files\Ptemp\shared`

instead of:

- `D:\files\Ptemp\flow_hud\shared`

The fix in the launcher was:

1. install `shared` explicitly
2. install frontend-only runtime dependencies explicitly
3. install `frontend` with `--no-deps`

Principle: when crossing OS and workspace boundaries, local `file:` dependencies are fragile. Launchers should not rely on them if a deterministic explicit install sequence is available.

### 6. PowerShell 5 UTF-8 output wrote a BOM that broke `tomllib`

The launcher generated `hud_config.toml` from PowerShell.

Using `Set-Content -Encoding UTF8` on Windows PowerShell 5 wrote a UTF-8 BOM. Python's `tomllib` then failed to parse the config with:

- `TOMLDecodeError: Invalid statement (at line 1, column 1)`

The fix was to write the file with `System.Text.UTF8Encoding($false)`.

Principle: configuration files consumed by strict parsers should be written with explicit encoding behavior. Do not trust legacy shell defaults.

### 7. "Stop" paths must be idempotent

Frontend stop logic originally failed if the process exited between PID read and process termination.

For operator-facing control scripts, that is the wrong contract. "Already stopped" should not be treated as failure.

Principle: process stop operations in control scripts should be idempotent and race-tolerant.

## What Worked Better

The final working shape had these characteristics:

- one desktop entrypoint for all common actions
- WSL work delegated to explicit shell scripts with logs
- backend status based on PID-file reality, not import probes
- Windows frontend runtime isolated in its own Windows venv
- frontend package startup routed through repo-owned entry code (`python -m flow_hud.windows_main`)
- launcher responsible only for orchestration, not application logic

This split kept launcher complexity acceptable while still allowing repo-side code to own runtime behavior.

## Resulting Rules

These rules should be treated as defaults for future Windows/WSL launcher work in this repository.

1. Keep product runtime logic in repo code; keep desktop scripts as thin orchestrators.
2. For WSL execution, prefer generated script files over nested `bash -lc` strings.
3. Do not trust package metadata blindly; launcher bootstrap flows must validate real runtime imports.
4. Avoid cross-platform reliance on relative `file:` dependencies in user-facing bootstrap paths.
5. Write machine-consumed config files with explicit no-BOM UTF-8.
6. Make `start`, `restart`, and `stop` actions idempotent where practical.
7. Validate launcher changes end-to-end from the real desktop entry, not just by unit tests or static review.

## Minimal Validation Checklist

Any future change to the Windows launcher flow should verify at least:

1. `start`
2. `status`
3. `restart`
4. `stop-all`
5. backend package bootstrap from a clean WSL venv
6. frontend package bootstrap from a clean Windows venv

Unit tests are still useful, but they are not sufficient for this path.

## Remaining Constraint

The current launcher is validated for the local machine it was built against. It still hardcodes:

- WSL distro name
- WSL repo path
- Windows target path

That is acceptable for local operation, but it is not a portable distribution mechanism yet.
