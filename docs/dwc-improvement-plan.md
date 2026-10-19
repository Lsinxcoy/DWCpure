# DWC Agent 改进方案

## 基于 Claude Code + DeepSeek (mini-SWE-agent) + Hermes 三方逆向分析

## 当前状态
- 通过率: 20% (1/5 pytest instances)
- 架构: 硬编码文件路径 + 硬编码 fix + 字符串替换 + 无迭代

## 改进目标
- 通过率: 20% → 40%+ (仅靠架构改进，不换模型)
- 模型: 可配置 (环境变量 DWC_LLM_MODEL)

## 改进方案

### Phase 1: LLM 驱动 + 迭代重试（核心）

**1.1 移除所有硬编码**
- 删除硬编码 rewrite.py 路径
- 删除硬编码 docstring fix
- 删除所有 fallback 逻辑

**1.2 LLM 驱动文件定位**
- 给 LLM 问题描述 + 文件列表
- LLM 输出需要读取的文件路径
- LLM 读取文件后，自主决定修改哪些

**1.3 LLM 驱动 Patch 生成**
- LLM 输出 old_string + new_string（或 unified diff）
- 工具只做 apply + test，不做智能判断

**1.4 迭代循环**
```
for attempt in range(3):
    patch = llm.generate(issue, files, previous_error)
    if apply(patch):
        if test_passed(patch):
            return success
        else:
            previous_error = test_output  # 喂回 LLM
    else:
        previous_error = apply_error  # 喂回 LLM
return failure
```

### Phase 2: 短上下文 + Fuzzy Matching

**2.1 短上下文步骤**
- 每步只给 LLM 需要的文件内容（< 4000 字符/文件）
- 不给整个 repo，只给相关文件

**2.2 Fuzzy Matching**
- 借鉴 Hermes patch 工具的 9 种策略
- 处理空白/缩进差异
- 提高 patch 应用成功率

**2.3 语法检查**
- Patch 应用后自动运行 py_compile
- 失败时把语法错误喂回 LLM

### Phase 3: 可配置 + 可扩展

**3.1 模型可配置**
- `DWC_LLM_MODEL` 环境变量
- `DWC_LLM_API_URL` 环境变量
- 默认: minimax-m2.5 (免费/低成本)

**3.2 评测 harness**
- 已有: scripts/dwc_benchmark_adapter.py (py38 + P2P suspect)
- 需要: 批量运行 + 报告生成

## 实现优先级
1. P0: 迭代循环 + LLM 驱动（通过率 20% → 40%）
2. P1: Fuzzy matching + 语法检查（40% → 50%）
3. P2: 可配置模型 + 评测 harness（长期）

## 参考
- Claude Code: LLM-driven, tool-dumb, iterative retry
- DeepSeek (mini-SWE-agent): short-context decomposition, 70% on SWE-bench Verified
- Hermes: fuzzy matching (9 strategies), syntax check after edit
