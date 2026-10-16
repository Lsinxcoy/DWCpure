# R300-A · 落地改执行：因果链重通（plan）

## 1. 根因（论文 L4 实证）

- 2606.09498 §3.4：接受规则="至少一 split 改进、另一不退化"（门引"Algorithm 1
  第 13 行"系假精确，论文无 Algorithm 1；语义对，编号错，附带修正）。
- 2608.24876 Eq.9：修好源失败＋开发集无回归才进部署层（语义对）。
- 2606.14249：−14.0% 是 Telecom R7 累积 edits 单轮回归（门文案"只用一组证伪"
  系误读，附带修正）。
- 三篇一致：promote 的是**可执行体**，promote 后**立即成为下一轮执行环境**
  （edit→环境变→分变，因果链闭合）。
- DWC 断两处：
  ① 存→用断：`_land_adopted`→rules.json→RULES（含 learned，import 生效），
  但 `_prompt` 不看 RULES（起草看不见历史，下轮质量不变）；
  ② 门是错的尺子：code 路 trial 分是码的分（恒 1.0），规则增量（信息）
  用分数 Δ 量，恒 0（007 天花板只是实例）。

## 2. 方案（A：因果链重通，门加分支不降门）

### 2.1 存→用（evolver.py::_prompt，加 learned 段）

- 起草时同簇 key（`Mutator.key_for(c:q:fn)`）查 RULES：
  有→拼"该簇已有落地规则〈m/patch 一句话〉，禁重复已落地机制；
  另寻机制，或明确写出超越点（新归因）"；
  无→不拼（prompt 一字不差，老路零变）。
- 只增上下文，不动起草语义/字段/校验。

### 2.2 门加分支（evolver.py::accept，加 mode 参）

- `accept(p, baseline, current, eps=0.0, mode="report")`（默认 report，
  老路零变；旧测无 mode 全走原三条件）。
- report 路：原三条件 intact（d_in≥0∧d_ho≥0∧max>0，分数渐变适用）。
- code 路：前两条件（不退化）沿用；第三条件换成**规则增量**：
  key 不在 RULES（含 learned）⇒增量 ✓→adopted_not_implemented；
  key 已在⇒rejected"重复"（非 blocked，门判过：见过，不采）。
- 哲学 intact：还是要"真的有改进"，只是知识落地的改进=信息增量，
  不是分数 Δ（论文量执行体，DWC 落知识，尺子必须跟对象走）。

### 2.3 run_round 接线（只增调用）

- `_real_trial` 已回 mode→run_round 传门时带 `mode=t.get("mode","report")`。
- `_land_adopted` 幂等 intact（already_landed 双保险；门已拒重复，
  落地层再挡一次不冲突）。

### 2.4 引文修正（注释/docstring，不改判定）

- accept docstring："Algorithm 1 第 13 行"→"§3.4 文字规则
  （improves ≥1 split ∧ degrades none）"。
- blocked why 文案："只用一组会证伪自己的门 −14.0%"→
  "Telecom R7 累积 edits 单轮 −14.0%（无 held-out 之戒）"。
- 旧测若断言 why 文案→同步改期望（只改期望不改逻辑，R287-E 纪律）。

## 3. 改动清单

1. `src/dwc/organs/evolver.py::_prompt`：加 `learned_hint` 可选参（默认 ""），
   非空拼段；`propose_from_cluster` 组 hint（同簇查 RULES）传入。
   ※ 先读 propose_from_cluster 全貌再下刀（RULES 访问口径：self.mutator.RULES
   还是类属性，读码定）。
2. `src/dwc/organs/evolver.py::accept`：加 mode 分支＋增量判（key 查 RULES）。
   accept 是 @staticmethod？读码确认（调法 `evolver.accept(...)`）。
   key 构造：`Mutator.key_for` 需 (c,q,fn) sig——p.failure_signature＋target
   回填（_land_adopted 同款 `_sig.setdefault("fn", p.target)`，不手拼）。
3. `scripts/dwc_evo_round.py::run_round`：传 mode。
4. 测试 `tests/test_r300_knowledge_gate.py`（零真 LLM，fake＋raises≥5%）：
   ① 有 learned 同簇⇒prompt 含禁重复段；② 无⇒prompt 无段；
   ③ code 路新 key＋不退化⇒adopted_not_implemented；
   ④ code 路重复 key⇒rejected；⑤ report 路原三条件 intact（Δ全0⇒rejected）；
   ⑥ raises：key 缺 fn⇒ValueError 大声（key_for 原生抛，不吞）。
5. 双副本 md5（evolver.py＋新测＋run_round 改动文件）。
6. 生产验证：手动 apply 轮——007 簇（key 新？007 从未落地⇒新 key；
   trial 通＋ho 出⇒adopted_not_implemented→_land_adopted→rules.json 首落）。
   若 ho=null（LLM 波动）⇒blocked 诚实等下轮（b_ho 已有 1.0 点）。

## 4. 全局约束

- judge 零改；dev/sealed/配对表不动；trial fail-closed 不动；
  基线快照/R299-b3 不动；report 路门语义零变。
- R292 总闸：新测写盘指 tmp。
- GAI：anchors 只增不改（rules.json 落盘是 append learned，非改 anchors）。

## 5. 成功标准

- 新测 6 绿＋相关回归（r287 adopt/r291 peer/r295 trial/r299 hint 全绿）。
- 全量＋gate＋双 e2e（基线 1939＋R299 的 10，零新增 FAILED）。
- 手动轮 rules.json 首落（adopted_not_implemented→landed）。
