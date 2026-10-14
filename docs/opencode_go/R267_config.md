# DWC LLM · OpenCode Go 接入说明（R267）

## 已知更新（2026-10-12 opencode.ai/docs/go/）

OpenCode Go 服务针对客户端的要求（R267 实测探测）:

1. **协议**
   - 仅 `/chat/completions` 与 `/responses`、`/messages` 三种端点；模型与 protocol 固定匹配:
     - `gpt-*` / `grok-*` / `muse-spark*` ⇒ `/responses` (codex_responses)
     - `minimax-*` / `qwen*` / `anthropic` ⇒ `/messages` (anthropic_messages)
     - 其他 ⇒ `/chat/completions`（我们 DWC 现只支持 chat/completions；请选以上 falling-through 模型）
2. **客户端身份**
   - urllib 默认 UA `(python-urllib/…)` 被 Cloudflare 1010 拒绝
   - ⇒ 必须发自定义 User-Agent，例如 `Divine-Wisdom-Core/1.0 (+dwccore)`
3. **会话亲和**
   - 缺失 `x-opencode-session` ⇒ `400 MissingSessionID`
   - ⇒ 每个 `LLMClient` 实例挂 stable id `dwc-<hex>` (已在 client 内实现)
4. **Base URL**
   - `https://opencode.ai/inference/go/v1` (新 canonical, /zen/go/v1 仍可用)
   - OpenCode Go model list: https://opencode.ai/inference/go/v1/models
5. **Key**
   - console 生成 (oc_sk_… 即 `.env` `OPENCODE_GO_API_KEY`)
   - DWC 取值优先级 (不可变): 显式参数 > env `DWC_LLM_*` > `config/llm.json`
6. **模型-协议映射**
   - thinking 模型（deepseek-v4-flash / muse-spark） reasoning_content 优先 / content fallback.
   - DWC client 在空 content 时回退 reasoning_content (stream included).

## 配置示例 (config/llm.json)

```json
{
  "base_url": "https://opencode.ai/inference/go/v1",
  "api_key": "oc_sk_...",
  "model": "cat-jam-free",
  "timeout": 60
}
```

env variant:
```
DWC_LLM_BASE_URL=https://opencode.ai/inference/go/v1
DWC_LLM_API_KEY=oc_sk_...
DWC_LLM_MODEL=cat-jam-free
```

## 注意
- DWC client 仅支持 chat/completions；选 model 看 endpoint 表；选 `/responses` 或 `/messages` 模型将返回不匹 (protocol mis-support)。
- 已知 thinking 模型 max_tokens 为 256+ (probe 8 → 256 fixed)。
