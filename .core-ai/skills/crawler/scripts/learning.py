#!/usr/bin/env python3
"""
Crawler Learning Manager — 学习流程管理

脚本只负责流程管理，不提供自动提取/泛化逻辑。
真正的学习由 Agent 自主驱动：读取 → 理解 → 泛化 → 整合。

Usage:
    python3 learning.py status              # 查看所有学习文件状态
    python3 learning.py list-unlearned      # 列出未学习的文件
    python3 learning.py get <filename>      # 获取文件完整内容（供 Agent 读取）
    python3 learning.py mark <filename>     # 标记文件为已学习
    python3 learning.py learned             # 查看已学习文件列表
"""

import argparse
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List

SKILL_DIR = Path(__file__).resolve().parent
LEARNING_DIR = SKILL_DIR.parent / ".learning"
MEMORY_FILE = SKILL_DIR.parent / "references" / "crawlerMemory.md"


# ─── 状态管理 ─────────────────────────────────────────────────────────────

def get_learned_files() -> List[str]:
    """从 crawlerMemory.md 头部注释中读取已学习文件列表。"""
    if not MEMORY_FILE.exists():
        return []
    content = MEMORY_FILE.read_text(encoding="utf-8")
    match = re.search(r'<!--\s*learned:\s*([^>]+?)\s*-->', content)
    if not match:
        return []
    return [f.strip() for f in match.group(1).split(",") if f.strip()]


def mark_as_learned(filename: str):
    """将文件标记为已学习。"""
    content = MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""
    learned = get_learned_files()
    if filename not in learned:
        learned.append(filename)
    learned_str = ", ".join(learned)
    learned_comment = f"<!-- learned: {learned_str} -->"
    if re.search(r'<!--\s*learned:', content):
        content = re.sub(r'<!--\s*learned:[^>]+-->', learned_comment, content)
    else:
        content = learned_comment + "\n" + content
    MEMORY_FILE.write_text(content, encoding="utf-8")


# ─── 文件读取 ─────────────────────────────────────────────────────────────

def parse_learning_file(filepath: Path) -> Dict:
    """解析 .learning/*.md 文件，提取 frontmatter 元信息。"""
    content = filepath.read_text(encoding="utf-8")
    frontmatter = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            fm_text = content[3:end].strip()
            for line in fm_text.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter[key.strip()] = val.strip()
    return {
        "filename": filepath.name,
        "site": frontmatter.get("site", filepath.stem),
        "script": frontmatter.get("script", ""),
        "status": frontmatter.get("status", "unknown"),
        "date": frontmatter.get("date", ""),
        "data_extracted": frontmatter.get("data_extracted", ""),
        "full_content": content,  # Agent 自行决定如何处理
    }


# ─── 命令实现 ─────────────────────────────────────────────────────────────

def cmd_status():
    """显示所有学习文件的状态。"""
    if not LEARNING_DIR.exists():
        print("No .learning/ directory found.", file=sys.stderr)
        return
    learned = get_learned_files()
    files = sorted(LEARNING_DIR.glob("*.md"))
    if not files:
        print("No learning files found.")
        return
    print(f"\n{'File':<30} {'Site':<20} {'Status':<15} {'Learned':<10}")
    print("-" * 75)
    for f in files:
        info = parse_learning_file(f)
        is_learned = f.name in learned
        print(f"{f.name:<30} {info['site']:<20} {info['status']:<15} {'✅' if is_learned else '❌':<10}")
    print(f"\nTotal: {len(files)} files, {len(learned)} learned, {len(files) - len(learned)} unlearned")


def cmd_list_unlearned():
    """列出未学习的文件。"""
    learned = get_learned_files()
    files = sorted(LEARNING_DIR.glob("*.md"))
    unlearned = [f for f in files if f.name not in learned]
    if not unlearned:
        print("All files have been learned! 🎉")
        return
    print("\nUnlearned files:")
    for f in unlearned:
        info = parse_learning_file(f)
        print(f"  - {f.name} (site: {info['site']}, status: {info['status']})")


def cmd_get(filename: str):
    """获取学习文件完整内容 —— 供 Agent 自行阅读和理解。"""
    filepath = LEARNING_DIR / filename if filename.endswith(".md") else LEARNING_DIR / f"{filename}.md"
    if not filepath.exists():
        print(f"Error: {filepath} not found", file=sys.stderr)
        return
    info = parse_learning_file(filepath)
    print(f"\n{'='*60}")
    print(f"Site: {info['site']} | Status: {info['status']}")
    print(f"Data: {info['data_extracted']}")
    print(f"{'='*60}")
    print(info['full_content'])


def cmd_learned():
    """查看已学习文件列表。"""
    learned = get_learned_files()
    if not learned:
        print("No files learned yet.")
        return
    print("\nLearned files:")
    for f in learned:
        print(f"  ✅ {f}")


def cmd_mark(filename: str):
    """手动标记文件为已学习。"""
    filepath = LEARNING_DIR / filename if filename.endswith(".md") else LEARNING_DIR / f"{filename}.md"
    if not filepath.exists():
        print(f"Error: {filepath} not found", file=sys.stderr)
        return
    mark_as_learned(filepath.name)
    print(f"✅ Marked {filepath.name} as learned")


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Crawler Learning Manager — 学习流程管理（Agent 自主驱动）"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="显示所有学习文件状态")
    sub.add_parser("list-unlearned", help="列出未学习的文件")
    sub.add_parser("learned", help="查看已学习文件列表")

    p_get = sub.add_parser("get", help="获取文件完整内容（供 Agent 阅读）")
    p_get.add_argument("filename", help="文件名")

    p_mark = sub.add_parser("mark", help="标记文件为已学习")
    p_mark.add_argument("filename", help="文件名")

    args = parser.parse_args()

    if args.cmd == "status":
        cmd_status()
    elif args.cmd == "list-unlearned":
        cmd_list_unlearned()
    elif args.cmd == "learned":
        cmd_learned()
    elif args.cmd == "get":
        cmd_get(args.filename)
    elif args.cmd == "mark":
        cmd_mark(args.filename)


if __name__ == "__main__":
    main()
