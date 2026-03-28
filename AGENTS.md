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
- **新增爬虫脚本**：必须包含 `CRAWLER_META` 字典，保存到 `skills/crawler/scripts/`，开发日志写入 `skills/crawler/.learning/{site}.md`。完整流程见 `skills/crawler/SKILL.md`。

## OpenClaw Runtime Constraints

以下约束仅适用于在 OpenClaw 平台上运行的 agent，不影响本地 Claude Code 使用。

### 执行模型：单轮同步 + session_spawn 异步

OpenClaw 每次用户消息触发**一轮同步执行**，轮次结束后 agent 进入休眠。
**没有隐式后台等待，不存在"完成后自动继续"机制。**

常见错误模式（必须避免）：
- ❌ "安装已启动，完成后我会继续配置" → 本轮结束，永远不会继续
- ❌ "下载中，请稍候..." → 命令没有阻塞执行，结果丢失
- ❌ 启动后台进程后说"稍后检查结果"

**处理长耗时操作的两种正确方式：**

#### 方式一：同步阻塞（耗时 < 2 分钟）

所有 shell 命令在同一轮内阻塞执行，等命令返回后再输出结论：
```bash
# 安装依赖、等待完成、验证结果，一次性完成
pip install nodriver beautifulsoup4 requests && python3 -c "import nodriver; print('OK')"
```

#### 方式二：session_spawn 异步（耗时长 / 需要独立环境）

用 `session_spawn` 启动一个独立 agent session 执行耗时任务，当前 session 继续响应用户：

```
session_spawn:
  identity: IDENTITY.md
  payload:
    kind: agentTurn
    message: |
      执行以下安装任务并在完成后通知用户：
      1. conda create -n claw-crawler python=3.13 -y
      2. pip install nodriver beautifulsoup4 requests websockets pytest
      3. 验证：python3 -c "import nodriver; print('nodriver OK')"
      完成后通过 Feishu 发送安装结果摘要。
  sessionTarget: isolated
```

适用场景：conda 环境初始化、大文件下载、多步骤部署流程。
- ✅ 派生 session 独立运行，不阻塞当前对话
- ✅ 完成后可通过 Feishu 或 cron 回调通知
- ✅ 若任务失败，派生 session 的日志独立可查

### 文件编辑

OpenClaw 的 Edit 工具要求 `oldText` 精确匹配，无正则、无容错。
编辑失败的常见原因：空白符差异、文件被 cron 并发修改、同一 session 内多次编辑未重新读取。

建议：
- 复杂编辑用 Python 脚本读写，不依赖平台 Edit 工具
- 每次编辑前先 Read，确认当前内容

---

## Quick References
- Web crawler registry: `skills/crawler/scripts/crawler.py` (match / run / list / info)
- Site-specific scrapers: `skills/crawler/scripts/{site}_menu.py` (nodriver + CDP)
- Crawler skill guide: `skills/crawler/SKILL.md` (execute / create / summarize modes)
- Crawler memory: `skills/crawler/references/crawlerMemory.md`
- Agent coordinator: `skills/agent-cron-job/scripts/coordinator.py`
- Task queue format: `task-queue/README.md`
