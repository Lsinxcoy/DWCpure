# -*- coding: utf-8 -*-
"""19 篇论文的进化相关性分类 —— 判据先行, 逐篇给证据。"""
import io, os, re
d = r"E:/Divine Wisdom Core/papers_txt"

# 判据 (可机械查):
#  A. 标题含 进化/自我改进 词根
#  B. 摘要含 进化 的核心动作 (evolve/self-improv/RSI/co-evolv/improve itself)
#  C. 摘要的"研究对象"是系统如何改变自己 (而非提供某个组件)
TITLE_EVO = re.compile(r'(self-?improv|recursive self|evolv|RSI\b|co-?evolution|Gödel|godel)', re.I)
ABS_EVO   = re.compile(r'(recursive self-?improv|\bRSI\b|self-?evolv|co-?evolv|evolv\w*\s+(the\s+)?(harness|agent|metric|skill|environment|world)|improve\s+(itself|themselves)|self-?modif)', re.I)
# 反向判据: 论文主题是"世界模型/认知/思维"
ABS_ALT   = re.compile(r'(world model|mental world|continuous thought|latent world)', re.I)

rows = []
for f in sorted(os.listdir(d)):
    t = io.open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
    # 标题
    title = ""
    m = re.search(r'\[?(\d{4}\.\d{4,5})\]?\s*([^\n]{10,150})', t)
    if m: title = m.group(2).strip()
    if not title or "Report GitHub" in title or "Content selection" in title:
        # 退路: 从 "arXiv:xxxx ... 标题" 取
        m2 = re.search(r'arXiv:\d{4}\.\d{4,5}v?\d*\s*\[[^\]]*\]\s*[^\n]*?\n([^\n]{15,180})', t)
        if m2: title = m2.group(1).strip()
    # 摘要段
    t2 = re.sub(r'Report GitHub Issue.*?Back to arXiv', ' ', t, flags=re.S)
    ab = ""
    for m in re.finditer(r'Abstract(.{200,4000}?)(?=\b1 Introduction\b|\bIntroduction\b)', t2, re.S):
        cand = " ".join(m.group(1).split())
        if len(cand) > len(ab): ab = cand
    if not ab: ab = " ".join(t2[:2500].split())

    ti_hit = bool(TITLE_EVO.search(title))
    ab_hit = bool(ABS_EVO.search(ab))
    alt_hit = bool(ABS_ALT.search(title + " " + ab))
    rows.append({"file": f, "title": title[:120], "title_evo": ti_hit,
                 "abs_evo": ab_hit, "alt": alt_hit, "ab": ab})

print("%-16s %-5s %-5s %-5s  %s" % ("文件", "题进", "摘进", "替代", "标题"))
print("-" * 130)
for r in rows:
    print("%-16s %-5s %-5s %-5s  %s" % (r["file"], "Y" if r["title_evo"] else "-",
          "Y" if r["abs_evo"] else "-", "Y" if r["alt"] else "-", r["title"]))

n_evo = sum(1 for r in rows if r["title_evo"] or r["abs_evo"])
print("\n★ 标题或摘要命中进化判据: %d / %d" % (n_evo, len(rows)))
n_only_alt = [r for r in rows if r["alt"] and not (r["title_evo"] or r["abs_evo"])]
print("★ 仅命中'世界模型/认知'替代判据: %d 篇" % len(n_only_alt))
for r in n_only_alt: print("    %s  %s" % (r["file"], r["title"]))

io.open(r"E:/Divine Wisdom Core/.cache/papers19_classify.json", "w", encoding="utf-8").write(
    __import__("json").dumps(rows, ensure_ascii=False, indent=1))
print("\n已存 .cache/papers19_classify.json")
