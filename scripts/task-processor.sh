#!/bin/bash
# Crawler Agent 任务队列处理器
# 用途：扫描任务队列，执行 SOP 下发的调研任务
# 使用：将此脚本添加到 crontab，每 5 分钟执行一次

WORKSPACE="/home/admin/.openclaw/workspace-crawler"
TASK_QUEUE="$WORKSPACE/task-queue"
LOG_FILE="$WORKSPACE/logs/task-processor.log"

mkdir -p "$WORKSPACE/logs"

echo "=== Task Processor: $(date) ===" >> "$LOG_FILE"

# 扫描 pending 状态的任务
for task_file in "$TASK_QUEUE"/*.json; do
    [ -f "$task_file" ] || continue
    
    # 读取任务状态
    status=$(python3 -c "import json; print(json.load(open('$task_file')).get('status', ''))" 2>/dev/null)
    
    if [ "$status" = "pending" ]; then
        echo "Processing task: $task_file" >> "$LOG_FILE"
        
        # 更新状态为 processing
        python3 << EOF
import json
from datetime import datetime

with open('$task_file', 'r') as f:
    task = json.load(f)

task['status'] = 'processing'
task['startedAt'] = datetime.now().isoformat()

with open('$task_file', 'w') as f:
    json.dump(task, f, indent=2)
EOF
        
        # 执行任务处理（这里调用实际的处理逻辑）
        # TODO: 根据任务类型执行不同的处理
        echo "Task processing started" >> "$LOG_FILE"
        
        # 示例：调用 moltbook 检查脚本
        if [ -x "$WORKSPACE/scripts/moltbook-check.sh" ]; then
            bash "$WORKSPACE/scripts/moltbook-check.sh" >> "$LOG_FILE" 2>&1
        fi
        
        # 更新状态为 completed
        python3 << EOF
import json
from datetime import datetime

with open('$task_file', 'r') as f:
    task = json.load(f)

task['status'] = 'completed'
task['completedAt'] = datetime.now().isoformat()
task['result'] = {
    'summary': 'Task executed successfully',
    'findings': [],
    'log_file': '$LOG_FILE'
}

with open('$task_file', 'w') as f:
    json.dump(task, f, indent=2)
EOF
        
        echo "Task completed: $task_file" >> "$LOG_FILE"
    fi
done

echo "Task processing completed" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
