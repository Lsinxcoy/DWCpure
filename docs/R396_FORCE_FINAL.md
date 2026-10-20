R396 · 卡住时强制 final_answer（提示词不是约束）

═══ 现场（2026-10-20 21:35 全池，R394 上线后）═══
cl01/cl02 仍 incomplete，`why` 都是复读熔断，但动作日志显示
**模型其实已经拿到答案了**：

    search ok=True → read src/dwc/organs/memory.py ok=True
                   → 又搜 3 次（全被熔断拦）→ incomplete

即：模型**知道答案却不提交**，反复自证到死。

═══ 根因 ═══
R385 的收敛机制只靠**提示词**（"现在立即调用 final_answer"）。
模型可以无视提示词继续调工具 —— **提示词不是约束**。

而且 R247 复读熔断会**先一步把任务判死**，连强制收尾的机会都没有。

═══ 修法（两层）═══
① **API 层硬约束**：卡住时 `tool_choice` 从 `"auto"` 换成

       {"type": "function", "function": {"name": "final_answer"}}

   端点强制模型只能调 final_answer（不依赖模型自觉）。
② **熔断不再直接判死**：原生工具模式下，复读熔断触发时
   先给**一次强制 final** 的机会（`_ff_used < 1`），
   仍不提交才判 incomplete。
   非原生（JSON 路径）行为不变。

═══ 验证 ═══
· TDD：R396（4 条）—— 卡住必强制 final / 首轮必须 auto /
  强制后能产出答案 / 正常 2 轮路径不被强制
· 重锚 `test_r247_readfix::test_dup_fusion_blowout`
  （旧语义"立即 incomplete" ⇒ 新语义"先强制 final，仍不提交才 incomplete"；
   新增 `test_dup_blowout_never_finalizing_is_incomplete` 锁住反面）
· 定向：R247 + R396 + R385 = 16 passed
· 全量 pytest：**2477 passed / 0 failed / EXIT=0**（294.24s）

═══ 诚实边界 ═══
1. `tool_choice` 指定函数是 OpenAI 兼容扩展，**端点不一定支持**；
   不支持时行为退回"只有提示词"（未做能力探测）。
2. 强制 final 只给 **1 次**机会；模型若在强制轮仍不提交，直接判 incomplete。
3. 强制 final 可能逼出**质量更差**的答案（模型没准备好也得交）——
   宁可要一个带证据的答案，也不要"零答案 + incomplete"。
4. 全池效果待测（R396 只做了单点/假 LLM 验证）。
