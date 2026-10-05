#!/usr/bin/env bash
# 浅克隆 Lsinxcoy 全部 39 个仓库
set -u
DEST="E:/Divine Wisdom Core/.cache/gh_clones"
mkdir -p "$DEST"
REPOS="ARSI PPTPRO.SKILL SYNTHEX-Autopoiesis-pure PPT.SKILL prometheus-nexus Prometheus-Ultra-MultiTypeKB Prometheus-Ultra Prometheus-Omega-Genesis Prometheus-Omega-Omega Prometheus-Omega Prometheus-Z Prometheus-Y Prometheus-X prometheus-v10 prometheus-v9pro prometheus-v8pro prometheus-v9 prometheus-v4 prometheus-v3 Protogonos prometheus-v5 prometheus prometheus-v8 prometheus-v7 prometheus-v6 CIP-Zhazhazhu CIP-KaoKaoJiang hermes-kanban-cip hermes-collective-intelligence MSTAR-Pro-V4.0 MSTAR-Pro-V4.0-Clean hermes-agent-backup mstar-pro Hermes-MSTAR-V2.0 hermes-agent hermes-scripts hermes-skills hermes-mstar mstar"
ok=0; fail=0; failed=""
for r in $REPOS; do
  t="$DEST/$r"
  if [ -d "$t/.git" ]; then echo "SKIP $r (已存在)"; ok=$((ok+1)); continue; fi
  if git clone --depth 1 --quiet "https://github.com/Lsinxcoy/$r.git" "$t" 2>/dev/null; then
    n=$(find "$t" -type f -not -path "*/.git/*" | wc -l)
    echo "OK   $r  ($n 文件)"
    ok=$((ok+1))
  else
    echo "FAIL $r"
    fail=$((fail+1)); failed="$failed $r"
  fi
done
echo "-----"
echo "成功 $ok / 失败 $fail"
[ -n "$failed" ] && echo "失败列表:$failed"
