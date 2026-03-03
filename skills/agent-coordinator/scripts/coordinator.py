#!/usr/bin/env python3
"""
Agent Coordinator - 多 Agent 协同调度

跨 Agent 任务委派、状态同步、结果回传，以及向人类主动汇报。
Agent 间通过 crontab 消息总线异步协调，Agent → Human 通过飞书 API 汇报。
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


# Agent 列表
AGENTS = {
    "main": {"name": "主智能体", "role": "日常对话 + 通用任务", "session_key": "agent:main:feishu:feishubot"},
    "dev": {"name": "开发智能体", "role": "技能开发 + 技术方案", "session_key": "agent:dev:feishu:feishu-dev"},
    "sop": {"name": "SOP 智能体", "role": "SOP 制定 + 流程优化", "session_key": "agent:sop:feishu:feishu-sop"},
    "ops": {"name": "运维智能体", "role": "运维部署 + 监控", "session_key": "agent:ops:feishu:feishu-ops"},
    "crawler": {"name": "爬虫智能体", "role": "数据爬取 + API 分析", "session_key": "agent:crawler:feishu:feishu-crawler"},
}

FEISHU_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "feishu-config.json"
USERS_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "users.json"


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
    """写入 users.json"""
    USERS_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_DATA_PATH.write_text(
        json.dumps(users, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def resolve_open_id(username):
    """通过 username 从当前 agent 的 users.json 查找 open_id。

    每个 agent 有独立工作空间，各自维护自己的用户列表。
    同一用户在不同 agent（不同飞书应用）下有不同的 open_id。
    """
    users = load_users()
    if username not in users:
        print_error(f"用户 '{username}' 不存在，请先用 user add 添加")
        sys.exit(1)

    open_id = users[username].get("open_id")
    if not open_id:
        print_error(f"用户 '{username}' 未设置 open_id")
        sys.exit(1)

    return open_id


def build_message_envelope(from_agent, to_agent, msg_type, message, reply_to=None):
    """构建消息信封"""
    return {
        "protocol": "agent-coordinator/v1",
        "from": from_agent,
        "to": to_agent,
        "type": msg_type,
        "payload": message,
        "reply_to": reply_to,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def send(args):
    """生成发送给目标 agent 的 crontab JSON"""
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
    )

    envelope_text = (
        f"[Agent Coordination] {json.dumps(envelope, ensure_ascii=False)}"
    )

    crontab_json = {
        "schedule": {"kind": "at", "at": "+20s"},
        "sessionTarget": "main",
        "wakeMode": "now",
        "agentId": args.to,
        "payload": {
            "kind": "systemEvent",
            "text": envelope_text,
        },
        "deleteAfterRun": True,
    }

    print_info(f"消息: {args.from_agent} → {args.to} ({args.type})")
    print()
    print(f"{Colors.BOLD}📨 Crontab JSON（请将此 JSON 作为参数调用 cron.add）：{Colors.END}")
    print()
    print(json.dumps(crontab_json, indent=2, ensure_ascii=False))
    print()
    print_info("下一步：复制上面的 JSON，调用 cron.add 工具完成发送")


def get_feishu_token():
    """获取飞书 tenant_access_token"""
    if not FEISHU_CONFIG_PATH.exists():
        print_error(f"飞书配置文件不存在: {FEISHU_CONFIG_PATH}")
        sys.exit(1)

    config = json.loads(FEISHU_CONFIG_PATH.read_text())
    app_id = config["appId"]
    app_secret = config["appSecret"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("code") != 0:
                print_error(f"获取 token 失败: {result.get('msg')}")
                sys.exit(1)
            return result["tenant_access_token"]
    except urllib.error.URLError as e:
        print_error(f"网络请求失败: {e}")
        sys.exit(1)


def reply_human(args):
    """通过飞书 API 向指定用户发送消息"""
    open_id = resolve_open_id(args.username)
    token = get_feishu_token()

    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = "?receive_id_type=open_id"

    msg_content = json.dumps({"text": args.message}, ensure_ascii=False)
    body = {
        "receive_id": open_id,
        "msg_type": "text",
        "content": msg_content,
    }

    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(
        url + params,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("code") != 0:
                print_error(f"发送失败: {result.get('msg')}")
                sys.exit(1)
            print_success(f"消息已发送给用户 {open_id}")
            print_info(f"message_id: {result.get('data', {}).get('message_id', 'N/A')}")
    except urllib.error.URLError as e:
        print_error(f"网络请求失败: {e}")
        sys.exit(1)


def user_add(args):
    """添加/更新用户"""
    users = load_users()
    if args.username not in users:
        users[args.username] = {"name": args.name or args.username, "open_id": args.open_id}
    else:
        if args.name:
            users[args.username]["name"] = args.name
        users[args.username]["open_id"] = args.open_id

    save_users(users)
    print_success(f"用户 '{args.username}' 已设置 (open_id: {args.open_id})")


def user_remove(args):
    """删除用户"""
    users = load_users()
    if args.username not in users:
        print_error(f"用户 '{args.username}' 不存在")
        sys.exit(1)

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
        open_id = info.get("open_id", "")
        print(f"\n  {Colors.BOLD}{username}{Colors.END}  ({info.get('name', '')})")
        print(f"    open_id: {open_id}")
    print()


def user_get(args):
    """查看用户详情"""
    users = load_users()
    if args.username not in users:
        print_error(f"用户 '{args.username}' 不存在")
        sys.exit(1)

    info = users[args.username]
    print(f"\n{Colors.BOLD}👤 用户详情{Colors.END}")
    print("━" * 50)
    print(f"  Username: {args.username}")
    print(f"  Name:     {info.get('name', '')}")
    print(f"  Open ID:  {info.get('open_id', '')}")
    print()


def list_agents(args):
    """列出所有可用 Agent"""
    print(f"""
{Colors.BOLD}🤖 可用 Agent 列表{Colors.END}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    for agent_id, info in AGENTS.items():
        print(f"  {Colors.BOLD}{agent_id:10s}{Colors.END}  {info['name']}")
        print(f"  {'':10s}  职责: {info['role']}")
        print(f"  {'':10s}  Session: {info['session_key']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Agent Coordinator - 多 Agent 协同调度：任务委派 / 状态同步 / 结果回传 / 人类汇报",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s send --from dev --to ops --message "请部署 main 分支到生产环境"
  %(prog)s reply-human --username cyril --message "部署已完成"
  %(prog)s user add --username cyril --name "Cyril" --open-id ou_xxx
  %(prog)s user list
  %(prog)s user get --username cyril
  %(prog)s user remove --username cyril
  %(prog)s list-agents
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # send 命令
    send_parser = subparsers.add_parser("send", help="生成发送给目标 agent 的 crontab JSON")
    send_parser.add_argument("--from", dest="from_agent", required=True, help="发送方 Agent ID")
    send_parser.add_argument("--to", required=True, help="目标 Agent ID")
    send_parser.add_argument("--type", default="request", choices=["request", "response", "notify"], help="消息类型 (默认: request)")
    send_parser.add_argument("--message", required=True, help="消息内容")
    send_parser.add_argument("--reply-to", default=None, help="回复的原始消息 timestamp（可选）")
    send_parser.set_defaults(func=send)

    # reply-human 命令
    reply_parser = subparsers.add_parser("reply-human", help="通过飞书向用户汇报结果")
    reply_parser.add_argument("--username", required=True, help="用户名（从当前 agent 的 users.json 查找 open_id）")
    reply_parser.add_argument("--message", required=True, help="消息内容")
    reply_parser.set_defaults(func=reply_human)

    # list-agents 命令
    list_parser = subparsers.add_parser("list-agents", help="列出可用 Agent")
    list_parser.set_defaults(func=list_agents)

    # user 子命令组
    user_parser = subparsers.add_parser("user", help="用户管理")
    user_subparsers = user_parser.add_subparsers(dest="user_command", help="用户管理命令")

    # user add
    user_add_parser = user_subparsers.add_parser("add", help="添加/更新用户")
    user_add_parser.add_argument("--username", required=True, help="用户名（唯一标识）")
    user_add_parser.add_argument("--name", default=None, help="显示名")
    user_add_parser.add_argument("--open-id", required=True, help="用户的飞书 open_id")
    user_add_parser.set_defaults(func=user_add)

    # user remove
    user_remove_parser = user_subparsers.add_parser("remove", help="删除用户")
    user_remove_parser.add_argument("--username", required=True, help="用户名")
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
