# AGENTS.md

Repository guide for agentic coding tools. Keep changes minimal and aligned
with existing patterns. This workspace includes Python CLI tools, shell
scripts, and Node utilities.

## Sources Of Truth
- Cursor rules: none found in `.cursor/rules/` or `.cursorrules`.
- Copilot rules: none found in `.github/copilot-instructions.md`.
- Primary docs: `README.md` files under `skills/`, `task-queue/`, and `knowledge-base/`.

## Project Shape
- `skills/`: individual skill packages with `scripts/`.
- `scripts/`: operational shell scripts used by cron or manual runs.
- `task-queue/`: JSON tasks for SOP to crawler handoff.
- `knowledge-base/` and `docs/`: reference documentation only.

## Build / Lint / Test
No centralized build or test runner was found (no `package.json`, `pyproject.toml`,
`pytest.ini`, `tox.ini`, or CI workflows). Use targeted commands per script.

### Python (scripts in `skills/*/scripts`)
Run a module/script directly:
- `python3 path/to/script.py --help`
- `python3 skills/crawler/scripts/crawler.py --url https://example.com --js`

Single-test guidance (if tests are added later):
- Prefer `pytest path/to/test_file.py -k test_name`.
- For unittest: `python3 -m unittest path.to.test_module.TestClass.test_name`.

### Node (one-off CLI)
- `node skills/dalle-image-sender/scripts/send-image.js --help` (or run with args)

### Shell scripts (cron helpers)
- `bash scripts/moltbook-check.sh`
- `bash scripts/task-processor.sh`
- `bash scripts/skill-analysis.sh`

### SearXNG docker helper
- `sh skills/searxng/scripts/run-searxng.sh`

## Local Environment / Secrets
- `.env` files exist; do not commit secrets or paste them in output.
- Some scripts embed tokens (see `scripts/moltbook-check.sh` and
  `skills/dalle-image-sender/scripts/send-image.js`). Treat these as sensitive.

## Code Style Guidelines
Follow existing file style. This repo mixes English and Chinese in docs and
comments. Keep the language consistent within the file you edit.

### General
- Keep scripts self-contained; avoid adding heavyweight dependencies.
- Prefer simple, direct control flow; avoid clever abstractions.
- Preserve CLI help text and examples when modifying interfaces.

### Imports
- Python: standard lib first, third-party second, local last.
- Node: built-in modules first, third-party second.
- Avoid unused imports; keep import lists minimal.

### Formatting
- Python: 4-space indentation; keep lines reasonably short (around 100 cols).
- Shell: 2-space or 4-space indentation is acceptable; be consistent in a file.
- JS: 2-space indentation is typical in existing scripts.
- Use `ensure_ascii=False` when emitting JSON that may contain CJK text.

### Types & Data Shapes
- Python: use type hints for public functions when it helps clarity.
- For JSON payloads, keep keys stable and document any new fields.
- When reading JSON from disk, handle missing keys with defaults.

### Naming Conventions
- Python: `snake_case` for functions/variables, `PascalCase` for classes.
- Shell: uppercase for constants and paths, lowercase for locals.
- JS: `camelCase` for functions/variables, `PascalCase` for classes.

### Error Handling
- Python: print clear errors to `stderr` and exit with non-zero status on failure.
- Shell: check command exit status for critical steps; log to files when used by cron.
- Node: throw or `console.error` with a non-zero exit code on failure.

### Logging / Output
- Cron scripts append to log files; preserve this behavior.
- Avoid noisy output for CLI tools unless in verbose/debug mode.

### I/O and Side Effects
- Be explicit about file paths; avoid implicit CWD assumptions when possible.
- Do not write outside the repo unless a script already targets external paths.
- Keep network requests behind explicit CLI actions.

### Security
- Never commit new secrets; prefer env vars for tokens.
- If you must add config, add placeholders and document required env vars.
- Do not disable SSL verification unless a script is explicitly for local use
  (see `skills/searxng/scripts/searxng.py`).

## Contributing Notes For Agents
- Avoid mass refactors; make focused changes tied to a request.
- If editing scripts under `skills/`, update related README usage examples.
- If adding new scripts, include `--help` output and usage examples.
- Keep docs factual; avoid marketing language unless the file already uses it.

## Quick References
- Web crawler: `skills/crawler/scripts/crawler.py`
- Agent coordinator: `skills/agent-cron-job/scripts/coordinator.py`
- Task queue format: `task-queue/README.md`
