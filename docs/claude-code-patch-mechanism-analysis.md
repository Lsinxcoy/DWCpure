# Claude Code Patch 生成机制 — 逆向分析

## 来源
逆向工程 `packages/builtin-tools/src/tools/FileEditTool/` (FileEditTool.ts + utils.ts)

## 核心架构：LLM-Driven, Tool-Dumb

### 1. Patch 应用机制（极度简单）
- `findActualString(fileContent, searchString)` = `fileContent.includes(searchString)` → 返回 searchString 或 null
- **没有 fuzzy matching**，**没有 diff**，**没有 auto-retry**
- 应用：`content.replace(oldString, newString)`（first occurrence）
- 如果不匹配 → 返回错误给 LLM，LLM 自行分析并重试

### 2. 失败处理
- 工具返回 `String to replace not found in file`
- LLM（Claude）读取错误信息，重新读取文件，重新生成 old_string/new_string
- 迭代循环由 LLM 的多轮对话自然驱动，不是工具内建的

### 3. 文件定位
- LLM 自己决定读哪个文件（通过 Read 工具）
- 没有硬编码文件路径
- LLM 基于问题语义 + 代码结构自主定位

### 4. 关键设计哲学
> 工具是 dumb 的，智能在 LLM。

- 工具只做确定性操作：find substring → replace → write
- 所有智能（定位、理解、生成、重试）都在 LLM 侧
- 模型是组件，架构是关键

## 对 DWC 的启示

### 当前 DWC 的问题
1. **工具太聪明**：硬编码 fix + fuzzy fallback + 验证逻辑，LLM 被动
2. **没有迭代**：失败即放弃，不反馈错误给 LLM
3. **文件定位硬编码**：只看 rewrite.py

### 改进方向（模型无关）
1. **LLM 驱动**：让 LLM 自己选文件、生成 patch
2. **迭代循环**：失败时把错误 + 文件内容喂回 LLM 重试（3-5 轮）
3. **模型可配置**：通过环境变量指定，不写死
4. **Patch 应用保持简单**：includes() + replace() 即可，不需要 fuzzy

### 预期效果
- 仅靠架构改进（迭代 + LLM 驱动），即使用免费模型也能从 20% 提升到 30-40%
- 如果能用更强 LLM，进一步提升到 50%+

---

# DeepSeek SWE-bench 评测 — Harness 分析

## 来源
Web search: DeepSeek V3/V3.2 Technical Reports, SWE-bench Leaderboard, Scaffold Effect paper

## DeepSeek 在 SWE-bench 上的表现

| 模型 | Harness | SWE-bench Verified | 成本 |
|------|---------|-------------------|------|
| DeepSeek V3.2 | mini-SWE-agent | 70.00% resolved | $0.45/task |
| DeepSeek V3.2 Reasoner | mini-SWE-agent | 60.00% resolved | $0.03/task |

## Harness 设计关键点（来自 Scaffold Effect paper）

### 1. Harness 选择影响与模型选择相当
- 固定模型下，best vs worst harness 差距 ~19.4 个百分点
- 固定 harness 下，Claude 模型间差距 ~22.8 个百分点
- **Harness 设计是一等公民，不是附属品**

### 2. mini-SWE-agent 的核心策略
- **短上下文分解**：成功的 agentic 轨迹通常 < 20k tokens
- **任务分解**：把复杂任务拆成短上下文步骤，而非长上下文推理
- **轻量级**：不使用复杂的工具注册表、上下文压缩、子代理

### 3. Harness 组件效果（NanoHarness 分析）
| 组件 | 效果 |
|------|------|
| 结构化工具使用 | 最稳定改进 |
| 任务特定子代理 | 最稳定改进 |
| 上下文压缩 | 可能伤害 repository-generation 性能 |
| 通用子代理 | 可能伤害性能 |
| 显式规划 | 对弱模型有帮助，强模型收益递减 |

### 4. Harness 与任务类型的关系
- **SWE-style issue repair**（固定流程、局部编辑）：复杂 harness 对弱模型有补偿，强模型收益递减
- **Repository-level 任务**（开放、复杂）：复杂 harness 是能力放大器，只有强模型能利用

## 对 DWC 的启示

### DeepSeek 的成功不是因为模型强
- DeepSeek V3.2 用 mini-SWE-agent（轻量 harness）达到 70%
- 关键是 **task decomposition into short-context steps**
- 而不是长上下文推理

