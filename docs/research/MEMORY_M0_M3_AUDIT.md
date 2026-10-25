# DWC 记忆 M0–M3 · 设计 vs 落地审计

日期：2026-10-25  
范围：`docs/research/MEMORY_STRENGTHENING_M0_M3_PLAN.md` 的 19 项机制（MEM-01–MEM-19）  
方法：矩阵逐行核对代码文件、符号、测试文件；再跑默认全量测试。  
复跑：`.venv/Scripts/python.exe -B scripts/audit_memory_plan.py`

## 1. 结论

- **19/19 有代码落点和测试文件**；审计脚本 `issues=[]`。
- **18 adopt / 1 conditional**：MEM-19（MemPO / RL Navigator / 向量检索）由 `memory_policy.py` 默认关闭，属于设计上的条件扩展，不是漏做。
- 开发仓默认全量：**3284 passed / 9 skipped**（7 个 live 测试自动 skip，2 个常规 skip）。
- 本轮补掉的“设计了但没有消费方”的两处：
  1. `from_task_result()` 已接入 `scripts/dwc_agent.py::run_user_task`，且默认门是 `result_verified()`：`status=done` + 至少一次成功的 `run/test/check`，不再拿 `done` 冒充正确。
  2. `trajectory_stitch.stitch()` 已接入 `task_exec._revision_retry` 的修订对，产出 `stitched_trajectory`；单边/空轨迹仍 `stitched=False`。

## 2. 逐项落点

| ID | 状态 | 代码落点 | 测试 |
|---|---|---|---|
| MEM-01 | adopt | `src/dwc/llm/executor.py:memory_text` | `test_memory_retrieval.py asserts access_count increases` |
| MEM-02 | adopt | `src/dwc/organs/memory.py:SCHEMA + record_retrieval` | `test_memory_retrieval.py asserts one row per query` |
| MEM-03 | adopt | `src/dwc/organs/memory.py:retrieval_stats` | `test_memory_retrieval.py asserts hit_rate and zero count` |
| MEM-04 | adopt | `src/dwc/organs/skill_writer.py:classify_skill_kind` | `test_skill_quality.py covers all three kinds` |
| MEM-05 | adopt | `src/dwc/organs/skill_writer.py:procedure_from_actions/from_task_result` | `test_skill_procedure.py asserts steps and evidence_ref` |
| MEM-06 | adopt | `src/dwc/llm/task_trajectory.py + src/dwc/llm/task_exec.py:execute_user_task` | `test_task_trajectory.py asserts refs and hashes` |
| MEM-07 | adopt | `src/dwc/organs/working_state.py` | `test_memory_working_state.py rejects claimed done` |
| MEM-08 | adopt | `src/dwc/organs/memory.py:revise/learn/dream` | `test_consolidation_guard.py asserts original hash unchanged` |
| MEM-09 | adopt | `src/dwc/organs/memory_guard.py` | `test_memory_guard.py rejects tool injection and binary garbage` |
| MEM-10 | adopt | `src/dwc/organs/memory.py:link/neighbors/multi_hop` | `test_memory_edges.py covers 2-hop recall` |
| MEM-11 | adopt | `src/dwc/organs/memory.py:Zone.SELF/revise_self` | `test_memory_self.py asserts evolver cannot overwrite` |
| MEM-12 | adopt | `src/dwc/organs/preference.py` | `test_memory_belief.py covers correction and decay` |
| MEM-13 | adopt | `src/dwc/organs/memory_context.py` | `test_memory_context.py asserts budget and raw_ref` |
| MEM-14 | adopt | `src/dwc/organs/memory.py:retrieval_quality` | `test_memory_retrieval_quality.py covers MRR and zero-result` |
| MEM-15 | adopt | `src/dwc/organs/memory_maintenance.py` | `test_memory_maintenance.py asserts delete guards` |
| MEM-16 | adopt | `src/dwc/harness/contrast.py` | `test_memory_contrast.py asserts fail-pass delta captured` |
| MEM-17 | adopt | `src/dwc/harness/trajectory_stitch.py + src/dwc/llm/task_exec.py:_revision_retry` | `test_trajectory_stitch.py covers two related traces` |
| MEM-18 | adopt | `src/dwc/organs/memory_bench.py` | `test_memory_bench.py reports hit rate and MRR/NDCG` |
| MEM-19 | conditional | `src/dwc/organs/memory_policy.py` | `test_memory_non_goals.py asserts feature flag off` |

## 3. 仍然“设计存在、但没有完全落地”的项

这些不是代码漏写，而是**外部条件或数据条件不满足**；不能靠再写一个模块消除。

| 项 | 现状 | 为什么不能算落地 | 处置 |
|---|---|---|---|
| MEM-19 MemPO / RL Navigator / 向量检索 | `memory_policy.py` 全 False，`require()` 抛错 | 没有 retrieval hit-rate/effect 证据；RL 需要配对数据和训练控制权 | 保持 conditional；先用 MEM-18 词法基线，只有证据不足才评估向量 |
| 生产成功/失败配对样本 | `contrast.py` 有 API，生产 `failure_sig=0` | 没有真实失败对，无法验证“分叉点”因果 | 在隔离工作区跑真实失败/修复对；不得合成轨迹 |
| 真端点 live 测试 | 7 个标记 `live`，默认 skip；`--run-live` 才跑 | 远程端点 HTTPS read 会阻塞，代码不能保证外部可用 | 默认全量不依赖端点；live 证据单独跑并如实记录 |
| 生产真实 smoke | 上次被端点阻塞；假 LLM 临时目录已验证 `trajectory_status=recorded` | 外部端点不可控 | `LLMClient` 已加总 deadline（默认 ≤90s），至少保证有界失败 |
| 价格 / 成本 | `pricing_status=not_configured` | 用户明确先跳过；没有真实费率 | 保持 `indeterminate`，不填 0、不估算 |
| Windows 低权限沙箱 | script/hook Probe 仍应 `blocked` | 当前主机未做低权限沙箱实测 | 保持不可用声明 |
| AKV serving / TIES / SFT | 未启用 | 远程 OpenAI 兼容端点无 `drop_message/reposition`、无 checkpoint 控制权 | 条件扩展，不声称支持 |
| synth_tests / coreset | 未实现 | 属于条件扩展，不能替代真值 | 保持未实现 |
| DWC 2.0 主计划 W1–W5 勾选 | `docs/DWC_PURE_2.0_DEVELOPMENT_PLAN.md` 末尾仍有 `[ ]` | W4 只在 shadow、未跑真实任务集；部分验收依赖 held-out/生产回滚 | 勾选状态保持未完成；状态文档已列 11 条边界，不用勾选掩盖 |

## 4. 审计判定

- **“方案设计了但代码没写”**：M0–M3 范围内 **0 项**。
- **“代码写了但没消费方”**：本轮补掉 2 项（`from_task_result`、`trajectory_stitch`）；MEM-16 `contrast` 仍缺真实配对样本，属于数据缺口。
- **“设计了但按设计不启用”**：MEM-19 1 项，明确 conditional。
- **“外部环境不具备”**：live 端点、AKV、TIES/SFT、Windows 沙箱、价格，均不能算代码落地。
