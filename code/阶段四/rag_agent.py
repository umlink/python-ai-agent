#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段四 · 综合实战：RAG 知识库 + 工具 Agent（无需外网 / 无需 API Key）
========================================================================

运行方式：
    python3 rag_agent.py

这个文件把阶段四三个小点的核心能力全部落到一份可运行代码上：

    Part 1  工具工厂（阶段四小点1）：自动给工具套上『校验+超时+权限+异常包装+精简』五要素
    Part 2  轻量向量库（阶段四小点2）：字符级 Embedding + 余弦相似度检索 + 元数据过滤
    Part 3  混合检索（阶段四小点2）：稠密(余弦) + 稀疏(BM25) 双路召回 + RRF 融合
    Part 4  RAG 检索工具（阶段四小点3）：查询改写 + 缓存去重 + 引用溯源 三件套
    Part 5  Agent-RAG 循环（阶段四小点3）：Agent 自主把多子问题拆开、逐步检索再汇总

环境需求：仅依赖 pydantic（本机已装），其余全用 Python 标准库，保证离线可跑。
若想换真实模型 / 真向量库（Qdrant/Chroma）+ 真 Rerank，只需替换 Part 2 的 store
与 MockLLM，接口保持不变。

阅读建议：先 python3 rag_agent.py 看一遍输出，再对着阶段四小点1/2/3 的代码逐个看懂。
"""

# ============================================================
# Part 1  工具工厂：把任意函数升级成"合格工具"（五要素）
# ============================================================

import hashlib
import inspect
import time
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from pydantic import create_model, ValidationError

# ---------- 工具工厂核心 ----------

_TOOL_WHITELIST = {"kb_search", "calc"}     # ① 权限白名单（硬编码，模型改不了）
_RESULT_MAX_LEN = 400                       # ⑤ 结果精简上限


def tool_factory(name: str, timeout: float = 10.0):
    """
    参数装饰器：给任意业务函数套上五要素。
      ① 入参校验   —— 用 pydantic 按函数签名动态生成模型，先校验再执行
      ③ 权限校验   —— 不在白名单直接拒绝（代码说了算，模型说了不算）
      ② 超时控制   —— 线程池隔离执行，到点强杀，不阻塞主线程
      ④ 异常包装   —— 任何异常都封装成友好消息回传，不抛出去中断 Agent
      ⑤ 结果精简   —— 长文本截断 + 摘要，别把大报文喂给 LLM
    """
    def decorator(func):
        # ① 依据函数签名动态生成 pydantic 入参模型
        sig = inspect.signature(func)
        fields = {
            p: (param.annotation, ...)          # 取参数的类型注解
            for p, param in sig.parameters.items()
            if p not in ("self", "cls")
        }
        ParamModel = create_model(name + "_params", **fields)

        def wrapper(*args, **kwargs):
            # ③ 权限校验：白名单之外一律拒绝
            if name not in _TOOL_WHITELIST:
                return json.dumps({"error": f"工具 {name} 未授权"}, ensure_ascii=False)
            # ① 入参校验：pydantic 层拦住非法参数
            try:
                kwargs = ParamModel(**kwargs).model_dump()
            except ValidationError as e:
                return json.dumps({"error": f"参数不合法: {e.errors()}"},
                                  ensure_ascii=False)
            # ② 超时控制：线程池隔离执行
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(func, **kwargs)
                try:
                    raw = fut.result(timeout=timeout)
                except TimeoutError:
                    return json.dumps({"error": f"工具 {name} 超时({timeout}s)"},
                                      ensure_ascii=False)
                except Exception as e:      # ④ 异常包装
                    return json.dumps({"error": f"工具 {name} 失败: {e}"},
                                      ensure_ascii=False)
            # ⑤ 结果精简：超长截断
            text = str(raw)
            if len(text) > _RESULT_MAX_LEN:
                text = text[:_RESULT_MAX_LEN] + "...(已截断)"
            return text
        return wrapper
    return decorator


# ---------- 云雨计算的"合格工具" ----------
# 业务逻辑只有几行，五要素全部由工厂自动继承。

@tool_factory("calc", timeout=3.0)
def calc(expression: str) -> str:
    """计算数学表达式（仅四则运算与括号，防注入）。"""
    from re import fullmatch
    if not fullmatch(r"[\d+\-*/().\s]+", expression):   # 白名单字符集校验
        return f"表达式含非法字符: {expression}"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))  # 禁内置名防注入
    except ZeroDivisionError:
        return "错误: 除数不能为 0"
    except Exception as e:
        return f"计算失败: {e}"


# ============================================================
# Part 2  轻量向量库：字符级 Embedding + 余弦检索 + 元数据过滤
# ============================================================
# 生产换 Qdrant/Chroma，这里用纯 Python 实现保证离线可跑。

DIM = 256   # 向量维度


def embed(text: str) -> list:
    """
    字符级 Bag-of-characters Embedding：
      把每个汉字的哈希映射到 DIM 维向量里累加 → 语义相近的文本（共享常用字）
      向量方向就接近。真实项目换成中文 BGE 模型（bge-small-zh），此处仅演示。
    """
    vec = [0.0] * DIM
    for ch in str(text):
        i = int(hashlib.md5(ch.encode()).hexdigest(), 16) % DIM
        vec[i] += 1.0
    return vec


def cos_sim(a, b) -> float:
    """余弦相似度：只关心向量方向，忽略长度。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb + 1e-12)