### DWC 应该学什么
1. **轻量 harness**：不要过度工程化（复杂工具注册表、上下文压缩等）
2. **短上下文步骤**：把任务拆成小步骤，每步只给 LLM 需要的上下文
3. **迭代重试**：LLM 驱动的多轮对话，失败时反馈错误
4. **模型无关**：DeepSeek 用 mini-SWE-agent 达到 70%，证明架构比模型更重要

### DWC 当前 vs DeepSeek harness
| 维度 | DWC | mini-SWE-agent (DeepSeek) |
|------|-----|--------------------------|
| 架构 | 硬编码 fix + fallback | LLM 驱动 + 短上下文步骤 |
| 上下文 | 单文件 4000 字符 | 短上下文分解 |
| 迭代 | 无 | LLM 多轮对话 |
| Patch 应用 | 字符串替换 | diff-based (git apply) |
| 通过率 | 20% (1/5) | 70% (SWE-bench Verified) |

---

# Hermes Agent Patch/编辑机制 — 逆向分析

## 来源
Hermes Agent 源码: `C:/Users/41228/hermes-agent/`

## 核心架构

### 1. 工具系统
Hermes 使用 `patch` 和 `write_file` 工具进行文件编辑：

**patch 工具** (targeted find-and-replace):
- 使用 fuzzy matching（9 种策略）处理空白/缩进差异
- 返回 unified diff
- 编辑后自动运行语法检查
- 要求 old_string 在文件中唯一（除非 replace_all=true）

**write_file 工具** (whole file overwrite):
- 完全替换文件内容
- 创建父目录
- 对已有文件要求先 read_file（防止盲写）
- 自动运行语法检查（.py/.json/.yaml/.toml 等）

### 2. FileEditTool 对应物
Hermes 没有专门的 FileEditTool，而是用 `patch` + `write_file` 两个通用工具：
- `patch` ≈ Claude Code 的 FileEditTool (find & replace)
- `write_file` ≈ Claude Code 的 Write 工具 (whole file)

### 3. Patch 应用策略
Hermes 的 `patch` 工具：
- 使用 fuzzy matching（9 种策略）处理空白差异
- 这比 Claude Code 的简单 `includes()` 更鲁棒
- 但仍然要求 old_string 在文件中唯一

### 4. 迭代机制
Hermes 通过 **多轮对话** 实现迭代：
- LLM 生成 patch → tool 执行 → 结果返回 LLM → LLM 分析 → 重新生成
- 没有内建的 auto-retry，完全依赖 LLM 的多轮对话
- 与 Claude Code 相同的设计哲学：智能在 LLM，工具 dumb

### 5. 文件定位
- Hermes 没有自动文件定位机制
- LLM 使用 `search_files` (grep/ripgrep) 查找相关文件
- LLM 使用 `read_file` 读取文件内容
- 完全由 LLM 驱动

### 6. 关键差异：Hermes vs Claude Code
| 维度 | Hermes | Claude Code |
|------|--------|-------------|
| Patch 工具 | patch (fuzzy 9 strategies) + write_file | FileEditTool (includes + replace) |
| Fuzzy matching | 9 种策略 | 无 (简单 includes) |
| 语法检查 | 编辑后自动运行 | 无 |
| 文件读取 | read_file (带行号分页) | Read 工具 |
| 搜索 | search_files (ripgrep) | Grep/Glob 工具 |
| 迭代 | LLM 多轮对话 | LLM 多轮对话 |
| 智能位置 | LLM | LLM |

### 7. Hermes 的优势
- **Fuzzy matching**：9 种策略处理空白/缩进差异，比 Claude Code 的简单 includes 更鲁棒
- **语法检查**：编辑后自动验证，防止语法错误
- **read_file 分页**：大文件分页读取，避免 context 溢出

### 8. Hermes 的劣势
- **没有内建的 diff 生成**：patch 工具只做 find & replace，不生成 unified diff
- **没有自动测试运行**：编辑后不自动跑测试
- **没有内建的迭代循环**：完全依赖 LLM 多轮对话

## 对 DWC 的启示

Hermes 的 patch 工具比 Claude Code 的更鲁棒（fuzzy matching），但 DWC 仍然：
1. 用字符串替换而非 diff-based patch
2. 没有迭代循环
3. 硬编码文件路径和 fix 模式

