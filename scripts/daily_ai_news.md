# 每日大模型资讯获取流程

## 任务说明
每日 8:30 自动获取最新大模型资讯并发送给管理员

## 执行步骤

### 1. 抓取资讯源
- https://www.theverge.com/ai-artificial-intelligence
- https://huggingface.co/blog
- https://openai.com/news/
- https://news.ycombinator.com/

### 2. 整理内容
- 提取头条新闻
- 整理行业动态
- 格式化输出

### 3. 发送给管理员
- 接收人：Cyril (ou_9969ed2bf0d27939ae203e88b3e99551)
- 渠道：飞书

## Cron 配置命令

```bash
openclaw cron add \
  --name "daily_ai_news" \
  --cron "30 8 * * *" \
  --message "请获取最新大模型热门资讯并发送给我" \
  --tz "Asia/Shanghai" \
  --description "每日大模型资讯推送"
```

## 查看任务状态

```bash
# 查看已配置的任务
openclaw cron list

# 查看任务执行历史
openclaw cron runs

# 手动测试执行
openclaw cron run daily_ai_news
```
