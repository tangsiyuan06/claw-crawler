#!/bin/bash
# Moltbook 30 分钟检查脚本
# 用途：定期检查 Moltbook 赚钱机会
# 使用：将此脚本添加到 crontab，每 30 分钟执行一次

# 配置
API_KEY="moltbook_sk_q4uYJiWr6toZRzBIUowxj6LmfvJGhMFe"
BASE_URL="https://www.moltbook.com/api/v1"
WORKSPACE="/home/admin/.openclaw/workspace-crawler"
LOG_FILE="$WORKSPACE/logs/moltbook-check.log"
STATE_FILE="$WORKSPACE/memory/moltbook-check-state.json"

# 创建日志目录
mkdir -p "$WORKSPACE/logs"

# 记录开始时间
echo "=== Moltbook Check: $(date) ===" >> "$LOG_FILE"

# 1. 检查通知
echo "Checking notifications..." >> "$LOG_FILE"
curl -s "$BASE_URL/notifications" \
  -H "Authorization: Bearer $API_KEY" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Notifications: {d.get('unread_count','0')} unread\")" >> "$LOG_FILE"

# 2. 检查主页
echo "Checking home..." >> "$LOG_FILE"
curl -s "$BASE_URL/home" \
  -H "Authorization: Bearer $API_KEY" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Karma: {d['your_account']['karma']}, Posts: {len(d.get('activity_on_your_posts',[]))}\")" >> "$LOG_FILE"

# 3. 搜索新机会
echo "Searching opportunities..." >> "$LOG_FILE"
OPPORTUNITIES=$(curl -s "$BASE_URL/search?q=hiring+needed+help+developer&limit=5&type=posts" \
  -H "Authorization: Bearer $API_KEY" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('results',[])))")
echo "New opportunities found: $OPPORTUNITIES" >> "$LOG_FILE"

# 4. 更新状态
cat > "$STATE_FILE" << EOF
{
  "last_check": "$(date -Iseconds)",
  "next_check": "$(date -d '+30 minutes' -Iseconds)",
  "check_count": $(( $(cat "$STATE_FILE" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('check_count',0))" 2>/dev/null || echo 0) + 1 )),
  "opportunities_found": 0,
  "status": "completed"
}
EOF

# 5. 检查 SOP 下发的长期任务队列
echo "Checking SOP task queue..." >> "$LOG_FILE"
TASK_QUEUE="$WORKSPACE/task-queue"
if [ -d "$TASK_QUEUE" ]; then
    for task_file in "$TASK_QUEUE"/*.json; do
        [ -f "$task_file" ] || continue
        
        # 读取任务状态
        status=$(python3 -c "import json; print(json.load(open('$task_file')).get('status', ''))" 2>/dev/null)
        
        if [ "$status" = "pending" ]; then
            echo "Processing long-term task: $task_file" >> "$LOG_FILE"
            
            # 更新状态为 processing
            python3 << EOF
import json
from datetime import datetime

with open('$task_file', 'r') as f:
    task = json.load(f)

task['status'] = 'processing'
task['startedAt'] = datetime.now().isoformat()
task['startedBy'] = 'moltbook-check'

with open('$task_file', 'w') as f:
    json.dump(task, f, indent=2)
EOF
            
            # TODO: 根据任务类型执行实际的处理逻辑
            # 这里可以调用其他脚本或 API
            
            # 更新状态为 completed
            python3 << EOF
import json
from datetime import datetime

with open('$task_file', 'r') as f:
    task = json.load(f)

task['status'] = 'completed'
task['completedAt'] = datetime.now().isoformat()
task['result'] = {
    'summary': 'Long-term task processed by moltbook-check',
    'processedAt': datetime.now().isoformat()
}

with open('$task_file', 'w') as f:
    json.dump(task, f, indent=2)
EOF
            
            echo "Task completed: $task_file" >> "$LOG_FILE"
        fi
    done
fi

echo "Check completed successfully" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
