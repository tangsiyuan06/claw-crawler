#!/bin/bash
# 每日大模型资讯获取脚本
# 用于 HEARTBEAT 定时任务调用

# 资讯源列表
SOURCES=(
    "https://www.theverge.com/ai-artificial-intelligence"
    "https://huggingface.co/blog"
    "https://openai.com/news/"
)

# 获取并整理资讯
echo "正在获取最新大模型资讯..."

# 这里会通过 OpenClaw 工具调用 web_fetch 获取内容
# 然后通过 message 工具发送给管理员

# 管理员 Feishu ID: ou_9969ed2bf0d27939ae203e88b3e99551
echo "资讯获取完成，准备发送..."
