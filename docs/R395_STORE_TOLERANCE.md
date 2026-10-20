R395 · 生产 store 半行导致全量测试 59 failed + 37 errors

═══ 现场（2026-10-20 21:12）═══
全量 pytest 突然报 **59 failed + 37 errors**，全部同一个异常：

    json.decoder.JSONDecodeError: Extra data: line 1 column 2 (char 1)
    src/dwc/organs/judge.py:668  TaskScoreStore.__init__
    → 每次构造 Loop() 都崩

═══ 根因：生产数据文件里有半行 ═══
`config/anchors/task_scores.jsonl` 第 46 行被写成**半行**：

    …"recorded_at": "2026-10-20T21:1      ← 第 46 行
    7:51"}                                ← 第 47 行（尾巴）

一条记录被拆成两行。原因：`io.open(path, "a")` 是**带缓冲的文本流**，
`f.write()` 不保证一次落盘；多进程/异常中断就会写半行。

而读侧 `json.loads` 直接抛 ⇒ **一条半行让整个系统起不来**。

═══ 修法（两条纪律）═══
① **读**：坏行跳过 + **计数 + 大声报**（不许静默吞，也不许整库崩）
   · `_load_jsonl_tolerant()` / `_load_evidence_tolerant()`
   · 每跳过一行写一条 stderr 警告
   · `store.n_corrupt` 暴露损坏条数（可观测，不假装没事）
② **写**：`_append_line()` 用**单次 `os.write`** 到 O_APPEND fd
   （≤4KB 小写入原子追加，不再写半行）
   · `record()` 与 `_store_evidence()` 全部改用

═══ 数据修复 ═══
· 备份 `config/anchors/task_scores.jsonl.bak_r395`
· 尝试合并半行 + 尾巴 → 无法还原（记录确实被截断）
· 丢弃该条，保留 84 条合法记录
· 复查：**0 坏行**

⚠ 丢失 1 条评分记录（code_fix_001 / round_index 91）——
  这是**不可恢复**的数据损失，如实记录。

═══ 验证 ═══
· TDD：R395（7 条）—— 坏行不崩/计数+警告/evidence 同款/
  _append_line 用 os.write/往返 5 条含中文/生产路径用 _append_line/
  生产 store 现在每行合法
· 全量 pytest：**2472 passed / 0 failed / EXIT=0**（311.16s）

═══ 诚实边界 ═══
1. `os.write` 的原子性依赖"≤4KB 且 O_APPEND"；超大记录仍可能部分写。
2. 没有**跨进程锁**：两个进程同时追加仍可能交错（只是不再产生半行）。
   真正并发安全需要文件锁（未做）。
3. 坏行是**丢弃**不是修复：数据丢了就是丢了，只保证系统能起来。
4. `n_corrupt` 目前只在内存里，未落盘/未进监控。
