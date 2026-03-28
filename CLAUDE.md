# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Workspace Is

This is the **CrawlerBot** OpenClaw agent workspace — a revenue-focused web crawling agent that extracts structured data from websites and coordinates with other agents in a multi-agent ecosystem. The agent runs on the OpenClaw platform and communicates via Feishu (飞书).

## Running Scripts

No centralized build or test runner exists. Scripts are executed directly.

### Crawler (main skill)
```bash
# Basic fetch (no JS)
python3 skills/crawler/scripts/crawler.py --url "https://example.com" --output json

# JavaScript-heavy sites (uses Playwright + Chromium)
python3 skills/crawler/scripts/crawler.py --url "https://example.com" --js --output markdown

# Target specific element
python3 skills/crawler/scripts/crawler.py --url "https://example.com" --selector ".article-content" --output text

# Wait for dynamic content to appear
python3 skills/crawler/scripts/crawler.py --url "https://example.com" --js --wait-for ".loaded-content"

# Basic auth + rate limiting
python3 skills/crawler/scripts/crawler.py --url "https://example.com" --auth "user:pass" --delay 2
```

Requires: `pip install playwright beautifulsoup4 requests` and `playwright install chromium`

### Agent Coordinator
```bash
# Delegate task to another agent
python3 skills/agent-cron-job/scripts/coordinator.py send --from crawler --to sop --message "Task description"

# Schedule recurring delivery to user
python3 skills/agent-cron-job/scripts/coordinator.py schedule --every 30m --message "Check moltbook" --notify-user cyril

# Manage user registry
python3 skills/agent-cron-job/scripts/coordinator.py user list
```

### SearXNG (metasearch)
```bash
uv run skills/searxng/scripts/searxng.py search "query" --output json
sh skills/searxng/scripts/run-searxng.sh   # Start local SearXNG Docker instance
```

### Operational cron scripts
```bash
bash scripts/moltbook-check.sh     # Revenue opportunity check (runs every 30 min)
bash scripts/task-processor.sh     # Process pending tasks in task-queue/
bash scripts/skill-analysis.sh     # Generate skill inventory report
```

## Architecture

### Skill-based structure
Each capability lives in `skills/<name>/` with a `SKILL.md` manifest and `scripts/` directory. The `SKILL.md` defines trigger phrases, dependencies, and usage examples for the OpenClaw harness.

### Core skills
| Skill | Purpose |
|-------|---------|
| `skills/crawler/` | CDP-based web crawling via Playwright |
| `skills/agent-cron-job/` | Inter-agent coordination and scheduling |
| `skills/searxng/` | Privacy-respecting web search |
| `skills/agent-collaboration-sop/` | P0-P3 priority protocol definitions |

### CDP Crawling (how it works)
`skills/crawler/scripts/crawler.py` uses Playwright (which wraps CDP) to control Chromium:
- `wait_until='networkidle'` for JS-heavy pages, `'load'` for static pages
- `bypass_csp=True` in browser context
- Chrome 120 user-agent, 1920×1080 viewport
- Auto-detects main content via semantic selectors: `main`, `article`, `.content`, etc.
- Falls back to full body text if no semantic container found

### Inter-agent communication
Agents communicate asynchronously via **OpenClaw cron jobs** (not direct messages):
- `sessionTarget: "isolated"` + `payload.kind: "agentTurn"` wakes the target agent regardless of its active session
- Message envelope format: `{"protocol": "agent-coordinator/v1", "from": "...", "to": "...", "type": "request|response|notify", "payload": "..."}`
- Why cron and not sessions_send: agents operate in Feishu DM sessions, not the webchat main session

### Task queue (SOP → Crawler handoff)
SOP Agent drops JSON files into `task-queue/`. Crawler polls and processes them:
```json
{
  "taskId": "unique-id",
  "from": "sop", "to": "crawler",
  "type": "research",
  "priority": "normal|high|urgent",
  "status": "pending|processing|completed|failed",
  "task": { "title": "...", "target": "URL or keyword" },
  "result": { "findings": [], "summary": "..." }
}
```

### Agent ecosystem (5 agents)
`main` (dispatcher) → `dev` (code) / `sop` (process) / `ops` (infra) / **`crawler`** (data extraction — this workspace)

## Environment & Secrets

- `.env` sets `WORKSPACE_PATH`, `SEARXNG_URL`, `CHROMIUM_EXECUTABLE_PATH`, timeouts
- `scripts/moltbook-check.sh` and `skills/dalle-image-sender/scripts/send-image.js` contain embedded API tokens — treat as sensitive, never commit new secrets
- Users registry lives at `/home/admin/.openclaw/data/users.json` (shared across agents)

## Code Conventions

- **Python**: 4-space indent, ~100 col limit, type hints on public functions, `ensure_ascii=False` for CJK JSON
- **Shell**: uppercase constants, log output to files for cron tasks
- **JS**: 2-space indent, camelCase functions, PascalCase classes
- Docs and comments mix English and Chinese — keep language consistent within the file you edit
- Scripts must be self-contained; avoid adding heavyweight dependencies

## CDP Script Development Workflow

When writing new crawler scripts:
1. Use `WebCrawler` as a context manager (`with WebCrawler() as crawler`)
2. Prefer `--js` + `--wait-for` for SPAs; skip `--js` for static sites (faster)
3. Use `--selector` to target specific DOM elements rather than parsing full-page text
4. Output `--output json` for programmatic use; `--output markdown` for human-readable delivery
5. Log errors to `stderr`; exit non-zero on failure
6. Add `--help` and usage examples in any new CLI script
