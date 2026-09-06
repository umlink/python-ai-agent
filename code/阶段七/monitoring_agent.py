#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段七 · 综合实战：Agent 观测台 + 告警 + Bad-case 闭环（无需外网 / 无需 API Key）
============================================================================================

运行方式：
    python3 monitoring_agent.py

这个文件把阶段七小点3"监控与运维"的核心能力落到一份可运行代码：

    Part 1  三大支柱：Logs 日志 / Metrics 指标 / Traces 追踪 采集器
    Part 2  黄金四指标：P95 延迟 / 成功率 / cost 饱和 / 告警分级(P0/P1/P2)
    Part 3  Bad-case 闭环：收集 → 四分类 → 修复 → 评测回归(周迭代SOP)

环境需求：仅 Python 标准库，离线可跑。
课堂对照：这就是一个"最小可用的 Agent 观测台"骨架。
阅读建议：先 python3 跑一遍看输出, 再对着阶段七小点3文档逐个看懂。
"""

import time
import random
import statistics

# ============================================================
# Part 1  三大支柱：Logs / Metrics / Traces 采集
# ============================================================

class LogCollector:
    """日志支柱: 单次事件的明细记录(谁/何时/发生了什么)"""
    def __init__(self):
        self.logs = []

    def info(self, trace_id, msg, **kw):
        self.logs.append({"trace_id": trace_id, "ts": time.time(),
                          "level": "info", "msg": msg, **kw})

    def error(self, trace_id, msg, **kw):
        self.logs.append({"trace_id": trace_id, "ts": time.time(),
                          "level": "error", "msg": msg, **kw})

    def by_trace(self, trace_id):
        """按 trace_id 拉出一次请求的完整日志——链路可追溯"""
        return [l for l in self.logs if l["trace_id"] == trace_id]


class MetricsCollector:
    """指标支柱: 可聚合的数值时间序列(直方图 + 计数器)"""
    def __init__(self):
        self.latencies, self.success = [], []
        self.errors = 0

    def record_call(self, latency, ok, prompt_tk=0, completion_tk=0):
        self.latencies.append(latency)
        self.success.append(ok)
        self.errors += (0 if ok else 1)
        # token 消耗速率(饱和度): 累计 prompt+completion token
        self.tokens = getattr(self, "tokens", 0) + prompt_tk + completion_tk

    def report(self) -> dict:
        """产出黄金四指标(Agent 版)"""
        return {
            "QPS": round(len(self.latencies) / 60, 2),
            "P95延迟(s)": round(self._p95(self.latencies), 3),
            "成功率": round(self.success.count(True) / len(self.success), 3),
            "token累积": self.tokens,
        }

    def _p95(self, v):
        if not v:
            return 0.0
        s = sorted(v)
        return s[min(int(len(s) * 0.95), len(s) - 1)]

    def all_latencies(self):
        return self.latencies


class TraceCollector:
    """追踪支柱: 一次请求跨步骤的完整路径"""
    def __init__(self):
        self.spans = []

    def start(self, trace_id, step):
        span = {"trace_id": trace_id, "step": step, "ts": time.time()}
        self.spans.append(span)
        return span

    def by_trace(self, trace_id):
        return [s for s in self.spans if s["trace_id"] == trace_id]


# ============================================================
# Part 2  黄金四指标 + 告警分级
# ============================================================

GOLDEN = {
    "success_rate":   {"p0": 0.90, "p1": 1.00, "level0": "P0", "action": "立刻电话"},
    "failure_rate":   {"p0": 0.05, "p1": 0.00, "level0": "P1", "action": "工单"},
    "p95_latency":    {"p0": 2.0,  "p1": 0.00, "level0": "P2", "action": "次日关注"},
}


def alert_check(metrics: dict) -> list:
    """告警分级: 阈值"可行动", 触发即按级别上报"""
    fired = []
    for metric, val in metrics.items():
        rule = GOLDEN.get(metric)
        if rule and val <= rule["p0"] if "rate" in metric else (rule and val >= rule["p0"]):
            pass  # 占位示意, 见下面真正实现
    return fired


def evaluate_golden(mat: MetricsCollector) -> dict:
    """计算并逐条告警检查(黄金四指标里挑可行动的三条)"""
    r = mat.report()
    out = {"QPS": r["QPS"], "token累积": r["token累积"]}
    sr = r["成功率"]; fr = 1 - sr; p95 = r["P95延迟(s)"]
    out["成功率"] = sr
    alerts = []
    if sr < 0.90:
        alerts.append(("P0", "成功率跌破90%", "立即电话"))
    elif fr > 0.05:
        alerts.append(("P1", "失败率>5%", "工单"))
    if p95 > 2.0:
        alerts.append(("P2", "P95变慢", "次日"))
    out["告警"] = alerts
    return out


# ============================================================
# Part 3  Bad-case 闭环：收集 → 四分类 → 修复 → 评测回归
# ============================================================

CATEGORY = {"prompt", "model", "tool", "retrieval"}   # 失败四分类


def classify(fail_case: str) -> str:
    """按失败文本归类到四分类(生产由 LLM 或规则归类)"""
    if any(k in fail_case for k in ("指令不清", "约束缺失")):
        return "prompt"
    if "库未收录" in fail_case or "召回无关" in fail_case:
        return "retrieval"
    if "工具" in fail_case or "超时" in fail_case:
        return "tool"
    return "model"


class BadCaseLoop:
    """Bad-case 闭环: 每周过队列归类 → 修 → 补评测集 → 回归通过才关闭"""
    def __init__(self):
        self.queue = []          # 待处理 bad-case
        self.done = []

    def enqueue(self, trace_id, fail_case):
        self.queue.append({"trace_id": trace_id, "case": fail_case})

    def weekly_sop(self):
        """周一: 过队列四分类归档 → 挑 Top3 高频"""
        cats = {}
        for item in self.queue:
            c = classify(item["case"])
            cats[c] = cats.get(c, 0) + 1
        top = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:3]
        print("\n[周一归类] 失败四分类:", cats, "→ Top3:", top)
        return top

    def fix_and_regression(self, category, fix):
        """周三修复 + 补评测集 → 周五回归通过才关闭"""
        fixed = [i for i in self.queue if classify(i["case"]) == category]
        n = len(fixed)
        self.done += [{"case": i["case"], "fix": fix, "regression": "pass"}
                      for i in fixed]
        self.queue = [i for i in self.queue if i not in fixed]
        print(f"[修复] {category} 类 {n} 条, fix={fix}, 回归通过, 已关闭")


# ============================================================
# 模拟一次 Agent 服务运行的流量
# ============================================================

def simulate_traffic(mat: MetricsCollector, logs: LogCollector,
                     traces: TraceCollector, n=60):
    """模拟 60 次请求, 产生日志/指标/追踪 + 一些失败样本"""
    for i in range(n):
        # 用函数属性做自增计数生成全局唯一 trace_id(等价于真实环境的 UUID)
        simulate_traffic.i = getattr(simulate_traffic, "i", 0) + 1
        tid = f"t{simulate_traffic.i:03d}"
        logs.info(tid, "agent start", step="receive")
        traces.start(tid, "llm")
        ok = random.random() > 0.28                 # 约两成失败
        lat = random.uniform(0.4, 3.4) if ok else random.uniform(2.0, 8.0)
        time.sleep(0.001)
        mat.record_call(lat, ok, prompt_tk=random.randint(100, 900),
                        completion_tk=random.randint(50, 400))
        if ok:
            logs.info(tid, "agent done")
        else:
            logs.error(tid, "agent failed", step="llm")


def main():
    print("=" * 64)
    print("阶段七综合实战 · Agent 观测台 + 告警 + Bad-case 闭环（离线可运行）")
    print("=" * 64)

    logs = LogCollector(); mat = MetricsCollector(); traces = TraceCollector()
    simulate_traffic(mat, logs, traces, n=60)

    # 1. 三支柱: 日志 + 追踪(按 trace_id 可追溯)
    print("\n>>> Part 1 三大支柱(日志/指标/追踪)")
    last_tid = traces.spans[-1]["trace_id"]
    print("  [追踪] 最新一次请求 spans:", [s["step"] for s in traces.by_trace(last_tid)])
    print("  [日志] 该请求日志:", [(l["level"], l["msg"]) for l in logs.by_trace(last_tid)])

    # 2. 黄金四指标 + 告警分级
    print("\n>>> Part 2 黄金四指标 + 告警")
    golden = evaluate_golden(mat)
    for k, v in golden.items():
        print(f"  {k}: {v}")
    p95 = min(sorted(mat.all_latencies())[int(len(mat.all_latencies())*0.95)],
              sorted(mat.all_latencies())[-1])
    print("  P95 vs 均值:", round(p95, 3), " vs ", round(statistics.mean(mat.all_latencies()), 3))
    # 简化: P95 已含在 golden["P95延迟"], 上面那行仅示意长尾对比

    # 3. Bad-case 闭环(周迭代)
    print("\n>>> Part 3 Bad-case 闭环(周一归类→周三修复→回归关闭)")
    loop = BadCaseLoop()
    for l in logs.logs:
        if l["level"] == "error":
            loop.enqueue(l["trace_id"], "工具超时: llm调用失败")
    top = loop.weekly_sop()
    if top:                                       # 修 Top-1 高频类
        loop.fix_and_regression(top[0][0], fix="给工具加超时+重试")
    else:
        print("[无失败样本] 无需修复")

    print("\n[Done] 阶段七综合实战运行完成")


if __name__ == "__main__":
    main()