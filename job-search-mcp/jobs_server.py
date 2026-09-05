#!/usr/bin/env python3
"""
Job Search MCP server.

Connects Claude (Claude Code or Claude Desktop) to live job listings so you can
search and browse openings from inside a conversation.

Why not LinkedIn directly? LinkedIn has no open jobs API, and scraping it breaks
their terms of service (and has been litigated). This server uses Adzuna instead:
a real, free, legal API that aggregates listings from many job boards. Most roles
that appear on LinkedIn also show up here, without the ban or legal risk.

The server speaks the Model Context Protocol over stdio using only the Python
standard library. No pip install. Requires Python 3.8+.

Setup:
  1. Get free credentials at https://developer.adzuna.com (register an app).
  2. Set two environment variables:
       ADZUNA_APP_ID
       ADZUNA_APP_KEY
  3. Point Claude at this file (see README.md for the exact config).

Self-test (no credentials or network needed):
  python3 jobs_server.py --selftest
"""

import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

SERVER_NAME = "job-search"
SERVER_VERSION = "1.0.0"

# Protocol version we advertise if the client doesn't send one. When the client
# does send one, we echo it back for maximum compatibility.
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"

# Country codes Adzuna supports. Kept here so we can reject typos early with a
# helpful message instead of a confusing HTTP error.
SUPPORTED_COUNTRIES = {
    "gb", "us", "at", "au", "be", "br", "ca", "ch", "de", "es", "fr",
    "in", "it", "mx", "nl", "nz", "pl", "sg", "za",
}

DEFAULT_COUNTRY = "us"
DEFAULT_RESULTS = 10
MAX_RESULTS = 50
HTTP_TIMEOUT_SECONDS = 20

# Adzuna accepts these sort_by values.
SORT_OPTIONS = {"relevance", "date", "salary"}


# ----------------------------------------------------------------------------
# Tool definition (advertised to the client via tools/list)
# ----------------------------------------------------------------------------

SEARCH_JOBS_TOOL = {
    "name": "search_jobs",
    "description": (
        "Search current job openings by keyword and location. Backed by the "
        "Adzuna API, which aggregates listings from many job boards (a legal "
        "alternative to scraping LinkedIn). Returns title, company, location, "
        "salary when known, posting date, a short description, and an apply link."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "what": {
                "type": "string",
                "description": "Keywords or job title, e.g. 'senior product designer'.",
            },
            "where": {
                "type": "string",
                "description": "Location, e.g. 'San Francisco', 'remote', 'London'.",
            },
            "country": {
                "type": "string",
                "description": (
                    "Two-letter country code for the market to search. "
                    "Default 'us'. Supported: "
                    + ", ".join(sorted(SUPPORTED_COUNTRIES))
                    + "."
                ),
            },
            "results": {
                "type": "integer",
                "description": f"How many jobs to return (1-{MAX_RESULTS}). Default {DEFAULT_RESULTS}.",
            },
            "salary_min": {
                "type": "integer",
                "description": "Only jobs paying at least this amount (in the market's currency).",
            },
            "max_days_old": {
                "type": "integer",
                "description": "Only jobs posted within this many days.",
            },
            "full_time": {
                "type": "boolean",
                "description": "If true, restrict to full-time roles.",
            },
            "sort_by": {
                "type": "string",
                "enum": sorted(SORT_OPTIONS),
                "description": "Ordering: 'relevance' (default), 'date' (newest first), or 'salary'.",
            },
        },
        "required": ["what"],
    },
}


# ----------------------------------------------------------------------------
# Adzuna call + formatting
# ----------------------------------------------------------------------------


def _credentials():
    """Return (app_id, app_key) or raise a clear error if they're missing."""
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        raise RuntimeError(
            "Missing Adzuna credentials. Get free ones at "
            "https://developer.adzuna.com and set ADZUNA_APP_ID and "
            "ADZUNA_APP_KEY in the server's environment (see README.md)."
        )
    return app_id, app_key