class TinyVectorStore:
    """极简向量库：hash 之后的向量 + 元数据，支持动态增删、元数据过滤、top-K 检索。"""

    def __init__(self):
        self.vecs = {}       # id -> 向量
        self.docs = {}       # id -> 原文
        self.meta = {}       # id -> 元数据 dict

    def upsert(self, doc_id: str, text: str, metadata: dict = None):
        self.vecs[doc_id] = embed(text)
        self.docs[doc_id] = text
        self.meta[doc_id] = metadata or {}

    def delete(self, doc_id: str):
        for m in (self.vecs, self.docs, self.meta):
            m.pop(doc_id, None)

    def query(self, q_vec: list, where: dict = None, n: int = 3) -> list:
        """检索：可选 where 元数据过滤，返回 [(id, score, text), ...]"""
        cand = [
            did for did in self.vecs
            if all(self.meta[did].get(k) == v for k, v in (where or {}).items())
        ]
        scored = sorted(
            ((did, cos_sim(q_vec, self.vecs[did])) for did in cand),
            key=lambda t: t[1], reverse=True,
        )
        return [(did, sc, self.docs[did]) for did, sc in scored[:n]]


# ============================================================
# Part 3  混合检索：稠密(余弦) + 稀疏(BM25) 双路召回 + RRF 融合
# ============================================================

from collections import Counter


def bm25_scores(query: list, store: TinyVectorStore, id_filter=None,
                k1=1.5, b=0.75):
    """
    稀疏 BM25 打分：精确词匹配。专治"矩形238号""张三"这类稠密向量容易漏的精确词。
    id_filter：可选，只对指定候选 id 子树打分（配合元数据过滤）。
    """
    q_terms = Counter(query)
    cand = {did for did in store.docs
            if id_filter is None or did in id_filter}
    df = Counter()
    for did in cand:
        for t in set(_tokenize(store.docs[did])):
            df[t] += 1
    N = len(cand)
    scores = {}
    for did in cand:
        dl = len(_tokenize(store.docs[did]))
        tf = Counter(_tokenize(store.docs[did]))
        s = 0.0
        for t, qf in q_terms.items():
            n = df[t]
            idf = 0.0 if n == 0 else ((N - n + 0.5) / (n + 0.5) + 1.0)
            denom = tf[t] + k1 * (1 - b + b * (dl / 50 if dl else 1))
            s += idf * (tf[t] * (k1 + 1)) / (denom + 1e-9) * qf
        scores[did] = s
    return scores


def _tokenize(text: str) -> list:
    """简易中文分词：1~2 字滑窗，够 BM25 演示用即可。"""
    out, S = [], str(text)
    for i in range(len(S)):
        out.append(S[i])
        if i + 1 < len(S):
            out.append(S[i:i + 2])
    return out