**建议 DWC 借鉴 Hermes 的 approach**：
- 使用 fuzzy matching（而非简单 includes）提高 patch 应用成功率
- 添加语法检查（防止无效 patch）
- 保持 LLM 驱动的架构

---

# OpenCode (anomalyco/opencode) Patch 生成机制 — 分析

## 来源
- Web: theagentstack.substack.com (OpenCode permissions & edit)
- Web: wuu73.org (AI File Editing Playbook — How Agent Harnesses Edit Files)

## 核心架构：9 层 Fallback + LSP 集成

### 1. Edit Tool (tool/edit.ts)
OpenCode 的 EditTool 实现 **9 种匹配算法**，按顺序尝试：

| # | Replacer | 作用 |
|---|----------|------|
| 1 | SimpleReplacer | 精确匹配 + 转义版本 |
| 2 | LineTrimmedReplacer | 逐行 trim 后比较 |
| 3 | BlockAnchorReplacer | 匹配首尾行 + 相似度检查 |
| 4 | WhitespaceNormalizedReplacer | 多空格/Tab → 单空格 |
| 5 | IndentationFlexibleReplacer | 移除公共缩进前缀 |
| 6 | EscapeNormalizedReplacer | 反转义 \n, \t, \" 等 |
| 7 | TrimmedBoundaryReplacer | 修剪整个块的边界 |
| 8 | ContextAwareReplacer | 50% 相似度阈值 + 上下文 |
| 9 | MultiOccurrenceReplacer | 查找所有匹配（replace_all） |

### 2. LSP 集成
- 每次编辑后，OpenCode 通过 LSP 检查语法错误
- 错误以 XML 格式追加到 tool response
- AI 可以看到错误并自行修正

### 3. Patch Tool (tool/patch.ts)
- 支持 unified diff 格式
- 用于多文件、复杂变更

### 4. 与其他 Agent 的对比

| Feature | Cline | Codex/Claude Code | OpenCode | Aider |
|---------|-------|-------------------|----------|-------|
| Primary Method | Search/Replace | Custom Patch | Search/Replace | Format-flexible |
| Fallback Layers | 4 | 3-4 | 9 | 5 |
| LSP Integration | Partial | Minimal | Full | Minimal |
| Multi-File Edits | Sequential | One Patch | Sequential | Sequential |
| Token Format | XML | Custom | JSON-ish | Markdown |

### 5. 五种核心编辑方法
| Method | Token Cost | Reliability | Best For | Used By |
|--------|-----------|-------------|----------|---------|
| Whole File Replacement | High | 100% | New files, small files | All (fallback) |
| Search & Replace | Low | Medium | Targeted edits | Cline, Aider, OpenCode |
| Unified Diff / Patch | Very Low | Variable | Multi-file refactors | Codex, Aider (udiff) |
| Line-Based / Anchor | Medium | Good | When exact match fails | OpenCode, Cline |
| Multi-Edit / Atomic | Medium | High | Bulk changes | OpenCode |

### 6. Fallback Cascade（级联回退）
所有 top-performing agents 都实现级联回退：
1. Exact Match (byte-for-byte)
2. Whitespace Flexible (normalize spaces/tabs, trim lines)
3. Anchor Matching (match first/last lines, fuzzy middle)
4. Diff/Patch Application (diff-match-patch or git cherry-pick)
5. Full Overwrite (nuclear option, 100% but expensive)

## 对 DWC 的启示

### OpenCode 的 9 层 fallback 与 Hermes 的 9 策略惊人相似
- OpenCode: 9 replacers (Simple, LineTrimmed, BlockAnchor, WhitespaceNormalized, IndentationFlexible, EscapeNormalized, TrimmedBoundary, ContextAware, MultiOccurrence)
- Hermes: 9 strategies (fuzzy matching)
- 两者都采用 "maximize success probability through redundancy" 哲学

### OpenCode 的 LSP 集成值得借鉴
- 编辑后立即检查语法错误
- 错误追加到 tool response，AI 可自行修正
- DWC 可以在 patch 应用后运行 `py_compile`，把错误喂回 LLM

### OpenCode vs Claude Code vs DeepSeek vs Hermes 对比

