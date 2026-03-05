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

Agent Account 映射：/home/admin/.openclaw/workspace-{agent}/skills/agent-cron-job/data/agent-accounts.json
  用于在 isolated session 中使用 message 工具时自动获取正确的 accountId。
"""

import argparse
import json
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
AGENT_ACCOUNTS_PATH = Path("/home/admin/.openclaw/workspace-dev/skills/agent-cron-job/data/agent-accounts.json")


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


def load_agent_accounts():
    """读取 agent-accounts.json，获取 agent 到 accountId 的映射"""
    if not AGENT_ACCOUNTS_PATH.exists():
        return {}
    return json.loads(AGENT_ACCOUNTS_PATH.read_text(encoding="utf-8"))


def get_account_id(agent_id):
    """获取指定 agent 的 accountId"""
    accounts = load_agent_accounts()
    mappings = accounts.get("mappings", {})
    if agent_id not in mappings:
        print_error(f"Agent '{agent_id}' 没有配置 accountId")
        print_info(f"可用 Agent: {', '.join(mappings.keys())}")
        sys.exit(1)
    return mappings[agent_id]["accountId"]


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

    # 计算 20 秒后的 ISO 8601 时间戳
    fire_at = (datetime.now(timezone.utc) + timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ")

    cron_job = {
        "name": f"AGENTCREATED: {args.from_agent}→{args.to}: {args.type}",
        "schedule": {"kind": "at", "at": fire_at},
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
        }

    print_info(f"协调：{args.from_agent} → {args.to} ({args.type})")
    if args.notify_user:
        print_info(f"delivery announce: {args.notify_user} → {args.to}")
    print()
    print(f"{Colors.BOLD}📨 请将以下 JSON 作为参数调用 cron.add 工具：{Colors.END}")
    print()
    print(json.dumps(cron_job, indent=2, ensure_ascii=False))
    print()
    print_info(f"触发时间：{fire_at}（约 20 秒后）")


def reply_human(args):
    """生成 cron.add 参数 JSON，委托 agent 执行任务并将结果汇报给用户。

    与 send 类似，创建 cron job 让目标 agent 执行任务。
    区别：reply-human 始终配置 delivery announce，agent 执行完任务后结果自动投递给用户。
    open_id 从统一的 users.json 中按 username + agent_id 查找。
    """
    open_id = resolve_open_id(args.username, args.agent_id)

    fire_at = (datetime.now(timezone.utc) + timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ")

    cron_job = {
        "name": f"AGENTCREATED: {args.agent_id} → {args.username}",
        "schedule": {"kind": "at", "at": fire_at},
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
        },
    }

    print_info(f"委托执行：{args.agent_id}，结果汇报给 {args.username} ({open_id})")
    print_info(f"delivery announce → {args.agent_id}")
    print()
    print(f"{Colors.BOLD}📨 请将以下 JSON 作为参数调用 cron.add 工具：{Colors.END}")
    print()
    print(json.dumps(cron_job, indent=2, ensure_ascii=False))
    print()
    print_info(f"触发时间：{fire_at}（约 20 秒后，OpenClaw 自动投递）")


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
    accounts = load_agent_accounts()
    mappings = accounts.get("mappings", {})
    
    print(f"""
{Colors.BOLD}🤖 可用 Agent 列表{Colors.END}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    for agent_id, info in AGENTS.items():
        account_id = mappings.get(agent_id, {}).get("accountId", "未配置")
        print(f"  {Colors.BOLD}{agent_id:10s}{Colors.END}  {info['name']}")
        print(f"  {'':10s}  职责：{info['role']}")
        print(f"  {'':10s}  AccountId: {account_id}")
        print()


def get_account_id_cmd(args):
    """获取指定 agent 的 accountId"""
    account_id = get_account_id(args.agent_id)
    print_success(f"Agent '{args.agent_id}' 的 accountId: {account_id}")


def generate_message_command(args):
    """生成 message 工具调用命令，包含正确的 accountId"""
    account_id = get_account_id(args.agent_id)
    
    message_cmd = {
        "action": "send",
        "channel": "feishu",
        "accountId": account_id,
        "target": f"user:{args.open_id}",
        "message": args.message,
    }
    
    print_info(f"为 Agent '{args.agent_id}' 生成 message 工具调用命令")
    print_info(f"使用 accountId: {account_id}")
    print()
    print(f"{Colors.BOLD}📨 请使用以下参数调用 message 工具：{Colors.END}")
    print()
    print(json.dumps(message_cmd, indent=2, ensure_ascii=False))
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Agent Coordinator - 多 Agent 协同调度：任务委派 / 状态同步 / 结果回传 / 人类汇报",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s send --from dev --to ops --message "请部署 main 分支到生产环境"
  %(prog)s reply-human --agent-id ops --username cyril --message "开始 v2.1.0 上线部署任务，汇报部署结果给 cyril"
  %(prog)s user add --username cyril --name "Cyril" --agent-id dev --open-id ou_xxx
  %(prog)s user list
  %(prog)s user get --username cyril
  %(prog)s user remove --username cyril
  %(prog)s list-agents
  %(prog)s get-account-id --agent-id dev
  %(prog)s message-cmd --agent-id dev --open-id ou_xxx --message "测试消息"
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
    send_parser.set_defaults(func=send)

    # reply-human 命令（委托 agent 执行任务，结果通过 delivery announce 汇报给用户）
    reply_parser = subparsers.add_parser("reply-human", help="委托 agent 执行任务并将结果汇报给用户（= send + 必配 delivery announce）")
    reply_parser.add_argument("--agent-id", dest="agent_id", required=True,
                               help="委托 Agent ID（执行任务的 agent）")
    reply_parser.add_argument("--username", required=True, help="结果汇报给谁（从 users.json 查找该 agent 下的 open_id）")
    reply_parser.add_argument("--message", required=True, help="任务描述（agent 执行后结果自动投递给用户）")
    reply_parser.set_defaults(func=reply_human)

    # list-agents 命令
    list_parser = subparsers.add_parser("list-agents", help="列出可用 Agent")
    list_parser.set_defaults(func=list_agents)

    # get-account-id 命令
    get_account_parser = subparsers.add_parser("get-account-id", help="获取指定 agent 的 accountId")
    get_account_parser.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    get_account_parser.set_defaults(func=get_account_id_cmd)

    # message-cmd 命令（生成 message 工具调用命令）
    message_parser = subparsers.add_parser("message-cmd", help="生成 message 工具调用命令（含正确的 accountId）")
    message_parser.add_argument("--agent-id", dest="agent_id", required=True, help="Agent ID")
    message_parser.add_argument("--open-id", required=True, help="目标用户 open_id")
    message_parser.add_argument("--message", required=True, help="消息内容")
    message_parser.set_defaults(func=generate_message_command)

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