def reciprocal_rank_fusion(dense_hits, sparse_scores, k=60) -> list:
    """RRF 融合：两路排名各按 1/(k+rank) 打分再求和，均衡语义与精确匹配。"""
    score = {}
    for rank, did in enumerate(dense_hits, start=1):
        score[did] = score.get(did, 0.0) + 1.0 / (k + rank)
    for did, s in sparse_scores.items():
        if s > 0:                       # 只对稀疏路也命中的项加分
            score[did] = score.get(did, 0.0) + 1.0 / (k + 1)
    return sorted(score.items(), key=lambda t: t[1], reverse=True)


# ============================================================
# Part 4  RAG 检索工具：查询改写 + 缓存去重 + 引用溯源
# ============================================================

class MockLLM:
    """离线"剧本模型"：用固定规则模拟 LLM 的改写 / 生成，便于无 Key 跑通。"""

    def __init__(self):
        self._cache = {}                # ② 内存缓存: 查询 -> (答案, ts)

    def rewrite(self, raw: str) -> str:
        """① 查询改写：补指代、去口语。生产用 LLM；这里用规则演示。"""
        rules = {
            "它": "年假", "这个": "报销", "那个": "请假",
        }
        q = raw
        for word, sub in rules.items():
            q = q.replace(word, sub)
        return q

    def answer(self, raw_question: str, hits: list, ttl: int = 120) -> dict:
        """
        生成带"引用溯源"的答案。
          - hits: [(id, score, text), ...]，已带来源 id
          - 强制"仅基于检索片段作答 + 标注来源"→ 缓解幻觉、可审计
          - 相同问题命中缓存则直接复用（节省 token / 延迟）
        """
        key = hashlib.md5(raw_question.encode()).hexdigest()
        now = time.time()
        if key in self._cache and now - self._cache[key]["ts"] < ttl:
            return {"answer": self._cache[key]["answer"], "cached": True, "hits": hits}
        if not hits:                                                   # 检索无结果
            ans = f"【{raw_question}】抱歉，知识库未收录相关内容。"
        else:
            # 按来源拼出带引用的答案（这里用 mock：把最相关片段当作答案 + 标注[id]）
            best_id, _, best_text = hits[0]
            ans = (f"根据知识库【{best_id}】：「{best_text[:50]}...」"
                   f"（另参考 {len(hits)-1} 条相关条目）")
        self._cache[key] = {"answer": ans, "ts": now}
        return {"answer": ans, "cached": False, "hits": hits}


@tool_factory("kb_search", timeout=5.0)
def kb_search(question: str) -> str:
    """
    知识库检索工具（真实项目此处用 LlamaIndex 的 QueryEngine）：
    改写 → 元数据过滤 → 混合召回 → RRF 融合 top3 → LLM 生成带引用答案。
    描述写清楚"可重试"，Agent 才能自主多轮检索。
    """
    q = _llm.rewrite(question)                       # ① 查询改写
    where = _topic_dept(q)                           # ② 元数据过滤(按部门圈定范围)
    q_vec = embed(q)
    dense = _store.query(q_vec, where=where, n=5)    # 稠密路(带部门过滤)
    cand_ids = {d for d, _, _ in dense}
    sparse = bm25_scores(_tokenize(q), _store, id_filter=cand_ids)  # 稀疏路(同域)
    fused = reciprocal_rank_fusion([d for d, _, _ in dense], sparse)[:3]
    # RRF 融合后，取对应原文 hits 供 LLM 生成
    hits = [(did, 0.0, _store.docs[did]) for did, _ in fused]
    res = _llm.answer(question, hits)                # ③ 引用溯源
    return json.dumps(
        {"answer": res["answer"],
         "cached": res["cached"],
         "sources": [f"[{s[0]}]" for s in res["hits"]]},
        ensure_ascii=False,
    )


def _topic_dept(question: str) -> dict:
    """元数据过滤：根据关键词推断问题所属部门，回传给存储做 where 过滤。
    生产上这条线索由 LLM 或路由规则给出，这里用关键词演示。
    """
    if any(w in question for w in ("报销", "发票", "财务", "打款")):
        return {"dept": "Finance"}
    if any(w in question for w in ("请假", "年假", "休假", "审批")):
        return {"dept": "HR"}
    if any(w in question for w in ("电脑", "工单", "IT", "显示器")):
        return {"dept": "IT"}
    return {}