| 维度 | Claude Code | DeepSeek (mini-SWE) | Hermes Agent | OpenCode |
|------|-------------|---------------------|--------------|----------|
| Patch 应用 | includes() + replace() | diff-based (git apply) | fuzzy 9 strategies | 9 replacers cascade |
| Fuzzy matching | 无 | N/A | 9 策略 | 9 replacers |
| LSP/语法检查 | 无 | 无 | 有（编辑后） | 有（LSP 全集成） |
| 迭代 | LLM 多轮 | LLM 多轮 | LLM 多轮 | LLM 多轮 |
| 文件定位 | LLM 自主 | LLM 自主 | LLM + search | LLM 自主 |
| 上下文 | LLM 自主 | 短上下文 (<20k) | LLM 自主 + 分页 | LLM 自主 |
| 通过率 | 高 | 70% (V3.2) | N/A | N/A |
| 核心哲学 | 工具 dumb, 智能在 LLM | 轻量 harness, 短上下文 | 工具 slightly smart | 最大冗余, 9 层 fallback |

### DWC 最终改进方案（综合四家之长）

1. **Patch 应用**: 采用 OpenCode/Hermes 的 9 层 fallback（而非 Claude Code 的简单 includes）
2. **LSP/语法检查**: 借鉴 OpenCode，编辑后运行 py_compile，错误喂回 LLM
3. **迭代循环**: LLM 驱动，失败时反馈错误（Claude Code 模式）
4. **短上下文**: 每步只给相关文件（DeepSeek 模式）
5. **模型可配置**: 环境变量，不写死
6. **工具 dumb**: 不做智能判断，只做 apply + test（Claude Code 哲学）

### 预期效果
- 架构改进 alone: 20% → 35-45%
- + 更强 LLM: 45% → 55-65%
- + 迭代 + 短上下文: 65% → 70%+

---

# SWE-bench Coding Agent 排名 (2026) — 值得学习的 Agent

## 来源
- awesomeagents.ai SWE-Bench Leaderboard (Apr 2026)
- trustthebench.com Autonomous Coding Agents Leaderboard (Sep 2026)
- codesota.com SWE-bench Leaderboard

## SWE-bench Verified 排名 (Top 16)

| Rank | Agent | Base Model | Verified | 开源? | 值得学习? |
|------|-------|------------|----------|-------|-----------|
| 1 | Augment Code SWE-Agent | Claude Opus 4.6 | 72.0% | ❌ | 闭源，但 blog 描述 hybrid BM25+embedding+code-graph |
| 2 | OpenHands + CodeAct v3 | Claude Opus 4.6 | 68.4% | ✅ | **强推** CodeAct 模式 |
| 3 | Cursor Background Agent | Claude Sonnet 4.6 | 65.7% | ❌ | IDE 集成 |
| 4 | Composio SWE-Kit | Claude Sonnet 4.6 | 62.3% | ❌ | Enterprise tooling |
| 5 | Cline (Autonomous) | Claude Sonnet 4.6 | 59.8% | ✅ | **强推** 9 层 fallback |
| 6 | Factory Droid | GPT-5.3-Codex | 58.1% | ❌ | CI/CD 集成 |
| 7 | Devin 2.0 | Proprietary | 45.8% | ❌ | Cognition AI |
| 8 | OpenHands + CodeAct v2 | GPT-5.2 | 44.7% | ✅ | 旧版 scaffold |
| 9 | SWE-agent v1 | Claude Sonnet 4.5 | 43.2% | ✅ | **强推** ACI 设计 |
| 10 | AutoCodeRover v2 | GPT-5.2 | 38.6% | ✅ | 程序分析引导 |
| 11 | Moatless Tools | Claude Haiku 4.5 | 35.9% | ✅ | **强推** 成本效率 |
| 12 | Agentless v2 | Claude Sonnet 4.5 | 34.2% | ✅ | **强推** 极简编排 |
| 13 | Aider (architect) | Claude Sonnet 4.5 | 31.4% | ✅ | **强推** 双模型架构 |
| 14 | SWE-agent v1 | GPT-5.2 | 29.7% | ✅ | 弱模型 baseline |
| 15 | Continue | Llama 4 Maverick | 18.3% | ✅ | 本地模型最佳 |
| 16 | Moatless Tools | Llama 4 Maverick | 14.7% | ✅ | 离线部署 |

## 值得学习的 Agent（按优先级）

