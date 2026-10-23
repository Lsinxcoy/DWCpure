"""skill_store · 技能的跨进程真源（R438 · skill 维度）。

定位声明 · **DWC-MEM**（记忆底座 · 技能=程序性记忆）
  ★ 只做存取与选择，不做判分（判分归 judge/verifier）。

★★★ 存在理由
  改前 `Mutator.SKILLS` 只是**进程内 dict**（evolver.py:1395）：
  写进去的"技能"进程一退就没了，而且全仓库没有任何消费者读它
  ⇒ skill 维度在生产上等于不存在（`skill_select` 也零调用）。

★★★ 产物格式（人可读、可评审、可 git diff）
    skills/<name>/SKILL.md
    ---
    name: <slug>
    trigger: <词元，空格分隔>
    description: <一句话>
    version: 3
    ---
    <正文：什么时候用、怎么做、踩过什么坑>

★ 为什么用文件而不是 json：技能是**给模型看的散文**，评审要能直接读。
"""
from __future__ import annotations

import os
import re
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
SKILLS_DIR = os.path.join(ROOT, "skills")


def _safe(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "")).strip("._")
    return s[:64] or "unnamed"


def path_of(name: str) -> str:
    return os.path.join(SKILLS_DIR, _safe(name), "SKILL.md")


def save(name: str, description: str = "", content: str = "",
         trigger: str = "", version: int = 1) -> dict[str, Any]:
    """写一个技能（原子写）。返回 {ok, path, name, version}。"""
    p = path_of(name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fm = ["---", "name: %s" % _safe(name),
          "trigger: %s" % " ".join(str(trigger or "").split()),
          "description: %s" % str(description or "").replace("\n", " ")[:200],
          "version: %d" % int(version), "---", ""]
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + str(content or "").strip() + "\n")
    os.replace(tmp, p)
    return {"ok": True, "path": p, "name": _safe(name),
            "version": int(version)}


def parse(text: str) -> dict[str, Any]:
    """解析 SKILL.md（frontmatter + 正文）。坏文件 ⇒ 尽力而为，不抛。"""
    meta: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for ln in parts[1].splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2].lstrip("\n")
    meta["body"] = body.strip()
    try:
        meta["version"] = int(meta.get("version", 1))
    except (TypeError, ValueError):
        meta["version"] = 1
    return meta


def load_all(root: str = "") -> dict[str, dict[str, Any]]:
    """读全部技能（目录不存在 ⇒ 空 dict，不报错）。"""
    base = root or SKILLS_DIR
    out: dict[str, dict[str, Any]] = {}
    if not os.path.isdir(base):
        return out
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d, "SKILL.md")
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                meta = parse(f.read())
        except OSError:
            continue
        meta.setdefault("name", d)
        meta["path"] = p
        out[str(meta["name"])] = meta
    return out


def _toks(s: str) -> set:
    """词元：英文标识符 + **中文二元组**。

    ★ 为什么中文要切二元组：`[\\u4e00-\\u9fa5]{2,}` 会把「读取事实再回答」
      整串当成一个 token ⇒ 与技能里的「读取 / 事实」零重叠 ⇒ 永远选不中。
      切成 读取/取事/事实/实再/再回/回答 才有交集。
    """
    t = str(s or "").lower()
    out = set(re.findall(r"[a-z_][a-z0-9_]{2,}", t))
    for run in re.findall(r"[\u4e00-\u9fa5]{2,}", t):
        out.update(run[i:i + 2] for i in range(len(run) - 1))
    return out


def select(task: str, skills: dict[str, Any] | None = None,
           k: int = 1) -> list[dict[str, Any]]:
    """按词元重叠选技能（≥2 才入选；同分按 version 高者优先）。"""
    table = skills if skills is not None else load_all()
    t = _toks(task)
    scored = []
    for s in table.values():
        _blob = " ".join([str(s.get("trigger", "")),
                          str(s.get("description", "")),
                          str(s.get("body", ""))[:600]])
        ov = len(t & _toks(_blob))
        if ov >= 2:
            scored.append((ov, int(s.get("version", 1) or 1), s))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [s for _, _, s in scored[:k]]


def context(task: str, k: int = 1, limit: int = 900) -> str:
    """注入块：选中的技能正文（供 task_exec 拼进 prompt）。"""
    hits = select(task, k=k)
    if not hits:
        return ""
    lines = ["可用技能（此前验证过，优先复用）:"]
    for s in hits:
        lines.append("- %s：%s" % (s.get("name", "?"),
                                   str(s.get("description", ""))[:100]))
        lines.append(str(s.get("body", ""))[:limit])
    return "\n".join(lines)[:limit * max(1, k)]
