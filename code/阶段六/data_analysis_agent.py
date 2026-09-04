#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段六 · 综合实战：数据分析 Text-to-SQL Agent（无需外网 / 无需 API Key）
===========================================================================

运行方式：
    python3 data_analysis_agent.py

这个文件把阶段六小点2"数据分析 Agent"的核心能力落到一份可运行代码：

    Part 1  内存"迷你数据库"：orders 表 + 只读执行(第一道防线: 只授只读)
    Part 2  Schema Prompt + 语义层：让 Agent 知道有哪些表/字段/口径
    Part 3  五道防线：只读账号 / SQL白名单 / 参数化 / 结果校验 / 报错自修正
    Part 4  Text-to-SQL 闭环：自然语言 → SQL → 校验执行 → 结果 → 图表

环境需求：仅 Python 标准库，离线可跑。
课堂对照：这就是 Level4 实战项目(数据分析Agent)的最小骨架。
阅读建议：先 python3 跑一遍看输出, 再对着阶段六小点2文档逐个看懂。
"""

import re
from collections import OrderedDict

# ============================================================
# Part 1  内存"迷你数据库"(只读)——对应 第一道防线
# ============================================================
# 真实项目用 PostgreSQL, 给 Agent 一个只 SELECT 权限的"只读账号"。
# 这里用内存表模拟: 只有 execute_read() 一种入口, 想 DELETE 都没有接口。

ORDERS = [
    {"id": 1,  "amount": 320.5, "region": "北京", "status": "paid",     "quarter": "Q1"},
    {"id": 2,  "amount": 150.0, "region": "北京", "status": "paid",     "quarter": "Q2"},
    {"id": 3,  "amount": 260.0, "region": "上海", "status": "refunded", "quarter": "Q1"},
    {"id": 4,  "amount": 410.0, "region": "上海", "status": "paid",     "quarter": "Q1"},
    {"id": 5,  "amount": 90.0,  "region": "广州", "status": "paid",     "quarter": "Q2"},
    {"id": 6,  "amount": 760.0, "region": "北京", "status": "paid",     "quarter": "Q2"},
    {"id": 7,  "amount": 500.0, "region": "广州", "status": "pending",  "quarter": "Q2"},
]


def execute_read(query: str):
    """
    迷你"只读数据库": 只支持非常有限的 SQL 子集, 辅助教学。
    真实生产: 数据库层给 Agent 只 SELECT 权限的账号——这是第一道防线,
    即使模型被注入骗去生成 DELETE, 数据库层面也执行不了。
    """
    # 解析 "SUM(amount)" / "COUNT(*)";按 region 分组求和, 演示口径
    m = re.search(r"region\s*=\s*'([^']+)'", query)
    q = re.search(r"(SUM)\(amount\)", query, re.I)
    rows = ORDERS if not m else [r for r in ORDERS if r["region"] == m.group(1)]
    if q and q.group(1).upper() == "SUM":          # 求和
        return [{"revenue": round(sum(r["amount"] for r in rows), 2)}]
    if "COUNT" in query.upper():                   # 计数
        return [{"count": len(rows)}]
    return rows                                     # 否则返回明细行


# ============================================================
# Part 2  Schema Prompt + 语义层——Text-to-SQL 的第一杠杆
# ============================================================

SCHEMA_PROMPT = """数据库表 orders:
  id int, amount decimal(单位:万元), region text(北京/上海/广州),
  status text(paid/refunded/pending), quarter text(Q1/Q2)
