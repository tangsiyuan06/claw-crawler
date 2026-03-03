# Agent 间任务队列 - SOP 下发给 Crawler

此目录用于 SOP Agent 向 Crawler Agent 下发调研任务。

## 使用说明
1. SOP Agent 在此目录创建任务文件
2. Crawler Agent 定期扫描此目录
3. 执行完成后更新任务状态

## 任务文件格式
```json
{
  "taskId": "唯一 ID",
  "createdAt": "ISO 时间戳",
  "from": "sop",
  "to": "crawler",
  "type": "research",
  "priority": "normal|high|urgent",
  "status": "pending|processing|completed|failed",
  "task": {
    "title": "任务标题",
    "description": "任务描述",
    "target": "目标 URL 或关键词",
    "deadline": "可选截止时间"
  },
  "result": {
    "completedAt": "完成时间",
    "findings": [],
    "summary": "摘要"
  }
}
```
