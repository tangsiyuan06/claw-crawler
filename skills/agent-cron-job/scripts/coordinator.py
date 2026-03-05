#!/usr/bin/env python3
"""
Agent Coordinator - 多 Agent 协同调度

跨 Agent 任务委派、状态同步、结果回传。
所有通讯通过 OpenClaw Cron Jobs（isolated + agentTurn）实现。

- Agent → Agent：通过 cron job 创建 isolated agentTurn 委派任务
- Agent → Human：在创建 cron job 时配置 delivery.announce，由 OpenClaw 自动投递结果给用户
- Agent → Agent 回传：目标 agent 重新创建 cron job 回传给发起方

用户数据统一管理：/home/admin/.openclaw/data/users.json
  同一用户在不同 agent（不同飞书应用）下有不同的 open_id，
  通过 user add --agent-id <agent> 分别注册。

结果回传统一使用 delivery.announce，由 OpenClaw 自动投递，agent 无需手动调用 message 工具。
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Agent 列表
AGENTS = {
    "main": {"name": "主智能体", "role": "日常对话 + 通用任务"},
    "dev": {"name": "开发智能体", "role": "技能开发 + 技术方案"},
    "sop": {"name": "SOP 智能体", "role": "SOP 制定 + 流程优化"},
    "ops": {"name": "运维智能体", "role": "运维部署 + 监控"},
    "crawler": {"name": "爬虫智能体", "role": "数据爬取 + API 分析"},
}

USERS_DATA_PATH = Path("/home/admin/.openclaw/data/users.json")
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")


def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")


def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")


def load_users():
    """读取 users.json，不存在则自动创建"""
    if not USERS_DATA_PATH.exists():
        USERS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        USERS_DATA_PATH.write_text("{}", encoding="utf-8")
        return {}
    return json.loads(USERS_DATA_PATH.read_text(encoding="utf-8"))


def save_users(users):
    """写入 users.json（统一存储在 /home/admin/.openclaw/data/）"""
    USERS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_DATA_PATH.write_text(
        json.dumps(users, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def resolve_open_id(username, agent_id):
    """从统一的 users.json 中，通过 username + agent_id 查找对应的 open_id。"""
    users = load_users()
    if username not in users:
        print_error(f"用户 '{username}' 不存在，请先用 user add 添加")
        sys.exit(1)

    open_ids = users[username].get("open_ids", {})
    open_id = open_ids.get(agent_id)
    if not open_id:
        print_error(
            f"用户 '{username}' 未设置 agent '{agent_id}' 的 open_id，"
            f"请运行：user add --username {username} --agent-id {agent_id} --open-id <open_id>"
        )
        sys.exit(1)

    return open_id


def parse_duration(s):
    """解析时间字符串为毫秒，支持格式: 30s, 5m, 1h, 2h30m, 1h15m30s"""
    pattern = r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$'
    m = re.fullmatch(pattern, s.strip())
    if not m or not any(m.groups()):
        print_error(f"无法解析时间格式 '{s}'，支持格式: 30s, 5m, 1h, 2h30m")
        sys.exit(1)
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000
    if total_ms == 0:
        print_error("时间间隔不能为 0")
        sys.exit(1)
    return total_ms


def build_schedule(args):
    """根据参数构建 schedule 对象，支持 at/every/cron 三种模式"""
    if getattr(args, "cron", None):
        schedule = {"kind": "cron", "expr": args.cron}
        if getattr(args, "tz", None):
            schedule["tz"] = args.tz
        return schedule
    elif getattr(args, "every", None):
        return {"kind": "every", "everyMs": parse_duration(args.every)}
    else:
        at = getattr(args, "at", None) or (datetime.now(timezone.utc) + timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"kind": "at", "at": at}


def format_schedule_info(schedule):
    """格式化 schedule 信息用于终端输出"""
    kind = schedule["kind"]
    if kind == "at":
        return f"触发时间：{schedule['at']}（一次性）"
    elif kind == "every":
        ms = schedule["everyMs"]
        if ms >= 3600000:
            return f"调度间隔：每 {ms // 3600000}h{(ms % 3600000) // 60000}m（周期性）"
        elif ms >= 60000:
            return f"调度间隔：每 {ms // 60000}m（周期性）"
        else:
            return f"调度间隔：每 {ms // 1000}s（周期性）"
    elif kind == "cron":
        tz = schedule.get("tz", "UTC")
        return f"Cron 表达式：{schedule['expr']}（时区：{tz}）"
    return str(schedule)


def build_message_envelope(from_agent, to_agent, msg_type, message, reply_to=None, notify_user=None):
    """构建消息信封"""
    envelope = {
        "protocol": "agent-coordinator/v1",
        "from": from_agent,
        "to": to_agent,
        "type": msg_type,
        "payload": message,
        "reply_to": reply_to,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if notify_user:
        envelope["notify_user"] = notify_user
    return envelope


def send(args):
    """生成 cron.add 参数 JSON，用于向目标 agent 投递消息。

    如指定 --notify-user，在 cron job 上配置 delivery announce，
    目标 agent 的回复会由 OpenClaw 自动投递给用户，无需独立工具调用。
    """
    if args.to not in AGENTS:
        print_error(f"未知的目标 Agent: {args.to}")
        print_info(f"可用 Agent: {', '.join(AGENTS.keys())}")
        sys.exit(1)

    if args.from_agent not in AGENTS:
        print_error(f"未知的发送方 Agent: {args.from_agent}")
        sys.exit(1)

    envelope = build_message_envelope(
        from_agent=args.from_agent,
        to_agent=args.to,
        msg_type=args.type,
        message=args.message,
        reply_to=args.reply_to,
        notify_user=getattr(args, "notify_user", None),
    )

    envelope_text = (
        f"[Agent Coordination] {json.dumps(envelope, ensure_ascii=False)}"
    )

    # 构建 agentTurn 指令：让目标 agent 解析信封并执行任务
    agent_message = (
        f"你收到了一条 Agent 协调消息，请解析并执行：\n\n{envelope_text}\n\n"
        f"请根据消息内容执行对应操作。"
    )

    # 如有 notify_user，告知 agent 其回复会通过 OpenClaw delivery announce 自动投递给用户
    if args.notify_user:
        agent_message += (
            f"\n\n📨 本次任务已配置 delivery announce，你的回复内容将由 OpenClaw 自动发送给用户 {args.notify_user}。"
            f"请在回复中直接包含面向用户的执行结果摘要，无需额外调用 reply-human。"
        )

    schedule = build_schedule(args)

    cron_job = {
        "name": f"AGENTCREATED: {args.from_agent}→{args.to}: {args.type}",
        "schedule": schedule,
        "sessionTarget": "isolated",
        "agentId": args.to,
        "payload": {
            "kind": "agentTurn",
            "message": agent_message,
        },
    }

    # 如有 notify_user，在 cron job 上配置 delivery announce
    # OpenClaw 会将目标 agent 的回复自动通过飞书投递给用户，无需 agent 额外调用
    if args.notify_user:
        open_id = resolve_open_id(args.notify_user, args.to)
        cron_job["delivery"] = {
            "mode": "announce",
            "channel": "feishu",
            "to": open_id,
            "bestEffort": True,
        }

    print_info(f"协调：{args.from_agent} → {args.to} ({args.type})")
    if args.notify_user:
        print_info(f"delivery announce: {args.notify_user} → {args.to}")
    print()
    print(f"{Colors.BOLD}📨 请将以下 JSON 作为参数调用 cron.add 工具：{Colors.END}")
    print()
    print(json.dumps(cron_job, indent=2, ensure_ascii=False))
    print()
    print_info(format_schedule_info(schedule))


def reply_human(args):
    """生成 cron.add 参数 JSON，委托 agent 执行任务并将结果汇报给用户。

    与 send 类似，创建 cron job 让目标 agent 执行任务。
    区别：reply-human 始终配置 delivery announce，agent 执行完任务后结果自动投递给用户。
    open_id 从统一的 users.json 中按 username + agent_id 查找。
    """
    open_id = resolve_open_id(args.username, args.agent_id)

    schedule = build_schedule(args)

    cron_job = {
        "name": f"AGENTCREATED: {args.agent_id} → {args.username}",
        "schedule": schedule,
        "sessionTarget": "isolated",
        "agentId": args.agent_id,
        "payload": {
            "kind": "agentTurn",
            "message": args.message,
        },
        "delivery": {
            "mode": "announce",
            "channel": "feishu",
            "to": open_id,
            "bestEffort": True,
        },
    }

    print_info(f"委托执行：{args.agent_id}，结果汇报给 {args.username} ({open_id})")
    print_info(f"delivery announce → {args.agent_id}")
    print()
    print(f"{Colors.BOLD}📨 请将以下 JSON 作为参数调用 cron.add 工具：{Colors.END}")
    print()
    print(json.dumps(cron_job, indent=2, ensure_ascii=False))
    print()
    print_info(format_schedule_info(schedule))


def user_add(args):
    """添加/更新用户的某个 agent open_id"""
    users = load_users()
    if args.username not in users:
        users[args.username] = {"name": args.name or args.username, "open_ids": {}}

    if args.name:
        users[args.username]["name"] = args.name

    if "open_ids" not in users[args.username]:
        # 兼容旧格式迁移
        old_open_id = users[args.username].pop("open_id", None)
        users[args.username]["open_ids"] = {}
        if old_open_id:
            print_warning(f"检测到旧格式，已迁移。旧 open_id '{old_open_id}' 需重新绑定到具体 agent")

    users[args.username]["open_ids"][args.agent_id] = args.open_id

    save_users(users)
    print_success(f"用户 '{args.username}' 已设置 agent '{args.agent_id}' 的 open_id: {args.open_id}")


def user_remove(args):
    """删除用户或某个 agent 的 open_id"""
    users = load_users()
    if args.username not in users:
        print_error(f"用户 '{args.username}' 不存在")
        sys.exit(1)

    if args.agent_id:
        open_ids = users[args.username].get("open_ids", {})
        if args.agent_id not in open_ids:
            print_error(f"用户 '{args.username}' 没有 agent '{args.agent_id}' 的 open_id")
            sys.exit(1)
        del open_ids[args.agent_id]
        save_users(users)
        print_success(f"已删除用户 '{args.username}' 的 agent '{args.agent_id}' open_id")
    else:
        del users[args.username]
        save_users(users)
        print_success(f"已删除用户 '{args.username}'")


def user_list(args):
    """列出用户"""
    users = load_users()
    if not users:
        print_info("暂无用户")
        return

    print(f"\n{Colors.BOLD}👥 用户列表{Colors.END}")
    print("━" * 50)
    for username, info in users.items():
        open_ids = info.get("open_ids", {})
        print(f"\n  {Colors.BOLD}{username}{Colors.END}  ({info.get('name', '')})")
        if open_ids:
            for agent_id, oid in open_ids.items():
                print(f"    {agent_id:10s} → {oid}")
        else:
            print(f"    (无 open_id)")
    print()


def user_get(args):
    """查看用户详情"""
    users = load_users()
    if args.username not in users:
        print_error(f"用户 '{args.username}' 不存在")
        sys.exit(1)

    info = users[args.username]
    open_ids = info.get("open_ids", {})
    print(f"\n{Colors.BOLD}👤 用户详情{Colors.END}")
    print("━" * 50)
    print(f"  Username:  {args.username}")
    print(f"  Name:      {info.get('name', '')}")
    print(f"  Open IDs:")
    if open_ids:
        for agent_id, oid in open_ids.items():
            print(f"    {agent_id:10s} → {oid}")
    else:
        print(f"    (无)")
    print()


def list_agents(args):
    """列出所有可用 Agent"""
    print(f"""
{Colors.BOLD}🤖 可用 Agent 列表{Colors.END}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    for agent_id, info in AGENTS.items():
        print(f"  {Colors.BOLD}{agent_id:10s}{Colors.END}  {info['name']}")
        print(f"  {'':10s}  职责：{info['role']}")
        print()


