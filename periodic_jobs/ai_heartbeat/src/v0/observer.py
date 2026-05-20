#!/usr/bin/env python3
"""
L1 Observer Agent (Trigger Script)
Instructs OpenCode-Builder to autonomously scan, filter, and write to memory.
"""
import os
import sys
import time
from datetime import datetime
from opencode_client import OpenCodeClient

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
KNOWLEDGE_BASE = os.path.join(_WORKSPACE_ROOT, "periodic_jobs", "ai_heartbeat", "docs", "KNOWLEDGE_BASE.md")
OBSERVATIONS_PATH = os.path.join(_WORKSPACE_ROOT, "contexts", "memory", "OBSERVATIONS.md")

PROMPT_TEMPLATE = """
【目标】：执行观测记忆提取并直接持久化到磁盘。
【基准日期】：{target_date}

【幂等性约束】：在执行任何写入前，**必须先**读取 OBSERVATIONS.md，检查是否已存在 `Date: {target_date}` 的条目。若存在，则**不要进行任何文件修改**，直接回复「Entry for {target_date} already exists, skipping」即可。

【SOP 路径】：
{kb_path}

【任务内容】：
1. **获取 Context**：请阅读上述 SOP 以及其中引用的 L3 约束文件。
2. **幂等性检查**：读取 OBSERVATIONS.md，若已有 `Date: {target_date}` 则跳过后续步骤。
3. **扫描与过滤**：扫描根目录（{workspace_root}）下 **所有** 以下目录的变动：
   - `contexts/thought_review/`
   - `contexts/survey_sessions/`
   - `contexts/agent_failure_cases/`
   - `contexts/memory/`
   - `contexts/daily_records/`（仅关注新增文件，忽略内容细节）
   - `contexts/life_record/`
   - `contexts/blog/`
   - `rules/`（skills, axioms 等）
   - `periodic_jobs/`
   - `adhoc_jobs/`
   - `tools/`
   使用 `find <dir> -type f -mtime -1` 逐目录扫描，不要只扫单个目录。
4. **写入记忆**：将针对 {target_date} 的 🔴 🟡 🟢 观测结果直接写入或追加到 `{observations_path}`。**鼓励使用命令行 append**（如 `echo "..." >> OBSERVATIONS.md` 或 `tee -a`），避免对大文件做全文编辑。
5. **范围约束**：**仅执行 L1 Observer 任务**。不要执行 SOP 中提到的 L2 Reflector 任务（即不要修改 `rules/` 下的任何文件，不要进行规则晋升或垃圾回收）。
6. **格式规范**：
   - 日期 Header 必须严格使用 `Date: YYYY-MM-DD` 格式（Date 首字母大写，冒号后空格，日期为 ISO 格式）。
   - 在结果文件中提到任何文件或目录时，**必须使用相对于根目录的完整路径**（例如：`rules/skills/workflow_deep_research_survey.md`），不要只写文件名。
7. **汇报**：完成后，在此回复一个简短的 Walkthrough。
"""

def main():
    import argparse
    parser = argparse.ArgumentParser(description='L1 Observer Agent')
    parser.add_argument('date', nargs='?', default=datetime.now().strftime("%Y-%m-%d"),
                        help='Target date (YYYY-MM-DD)')
    parser.add_argument('--model', default='openai/gpt-5.2',
                        help='Model ID to use (format: provider/model-id or just model-id)')
    parser.add_argument('--no-delete', action='store_true',
                        help='Keep session after completion (default: delete)')
    args = parser.parse_args()

    target_date = args.date
    model_id = args.model
    delete_after = not args.no_delete

    # Idempotency: skip if entry for target_date already exists
    if os.path.exists(OBSERVATIONS_PATH):
        with open(OBSERVATIONS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        if f"Date: {target_date}" in content:
            print(f"Idempotent skip: entry for {target_date} already exists in OBSERVATIONS.md")
            return

    print(f"Triggering Fully Agentic Observer for date: {target_date} using model: {model_id}...")
    client = OpenCodeClient()
    
    session_id = client.create_session(f"Heartbeat L1 - Persistence Mode - {target_date}")
    if not session_id:
        return
        
    prompt = PROMPT_TEMPLATE.format(kb_path=KNOWLEDGE_BASE, target_date=target_date,
                                    workspace_root=_WORKSPACE_ROOT, observations_path=OBSERVATIONS_PATH)
    client.send_message(session_id, prompt, model_id=model_id, agent="build")
    # If send_message timed out, agent may still be running; poll until done
    print("Waiting for session to complete (sync mode)...")
    client.wait_for_session_complete(session_id)
    # Ephemeral: delete session by default (--no-delete to keep)
    if delete_after:
        if client.delete_session(session_id):
            print(f"Task complete (session {session_id} deleted).")
        else:
            print(f"Task complete (Session: {session_id}).")
    else:
        print(f"Task complete (Session: {session_id}).")

if __name__ == "__main__":
    main()
