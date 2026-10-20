R398 · 收件箱无限重取：一单被重跑 52 次，整轮跑批作废

═══ 现场（2026-10-21 00:09，第二轮全池）═══
第二轮跑批卡死在 `nb_1020_232218_38`（analyze），会话日志 157KB：

    task_mode 出现 **52 次**（同一 task_id，每 30~60 秒一次）
    final 202 / run 180 / judge 179 / refcheck 102 / revision 89
    这一单跑了 45 分钟，后面 11 单全部超时（timeout/no-report）

═══ 根因链（三环）═══
① `run_user_task` 只在**开始时**写一次 `running:<ts>`
② 长任务跑超过 15 分钟 ⇒ `take_inbox()` 判它 **stale**（以为线程死了）
③ stale ⇒ 重取 ⇒ 再跑一遍；重取的线程又写回**旧标记**（或写失败）
   ⇒ 永远 stale ⇒ **无限重跑**

═══ 修法（两道闸）═══
① **执行期心跳**：`run_user_task` 每 60s 刷新 `running:<now>`
   ⇒ 正常长任务不会再被判 stale
   · 执行抛异常也必须停心跳（否则标记永远 running —— 比崩溃更糟：
     这一单既不会完成也不会被重取）
   · 终态写入前先 `_hb_stop.set()`（防心跳覆盖终态）
② **重取硬上限**：同一 task_id 最多重取 `MAX_REPICK = 3` 次
   · 计数落盘 `var/dwc_inbox_attempts.json`（跨重启保持，重启不重置预算）
   · 超限 ⇒ 标记 `failed:too_many_attempts` + 停止重试 + 记日志
   · 计数写失败 ⇒ 返回 1（不许因为计数把队列卡死）

═══ 验证 ═══
· TDD：R398（6 条）—— stale 可重取一次 / 超限不再返回并标记 failed /
  新鲜 running 不受影响 / done 永不重取 / 计数持久化 / 计数失败不阻断
· 全量 pytest：**2485 passed / 0 failed / EXIT=0**（302.12s）

═══ 诚实边界 ═══
1. `MAX_REPICK = 3` 是**拍的数**，没有数据支撑"3 次足够恢复"。
2. 心跳 60s + stale 阈值 900s ⇒ 理论上仍有 15 分钟的判定窗口，
   只是不会再被误判（标记一直新鲜）。
3. 重取上限只挡"重复重取"，**不解决任务本身跑 45 分钟**的问题
   —— 那单 analyze 为什么跑 45 分钟仍未查（refcheck 引用路径不存在
   `knowledge3_R1_audit.json` 导致 revision 循环 89 次）。
4. 第二轮全池因此**作废**，方差样本仍缺。
