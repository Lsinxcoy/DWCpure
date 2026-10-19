# -*- coding: utf-8 -*-
"""9-layer fuzzy matching for patch application (OpenCode/Hermes pattern)."""
import re


def _simple(content, search):
    if search in content:
        return search
    unescaped = search.replace("\\n", "\n").replace("\\t", "\t")
    if unescaped in content:
        return unescaped
    return None


def _line_trimmed(content, search):
    search_lines = [l.strip() for l in search.splitlines()]
    content_lines = content.splitlines()
    if not search_lines:
        return None
    for i in range(len(content_lines) - len(search_lines) + 1):
        window = [l.strip() for l in content_lines[i:i+len(search_lines)]]
        if window == search_lines:
            return "\n".join(content_lines[i:i+len(search_lines)])
    return None


def _block_anchor(content, search):
    search_lines = search.splitlines()
    if len(search_lines) < 2:
        return None
    first = search_lines[0].strip()
    last = search_lines[-1].strip()
    content_lines = content.splitlines()
    for i in range(len(content_lines)):
        if content_lines[i].strip() == first:
            for j in range(i + 1, len(content_lines)):
                if content_lines[j].strip() == last:
                    middle_search = search_lines[1:-1]
                    middle_content = content_lines[i+1:j]
                    if len(middle_search) == 0:
                        return "\n".join(content_lines[i:j+1])
                    matches = sum(1 for a, b in zip(middle_search, middle_content)
                                 if a.strip() == b.strip())
                    if matches >= len(middle_search) * 0.5:
                        return "\n".join(content_lines[i:j+1])
    return None


def _whitespace_normalized(content, search):
    def normalize(s):
        return re.sub(r'[ \t]+', ' ', s)
    search_norm = normalize(search)
    content_lines = content.splitlines()
    search_lines = search.splitlines()
    if not search_lines:
        return None
    for i in range(len(content_lines) - len(search_lines) + 1):
        window = "\n".join(normalize(l) for l in content_lines[i:i+len(search_lines)])
        if window == search_norm:
            return "\n".join(content_lines[i:i+len(search_lines)])
    return None


def _indentation_flexible(content, search):
    search_lines = search.splitlines()
    content_lines = content.splitlines()
    if not search_lines:
        return None
    search_stripped = [l.lstrip() for l in search_lines]
    for i in range(len(content_lines) - len(search_lines) + 1):
        window_stripped = [l.lstrip() for l in content_lines[i:i+len(search_lines)]]
        if window_stripped == search_stripped:
            return "\n".join(content_lines[i:i+len(search_lines)])
    return None


def _escape_normalized(content, search):
    unescaped = search.replace("\\\\n", "\n").replace("\\\\t", "\t").replace("\\\\\"", "\"")
    if unescaped in content:
        return unescaped
    return None


def _trimmed_boundary(content, search):
    search_trimmed = search.strip()
    if not search_trimmed:
        return None
    idx = content.find(search_trimmed)
    if idx != -1:
        return content[idx:idx+len(search_trimmed)]
    return None


def _context_aware(content, search):
    search_lines = search.splitlines()
    content_lines = content.splitlines()
    if len(search_lines) < 3:
        return None
    best_score = 0
    best_start = -1
    for i in range(len(content_lines) - len(search_lines) + 1):
        matches = sum(1 for a, b in zip(search_lines, content_lines[i:i+len(search_lines)])
                     if a.strip() == b.strip())
        score = matches / len(search_lines)
        if score > best_score and score >= 0.5:
            best_score = score
            best_start = i
    if best_start != -1:
        return "\n".join(content_lines[best_start:best_start+len(search_lines)])
    return None


def _multi_occurrence(content, search):
    count = content.count(search)
    if count >= 1:
        return search
    return None


REPLACERS = [
    _simple,
    _line_trimmed,
    _block_anchor,
    _whitespace_normalized,
    _indentation_flexible,
    _escape_normalized,
    _trimmed_boundary,
    _context_aware,
    _multi_occurrence,
]


def _aligned(content, actual):
    """匹配是否整行对齐（允许跳过行首缩进，但拒绝行内片段）。

    ★ Phase C 实测：LLM 给出行内片段（如 `for name, new in`）时，
      `search in content` 会命中，替换后残留后半行
      ⇒ `setattr(...) enumerate(field):` 这类 invalid syntax。
      行对齐检查把这类匹配挡在落地之前，让 LLM 拿到明确反馈重试。
    """
    idx = content.find(actual)
    if idx == -1:
        return False
    start, end = idx, idx + len(actual)
    if start > 0 and content[start - 1] != "\n":
        ls = content.rfind("\n", 0, start) + 1
        if content[ls:start].strip():        # 前面还有代码 ⇒ 行内片段
            return False
    if end < len(content) and content[end] != "\n":
        le = content.find("\n", end)
        if le == -1:
            le = len(content)
        if content[end:le].strip():          # 后面还有代码 ⇒ 行内片段
            return False
    return True


def find_actual_string(content, search, require_line_aligned=False):
    """Try all 9 replacers in order. Return actual string found in content, or None.

    require_line_aligned=True 时跳过所有行内片段匹配（默认 False 保持旧行为）。
    """
    for replacer in REPLACERS:
        result = replacer(content, search)
        if result is None:
            continue
        if require_line_aligned and not _aligned(content, result):
            continue
        return result
    return None


def _indent_of(line):
    """返回一行的前导空白。"""
    return line[:len(line) - len(line.lstrip())]


def reindent_to_match(actual, new_str):
    """把 new_str 的基准缩进对齐到 actual 的基准缩进。

    ★ 为什么需要：`_indentation_flexible` 能在缩进不同的情况下找到 old_string，
      但替换时若把 new_str 原样插入，块内相对缩进保留、基准缩进却错位
      ⇒ IndentationError（Phase C 实测：5103 rewrite.py:739 / 5221 fixtures.py:57）。

    规则:
      · 首个非空行的缩进差 = delta，非空行统一平移 delta
      · 行缩进比 new_str 基准更浅的行保持原样（不硬改，交给语法检查兜底）
      · 空行原样保留
    """
    if not actual or not new_str:
        return new_str
    a_line = next((l for l in actual.splitlines() if l.strip()), "")
    n_line = next((l for l in new_str.splitlines() if l.strip()), "")
    if not a_line or not n_line:
        return new_str
    a_ind, n_ind = _indent_of(a_line), _indent_of(n_line)
    if a_ind == n_ind:
        return new_str

    out = []
    for line in new_str.splitlines():
        if not line.strip():
            out.append(line)
        elif line.startswith(n_ind):
            out.append(a_ind + line[len(n_ind):])
        else:
            out.append(line)
    return "\n".join(out)


def apply_replacement(content, old_str, new_str, replace_all=False):
    """Apply replacement using found actual string. Returns (new_content, msg).

    ★ 只接受整行对齐的匹配：行内片段会污染后续代码（Phase C 实测两类
      invalid syntax 都源于此）。找不到对齐匹配 ⇒ 明确报错让 LLM 重试。
    """
    actual = find_actual_string(content, old_str, require_line_aligned=True)
    if actual is None:
        return None, ("old_string 未找到整行对齐的匹配（9 层匹配器均失败，"
                      "或只命中行内片段）— 请提供完整整行内容，含首尾行")
    count = content.count(actual)
    if count > 1 and not replace_all:
        return None, f"old_string found {count} times; provide more context"
    new_final = reindent_to_match(actual, new_str)
    if replace_all:
        new_content = content.replace(actual, new_final)
    else:
        new_content = content.replace(actual, new_final, 1)
    return new_content, "ok"
