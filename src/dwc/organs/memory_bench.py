"""memory_bench · 词法检索基线（M3.4/MEM-18）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 只读：调用 `recall_search`，不写 access/不写 retrieval 事件。
  ★ 只算有 labeled relevance 的 query；没有标签返回 None，不伪造分数。
  ★ 这是“是否值得引向量”的前置基线，不是向量实现。
"""
from __future__ import annotations

import math
from typing import Any


def bench(memory: Any, labels: dict[str, list[str]], k: int = 5) -> dict[str, Any]:
    """返回 `{k, n_queries, hit_rate, mrr, ndcg, note}`。"""
    n = 0
    hits = 0
    rr: list[float] = []
    ndcg: list[float] = []
    for query, relevant in (labels or {}).items():
        rel = set(str(x) for x in (relevant or []))
        if not rel:
            continue
        n += 1
        got = [node.node_id for node in memory.recall_search(query, k=int(k))]
        rel_flags = [1 if nid in rel else 0 for nid in got]
        if any(rel_flags):
            hits += 1
        first = 0.0
        for i, flag in enumerate(rel_flags, 1):
            if flag:
                first = 1.0 / i
                break
        dcg = sum(flag / math.log2(i + 1)
                  for i, flag in enumerate(rel_flags, 1))
        ideal_n = min(len(rel), len(got))
        idcg = sum(1.0 / math.log2(i + 1)
                   for i in range(1, ideal_n + 1))
        rr.append(first)
        ndcg.append((dcg / idcg) if idcg else 0.0)
    return {
        "k": int(k),
        "n_queries": n,
        "hit_rate": (hits / n) if n else None,
        "mrr": round(sum(rr) / n, 6) if n else None,
        "ndcg": round(sum(ndcg) / n, 6) if n else None,
        "note": "lexical baseline only; no embedding/vector",
    }
