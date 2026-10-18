# 后续开发 backlog（R329 后，未做项 guiding）

| # | 项 | 来源 | 成本 | 状态 |
|---|---|---|---|---|
| N1 | 执行侧真复现（trial 接 LLMTaskExecutor，真跑 agent 路径） | R329 | 大 | todo（需方案轮先行） |
| N2 | fresh split 判分接入 A1b-2 | R326 | 中 | done（R330） |
| N3 | C1 parent 选择器＋archive 落盘 | R324 | 中 | done（R331） |
| N4 | lam/gamma 门参数启用（对照实验先行） | R313 | 大 | todo |
| N5 | evo_1019_01 转单跟进（agent 接单后 average 小数病是否根除，sigs 是否停产） | R329 | 被动 | todo（等 agent） |
| N6 | 普通轮起草复活验证（默认 4000 后首轮 cron 是否 drafted:true） | R328 | 被动 | todo（等 cron） |
| N7 | max_tokens 预算再校准（4000 是否最小可用，2500/3000 探针） | R328 | 小 | todo |

顺序建议：N2 → N7 → N3 → N1/N4（方案轮）→ N5/N6（被动跟进）。
N2 理由：fresh 集已落地＋m 参数已就绪，判分接入即闭环 Eq.8 m 真实来源；
且 N1/N4 动前需要"trial 能判"的基建，N2 正是补这块。
