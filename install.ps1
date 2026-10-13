# ============================================================
# DWC · Windows 一键安装（R228 — 头部 agent 惯例: 一条命令）
#   用法: powershell -ExecutionPolicy Bypass -File install.ps1
#   做四件事: venv → 依赖 → 目录初始化 → 冒烟（不碰你的任何配置）
# ============================================================
$ErrorActionPreference = "Stop"

# ===== bootstrap（R250）: 支持一条命令安装, 免手动 clone =====
#   irm https://raw.githubusercontent.com/Lsinxcoy/divine-wisdom-core/master/install.ps1 | iex
#   -File 模式: 当前目录即仓库 ⇒ 用脚本所在目录;
#   iex 模式 : 无脚本路径 ⇒ 自动 clone/pull 到 %USERPROFILE%\.dwc
$RepoUrl = "https://github.com/Lsinxcoy/divine-wisdom-core.git"
$Dest    = Join-Path $env:USERPROFILE ".dwc"
$Self    = $MyInvocation.MyCommand.Path
if ($Self) {
    $Dir0 = Split-Path -Parent $Self
    if (Test-Path (Join-Path $Dir0 "pyproject.toml")) { $Root = $Dir0 }
}
if (-not $Root) {
    if (-not (Test-Path (Join-Path $Dest "pyproject.toml"))) {
        Write-Host "克隆仓库到 $Dest ..."
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Host "需要 git（未找到 git 命令）— 安装 git 后重试: https://git-scm.com" -ForegroundColor Red
            exit 1
        }
        git clone $RepoUrl $Dest
        if ($LASTEXITCODE -ne 0) { Write-Host "clone 失败" -ForegroundColor Red; exit 1 }
    } else {
        Write-Host "已存在 $Dest — 拉取最新..."
        git -C $Dest pull --ff-only
        if ($LASTEXITCODE -ne 0) { Write-Host "pull 失败（本地改动?）" -ForegroundColor Yellow }
    }
    $Root = $Dest
}
# ===== bootstrap 结束 =====

Write-Host "== DWC 安装 ==" -ForegroundColor Cyan
Write-Host "仓库根: $Root"

# ① venv（仓库内 .venv — 不污染系统 Python）
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "[1/4] 创建虚拟环境..."
    $SysPy = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $SysPy) { Write-Host "需要 Python 3.11+（未找到 python 命令）" -ForegroundColor Red; exit 1 }
    & $SysPy -m venv (Join-Path $Root ".venv")
} else { Write-Host "[1/4] venv 已存在 ✓" }

# ② 依赖
Write-Host "[2/4] 安装依赖..."
& $Py -m pip install -q -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Host "依赖安装失败" -ForegroundColor Red; exit 1 }

# ②b 注册 dwc 命令（console_scripts — venv 内 dwc 直接可用, R235）
Write-Host "注册 dwc 命令..."
& $Py -m pip install -q -e $Root
if ($LASTEXITCODE -ne 0) { Write-Host "dwc 命令注册失败" -ForegroundColor Red; exit 1 }

# ③ 目录初始化（运行时区; 已有不动）
Write-Host "[3/4] 初始化运行时目录..."
foreach ($d in @("var\inbox_work", "var\dwc_reports", "var\dwc_sessions",
                 "var\dwc_ask", "var\backup")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}
Copy-Item (Join-Path $Root "config\anchors\dev.json") (Join-Path $Root "var\backup\dev_seed.json") -Force -ErrorAction SilentlyContinue

# ④ 冒烟（不触网不花钱: 模块导入 + 根发现 + 配置校验器）
Write-Host "[4/4] 冒烟自检..."
$env:DWC_ROOT = $Root
& $Py -c "import sys; sys.path.insert(0, r'$Root\src'); from dwc.foundation.paths import find_root; print('  根发现:', find_root()); from dwc.foundation import dial_config; dial_config.load_world_tree(); dial_config.load_drift(); print('  配置校验器: OK'); from dwc.llm import task_exec; print('  执行器: OK')"
if ($LASTEXITCODE -ne 0) { Write-Host "冒烟失败 — 请把上面报错发给维护者" -ForegroundColor Red; exit 1 }

# ⑤ dwc 命令进用户 PATH（.local/bin — 跨工具惯例目录; 无则建）
$BinDir = Join-Path $env:USERPROFILE ".local\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
Set-Content -Path (Join-Path $BinDir "dwc.cmd") -Encoding ascii `
    -Value "@echo off`r`n`"$Py`" -m dwc.cli_main %*"
$shim = Join-Path $BinDir "dwc"
Set-Content -Path $shim -Encoding utf8 -Value "#!/bin/sh`nexec `"$Py`" -m dvwc.cli_main `"$@`"".Replace("dvwc", "dwc")
$up = [Environment]::GetEnvironmentVariable("Path", "User")
if ($up -notlike "*$BinDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$up;$BinDir", "User")
    Write-Host "已把 $BinDir 加入用户 PATH（重开终端生效）"
}

Write-Host ""
Write-Host "== 安装完成 ==" -ForegroundColor Green
Write-Host "下一步（首次配置向导, 交互式设置 LLM 端点）:"
Write-Host "  dwc setup"
Write-Host "之后:"
Write-Host "  dwc          # 交互界面（重开终端生效）"
Write-Host "  dwc start --llm   # 常驻 agent"
Write-Host "  dwc update   # 从 GitHub 更新"