# 工具、库存、模型全局实例（便于 kb_search 闭包引用）
_llm = MockLLM()
_store = TinyVectorStore()


# ============================================================
# Part 5  Agent-RAG 循环：把"多子问题"拆开逐步检索再汇总
# ============================================================
# 演示普通 RAG（一次检索）与 Agent-RAG（分步检索）的关键差异。

def _ingest():
    """往库存里灌几段假的"公司规章制度"知识。"""
    docs = [
        ("HR-01", "公司年假制度：入职满一年可休年假，最长 15 天，需提前 3 天在 OA 提交申请。", {"dept": "HR"}),
        ("HR-02", "请假审批流程：员工在 OA 提交请假单 → 直属主管审批 → 人力部备案。", {"dept": "HR"}),
        ("FIN-01", "报销流程：员工垫付后，在财务系统上传发票照片 → 财务审核 → 3 个工作日内打款。", {"dept": "Finance"}),
        ("FIN-02", "报销须知：所有报销必须附合规发票，单笔超 5000 元需部门负责人加签。", {"dept": "Finance"}),
        ("IT-01", "新员工电脑领用：IT 收到工单后 1 个工作日发放，可加配外接显示器。", {"dept": "IT"}),
    ]
    for did, text, meta in docs:
        _store.upsert(did, text, meta)


def run_agent_rag(question: str):
    """
    极简 ReAct 循环：
      1) 把多子问题拆开（脚本策略，模拟 LLM 的 decision）
      2) 对每个子问题调用 kb_search（多轮迭代检索）
      3) 汇总所有带来源的答案
    这是普通 RAG 一次检索无法做到的。
    """
    print(f"\n[用户] {question}")
    print("[Agent] think：识别到这是多子问题，需分别检索 →")
    topics = []
    if "假" in question or "休" in question:
        topics.append("请假审批流程")
    if "报销" in question or "钱" in question or "发票" in question:
        topics.append("报销流程")

    trail = []                                  # 推理轨迹（多轮检索记录）
    for t in topics:
        print(f"[Agent] tool_call → kb_search({t})")
        r = kb_search(question=t)               # 调工具（内部含改写+缓存+溯源）
        trail.append(json.loads(r))
        print(f"[tool]  {r}")

    # 总结：把每一步的答案 + 来源合并
    text_parts = [f"- {s['answer']}（来源:{'、'.join(s['sources'])}）" for s in trail]
    summary = "您好，为您分条解答：\n" + "\n".join(text_parts)
    print("[Agent] 汇总：\n" + summary)
    return summary


def main():
    print("=" * 64)
    print("阶段四综合实战 · RAG 知识库 + 工具 Agent（离线可运行）")
    print("=" * 64)

    _ingest()   # 1. 灌数据

    # 2. 单个工具：五要素自动生效
    print("\n>>> Part 1 工具工厂(calc) 五要素演示")
    print(calc(expression="1 + 2 * 3"))              # 正常
    print(calc(expression="1 + 2; import os"))       # 非法字符被拒
    print(calc(expression="1 / 0"))                  # 异常被包装成消息

    # 3. 混合检索演示（稠密+稀疏+RRF）
    print("\n>>> Part 3 混合检索演示（查询: 报销 发票）")
    dense = _store.query(embed("报销 发票"), n=3)
    print("稠密路 top3:", [d[0] for d in dense])
    sparse = bm25_scores(_tokenize("报销 发票"), _store)
    fused = reciprocal_rank_fusion([d[0] for d in dense], sparse)[:3]
    print("RRF 融合 top3:", [d[0] for d in fused])

    # 4. RAG 检索工具（缓存去重演示：问两次相同问题）
    print("\n>>> Part 4 RAG 检索工具(缓存+溯源)")
    print(kb_search(question="请假怎么做"))
    print(kb_search(question="请假怎么做"))          # 第二次应命中缓存 cached=true

    # 5. Agent-RAG 多子问题拆解
    print("\n>>> Part 5 Agent-RAG：多子问题逐步检索")
    run_agent_rag("我要请假和报销，分别走什么流程？")
    print("\n[Done] 阶段四综合实战运行完成")


if __name__ == "__main__":
    main()