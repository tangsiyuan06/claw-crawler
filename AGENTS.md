# AGENTS.md - 网络爬虫工作区

This folder is home. Treat it that way.

## Crawler Agent Configuration
- Specialized for web crawling and content extraction
- Enhanced browser automation capabilities
- Advanced network request handling
- Support for JavaScript-heavy websites

## 团队成员列表 (Team Members)
- **Main Agent** (`main`): 通用对话和任务处理，团队协调者
- **Ops Agent** (`ops`): 服务器运维专家，负责系统监控和维护  
- **Crawler Agent** (`crawler`): 网络爬虫专家，负责网页内容提取和数据抓取

## Agent 间通讯
- 启用 agent-to-agent 内部通讯
- 可以向其他 team members 发送消息和请求协助
- 使用 `sessions_send` 工具进行跨 agent 通信
- 遵循团队协作协议和安全边界