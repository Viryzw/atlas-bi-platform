# backend/test_agent.py

import json
from agent_tools import run_agent

def test_agent(question: str):
    print(f"\n========== 问题: {question} ==========")
    result = run_agent(question)
    if result["status"] == "success":
        print("✅ Agent 回答:\n", result["answer"])
    else:
        print("❌ 错误:", result["message"])

if __name__ == "__main__":
    # ---------- 测试用例 ----------
    test_agent("帮我查询上个月的销售总额")
    test_agent("分析一下这个月销售额是否异常，当前值是 150 万")
    test_agent("生成一份关于本月销售情况的报告摘要")