def schedule_cmd(args):
    """独立创建定时任务（不包裹消息信封），用于 Agent 自建任务场景。"""
    schedule = build_schedule(args)

    cron_job = {
        "name": f"AGENTCREATED: {args.agent_id} scheduled task",
        "schedule": schedule,
        "sessionTarget": "isolated",
        "agentId": args.agent_id,
        "payload": {
            "kind": "agentTurn",
            "message": args.message,
        },
    }

    if args.username:
        open_id = resolve_open_id(args.username, args.agent_id)
        cron_job["delivery"] = {
            "mode": "announce",
            "channel": "feishu",
            "to": open_id,
            "bestEffort": True,
        }

    print_info(f"定时任务：{args.agent_id}")
    if args.username:
        print_info(f"delivery announce → {args.username}")
    print()
    print(f"{Colors.BOLD}📨 请将以下 JSON 作为参数调用 cron.add 工具：{Colors.END}")
    print()
    print(json.dumps(cron_job, indent=2, ensure_ascii=False))
    print()
    print_info(format_schedule_info(schedule))


def add_schedule_args(parser):
    """为 parser 添加通用的调度参数（--at, --every, --cron, --tz）"""
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--at", default=None, help="一次性触发时间（ISO 8601，如 2026-03-05T12:00:00Z）。默认 T+20s")
    group.add_argument("--every", default=None, help="固定间隔（如 30s, 5m, 1h, 2h30m）")
    group.add_argument("--cron", default=None, help="Cron 表达式（如 '0 9 * * *'）")
    parser.add_argument("--tz", default=None, help="Cron 时区（如 Asia/Shanghai），仅 --cron 时生效")


