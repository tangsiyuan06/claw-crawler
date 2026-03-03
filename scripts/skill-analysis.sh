#!/bin/bash
# 技能分析报告脚本
# 定期分析 OpenClaw 热门技能并生成报告

REPORT_DIR="/home/admin/.openclaw/workspace-crawler/reports"
REPORT_FILE="$REPORT_DIR/skill-analysis-$(date +%Y%m%d-%H%M%S).md"

# 创建报告目录
mkdir -p "$REPORT_DIR"

echo "# OpenClaw 技能分析报告" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 分析本地技能
echo "## 本地已安装技能" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

SKILL_COUNT=0
echo '```' >> "$REPORT_FILE"
for skill_dir in /opt/openclaw/skills/*/; do
    if [ -f "$skill_dir/SKILL.md" ]; then
        skill_name=$(basename "$skill_dir")
        # 提取技能名称和描述
        name_line=$(grep "^name:" "$skill_dir/SKILL.md" 2>/dev/null | head -1)
        desc_line=$(grep "^description:" "$skill_dir/SKILL.md" 2>/dev/null | head -1)
        
        if [ -n "$name_line" ]; then
            skill_name=$(echo "$name_line" | sed 's/name: *//' | tr -d '"')
        fi
        
        echo "- $skill_name" >> "$REPORT_FILE"
        if [ -n "$desc_line" ]; then
            desc=$(echo "$desc_line" | sed 's/description: *//' | tr -d '"')
            echo "  - $desc" >> "$REPORT_FILE"
        fi
        ((SKILL_COUNT++))
    fi
done
echo '```' >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**总计**: $SKILL_COUNT 个技能" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 分析扩展技能
echo "## 扩展技能" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

EXT_SKILL_COUNT=0
if [ -d "/home/admin/.openclaw/extensions" ]; then
    echo '```' >> "$REPORT_FILE"
    for ext_dir in /home/admin/.openclaw/extensions/*/skills/*/; do
        if [ -f "$ext_dir/SKILL.md" ]; then
            ext_name=$(dirname "$ext_dir")
            ext_name=$(basename "$ext_name")
            skill_name=$(basename "$ext_dir")
            echo "- $ext_name/$skill_name" >> "$REPORT_FILE"
            ((EXT_SKILL_COUNT++))
        fi
    done
    echo '```' >> "$REPORT_FILE"
fi
echo "**总计**: $EXT_SKILL_COUNT 个扩展技能" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 工作区技能
echo "## 工作区技能" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

WORKSPACE_SKILL_COUNT=0
if [ -d "/home/admin/.openclaw/workspace-crawler/skills" ]; then
    echo '```' >> "$REPORT_FILE"
    for ws_skill in /home/admin/.openclaw/workspace-crawler/skills/*/; do
        if [ -f "$ws_skill/SKILL.md" ]; then
            skill_name=$(basename "$ws_skill")
            name_line=$(grep "^name:" "$ws_skill/SKILL.md" 2>/dev/null | head -1)
            
            if [ -n "$name_line" ]; then
                skill_name=$(echo "$name_line" | sed 's/name: *//' | tr -d '"')
            fi
            
            echo "- $skill_name" >> "$REPORT_FILE"
            ((WORKSPACE_SKILL_COUNT++))
        fi
    done
    echo '```' >> "$REPORT_FILE"
fi
echo "**总计**: $WORKSPACE_SKILL_COUNT 个工作区技能" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 尝试获取 ClawHub 热门技能（如果 clawhub CLI 可用）
echo "## ClawHub 热门技能" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if command -v clawhub &> /dev/null; then
    echo '```' >> "$REPORT_FILE"
    clawhub search "" --limit 20 2>/dev/null >> "$REPORT_FILE" || echo "无法获取 ClawHub 技能列表" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
else
    echo "_clawhub CLI 未安装，无法获取在线技能列表_" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "安装方法:" >> "$REPORT_FILE"
    echo '```bash' >> "$REPORT_FILE"
    echo "npm install -g clawhub" >> "$REPORT_FILE"
    echo '```' >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# 统计摘要
echo "## 统计摘要" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "| 类别 | 数量 |" >> "$REPORT_FILE"
echo "|------|------|" >> "$REPORT_FILE"
echo "| 核心技能 | $SKILL_COUNT |" >> "$REPORT_FILE"
echo "| 扩展技能 | $EXT_SKILL_COUNT |" >> "$REPORT_FILE"
echo "| 工作区技能 | $WORKSPACE_SKILL_COUNT |" >> "$REPORT_FILE"
echo "| **总计** | **$((SKILL_COUNT + EXT_SKILL_COUNT + WORKSPACE_SKILL_COUNT))** |" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 输出报告路径
echo "报告已生成：$REPORT_FILE"

# 同时输出到标准输出，方便查看
cat "$REPORT_FILE"
