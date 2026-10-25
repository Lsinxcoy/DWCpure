# -*- coding: utf-8 -*-
"""判决性扫描: 每个仓库的进化顺序 —— 先测后落, 还是先落后测?

判据 (机械可查):
  A. mutate → validate → evaluate → apply   (先测后落)  ← 用户设计
  B. mutate → apply → observe/await → decide (先落后测)  ← 影子
  C. 只生成提案, 无 apply                    (不落地)
"""
import io, os, re, json

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "gh_clones")
OUT  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "evolution_order.json")

def read(p):
    try: return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception: return ""

# 关键符号
VALIDATE = re.compile(r'(validate|verif|gate|check|dry_run|dry-run|simulate|replay|screen|compile_gate|passes)', re.I)
APPLY    = re.compile(r'(def apply|\.apply\(|apply_mutation|apply_gene|apply_suggested|write_back|commit_|setattr\(|_apply\()', re.I)
SHADOW   = re.compile(r'(shadow|影子|SHADOW)', re.I)
ROLLBACK = re.compile(r'(rollback|revert|inverse_op|undo)', re.I)
PROPOSAL_ONLY = re.compile(r'(proposal|manifest|suggest|dry_run|plan_only|不落地|只出计划|reviewable artifact)', re.I)
LOOP_ORDER = re.compile(r'(mutate\s*[→\->]+\s*validate|validate\s*[→\->]+\s*evaluate|evaluate\s*[→\->]+\s*apply|'
                        r'mutate.{0,40}validate.{0,40}evaluate.{0,40}apply|'
                        r'mutate.{0,30}apply.{0,30}(observe|await|wait|evaluat))', re.I|re.S)

rows = []
for repo in sorted(os.listdir(ROOT)):
    rp = os.path.join(ROOT, repo)
    if not os.path.isdir(rp): continue
    evo = []
    for dp, dn, fns in os.walk(rp):
        dn[:] = [x for x in dn if x not in ("__pycache__", ".git", "node_modules", ".venv", "venv", "tests")]
        for f in fns:
            if not f.endswith(".py"): continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, rp).replace("\\", "/")
            if not re.search(r'(evolution|evolv|harness|mutator|gene|accept|gates|manifest|rsi)', rel, re.I):
                continue
            evo.append((rel, p))
    if not evo:
        rows.append({"repo": repo, "verdict": "无进化代码", "n": 0}); continue
    blob = {rel: read(p) for rel, p in evo}
    allt = "\n".join(blob.values())

    v_val  = len(VALIDATE.findall(allt))
    v_app  = len(APPLY.findall(allt))
    v_sh   = len(SHADOW.findall(allt))
    v_rb   = len(ROLLBACK.findall(allt))
    v_po   = len(PROPOSAL_ONLY.findall(allt))

    # 顺序证据: 找 "mutate/生成 → validate/验证 → apply" 的三段相邻出现
    seq3 = len(re.findall(r'(mutat\w*|generat\w*|propos\w*)[^\n]{0,200}?(validat\w*|verif\w*|gate\w*|check\w*)[^\n]{0,200}?(apply\w*|commit\w*|promote\w*)', allt, re.I|re.S))
    seq_bad = len(re.findall(r'(apply\w*|commit\w*|promote\w*|setattr\()[^\n]{0,160}?(observe|await|wait|window|shadow|影子)', allt, re.I|re.S))

    verdict = []
    if seq3 > 0: verdict.append("先测后落(有 mutate→validate→apply 序列)")
    if seq_bad > 0: verdict.append("★先落后测(%d 处 apply→observe/window)" % seq_bad)
    if v_sh > 0: verdict.append("含影子符号 %d" % v_sh)
    if v_rb > 0: verdict.append("有回滚 %d" % v_rb)
    if not verdict: verdict.append("未识别")

    rows.append({"repo": repo, "n_files": len(evo),
                 "validate": v_val, "apply": v_app, "shadow": v_sh,
                 "rollback": v_rb, "proposal_only": v_po,
                 "seq_validate_then_apply": seq3, "seq_apply_then_observe": seq_bad,
                 "verdict": " | ".join(verdict)})

print("%-34s %5s %5s %5s %5s %5s %5s  %s" % ("仓库","验证","应用","影子","回滚","测→落","落→观","判定"))
print("-"*140)
for r in rows:
    if r.get("verdict") == "无进化代码":
        print("%-34s   ——— 无进化代码" % r["repo"]); continue
    print("%-34s %5d %5d %5d %5d %5d %5d  %s" % (
        r["repo"][:34], r["validate"], r["apply"], r["shadow"], r["rollback"],
        r["seq_validate_then_apply"], r["seq_apply_then_observe"], r["verdict"][:80]))

json.dump(rows, io.open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已存:", OUT)
