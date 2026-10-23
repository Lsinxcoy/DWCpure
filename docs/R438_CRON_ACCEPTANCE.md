# R438 · 进化 cron 手动触发验收记录

- 日期：2026-10-23 23:51–23:54（本地时区 +08:00）
- 对象：cron job `5e3846731b27`「DWC evo收尾每日」（`0 4 * * *`，`no_agent` 脚本作业）
- 目的：不等次日 04:00，**手动触发真实 cron 路径**，确认 R438 的 19 项落地没有把定时链路打断
- 结论：**第一次 failed，修完后连续 2 次 succeeded；四个进化维度均正确执行并正确跳过**

---

## 1. 触发方式

```bash
hermes cron run 5e3846731b27
```

走的是**真实 cron 路径**（调度器 → `%LOCALAPPDATA%/hermes/scripts/dwc_evo_round_cron.py` →
cron 自带解释器 → 结果写 `cron/output/5e3846731b27/<ts>.md`），不是手动跑仓库脚本。

---

## 2. 第一次：failed

```
Ran now: failed.

Traceback (most recent call last):
  File ".../hermes/scripts/dwc_evo_round_cron.py", line 343, in <module>
    sys.exit(main())
  File ".../hermes/scripts/dwc_evo_round_cron.py", line 121, in main
    from dwc.foundation.dial_config import load_evolution
  File "E:\Divine Wisdom Core\src\dwc\foundation\dial_config.py", line 25, in <module>
    import yaml
ModuleNotFoundError: No module named 'yaml'
```

### 根因

| 事实 | 证据 |
|---|---|
| cron 用 Hermes 自带解释器 | `%LOCALAPPDATA%/hermes/tools/python-3.14.7+…/python.exe` |
| 该解释器**没有 PyYAML** | `python.exe -c "import yaml"` → `ModuleNotFoundError` |
| R438 新增的 `load_evolution` 在 **import 期**就 `import yaml` | `dial_config.py:25` |
| 旧副本不 import `dial_config` | 所以过去 8 次 cron 一直"看起来正常" |

### 为什么会现在炸

R438 改的是**仓库里的** `scripts/dwc_evo_round_cron.py`（9,576 B → 16,434 B），
而 cron 跑的是 `%LOCALAPPDATA%/hermes/scripts/` 下的**副本**。

同步新脚本的那一刻，才把这个雷从"明天 04:00"提前引爆。
**这次手动触发，本质上是一次排雷。**

---

## 3. 两处修复

### 修法 1 · 解释器自举（`dwc_evo_round_cron.py`）

```python
def _bootstrap_interpreter() -> None:
    """缺 yaml 就换到 Hermes venv 的解释器重跑本文件。"""
    try:
        import yaml
        return
    except ImportError:
        pass
    if os.environ.get("DWC_REEXEC") == "1":
        raise SystemExit("缺少 PyYAML，自举后仍缺（DWC_REEXEC 已设，避免死循环）")
    # → subprocess.call([venv_python, __file__] + argv[1:], env={..., "DWC_REEXEC": "1"})
```

要点：
- **不用 `os.execv`** —— Windows 上含空格路径会被拆断（R428 教训）；
- `DWC_REEXEC=1` 防死循环；
- 子进程退出码直接作为本进程退出码。

### 修法 2 · 报告瘦身

改前：`print(json.dumps(rep)[:2000])`，而 `behavior_sigs` 有 **2,093 条**，
把 `lessons_promoted` / `prompt_evolve` / `meta_evolution` 全部挤出视野
——cron 输出看起来只有一堆签名，**等于没报告**。

改后：剔掉大数组（`behavior_sigs` 折叠成"2093 条（已省略）"），上限提到 6,000 字。

---

## 4. 验证时间线

| 时间 | 结果 | 说明 |
|---|---|---|
| 23:51:27 | **failed** | `ModuleNotFoundError: yaml` |
| 23:52:56 | **succeeded** | 自举生效 |
| 23:54:19 | **succeeded** | 报告瘦身生效 |

`hermes cron runs` 均为 `source=direct`（手动触发），退出码 0。

### 第三次的完整报告（节选）

```json
{
 "n_clusters": 0,
 "results": [],
 "filtered_nonreproducible": 2093,
 "n_code_sigs": 0,
 "n_behavior_sigs": 2093,
 "behavior_queued": 0,
 "behavior_queue_total": 11,
 "predictor": {"n": 200, "brier": 0.0475, "version": "pred-v1"},
 "lessons_promoted": {"to_medium": 0, "long_hints": 10, "n": 1205},
 "prompt_evolve": {"outcome": "not_scheduled", "weekday": 4, "configured": 6},
 "meta_evolution": {"outcome": "no_pressure"},
 "auto_apply": true,
 "rules_loaded": 0,
 "ledger": {"path": "E:\\Divine Wisdom Core\\var\\evolution_ledger.jsonl", "n": 0}
}
```

---

## 5. 判断正确性逐条核对

| 维度 | 输出 | 是否应如此 | 依据 |
|---|---|---|---|
| 聚簇 | `n_clusters: 0` | ✅ | 唯一可复现簇 `E_VALUE:wrong_magnitude:average` 已于 23:40 学过 ⇒ 幂等过滤，不重复学 |
| 代码签名 | `n_code_sigs: 0` | ✅ | 同上（学过的 key 不再进候选） |
| 行为签名 | `n_behavior_sigs: 2093` | ✅ | 不可复现签名只进队列，不参与试跑 |
| 教训晋升 | `to_medium: 0, n: 1205` | ✅ 但**偏低** | `use_count` 不够；晋升机制已跑，产出为 0 |
| 提示词 | `not_scheduled` | ✅ | 今天周五(`weekday=4`)，配置周日(`6`) |
| 元进化 | `no_pressure` | ✅ | 无压力信号 ⇒ 不动旋钮 |
| 落地 | `rules_loaded: 0` | ✅ | 本轮无候选 |

---

## 6. 结论

1. **cron 链路已通**：解释器自举 + 报告可读，连续 2 次 succeeded。
2. **R438 的 19 项落地没有破坏定时链路** —— 但差点破坏，靠这次手动触发提前发现。
3. **"改仓库 ≠ 进程跑新码"再次应验**：cron 跑的是 `hermes/scripts/` 副本，
   且**副本用的解释器与仓库 venv 不是同一个**。两个变量都要管。

---

## 7. 遗留（不在本轮范围）

| 项 | 现状 | 影响 |
|---|---|---|
| 教训晋升 | 1,205 条全 `short`，`to_medium: 0` | 晋升机制空转 |
| `behavior_queue` | 11 条只写不读 | 行为类签名进不了提案 |
| `architecture_queue` | 空 | 尚无架构提案过门 |
| 提示词 A/B | 仅 1 条 `dry_run` | 首次真跑：周日 04:00 |
| cron 解释器 | 依赖自举兜底 | 建议后续给 `tools/python` 装 PyYAML，去掉对自举的依赖 |

---

## 8. 复现命令

```bash
# 手动触发（走真实 cron 路径）
hermes cron run 5e3846731b27

# 看结果
hermes cron runs 5e3846731b27
ls -t ~/AppData/Local/hermes/cron/output/5e3846731b27/ | head -1

# 改完仓库脚本后必须同步，否则 cron 跑的仍是旧副本
python scripts/sync_hermes_scripts.py
```