def build_request_url(args, app_id, app_key):
    """Build the full Adzuna search URL from tool arguments.

    Kept separate from the HTTP call so it can be unit-tested without network.
    """
    what = (args.get("what") or "").strip()
    if not what:
        raise ValueError("'what' (keywords or job title) is required.")

    country = (args.get("country") or DEFAULT_COUNTRY).strip().lower()
    if country not in SUPPORTED_COUNTRIES:
        raise ValueError(
            f"Unsupported country '{country}'. Supported: "
            + ", ".join(sorted(SUPPORTED_COUNTRIES))
            + "."
        )

    try:
        results = int(args.get("results", DEFAULT_RESULTS))
    except (TypeError, ValueError):
        results = DEFAULT_RESULTS
    results = max(1, min(MAX_RESULTS, results))

    query = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results,
        "what": what,
        "content-type": "application/json",
    }

    where = (args.get("where") or "").strip()
    if where:
        query["where"] = where

    if args.get("salary_min") is not None:
        try:
            query["salary_min"] = int(args["salary_min"])
        except (TypeError, ValueError):
            pass

    if args.get("max_days_old") is not None:
        try:
            query["max_days_old"] = int(args["max_days_old"])
        except (TypeError, ValueError):
            pass

    if args.get("full_time"):
        query["full_time"] = 1

    sort_by = (args.get("sort_by") or "").strip().lower()
    if sort_by in SORT_OPTIONS:
        # Adzuna uses 'relevance' implicitly; only send an explicit override.
        if sort_by != "relevance":
            query["sort_by"] = sort_by

    # Page 1. Country goes in the path, not the query string.
    path = f"{ADZUNA_BASE}/{country}/search/1"
    return path + "?" + urllib.parse.urlencode(query)


def fetch_jobs(args):
    """Call Adzuna and return the parsed JSON dict."""
    app_id, app_key = _credentials()
    url = build_request_url(args, app_id, app_key)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        if e.code in (401, 403):
            raise RuntimeError(
                "Adzuna rejected the credentials (HTTP "
                f"{e.code}). Check ADZUNA_APP_ID and ADZUNA_APP_KEY. {detail}".strip()
            )
        raise RuntimeError(f"Adzuna request failed (HTTP {e.code}). {detail}".strip())
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Adzuna: {e.reason}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("Adzuna returned a response that wasn't valid JSON.")


def _clean(text):
    """Collapse whitespace and trim a description snippet."""
    if not text:
        return ""
    return " ".join(str(text).split())


def _salary(job):
    lo = job.get("salary_min")
    hi = job.get("salary_max")

    def fmt(n):
        try:
            return f"{int(n):,}"
        except (TypeError, ValueError):
            return None

    lo_s, hi_s = fmt(lo), fmt(hi)
    if lo_s and hi_s and lo_s != hi_s:
        base = f"{lo_s}-{hi_s}"
    elif lo_s or hi_s:
        base = lo_s or hi_s
    else:
        return None
    if job.get("salary_is_predicted") in (1, "1", True):
        base += " (estimated)"
    return base


def format_results(data, args):
    """Turn Adzuna JSON into a readable text block for the model."""
    results = data.get("results") or []
    total = data.get("count")

    what = (args.get("what") or "").strip()
    where = (args.get("where") or "").strip()
    scope = f"'{what}'"
    if where:
        scope += f" in {where}"

    if not results:
        return f"No job listings found for {scope}. Try broader keywords or a different location."

    lines = []
    header = f"Found {len(results)} job listings for {scope}"
    if isinstance(total, int) and total > len(results):
        header += f" (of ~{total:,} total matches)"
    lines.append(header + ":\n")

    for i, job in enumerate(results, 1):
        title = _clean(job.get("title")) or "(untitled role)"
        company = _clean((job.get("company") or {}).get("display_name")) or "Unknown company"
        location = _clean((job.get("location") or {}).get("display_name"))
        created = (job.get("created") or "")[:10]
        url = job.get("redirect_url") or ""
        salary = _salary(job)
        desc = _clean(job.get("description"))
        if len(desc) > 240:
            desc = desc[:240].rstrip() + "..."

        lines.append(f"{i}. {title} - {company}")
        meta = []
        if location:
            meta.append(location)
        if salary:
            meta.append(f"salary {salary}")
        if created:
            meta.append(f"posted {created}")
        if meta:
            lines.append("   " + " | ".join(meta))
        if desc:
            lines.append(f"   {desc}")
        if url:
            lines.append(f"   Apply: {url}")
        lines.append("")

    return "\n".join(lines).rstrip()


def run_search(args):
    """High-level: fetch and format. Returns a text string."""
    data = fetch_jobs(args)
    return format_results(data, args)


# ----------------------------------------------------------------------------
# Minimal JSON-RPC / MCP stdio plumbing
# ----------------------------------------------------------------------------