### 1. SWE-agent (Princeton NLP) — ⭐⭐⭐⭐⭐
- **开源**: https://github.com/SWE-agent/SWE-agent
- **核心贡献**: Agent-Computer Interface (ACI) — 为 SWE 任务设计的专用工具集
- **工具**: view_file, create_file, search_dir, edit_file 等
- **通过率**: 43.2% (Sonnet 4.5) / 29.7% (GPT-5.2)
- **DWC 可学**: ACI 设计模式——为特定任务设计专用工具，而非通用工具

### 2. OpenHands + CodeAct — ⭐⭐⭐⭐⭐
- **开源**: https://github.com/All-Hands-AI/OpenHands
- **核心贡献**: CodeAct — 用代码作为 action（而非 JSON tool call）
- **通过率**: 68.4% (Opus 4.6)
- **DWC 可学**: 代码即 action 的模式，比 JSON tool call 更灵活

### 3. Aider — ⭐⭐⭐⭐
- **开源**: https://github.com/Aider-AI/aider
- **核心贡献**: Architect-Editor 双模型架构（一个规划，一个执行）
- **通过率**: 31.4% (Sonnet 4.5)
- **DWC 可学**: 双模型分工——弱模型规划 + 强模型执行，降低成本

### 4. Moatless Tools — ⭐⭐⭐⭐
- **开源**: https://github.com/aorwall/moatless-tools
- **核心贡献**: 程序分析引导的文件定位 + 成本效率优化
- **通过率**: 35.9% (Haiku 4.5) / 14.7% (Llama 4 Maverick)
- **DWC 可学**: 用静态分析定位相关文件，而非 LLM 猜测；成本效率极高

### 5. Agentless — ⭐⭐⭐⭐
- **开源**: https://github.com/OpenAutoGPT/Agentless
- **核心贡献**: 极简编排——无工具调用，纯 LLM 生成 patch
- **通过率**: 34.2% (Sonnet 4.5)
- **DWC 可学**: 最简架构也能达到 34%，证明复杂工具不是必须的

### 6. Cline — ⭐⭐⭐
- **开源**: https://github.com/cline/cline
- **核心贡献**: 9 层 fallback + LSP 集成
- **通过率**: 59.8% (Sonnet 4.6)
- **DWC 可学**: OpenCode 的 9 replacers 已覆盖，Cline 的 LSP 集成值得学

## 关键数据点

### Scaffold Effect (Harness 选择的影响)
- 固定模型下，best vs worst harness 差距: **~19.4 个百分点**
- 固定 harness 下，Claude 模型间差距: **~22.8 个百分点**
- **Harness 设计 ≈ 模型选择**（影响相当）

### 成本效率
| Agent | 模型 | 通过率 | 成本/task |
|-------|------|--------|-----------|
| DeepSeek V3.2 | DeepSeek V3.2 | 70% | $0.45 |
| DeepSeek V3.2 Reasoner | DeepSeek V3.2 | 60% | $0.03 |
| Moatless + Haiku | Claude Haiku 4.5 | 35.9% | ~$0.42 |
| Aider | Claude Sonnet 4.5 | 31.4% | ~$0.50 |

### DWC 的定位
- 当前: 20% (1/5 pytest instances)
- 目标: 40%+ (通过架构改进，不换模型)
- 天花板: 70%+ (需要更强 LLM + 完善架构)

## 建议的 DWC 学习路径

1. **先学 Agentless**（最简单）：理解极简 patch 生成的上限
2. **再学 Moatless**（成本效率）：理解程序分析引导的文件定位
3. **再学 SWE-agent**（ACI）：理解专用工具设计
4. **最后学 OpenHands CodeAct**（高通过率）：理解 CodeAct 模式

---

# Augment Code — 逆向分析

