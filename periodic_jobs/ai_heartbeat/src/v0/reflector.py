#!/usr/bin/env python3
"""
L2 Reflector Agent (Trigger Script)
Instructs OpenCode-Builder to perform memory garbage collection directly on the file.
"""
import os
import sys
from opencode_client import OpenCodeClient
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
KNOWLEDGE_BASE = os.path.join(_WORKSPACE_ROOT, "periodic_jobs", "ai_heartbeat", "docs", "KNOWLEDGE_BASE.md")
OBSERVATIONS_PATH = os.path.join(_WORKSPACE_ROOT, "contexts", "memory", "OBSERVATIONS.md")

PROMPT_TEMPLATE = """
执行记忆系统的"反思与晋升"任务。

【SOP 路径】：{kb_path}
【观测文件】：{observations_path}
【工作区根目录】：{workspace_root}

步骤：
1. 先读取 SOP（上述路径）以及 L3 约束文件（`rules/` 下的 SOUL.md, USER.md, COMMUNICATION.md, WORKSPACE.md）。
2. 读取 {observations_path}，分析所有 🔴 和高优 🟡 条目。
3. 将具有普适性的内容晋升到 rules/，按职责边界分类：
   - SOUL.md: Agent 身份与核心价值观
   - USER.md: 用户画像与人生哲学
   - COMMUNICATION.md: 沟通风格（仅限沟通，不含技术知识）
   - WORKSPACE.md: 目录路由
   - skills/: 技术方法论、工作流、最佳实践
4. GC：重写 {observations_path}，删除已晋升内容及过期 🟢 记录。保留头部格式说明不变。
5. 所有文件引用使用相对于根目录（{workspace_root}）的路径。

晋升门槛：跨项目通用 + 多次验证 + 有明确适用场景。
完成后回复简短晋升汇报。
"""

def main():
    import argparse
    parser = argparse.ArgumentParser(description='L2 Reflector Agent')
    parser.add_argument('--model', default='openai/gpt-5.2',
                        help='Model ID to use (format: provider/model-id or just model-id)')
    parser.add_argument('--no-delete', action='store_true',
                        help='Keep session after completion (default: delete)')
    args = parser.parse_args()

    model_id = args.model
    delete_after = not args.no_delete
    target_date = datetime.now().strftime("%Y-%m-%d")

    print(f"Triggering Fully Agentic Reflector using model: {model_id}...")
    client = OpenCodeClient()

    session_id = client.create_session(f"Heartbeat L2 Reflector - {target_date}")
    if not session_id:
        return

    prompt = PROMPT_TEMPLATE.format(
        kb_path=KNOWLEDGE_BASE,
        observations_path=OBSERVATIONS_PATH,
        workspace_root=_WORKSPACE_ROOT,
    )
    client.send_message(session_id, prompt, model_id=model_id, agent="build")
    # If send_message timed out, agent may still be running; poll until done
    print("Waiting for session to complete (sync mode)...")
    client.wait_for_session_complete(session_id)
    if delete_after:
        if client.delete_session(session_id):
            print(f"Task complete (session {session_id} deleted).")
        else:
            print(f"Task complete (Session: {session_id}).")
    else:
        print(f"Task complete (Session: {session_id}).")

if __name__ == "__main__":
    main()
