# DWC 铁律生产豁免清单（R206 · 2026-10-12）

> 用途：生产运行前的**诚实边界声明**。11 条铁律中 2 条真判、1 条无对象、
> **8 条数据面无设置方（not_instrumented）**——本文逐条写明为什么、
> 补全的前置条件、以及在补齐之前生产运行必须配的人工门。
> 机器可读版：`rep.iron_report`（run_term 每轮产出，not_instrumented
> 带逐条 why）。真值源：`config/iron_laws.yaml`（agent 不可写）。

## 一 · 已生效（真判，无需豁免）

| 律 | 判据 | 执行点 |
|---|---|---|
| G8 | 因果链五环 stages 齐套 | run_term 盘点（缺环 ⇒ warn[G8]） |
| G11 | report_must_quote：报告必引 certification_limit | 动作侧摘录 + 判在位（缺 ⇒ block[G11]） |

## 二 · 本轮无对象（na，非豁免）

| 律 | 原因 |
|---|---|
| G1 | trigger=pre_apply——term 周期无候选落地动作（applier 不在链上） |

## 三 · 豁免清单（8 条 · 数据面无设置方）

| 律 | 为什么豁免（实测依据） | 补全前置条件 | 补齐前的人工门 |
|---|---|---|---|
| G2 阈值单调 | dials/drift/difficulty 均为**单层** config，无 i<j 层级可判 | 出现多层阈值结构（如分层 θ）时 | 阈值改动一律人工 review（git diff 可审） |
| G3 冻结/主权 | frozen 字段**无设置方**：src 全仓 grep `frozen` 零业务命中（ARSI 同款病） | 落地 `config/freeze.yaml` + 写路径读它 | 锚/真值源改动 100% 人工（agent 无写权限——物理隔离） |
| G4 巩固字段 | memory.py grep `consolidat` **零命中**——巩固记录面不存在 | memory 落地巩固记录（why/trigger/verify 三字段） | 记忆写入全部经 judge/actor 既有校验路径 |
| G5 效用锚 | credit/evolver/applier grep `effect` **零命中**——效用记录面不存在 | credit 流水落 effect 字段 + 范围配置 | 进化采用只经 loop 门链（gate_chain blocked 不落地） |
| G6 熔断 | runner 无 LLM client 句柄——n_fail 活在 client 实例上，run_term 递不到 | LLMClient 把熔断状态暴露到 runner 注入面 | llm/client 自带 retries=1 + 超时；运行器异常 rc1 告警 |
| G7 Lyapunov | src grep `lyapunov` **零命中**——无埋点 | R144 四量度补 Lyapunov 单调量 | 四量度已有 instrumented_count 显式缺席 |
| G9 高熵验证 | decision/memory_write 触发点**无熵度量** | 写入路径加熵计算 + 验证门 | 高熵写入（大 patch）经三层验证强制 |
| G10 sealed 审计 | splitfeed 有锁语义但**无访问留痕**可判 | sealed 读写加审计日志 | test_sealed 判据路径只读（写锁已有测试） |

## 四 · 生产模式声明

1. **当前生产形态**：`dwc_prod_run.py` 多 term 轮询 + 人工观察台账——
   **无人值守自动写锚不存在**（anchor 只增不改由 `record_epoch` 机器锁 +
   文件权限双重保证）。8 条豁免在此形态下的暴露面=零（无自动写路径可保护）。
2. **豁免收紧触发条件**：任何一条的"补全前置条件"落地后，必须同轮把该律
   接进 `iron_runtime` 真判并删本表对应行（Layer 22 同族：不留死豁免）。
3. **审计入口**：每轮 `rep.iron_report`；台账 `var/dwc_prod_log.jsonl`
   每 term 记 `iron_block/iron_warn`；豁免表与 `iron_laws.yaml` 的
   not_instrumented why 一一对应（11=2+1+8 无静默）。