## 来源
- Web: augmentcode.com/blog (Auggie tops SWE-Bench Pro)
- Web: augmentcode.com/blog (#1 open-source agent on SWE-Bench Verified)
- GitHub: augmentcode/augment-swebench-agent (开源)

## 架构

### 1. 核心组件
- **Context Engine**: 混合 BM25 + embedding 检索 + code-graph 层（symbol 依赖追踪）
- **Agent**: 基于 Anthropic blog post 的 SWE-bench agent 架构
- **Ensembler**: OpenAI o1 majority vote 选择最佳方案

### 2. 工具集
- Bash 命令执行
- 文件查看和编辑（string-replace based）
- Sequential Thinking MCP（复杂问题求解）

### 3. SWE-bench 成绩
| 版本 | 模型 | SWE-bench Verified | SWE-bench Pro |
|------|------|-------------------|---------------|
| v1 (开源) | Claude Sonnet 3.7 + o1 ensembler | 65.4% | - |
| Auggie (闭源) | Claude Opus 4.6 | 72.0% | 51.80% |

### 4. 关键发现

**什么有效**:
- Sequential Thinking MCP（替代 Anthropic 未发布的 planning tool）
- o1 ensembler（majority vote 选最佳方案）
- string-replace based 文件编辑（够用）

**什么无效**:
- Sonnet 3.7 thinking mode（SWE-bench 中无效）
- 单独的 "fix regressions" agent（引入新 bug，净效果为零）
- embedding-based retrieval（SWE-bench 中 grep/find 足够；产品体验中 embedding 才关键）
- "smart paste model"（实验性，无帮助）

### 5. Context Engine（产品级检索）
- 混合 BM25 + embedding，理解 code 关系
- 实时语义索引，秒级更新
- code-graph 追踪 symbol 依赖
- "add logging to payment requests" → 映射整个路径（React → Node → payment → DB → webhook）

### 6. Ensembling 策略
- 多个 candidate solutions（diffs）
- o1 分析并选择 majority vote solution
- 提供额外 context 无帮助
- o1 比 Sonnet 3.7 ensembling 好 ~2%

### 7. Agent 架构（开源版）
```
Agent (Claude Sonnet 3.7)
  ├── Bash tool (命令执行)
  ├── File view/edit tool (string-replace)
  ├── Sequential Thinking MCP (复杂推理)
  └── Majority Vote Ensembler (o1)
```

## 对 DWC 的启示

### Augment 的 lesson
1. **Context Engine 是核心竞争力**：混合检索 + code-graph，不是简单的 grep
2. **Ensembling 有效**：多 candidate + o1 选最佳，提升 ~2-3%
3. **string-replace 够用**：不需要复杂的 patch 格式
4. **thinking mode 无效**：Sonnet 3.7 的 thinking 在 SWE-bench 中反而没帮助
5. **"fix regressions" agent 有害**：引入新 bug，净效果为零

### DWC 可借鉴
- **Ensembling**: 生成 3-5 个 candidate patch，用 LLM 选最佳（成本增加但通过率提升）
- **Context Engine**: 对 DWC 来说，简单的 grep + 文件读取可能就够（Augment 在 SWE-bench 中发现 grep 足够）
- **Sequential Thinking**: 对复杂 issue，让 LLM 先分析再行动

---

# OpenHands (OpenDevin) — 逆向分析

## 来源
- Web: github.com/OpenHands/OpenHands (README + codeact_agent)
- Web: arxiv.org/html/2407.16741 (OpenHands paper)

## 核心架构

### 1. CodeAct Agent
- **核心理念**: 将 LLM agent 的 actions 统一到 code action space（而非 JSON tool call）
- **优势**: 简单 + 高性能
- **工具集**:
  1. `execute_bash` — Linux bash 命令执行
  2. `execute_ipython_cell` — IPython 代码执行
  3. `browser` / `web_read` — 网页交互
  4. `str_replace_editor` — string replacement 编辑（精确匹配 + undo）
  5. `edit_file` (LLM-based) — LLM 生成内容编辑（支持行范围）

### 2. 两种文件编辑模式
| 模式 | 工具 | 特点 |
|------|------|------|
| String Replace | str_replace_editor | 精确匹配，undo 支持，行号查看 |
| LLM-based | edit_file | LLM 生成内容，支持行范围，大文件友好 |

### 3. str_replace_editor
- View, create, edit files through string replacement
- Persistent state across command calls
- File viewing with line numbers
- String replacement with **exact matching**
- Undo functionality for edits

### 4. edit_file (LLM-based)
- Edit files using LLM-based content generation
- Support for partial file edits with line ranges
- Handles large files by editing specific sections
- Append mode for adding content

### 5. AgentSkills 库
- 文件编辑工具 adapted from SWE-Agent + Aider
- `edit_file` — 修改现有文件的指定行
- `scroll_up` / `scroll_down` — 查看文件不同部分

### 6. Event Stream 架构
- 用户界面、agent、环境通过 event stream 交互
- 强大且灵活
- Docker-sandboxed runtime（安全隔离的 Linux OS）

### 7. Micro-agents
- 专用 micro-agents 处理特定任务（npm, github 等）
- 可扩展

### 8. SWE-bench 成绩
| 版本 | 模型 | SWE-bench Verified |
|------|------|-------------------|
| OpenHands + CodeAct v3 | Claude Opus 4.6 | 68.4% |
| OpenHands + CodeAct v2 | GPT-5.2 | 44.7% |

### 9. 关键发现
- "Current agent suffers a lot when editing long files" — 长文件编辑是痛点
- LLM-based edit_file 是为了解决长文件编辑问题
- str_replace_editor 用于精确小编辑，edit_file 用于大范围编辑

## 对 DWC 的启示

### OpenHands 的 lesson
1. **CodeAct 模式**: 用代码作为 action，比 JSON tool call 更灵活
2. **双编辑模式**: 精确 string replace + LLM-based 大范围编辑，按场景选择
3. **LLM-based 编辑**: 对长文件，让 LLM 生成目标内容而非 old/new string
4. **Undo 支持**: 编辑可回滚，降低风险
5. **AgentSkills 库**: 复用 SWE-Agent + Aider 的 proven 工具

### DWC 可借鉴
- **双编辑模式**: string replace（小编辑）+ LLM 生成（大编辑）
- **LLM-based 编辑**: 对长文件，直接让 LLM 输出修改后的文件内容，而非 old/new string
- **Undo 支持**: 编辑前 git stash，失败时回滚

---

# Cursor — 逆向分析

## 来源
- Web: cursor.com/blog (Composer 2 Technical Report, Agents benchmark)
- Web: arxiv.org (CORVUS paper, Composer 2 Technical Report)
- Web: chatgptaihub.com (How to Build an AI Agent with Cursor in 2026)

## 核心架构

### 1. Composer 2
- **专用模型**: 为 agentic software engineering 设计
- **SWE-bench Verified**: 71.4% (GPT-5.3-codex) / 68.9% (Claude Sonnet 4.6)
- **工具**: read_file, edit_file, run_terminal, semantic_search, web_search
- **Prompt**: system message + tool call format + recent file info + past user messages + current task

### 2. 六层架构
| 层 | 作用 |
|----|------|
| 1. Model Router | 路由到不同模型（GPT-5.3-codex, Claude Sonnet 4.6, Gemini 3.1 Pro） |
| 2. Context Assembler | symbol graph, diffs, open files with caching |
| 3. Tool Layer | read_file, edit_file, run_terminal, semantic_search, web_search |
| 4. MCP Integration | HTTP/stdio processes, JSON Schema catalog |
| 5. Prompt Caching | 代码上下文成本降低 90% |
| 6. Verification Loop | 单 agent + 验证循环 > 多 agent 编排 |

### 3. 关键发现

**架构选择**:
- **单 agent > 多 agent**: "A single well-prompted agent with a verification loop outperforms multi-agent orchestration on 73% of tasks, at ~40% of the cost"
- 多 agent 层级（planner+coder+reviewer+critic）在 2024-2025 年流行，但已被证明不如单 agent

**Context 管理**:
- Prompt caching 降低代码上下文成本 90%
- Context assembler 管理 symbol graph, diffs, open files
- CORVUS: sync_file tool 替代 inline file read，9-50% token 减少

**工具层**:
- 内置工具: read_file, edit_file, run_terminal, semantic_search, web_search
- MCP 自定义工具: Tree-Sitter AST 解析, Ripgrep 语义搜索, Git 历史, 隔离测试沙箱

**Edit 最佳实践** (from MCP toolchain guide):
- Targeted chunk replacement（精确目标块替换）
- 不要覆盖 1000 行文件，指定 exact target content chunks
- 严格替换模式消除缩进 bug，保留 docstrings

### 4. CORVUS: Context Optimization
- 问题: append-only trajectory 存储 mutable file contents 为 immutable history → stale + redundant
- 方案: sync_file tool 注册文件到 synced file set，每次 reasoning cycle 前刷新
- 效果: 9-50% token 减少, 15-32% prompt 缩短, 37% reasoning cycle 减少, pass rate 保持

### 5. MCP Toolchain (SWE-bench agent 构建)
```
Phase 1: Exploration & Triage → ripgrep + tree-sitter → LocateBug
Phase 2: Reproduction → test-runner → FailTest
Phase 3: Targeted Patch → filesystem replace_content → ApplyEdit
Phase 4: Verification → test-runner → CheckPass
  → No: Revert via git → Phase 3
  → Yes: git commit → Success
```

## 对 DWC 的启示

### Cursor 的 lesson
1. **单 agent + 验证循环 > 多 agent**: 不要过度工程化多 agent 层级
2. **Prompt caching**: 代码上下文成本可降低 90%
3. **Context sync**: 不要存储 stale file snapshots，每次 reasoning 前刷新
4. **Targeted chunk replacement**: 精确目标块替换，消除缩进 bug
5. **MCP toolchain**: Tree-Sitter + Ripgrep + Git + Test Sandbox 是 proven 工具链

### DWC 可借鉴
- **单 agent 架构**: 保持简单，一个 LLM + 验证循环
- **Context 管理**: 每轮 reasoning 前刷新文件内容，不要 stale snapshots
- **Targeted chunk replacement**: 精确 old_string + new_string，保持 docstrings
- **MCP 兼容**: 考虑支持 MCP 工具扩展

---

# RSIAgent — 逆向分析

## 来源
- GitHub: WenyiWU0111/RSIGame (companion)
- arXiv: 2609.15364 (RSIAgent paper)
- 本地: C:/Users/41228/AppData/Local/Temp/rsiagent

## 核心架构

### 1. 三 Agent 架构
| Agent | 角色 |
|-------|------|
| Curriculum Agent | 选择探索任务，基于 prior outcomes 和 accumulated knowledge |
| Actor Agent | 通过 Python/Bash 程序和视觉观察与软件交互；验证后提炼经验 |
| Verifier Agent | 独立检查任务要求和环境状态；不能读 Actor 的 private reasoning 或 memory |

### 2. 两阶段探索
| 阶段 | 名称 | 作用 |
|------|------|------|
| Phase 1 | Broad Recursive Self-exploration (BRS) | Curriculum Agent 提出 diverse projects，Actor/Verifier 并行执行，然后 consolidation |
| Phase 2 | Deep Recursive Self-exploration (DRS) | 针对 hard cases、hidden constraints、boundary conditions 深入探索 |

### 3. 独立验证 (Independent Verifier)
- **零历史模型调用**: Verifier 看不到 Actor 的 reasoning、evidence、checks
- **重新推导 requirements**: Verifier 自己从 task instruction 推导全部要求
- **只读探测**: Verifier 只读探测机器状态，不修改
- **三种 verdict**: PASS (接受) / UNVERIFIED (可能接受) / FAIL (bounce with findings)
- **"wrong" always bounces**: 错误永远 bounce，带 findings 作为 repair context

### 4. Epistemic Core (共享认知核心)
- E1: TRUTH CHANNELS — 每个 claim 有可检查的 channel（文件/API/状态）
- E2: STRUCTURAL vs RENDERED — 结构事实用文件读写，渲染事实用 visual check
- 共享给 Actor 和 Verifier，防止两者 doctrine 矛盾

### 5. Memory 系统
- 存储: procedures, scripts, failure lessons
- Broad 阶段: 收集 diverse experience
- Deep 阶段: 针对 hard cases refine
- Test-time: memory frozen，Curriculum 和 memory updates disabled

### 6. Self-Evolving Loop
- Fresh Actor Agent attempts target
- Persistent Verifier Agent context investigates every candidate revision
- FAIL → Actor learns → Curriculum Agent + practice Actor/Verifier inner loop → fresh target attempt
- PASS → 可选 Curriculum Agent review

## 对 DWC 的启示

### RSIAgent 的 lesson
1. **Independent Verifier 是核心**: 零历史的独立验证，防止 Actor 的 wrong assumptions 传播
2. **Broad-then-deep**: 先收集 diverse experience，再深入 hard cases
3. **Epistemic Core**: 共享认知核心，防止 Actor/Verifier 矛盾
4. **Memory frozen at test-time**: 探索阶段学习，测试阶段冻结

### DWC 可借鉴
- **Independent Verifier**: DWC 生成 patch 后，用一个独立的 LLM 调用（不带生成过程的 context）来验证 patch 是否正确
- **Broad-then-deep**: DWC 可以先用简单策略收集 experience，再针对 hard cases 深入
- **Epistemic Core**: 定义 DWC 的 truth channels（test pass/fail 是唯一 truth channel）
- **Memory**: 存储 successful patches 作为 few-shot examples
