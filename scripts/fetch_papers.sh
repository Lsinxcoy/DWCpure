#!/usr/bin/env bash
# DWC · 论文全文抓取 v2 (2026-10-02)
#
# v1 的教训 (记录在此, 防止重犯):
#   ar5iv.labs.arxiv.org 对多数论文只返回 ~4.8KB 的摘要页,
#   看着"抓到了"实则没有正文 —— 那是"有文件但无全文"的假成功。
#   正确路径: arxiv.org/html/<id>  (LaTeX 官方 HTML 渲染)
#   ar5iv 实测: 2609.04128 → 4,663 字符(摘要页)
#             arxiv/html → 47,001 字符(全文)
#
# 判据: 纯文本 < 40000 字符 = 不是全文, 记为 PARTIAL
set -u
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
OUT="$(dirname "$0")/../papers"
mkdir -p "$OUT"

IDS="2609.13406 2609.24972 2609.26457 2603.25111 2607.12790 \
2609.14858 2609.14857 2609.11873 2609.08183 2609.06396 \
2609.04128 2608.24876 2608.10299 2607.27924 2607.27201 \
2606.14249 2606.09498 2603.06333 2505.05522"

for id in $IDS; do
  f="$OUT/$id.html"
  # 已有且够大就跳过
  if [ -s "$f" ]; then
    sz=$(wc -c < "$f")
    if [ "$sz" -gt 120000 ]; then echo "SKIP  $id (已有 ${sz}B)"; continue; fi
  fi
  curl -sL --max-time 55 -A "$UA" "https://arxiv.org/html/$id" -o "$f" 2>/dev/null
  sz=$(wc -c < "$f" 2>/dev/null || echo 0)
  if [ "$sz" -lt 60000 ]; then
    # arxiv/html 也没有 (老论文无 HTML 渲染) → 只存摘要页, 明确标记
    curl -sL --max-time 40 -A "$UA" "https://arxiv.org/abs/$id" -o "$f" 2>/dev/null
    echo "PARTIAL $id (无全文渲染, 仅摘要 ${sz}B)"
  else
    echo "OK     $id ${sz}B"
  fi
  sleep 1
done
echo "--- DONE ---"