def _send(message):
    """Write a single JSON-RPC message as one line to stdout."""
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _result(req_id, result):
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def handle_request(msg):
    """Dispatch a single parsed JSON-RPC message.

    Notifications (no 'id') never get a response. Requests always do.
    """
    method = msg.get("method")
    req_id = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        params = msg.get("params") or {}
        protocol_version = params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION
        _result(
            req_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
        return

    if method == "notifications/initialized":
        return  # notification, no reply

    if method == "ping":
        if not is_notification:
            _result(req_id, {})
        return

    if method == "tools/list":
        _result(req_id, {"tools": [SEARCH_JOBS_TOOL]})
        return

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        if name != "search_jobs":
            _result(
                req_id,
                {
                    "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True,
                },
            )
            return
        try:
            text = run_search(args)
            _result(req_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:
            # Tool-level failures come back as content with isError, so the model
            # sees the message and can relay it, rather than a protocol crash.
            _result(
                req_id,
                {"content": [{"type": "text", "text": str(e)}], "isError": True},
            )
        return

    # Unknown method: error for requests, silence for notifications.
    if not is_notification:
        _error(req_id, -32601, f"Method not found: {method}")


def serve():
    """Read newline-delimited JSON-RPC from stdin until EOF."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _error(None, -32700, "Parse error")
            continue
        try:
            handle_request(msg)
        except Exception as e:
            # Last-resort guard so one bad message can't kill the server.
            if "id" in msg:
                _error(msg.get("id"), -32603, f"Internal error: {e}")


# ----------------------------------------------------------------------------
# Self-test (no network, no credentials)
# ----------------------------------------------------------------------------


def selftest():
    """Exercise protocol handling, URL building, and formatting offline."""
    failures = []

    def check(label, cond):
        status = "ok" if cond else "FAIL"
        print(f"  [{status}] {label}")
        if not cond:
            failures.append(label)

    print("URL building:")
    url = build_request_url(
        {
            "what": "product designer",
            "where": "remote",
            "country": "us",
            "results": 5,
            "salary_min": 120000,
            "full_time": True,
            "sort_by": "date",
            "max_days_old": 14,
        },
        "TESTID",
        "TESTKEY",
    )
    check("path has country and search segment", "/jobs/us/search/1?" in url)
    check("app_id present", "app_id=TESTID" in url)
    check("app_key present", "app_key=TESTKEY" in url)
    check("what url-encoded", "what=product+designer" in url)
    check("where present", "where=remote" in url)
    check("results_per_page=5", "results_per_page=5" in url)
    check("salary_min passed", "salary_min=120000" in url)
    check("full_time passed", "full_time=1" in url)
    check("sort_by=date passed", "sort_by=date" in url)
    check("max_days_old passed", "max_days_old=14" in url)

    # results clamps to the max
    url2 = build_request_url({"what": "x", "results": 999}, "a", "b")
    check("results clamped to max", f"results_per_page={MAX_RESULTS}" in url2)

    # relevance is implicit, not sent
    url3 = build_request_url({"what": "x", "sort_by": "relevance"}, "a", "b")
    check("relevance sort not sent explicitly", "sort_by=" not in url3)

    print("Validation:")
    try:
        build_request_url({"what": "x", "country": "zz"}, "a", "b")
        check("bad country rejected", False)
    except ValueError:
        check("bad country rejected", True)
    try:
        build_request_url({"what": "   "}, "a", "b")
        check("empty what rejected", False)
    except ValueError:
        check("empty what rejected", True)

    print("Result formatting:")
    sample = {
        "count": 812,
        "results": [
            {
                "title": "Senior Product Designer",
                "company": {"display_name": "Acme Inc"},
                "location": {"display_name": "San Francisco, CA"},
                "salary_min": 150000,
                "salary_max": 190000,
                "created": "2026-08-30T09:00:00Z",
                "redirect_url": "https://example.com/job/1",
                "description": "  Design   things.   " * 40,
            }
        ],
    }
    text = format_results(sample, {"what": "product designer", "where": "SF"})
    check("header shows total", "812" in text)
    check("title rendered", "Senior Product Designer" in text)
    check("company rendered", "Acme Inc" in text)
    check("salary range rendered", "150,000-190,000" in text)
    check("apply link rendered", "https://example.com/job/1" in text)
    check("long description truncated", "..." in text)

    empty = format_results({"count": 0, "results": []}, {"what": "nope"})
    check("empty results handled", "No job listings found" in empty)

    print("Protocol handling:")
    captured = []
    global _send
    original_send = _send
    _send = lambda m: captured.append(m)  # noqa: E731
    try:
        handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18"}})
        handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
        handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        handle_request({"jsonrpc": "2.0", "id": 3, "method": "ping"})
    finally:
        _send = original_send

    ids = [m.get("id") for m in captured]
    check("initialize replied", any(m.get("id") == 1 for m in captured))
    init_reply = next((m for m in captured if m.get("id") == 1), {})
    check("protocolVersion echoed", init_reply.get("result", {}).get("protocolVersion") == "2025-06-18")
    check("initialized notification produced no reply", None not in ids)
    tools_reply = next((m for m in captured if m.get("id") == 2), {})
    tools = tools_reply.get("result", {}).get("tools", [])
    check("tools/list returns search_jobs", tools and tools[0]["name"] == "search_jobs")
    check("ping replied", any(m.get("id") == 3 for m in captured))

    print()
    if failures:
        print(f"SELFTEST FAILED: {len(failures)} check(s) failed.")
        return 1
    print("SELFTEST PASSED: all checks green.")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    serve()

