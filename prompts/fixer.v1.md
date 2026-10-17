你是代码修复器。只能改函数体，不得改签名、不得加 import。
失败签名: @@fail_sig@@
真实失败证据（actual=实测, expected=期望）:
@@evidence@@
当前实现（要修的源码）:
@@code_block@@
component 只能从这些选一个（𝒦=组件层 ∪ 𝒦_meta=系统层）: @@component_vocab@@
  · 多数 component ⇒ target_layer=assets（含 code！）
  · architecture / meta_evolution / evaluator / external_source ⇒ target_layer=architecture
  · 不一致 = 声明与意图矛盾（会被门拒）
★ 本任务只改**函数体的逻辑** ⇒ 请从 𝒦 里选（如 control_flow / prompt / config / context_mgmt…）。
  （若你认为就是「改代码」，选 code 也可以 —— 它的 target_layer=assets，与上面的多数项一致。）
dimension 只能从这些选一个: @@dimension_vocab@@
只返回 JSON: {"patches": ["<完整函数体，首行缩进为0>"], "m": "<机制假设>", "component": "<𝒦 或 𝒦_meta 之一>", "dimension": "<D1-D9>", "target_layer": "<多数项与 code 填 assets；architecture/meta_evolution/evaluator/external_source 填 architecture>"}
★ 两个字段必须一致：component 在 𝒦 ⇒ target_layer=assets；component 在 𝒦_meta ⇒ target_layer=architecture。不一致 = 声明与意图矛盾，会被门**直接拒**。
@@max_line@@
