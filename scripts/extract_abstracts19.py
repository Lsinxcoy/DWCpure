# -*- coding: utf-8 -*-
"""提取 19 篇论文的 Abstract, 为进化相关性分类做准备。"""
import io, os, re
d = r"E:/Divine Wisdom Core/papers_txt"
out = []
for f in sorted(os.listdir(d)):
    p = os.path.join(d, f)
    t = io.open(p, encoding="utf-8", errors="replace").read()
    # 去 arXiv 页头噪声
    t2 = re.sub(r'Report GitHub Issue.*?Back to arXiv', ' ', t, flags=re.S)
    # 找 Abstract
    m = re.search(r'\bAbstract\b(.*?)(?=\b(1 Introduction|1\. Introduction|Keywords|CCS Concepts|Contents)\b)', t2, re.S)
    ab = " ".join(m.group(1).split()) if m else ""
    if len(ab) < 120:
        # 退路: 取正文开头
        m2 = re.search(r'\bAbstract\b(.*)', t2, re.S)
        ab = " ".join(m2.group(1).split())[:900] if m2 else " ".join(t2[:900].split())
    print("=" * 84)
    print("### %s" % f)
    print(ab[:1000])
    out.append((f, ab[:1400]))
print("\n\n" + "#" * 84)
print("=== 全部摘要已提取 %d 篇 ===" % len(out))
io.open(r"E:/Divine Wisdom Core/.cache/papers19_abstracts.txt", "w", encoding="utf-8").write(
    "\n\n".join("### %s\n%s" % (a, b) for a, b in out))
