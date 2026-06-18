#!/usr/bin/env python3
"""Preflight checks for tag管理系统 online platform access."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Iterable


DEFAULT_HOST = "192.168.10.89"
DEFAULT_PORTS = (8080, 8000, 3000)
ENV_NAMES = (
    "TAG_RESOLVE_BASE_URL",
    "TAG_PLATFORM_BASE_URL",
    "TAG_SYSTEM_BASE_URL",
    "TAG_API_BASE_URL",
    "TAGSYS_BASE_URL",
)


@dataclass
class UrlCheck:
    url: str
    ok: bool
    status: int | None = None
    error: str | None = None
    elapsed_ms: int | None = None


def split_env_urls() -> list[str]:
    values: list[str] = []
    for name in ENV_NAMES:
        raw = os.environ.get(name, "")
        for part in raw.replace("\n", ",").replace(" ", ",").split(","):
            part = part.strip()
            if part:
                values.append(part)
    return values


def normalize_base_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    return url.rstrip("/")


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def candidate_base_urls(host: str, explicit: list[str]) -> list[str]:
    candidates = [normalize_base_url(u) for u in explicit]
    candidates.extend(f"http://{host}:{port}" for port in DEFAULT_PORTS)
    candidates.append(f"http://{host}")
    return unique(candidates)


def ping_host(host: str, timeout: float) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-c", "1", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def tcp_probe(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def url_paths_for(base_url: str) -> list[str]:
    parsed = urllib.parse.urlparse(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1"):
        return ["", "/tags/types", "/master-table/latest-committed", "/dict-versions"]
    return [
        "/",
        "/api/v1/tags/types",
        "/api/v1/master-table/latest-committed",
        "/api/v1/dict-versions",
        "/docs",
    ]


def join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def check_url(url: str, timeout: float) -> UrlCheck:
    start = time.monotonic()
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "tag-resolve-preflight/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            elapsed = int((time.monotonic() - start) * 1000)
            return UrlCheck(url=url, ok=True, status=response.status, elapsed_ms=elapsed)
    except urllib.error.HTTPError as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        # Auth failures still prove that the platform endpoint is reachable.
        return UrlCheck(url=url, ok=exc.code < 500, status=exc.code, error=str(exc), elapsed_ms=elapsed)
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        return UrlCheck(url=url, ok=False, error=type(exc).__name__ + ": " + str(exc), elapsed_ms=elapsed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check tag管理系统 online platform access.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"default host to test, default: {DEFAULT_HOST}")
    parser.add_argument("--base-url", action="append", default=[], help="candidate platform base URL; can be repeated")
    parser.add_argument("--timeout", type=float, default=2.0, help="timeout per probe in seconds")
    parser.add_argument("--require-platform", action="store_true", help="exit non-zero if no HTTP/API endpoint responds")
    args = parser.parse_args()

    explicit_urls = args.base_url + split_env_urls()
    bases = candidate_base_urls(args.host, explicit_urls)
    host_ping = ping_host(args.host, args.timeout)
    tcp_ports = {str(port): tcp_probe(args.host, port, args.timeout) for port in DEFAULT_PORTS}

    checks: list[UrlCheck] = []
    selected_base_url: str | None = None
    for base in bases:
        base_ok = False
        for path in url_paths_for(base):
            check = check_url(join_url(base, path), args.timeout)
            checks.append(check)
            if check.ok:
                base_ok = True
                selected_base_url = base
                break
        if base_ok:
            break

    platform_reachable = selected_base_url is not None
    result = {
        "host": args.host,
        "host_ping": host_ping,
        "tcp_ports": tcp_ports,
        "candidate_base_urls": bases,
        "platform_reachable": platform_reachable,
        "selected_base_url": selected_base_url,
        "checks": [asdict(check) for check in checks],
        "next_step": (
            "Use selected_base_url for tag platform work."
            if platform_reachable
            else "Confirm the tag platform address with the user before online import/sync/export."
        ),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.require_platform and not platform_reachable:
        return 20
    return 0


if __name__ == "__main__":
    sys.exit(main())
