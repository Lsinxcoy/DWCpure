#!/usr/bin/env bash
# ============================================================
# DWC · macOS/Linux/WSL 一键安装（R228）
#   用法: bash install.sh
# ============================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "== DWC 安装 =="
echo "仓库根: $ROOT"

# ① venv
PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "[1/4] 创建虚拟环境..."
  "${PYTHON:-python3}" -m venv "$ROOT/.venv"
else
  echo "[1/4] venv 已存在 ✓"
fi

# ② 依赖
echo "[2/4] 安装依赖..."
"$PY" -m pip install -q -r "$ROOT/requirements.txt"

# ②b 注册 dwc 命令（console_scripts — R235）
echo "注册 dwc 命令..."
"$PY" -m pip install -q -e "$ROOT"

# ③ 目录
echo "[3/4] 初始化运行时目录..."
mkdir -p "$ROOT"/var/inbox_work "$ROOT"/var/dwc_reports "$ROOT"/var/dwc_sessions \
         "$ROOT"/var/dwc_ask "$ROOT"/var/backup
cp "$ROOT/config/anchors/dev.json" "$ROOT/var/backup/dev_seed.json" 2>/dev/null || true

# ④ 冒烟
echo "[4/4] 冒烟自检..."
export DWC_ROOT="$ROOT"
"$PY" - <<'PYEOF'
import sys
sys.path.insert(0, __import__("os").environ["DWC_ROOT"] + "/src")
from dwc.foundation.paths import find_root
print("  根发现:", find_root())
from dwc.foundation import dial_config
dial_config.load_world_tree(); dial_config.load_drift()
print("  配置校验器: OK")
from dwc.llm import task_exec
print("  执行器: OK")
PYEOF

echo ""
echo "== 安装完成 =="
echo "首次配置向导:  dwc setup"
echo "自检:          $PY $ROOT/scripts/dwc_cli.py doctor"
echo "交互界面:      $PY $ROOT/scripts/dwc_chat.py"
echo "常驻 agent:    $PY $ROOT/scripts/dwc_agent.py --llm"
