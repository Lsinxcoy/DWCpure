# 草稿代码（架构定稿前写的，未纳入设计）

2026-10-03：用户在"先补 GAI 缺的 m 和 U"的指示下，我在架构（器官归属/目录结构/
接口契约）尚未定稿时就开始写码。用户当即纠正："这就开始写代码了？我们还没有完全
搞定架构啊"。

这 4 个文件是在**架构未定稿**状态下写的，因此：
- 它们**不是** DWC 设计的一部分
- 它们让 scripts/gate.py 的 G1 定位门报红（缺定位声明），故移出 src/
- 去留待架构定稿后决定：可复用其中与定稿一致的部分，其余作废

文件：
    dwc__init__.py                 空包文件（我当时刚建）
    dwc__evolution__init__.py      空包文件（我当时刚建）
    dwc__evolution__activity.py              活性六层 + 四量度量
    dwc__evolution__component_taxonomy.py    RRSI 𝒦 词表
    dwc__evolution__modifier.py              m（改进器）+ 退火预算
    dwc__evolution__modification_critic.py   U（改动评估器）

教训（写进纪律）：**架构未定稿前不写承重代码**。方向确认 ≠ 可以开工；
"做乙"要先问清"做到什么粒度"。
