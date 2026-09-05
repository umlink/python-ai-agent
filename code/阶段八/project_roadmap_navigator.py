#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段八 · 综合实战：五级项目路线导航器（无需外网 / 无需 API Key）
===========================================================================

运行方式：
    python3 project_roadmap_navigator.py

这个文件不构建某个 Agent，而是把它"钉死"在阶段八最重要的目标上：
**把五个 Level 项目按依赖顺序排成路线，并跟踪自己的通关进度**。

它能帮你：
    Part 1  展示五级项目递进关系(Level1→Level5) + 每级依赖前面哪几个阶段
    Part 2  能力覆盖图：每个 Level 复用了前面阶段的哪些能力
    Part 3  进度跟踪：打卡通关 → 自动提示下一步该做哪个项目、缺哪些前置
    Part 4  排期贴合：把每个 Level 对应到 16 周计划的周数

环境需求：仅 Python 标准库，离线可跑。
阅读建议：先 python3 跑一遍，再把你想做的项目用 mark_done() 勾掉，看导航器如何提醒前置。
"""

# ============================================================
# Part 1 五级项目定义：难度 / 周期 / 前置阶段 / 核心能力
# ============================================================

LEVELS = [
    {
        "id": 1, "name": "ReAct 智能问答",
        "difficulty": "入门", "weeks": "1-2 周", "weeks_range": (7, 8),
        "inherits": ["阶段二 ReAct", "阶段三 LangGraph"],           # 前置
        "skills": ["手写Agent循环", "工具调用流程", "状态流转", "解析异常"],  # 覆盖能力
        "demo": "code/阶段二/react_agent.py + code/阶段三/react_langgraph_agent.py",
    },
    {
        "id": 2, "name": "知识库 RAG",
        "difficulty": "进阶", "weeks": "2-3 周", "weeks_range": (9, 10),
        "inherits": ["阶段四 RAG", "阶段四 向量库"],
        "skills": ["文档分块", "混合检索", "Rerank精排", "引用溯源", "流式输出"],
        "demo": "code/阶段四/rag_agent.py",
    },
    {
        "id": 3, "name": "多角色内容创作",
        "difficulty": "高级", "weeks": "3-4 周", "weeks_range": (12, 12),
        "inherits": ["阶段五 多智能体", "阶段六 内容创作", "阶段三 CrewAI/Supervisor"],
        "skills": ["角色分工", "任务调度", "冲突仲裁", "素材溯源"],
        "demo": "code/阶段五/planning_memory_agent.py",
    },
    {
        "id": 4, "name": "数据分析 SQL Agent",
        "difficulty": "实战", "weeks": "4-6 周", "weeks_range": (13, 14),
        "inherits": ["阶段六 数据分析", "阶段七 工程化"],
        "skills": ["Text-to-SQL", "五道防线", "图表生成", "报告组装", "API安全"],
        "demo": "code/阶段六/data_analysis_agent.py",
    },
    {
        "id": 5, "name": "企业智能客服",
        "difficulty": "生产", "weeks": "6-8 周", "weeks_range": (15, 16),
        "inherits": ["Level1-4 全部能力", "阶段七 部署/监控"],
        "skills": ["多租户隔离", "状态持久化", "权限控制", "监控告警", "迭代闭环"],
        "demo": "需要真实部署(Docker), 见 Level5 文档",
    },
]


def show_levels():
    """Part 1: 打印五级递进路线 + 前置依赖"""
    print("=" * 70)
    print("阶段八 · 五级项目路线（从入门到生产）")
    print("=" * 70)
    for i, lv in enumerate(LEVELS, 1):
        arrow = " -> " if i < len(LEVELS) else "    "
        print(f"L{lv['id']} [{lv['difficulty']}] {lv['name']:<14} "
              f"({lv['weeks']}){arrow}")
        print(f"    依赖前置: {', '.join(lv['inherits'])}")
    print(">>> 每个 Level 必须先消化它'依赖前置'里的阶段才能顺利开工")


# ============================================================
# Part 2 能力覆盖图：每个 Level 复用了哪些前面的能力
# ============================================================

def show_skills():
    """Part 2: 打印每个 Level 覆盖的能力点, 建立"重学前置"的索引"""
    print("\n" + "=" * 70)
    print("能力覆盖图：这个 Level 会用到前面学过的哪些能力")
    print("=" * 70)
    for lv in LEVELS:
        skills = " / ".join(lv["skills"])
        print(f"L{lv['id']} {lv['name']:<14} → {skills}")


# ============================================================
# Part 3 进度跟踪：打卡 → 提示下一步 + 缺前置
# ============================================================

class RoadmapTracker:
    """极简进度跟踪器: 记住已完成的 Level, 自动给"下一步"建议"""

    def __init__(self, levels: list):
        self.levels = levels
        self.done = set()                  # 已完成的 Level 编号
        self.current = 0                   # 指示器, 指向当前聚焦的 Level

    def mark_done(self, level_id: int):
        """打卡完成一个 Level"""
        self.done.add(level_id)

    def next_up(self) -> dict:
        """返回下一个应做的 Level(未完成中编号最小者)"""
        for lv in self.levels:
            if lv["id"] not in self.done:
                return lv
        return None                        # 全部完成

    def missing_prereq(self, lv: dict, stage_done: set) -> list:
        """检查该 Level 依赖的阶段是否都掌握; 返回仍缺的前置提示"""
        # 依赖条目形如 "阶段二 ReAct" / "阶段01-数据分析" / "Level1-4 全部能力";
        # 截取阶段前缀: 取第一个 "-" 或空格 之前的部分,
        # 兼容 "阶段二 ReAct"(空格分隔) 与 "阶段01-数据分析"(连字符分隔) 两种命名
        missing = []
        for item in lv["inherits"]:
            if not item.startswith("阶段"):
                continue                     # 非 "阶段X" 条目(如 Level1-4)不在此检查
            stage = item.split("-")[0].split(" ")[0]        # "阶段二" / "阶段01"
            if stage not in stage_done:
                missing.append(item)         # 前置阶段没消化 → 记为缺失
        return missing


# ============================================================
# Part 4 排期贴合：映射到 16 周计划
# ============================================================

def show_schedule():
    """Part 4: 打印每个 Level 对应的周数区间, 对齐四个月学习计划"""
    print("\n" + "=" * 70)
    print("排期映射（对齐 16 周 / 四个月学习计划）")
    print("=" * 70)
    for lv in LEVELS:
        s, e = lv["weeks_range"]
        bar = "▓" * (e - s + 1)
        gap = " " * (s - 7)
        label = f"第{s}周" if s == e else f"第{s}-{e}周"
        print(f"L{lv['id']} {lv['name']:<14} {label:<10} {' ' * 1}{gap}{bar}")


# ============================================================
# 运行入口
# ============================================================

def main():
    show_levels()
    show_skills()
    show_schedule()

    # 进度跟踪演示: 假设你已完成 Level1、Level2, 想直接做 Level4
    print("\n" + "=" * 70)
    print("进度跟踪演示：已完成 L1、L2 → 导航器会怎么提醒")
    print("=" * 70)
    tracker = RoadmapTracker(LEVELS)
    tracker.mark_done(1)
    tracker.mark_done(2)

    stage_done = {"阶段二", "阶段三", "阶段四"}   # 你已掌握的阶段
    nxt = tracker.next_up()
    # 按数字顺序(阶段二<阶段七)而非 Unicode 顺序排列展示
    order = {"阶段二": 2, "阶段三": 3, "阶段四": 4, "阶段五": 5,
             "阶段六": 6, "阶段七": 7}
    sorted_done = sorted(stage_done, key=lambda s: order.get(s, 0))
    print(f">> 当前已掌握阶段: {', '.join(sorted_done)}")
    print(f">> 建议下一步: L{nxt['id']} {nxt['name']}")
    miss = tracker.missing_prereq(nxt, stage_done)
    if miss:
        print(f">> 但该 Level 仍缺前置: {', '.join(miss)} → 先去消化再开工")
    else:
        print(f">> 前置已齐, 可以直接开工")

    print("\n>>> 小提示: Level 4 依赖阶段六(数据分析)与阶段七(工程化), "
          "若你还没到阶段六就跳到 L4, 五道防线会很难落地.")
    print("\n[Done] 阶段八综合实战运行完成")


if __name__ == "__main__":
    main()