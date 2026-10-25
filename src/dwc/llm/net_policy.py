"""P1 · 出站 URL 策略（SSRF 第一道门）。

★ 这不是完整 SSRF 防御：DNS 解析与实际连接之间仍有 TOCTOU。
  生产更强做法是把解析结果钉到 IP + Host 头，或用代理白名单；
  当前先封 loopback/私网/link-local/元数据地址，并禁止自动重定向。
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.request
from urllib.parse import urlsplit


class EgressDenied(Exception):
    """URL 不允许出站。"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """拒绝自动跟随；需要跳转时由调用方重新 check_url。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_url(url: str, *, allow_hosts: tuple[str, ...] = ()) -> str:
    """校验 scheme/host/userinfo/DNS 结果；返回原 URL。"""
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        raise EgressDenied("只允许 http/https")
    if p.username or p.password:
        raise EgressDenied("URL 不允许 userinfo")
    host = p.hostname
    if not host:
        raise EgressDenied("URL 缺 host")
    if host.lower() in {h.lower() for h in allow_hosts}:
        return url
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as e:
        raise EgressDenied("DNS 解析失败: %s" % e) from e
    if not infos:
        raise EgressDenied("DNS 无结果")
    for _family, _type, _proto, _canon, sockaddr in infos:
        raw = str(sockaddr[0]).split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError as e:
            raise EgressDenied("无法解析 IP: %s" % raw) from e
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            raise EgressDenied("禁止私网/loopback/link-local: %s" % ip)
    return url
