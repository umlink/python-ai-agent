# 阶段五 · 小点 4：Agent 评估与评测

> 所属：阶段五 进阶技术：能力增强与优化
> 定位：怎么证明你的 Agent 「变好了」？评估是 Agent 工程的「回归测试」——没有评测集，改 prompt / 换模型全靠玄学。这一讲讲清五大指标、公开/自建评测集的取舍、LLM-as-judge 三原则，以及让 Agent 持续变好的 Bad-case 迭代闭环。

## 精简大纲

1. 五大核心指标
2. 公开 Benchmark vs 自建业务评测集
3. LLM-as-judge（模型当裁判）三原则
4. Bad-case 四分类与迭代闭环
5. 一个可运行的 evaluate 骨架

## 学习内容详情

> 原则：公开 Benchmark 只做选型参考；**业务效果必须用自己的评测集说话**。

### 1. 五大核心指标

```mermaid
graph TD
    A[五大核心指标] --> B[任务成功率 ★核心]
    A --> C[工具调用准确率]
    A --> D[步骤数/token成本]
    A --> E[幻觉率]
    A --> F[平均完成耗时]
```

1. **任务成功率**：评测集里「完整达成用户意图」的占比——最核心指标。
2. **工具调用准确率**：该调的调了 + 不该调的没调（闲聊触发检索也算错——过度调用浪费 token 且拖慢响应）。
3. **步骤数量 / token 成本**：完成任务用了几轮循环、烧了多少 token；同等成功率下步骤越少越优秀——**无限循环的 Agent 就是被这个指标暴露的**。
4. **幻觉率**：回答中「编造事实」的比例，靠 LLM 裁判 + 人工抽检结合评估。
5. **平均完成耗时**：延迟体感指标。

### 2. 公开 Benchmark vs 自建评测集

| 维度 | 公开 Benchmark | 自建业务评测集 |
|-|-|-|
| 例子 | AgentBench / GAIA / MMLU-Pro / HumanEval | 你的真实业务问题整理成固定用例 |
| 作用 | 选模型时横向参考 | Agent 的「回归测试」 |
| 局限 | 题目 ≠ 你的业务 | 需要花时间维护 |

- **自建业务评测集**：把真实业务问题整理成固定用例集：**输入 + 期望要点**（该调什么工具、答案含什么关键词、来源是什么）。每次改 prompt / 换模型后重跑——这就是 Agent 的「回归测试」。

```python
# 自建评测集示例: 每条用例 = 输入 + 期望要点
EVAL_CASES = [
    {"input": "北京明天天气如何？",
     "expect": {"tool": "get_weather", "keyword": ["北京"]}},       # 应调天气工具
    {"input": "你好",
     "expect": {"tool": None, "keyword": []}},                       # 闲聊不应调工具
    {"input": "报销流程是什么？",
     "expect": {"tool": "kb_search", "keyword": ["报销", "发票"]}},
]
```

### 3. LLM-as-judge 三原则

> LLM 当裁判省人工，但会错。三条铁律缺一不可。

1. **裁判模型要比被测模型强**（否则判不准）。
2. **评分标准与输出格式必须固定**（否则结果不可比）。
3. **抽 10% 人工复核**（裁判自己也会幻觉）。

```python
JUDGE_PROMPT = """你是评测裁判。请仅依据给定标准判断回答是否达成用户意图。
评分标准(必须返回 JSON): {{"success": true/false, "reason": "..."}}
用例来源必须存在, 编造内容判 false。
作答:{answer}"""

def judge_success(answer: str, keyword: list) -> bool:
    """简化裁判: 检查期望关键词是否出现。生产用 LLM 裁判 + 人工抽检。"""
    return all(k in answer for k in keyword)
```

### 4. Bad-case 四分类与迭代闭环

```mermaid
graph TD
    A[失败样本归因四分类] --> B[Prompt 问题<br/>指令不清/约束缺失]
    A --> C[模型问题<br/>能力不足]
    A --> D[工具问题<br/>执行失败/脏数据]
    A --> E[检索问题<br/>没召回/召回无关]
    B --> F[对应修法: 改prompt]
    C --> G[换模型]
    D --> H[修工具]
    E --> I[调检索]
```

- 失败样本归因四类：**prompt 问题**（指令不清 / 约束缺失）、**模型问题**（能力不足）、**工具问题**（执行失败 / 返回脏数据）、**检索问题**（没召回 / 召回了无关内容）。
- **分类决定修法**：改 prompt / 换模型 / 修工具 / 调检索——**别用改 prompt 去治工具的病**。
- **迭代闭环**：改 prompt / 修工具 → 重跑 evaluate → 指标回升 = 修对了；指标回落 = 改坏了别处（回归测试防「按下葫芦浮起瓢」）。

```mermaid
graph LR
    A[改 prompt/修工具] --> B[重跑 evaluate]
    B --> C{指标?}
    C -->|回升| D[修对了 ✓]
    C -->|回落| E[改坏了别处<br/>定位回归]
```

### 5. 一个可运行的 evaluate 骨架

把上述指标落到代码，跑了就能得到一份「Agent 健康报告」。

```python
import time

class Evaluator:
    """对一批评测用例跑 Agent, 统计五大指标"""
    def __init__(self, cases: list, agent_call):
        self.cases, self.agent_call = cases, agent_call

    def run(self) -> dict:
        succ = ok_tool = steps = hal = lat = 0
        for c in self.cases:
            t0 = time.time()
            result = self.agent_call(c["input"] or "")   # → (answer, used_tool, n_steps)
            lat += time.time() - t0
            answer, used_tool, n_steps = result
            # ① 任务成功率: 期望关键词都命中
            if c["expect"].get("keyword", []) and \
               all(k in answer for k in c["expect"]["keyword"]):
                succ += 1
            # ② 工具调用准确率: 该调的调了/不该调的没调
            if used_tool == c["expect"].get("tool"):
                ok_tool += 1
            steps += n_steps                             # ③ 步骤数(越低越好)
            if "编造" in answer:                          # ④ 简化幻觉计数
                hal += 1
        n = len(self.cases)
        return {
            "任务成功率": round(succ / n, 3),
            "工具调用准确率": round(ok_tool / n, 3),
            "平均步骤数": round(steps / n, 2),            # ③ 无限循环在此暴露
            "幻觉率": round(hal / n, 3),
            "平均耗时(s)": round(lat / n, 3),             # ⑤ 延迟体感
        }

# 用法: ev = Evaluator(EVAL_CASES, my_agent.run); print(ev.run())
```

## 本节自检

- [ ] 能构建包含 3 个以上业务用例的评测集并跑出五大指标
- [ ] 能对失败样本完成四分类归因并给出对应修法
- [ ] 能说清 LLM-as-judge 三原则并演示一个 evaluate 骨架