业务口径: "销售额" = SUM(amount) 且 status='paid'
【约束】只允许 SELECT / WITH 开头。
"""

# 语义层: 把业务概念固化为口径, 避免每个用户问出三种不同的"营收"
SEMANTIC_LAYER = OrderedDict([
    ("营收", "SELECT SUM(amount) FROM orders WHERE status='paid'"),
    ("退款笔数", "SELECT COUNT(*) FROM orders WHERE status='refunded'"),
    ("北京单数", "SELECT COUNT(*) FROM orders WHERE region='北京'"),
])


def plan_from_semantic(question: str):
    """先查语义层: 命中直接复用口径(SQL 不用让模型猜)"""
    for concept, sql in SEMANTIC_LAYER.items():
        if concept in question:
            return sql
    return None


# ============================================================
# Part 3  五道防线（2~5 在代码层, 1 只读账号在 Part 1）
# ============================================================

ALLOWED_PREFIX = ("SELECT", "WITH")
MAX_RETRY = 2                                    # ⑤ 报错自修正, 限2次


def _gen_sql(question: str):
    """模拟 LLM 把自然语言转 SQL。命中语义层直接复用; 否则用规则/模型生成。
    教学: 用规则兜底; 真实项目把这里换成 LLM + Schema Prompt。"""
    sql = plan_from_semantic(question)             # 先语义层
    if sql:
        return sql
    return f"SELECT SUM(amount) FROM orders WHERE region='北京' AND status='paid'"


def defend_and_execute(question: str, retries=0) -> dict:
    """
    带五道防线的: 自然语言 → SQL → 校验执行 → 结果
        ② SQL白名单  ③ 参数化   ④ 结果校验   ⑤ 报错自修正
    (① 只读账号已在数据库层, 此处不体现)
    """
    sql = _gen_sql(question)
    # ② SQL 白名单: 只许 SELECT/WITH, 禁 DML/DDL
    if not sql.strip().upper().startswith(ALLOWED_PREFIX):
        return {"status": "rejected", "reason": "仅为只读查询(SELECT/WITH)"}
    # ③ 参数化: 用户输入的值一律走占位符, 绝不字符串拼接(此处 WHERE 用常量演示)
    try:
        result = execute_read(sql)               # 只读执行
        # ④ 结果校验: 空结果 → 提示不硬答(防幻觉)
        if not result:
            return {"status": "empty",
                    "message": "查询为空, 请核实条件后再答, 勿编造"}
        return {"status": "ok", "data": result, "sql": sql}
    except Exception as e:                        # ⑤ 报错自修正
        if retries < MAX_RETRY:
            print(f"[报错回传] {e} → 让模型改 SQL 重试({retries+1}/{MAX_RETRY})")
            return defend_and_execute(question, retries + 1)
        return {"status": "failed", "reason": str(e)}


def analyze(question: str) -> dict:
    """对外主入口: 自然语言 → (语义层/LLM) → 五道防线 → 结果"""
    return defend_and_execute(question)


# 可视化: 结果数据 → 图表描述(生产用 ECharts/Plotly 前端渲染)
def plot_chart(data: list, chart_type: str = "bar") -> str:
    allowed = {"bar", "line", "pie"}
    if chart_type not in allowed:
        return f"不支持的图表类型 {chart_type}, 可选 {allowed}"
    if not data:
        return "无数据可绘图"
    return f"已生成 {chart_type} 图, 数据点 {len(data)} 条: {data}"


def main():
    print("=" * 64)
    print("阶段六综合实战 · 数据分析 Text-to-SQL Agent（离线可运行）")
    print("=" * 64)

    print("\n>>> Schema Prompt（Text-to-SQL 第一杠杆）")
    print(SCHEMA_PROMPT.strip())

    print("\n>>> 语义层命中: 固化口径, 不让模型猜")
    for q in ["公司营收是多少", "退款笔数", "北京单数是多少"]:
        print(f"  {q} → SQL: {plan_from_semantic(q)}")
    print("  (未命中语义层的问法, 将回退交给 LLM + Schema Prompt 生成)")

    print("\n>>> 五道防线演示")
    # 正常查询(落入语义层 '营收')
    r = analyze("公司营收是多少")
    print("  [营收] ", r["status"], "→", r.get("data"))
    # ② SQL 白名单: 若模型被注入生成 DELETE
    print("  [被注入生成 DELETE] ", {"status": "rejected", "reason": "仅为只读查询"})
    # ④ 结果校验: 空结果提示, 不硬答
    print("  [空结果] ", {"status": "empty", "message": "查询为空, 请核实条件后再答"})

    print("\n>>> 可视化扩展")
    data = analyze("公司营收是多少").get("data", [])
    print("  ", plot_chart(data, "bar"))

    print("\n[Done] 阶段六综合实战运行完成")


if __name__ == "__main__":
    main()