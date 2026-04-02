#!/usr/bin/env python3
"""
Crawler Registry Manager
扫描 scripts/ 目录下所有爬虫脚本，读取其 CRAWLER_META，
返回已开发脚本的域名覆盖范围和数据能力，供大模型决策使用。

Usage:
    python3 crawler.py list                     # 列出所有可用脚本（表格）
    python3 crawler.py list --format json       # JSON 输出（供程序处理）
    python3 crawler.py match --url "https://www.grubhub.com/restaurant/..."
    python3 crawler.py info grubhub_menu        # 某脚本详情
    python3 crawler.py run grubhub_menu --url "..." --output json
"""

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

SCRIPTS_DIR = Path(__file__).parent


# ─── Meta parser ─────────────────────────────────────────────────────────────

def parse_meta(script_path: Path) -> Optional[Dict]:
    """用 ast 安全解析脚本中的 CRAWLER_META 字典，不执行脚本。"""
    try:
        source = script_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return None

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "CRAWLER_META"
            and isinstance(node.value, ast.Dict)
        ):
            try:
                return ast.literal_eval(node.value)
            except Exception:
                return None
    return None


def load_all_metas() -> List[Dict]:
    """扫描 scripts/ 目录，收集所有含 CRAWLER_META 的脚本。"""
    results = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        if path.name.startswith("test_") or path.name == "crawler.py":
            continue
        meta = parse_meta(path)
        if meta:
            meta["_script"] = path.name
            meta["_path"] = str(path)
            results.append(meta)
    return results


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_list(fmt: str):
    metas = load_all_metas()
    if not metas:
        print("No crawler scripts with CRAWLER_META found.", file=sys.stderr)
        sys.exit(0)

    if fmt == "json":
        print(json.dumps(metas, indent=2, ensure_ascii=False))
        return

    # 表格输出
    col_w = [20, 30, 42, 10]
    header = ["Script", "Domains", "Data", "Framework"]
    sep = "  ".join("-" * w for w in col_w)
    row_fmt = "  ".join(f"{{:<{w}}}" for w in col_w)

    print(sep)
    print(row_fmt.format(*header))
    print(sep)
    for m in metas:
        domains = ", ".join(m.get("domains", []))
        print(row_fmt.format(
            m.get("name", m["_script"])[:col_w[0]],
            domains[:col_w[1]],
            m.get("data", "")[:col_w[2]],
            m.get("framework", "")[:col_w[3]],
        ))
    print(sep)
    print(f"\n{len(metas)} script(s) available.")


def cmd_match(url: str):
    """根据 URL 匹配最合适的脚本。"""
    domain = urlparse(url).netloc.replace("www.", "")
    metas = load_all_metas()

    matched = []
    for m in metas:
        for d in m.get("domains", []):
            if domain == d or domain.endswith("." + d) or d in domain:
                matched.append(m)
                break

    if not matched:
        result = {"matched": False, "domain": domain, "suggestion": "create_new"}
        print(json.dumps(result, ensure_ascii=False))
        return

    best = matched[0]
    result = {
        "matched": True,
        "domain": domain,
        "script": best["_script"],
        "name": best.get("name", ""),
        "data": best.get("data", ""),
        "example": best.get("example", ""),
        "run": f"python3 {best['_script']} --url \"{url}\" --output json",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_info(script_name: str):
    """打印某个脚本的完整 meta 信息。"""
    # 支持 "grubhub_menu" 或 "grubhub_menu.py"
    name = script_name if script_name.endswith(".py") else script_name + ".py"
    path = SCRIPTS_DIR / name
    if not path.exists():
        print(f"Error: {name} not found in {SCRIPTS_DIR}", file=sys.stderr)
        sys.exit(1)

    meta = parse_meta(path)
    if not meta:
        print(f"Error: {name} has no CRAWLER_META", file=sys.stderr)
        sys.exit(1)

    meta["_script"] = name
    print(json.dumps(meta, indent=2, ensure_ascii=False))


def cmd_run(script_name: str, extra_args: List[str]):
    """代理执行某个脚本，传递剩余参数。"""
    name = script_name if script_name.endswith(".py") else script_name + ".py"
    path = SCRIPTS_DIR / name
    if not path.exists():
        print(f"Error: {name} not found", file=sys.stderr)
        sys.exit(1)

    cmd = [sys.executable, str(path)] + extra_args
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Crawler Registry Manager — 查询/匹配/执行已开发的爬虫脚本"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # list
    p_list = sub.add_parser("list", help="列出所有可用爬虫脚本")
    p_list.add_argument("--format", choices=["table", "json"], default="table")

    # match
    p_match = sub.add_parser("match", help="根据 URL 匹配合适的脚本")
    p_match.add_argument("--url", required=True)

    # info
    p_info = sub.add_parser("info", help="查看某脚本的详细 meta 信息")
    p_info.add_argument("script")

    # run
    p_run = sub.add_parser("run", help="执行某脚本（透传剩余参数）")
    p_run.add_argument("script")
    p_run.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list(args.format)
    elif args.cmd == "match":
        cmd_match(args.url)
    elif args.cmd == "info":
        cmd_info(args.script)
    elif args.cmd == "run":
        cmd_run(args.script, args.args)


if __name__ == "__main__":
    main()
