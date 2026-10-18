# 后续开发 backlog（R329 后，未做项 guiding）

| # | 项 | 来源 | 成本 | 状态 |
|---|---|---|---|---|
| N1 | 执行侧sigs归agent_quality回路（cron自动投单） | R329 | 中 | done（R332） |
| N2 | fresh split 判分接入 A1b-2 | R326 | 中 | done（R330） |
| N3 | C1 parent 选择器＋archive 落盘 | R324 | 中 | done（R331） |
| N4 | lam/gamma 门参数启用（对照实验先行） | R313 | 大 | deferred（无自动对照 harness；lam 默认 0 保持老路，不静默启用） |
| N5 | evo_1019_01 转单跟进（agent 接单后 average 小数病是否根除，sigs 是否停产） | R329 | 被动 | monitoring（cron 自动投单已接通，下轮 cron 验证） |
| N6 | 普通轮起草复活验证（默认 2000 后首轮 cron 是否 drafted:true） | R328 | 被动 | monitoring（下轮 cron 验证） |
| N7 | max_tokens 预算再校准（probe 实测 want_code 路 1000 fail/1500 pass；默认校准 2000） | R328 | 小 | done（R332，probe） |

顺序建议：N2 → N7 → N3 → N1/N4（方案轮）→ N5/N6（被动跟进）。
N2 理由：fresh 集已落地＋m 参数已就绪，判分接入即闭环 Eq.8 m 真实来源；
且 N1/N4 动前需要"trial 能判"的基建，N2 正是补这块。

## R333-R337 (RSI survey 落地)
| R333 | state inheritance 启动接线 + 版本化 | done |