def main():
    parser = argparse.ArgumentParser(
        description="Agent Coordinator - 多 Agent 协同调度：任务委派 / 状态同步 / 结果回传 / 人类汇报",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s send --from dev --to ops --message "请部署 main 分支到生产环境"
  %(prog)s send --from dev --to ops --every "30m" --message "每 30 分钟检查服务状态"
  %(prog)s send --from dev --to ops --cron "0 9 * * *" --tz Asia/Shanghai --message "每天 9 点执行检查"
  %(prog)s reply-human --agent-id ops --username cyril --message "开始 v2.1.0 上线部署任务"
  %(prog)s reply-human --agent-id sop --username cyril --every "30m" --message "执行 SOP 健康检查"
  %(prog)s schedule --agent-id sop --every "30m" --message "执行健康检查" --username cyril
  %(prog)s user add --username cyril --name "Cyril" --agent-id dev --open-id ou_xxx
  %(prog)s user list
  %(prog)s list-agents
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # send 命令
    send_parser = subparsers.add_parser("send", help="生成发送给目标 agent 的 crontab JSON")
    send_parser.add_argument("--from", dest="from_agent", required=True, help="发送方 Agent ID")
    send_parser.add_argument("--to", required=True, help="目标 Agent ID")
    send_parser.add_argument("--type", default="request", choices=["request", "response", "notify"], help="消息类型 (默认：request)")
    send_parser.add_argument("--message", required=True, help="消息内容")
    send_parser.add_argument("--reply-to", default=None, help="回复的原始消息 timestamp（可选）")
    send_parser.add_argument("--notify-user", dest="notify_user", default=None,
                             help="任务完成后需通知的用户名（在 cron job 上配置 delivery announce，自动投递结果给用户）")
    add_schedule_args(send_parser)
    send_parser.set_defaults(func=send)

    # reply-human 命令（委托 agent 执行任务，结果通过 delivery announce 汇报给用户）
    reply_parser = subparsers.add_parser("reply-human", help="委托 agent 执行任务并将结果汇报给用户（= send + 必配 delivery announce）")
    reply_parser.add_argument("--agent-id", dest="agent_id", required=True,
                               help="委托 Agent ID（执行任务的 agent）")
    reply_parser.add_argument("--username", required=True, help="结果汇报给谁（从 users.json 查找该 agent 下的 open_id）")
    reply_parser.add_argument("--message", required=True, help="任务描述（agent 执行后结果自动投递给用户）")
    add_schedule_args(reply_parser)
    reply_parser.set_defaults(func=reply_human)

    # schedule 命令（独立创建定时任务，不包裹消息信封）
    schedule_parser = subparsers.add_parser("schedule", help="独立创建定时任务（不包裹消息信封），用于 Agent 自建任务场景")
    schedule_parser.add_argument("--agent-id", dest="agent_id", required=True, help="执行任务的 Agent ID")
    schedule_parser.add_argument("--message", required=True, help="任务描述")
    schedule_parser.add_argument("--username", default=None, help="结果汇报给谁（可选，有则配 delivery）")
    add_schedule_args(schedule_parser)
    schedule_parser.set_defaults(func=schedule_cmd)

    # list-agents 命令
    list_parser = subparsers.add_parser("list-agents", help="列出可用 Agent")
    list_parser.set_defaults(func=list_agents)

    # user 子命令组
    user_parser = subparsers.add_parser(
        "user",
        help="管理用户列表（统一存储各 agent 的 open_id）",
        description="管理用户列表，按 agent 存储各飞书应用下的 open_id。\n\n"
                    "同一用户在不同 agent（不同飞书应用）下有不同的 open_id，\n"
                    "通过 --agent-id 指定要绑定的 agent。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    user_subparsers = user_parser.add_subparsers(dest="user_command", help="用户管理命令")

    # user add
    user_add_parser = user_subparsers.add_parser("add", help="添加/更新用户的某个 agent open_id")
    user_add_parser.add_argument("--username", required=True, help="用户名（唯一标识）")
    user_add_parser.add_argument("--name", default=None, help="显示名")
    user_add_parser.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID（如 dev, sop, ops）")
    user_add_parser.add_argument("--open-id", required=True, help="该用户在此 agent 飞书应用下的 open_id")
    user_add_parser.set_defaults(func=user_add)

    # user remove
    user_remove_parser = user_subparsers.add_parser("remove", help="删除用户或某个 agent 的 open_id")
    user_remove_parser.add_argument("--username", required=True, help="用户名")
    user_remove_parser.add_argument("--agent-id", dest="agent_id", default=None, help="指定则只删该 agent 的 open_id，不指定则删除整个用户")
    user_remove_parser.set_defaults(func=user_remove)

    # user list
    user_list_parser = user_subparsers.add_parser("list", help="列出用户")
    user_list_parser.set_defaults(func=user_list)

    # user get
    user_get_parser = user_subparsers.add_parser("get", help="查看用户详情")
    user_get_parser.add_argument("--username", required=True, help="用户名")
    user_get_parser.set_defaults(func=user_get)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "user" and getattr(args, "user_command", None) is None:
        user_parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as e:
        print_error(f"命令执行失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
