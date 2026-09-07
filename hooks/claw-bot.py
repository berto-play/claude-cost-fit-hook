#!/usr/bin/env python3
"""Claw Bot — one assistant, two modes, and a rulebook that bites.

THE PROBLEM THIS SOLVES
    Rules written in CLAUDE.md are advice. An assistant under pressure to finish
    a task will talk itself past advice, and you find out afterwards. A rule that
    lives in a PreToolUse hook is not advice: the tool call is refused before it
    runs, and no amount of reasoning gets around it.

    So the rules live here, not in a prompt.

TWO MODES
    admin   Strict. Every rule is on. This is the default, and it is what a
            missing, empty, or corrupt state file falls back to. If Claw Bot
            cannot work out which mode it is in, it picks the careful one.

    build   Loose. Only the rules marked "always" stay on; the rest stand down.
            For work where being stopped every few minutes costs more than the
            mistakes being prevented.

    Switch by typing the whole message `claw build` or `claw admin`. Whole
    message, not a substring: the cost hook in this repo once fired a pricing
    card at a code review because a pasted file happened to contain the words
    "how does the pricing work". Same lesson applied here from the start.

THREE OUTCOMES PER RULE
    deny    The tool call is refused. Claude is told why and carries on without it.
    ask     The call is put to you for a yes or no. For actions that are usually
            fine and occasionally a disaster.
    (no match) Silence. Nothing is printed and nothing is logged.

WHERE THE RULES LIVE
    DEFAULT_RULES below ship inside this file, so Claw Bot always has a rulebook
    even with nothing else installed. ~/.claude/clawbot/rules.json, when present
    and valid, replaces them entirely. When present and broken, the built-ins are
    used and the breakage is reported rather than swallowed: a rulebook that
    silently stopped applying is worse than one that never existed.

WHAT IT WILL NOT DO
    Change a model, edit a file, or take an action of its own. It only ever
    refuses, asks, or stays quiet. Every allow is silent, so the absence of a
    card means the call went through untouched.
"""

import fnmatch
import json
import os
import re
import subprocess
import sys
import time

MODES = ("admin", "build")
DEFAULT_MODE = "admin"          # fail-closed: unknown state means the strict mode


# ── the rulebook ─────────────────────────────────────────────────────────────
# level   "always" = on in both modes. "admin" = stands down in build mode.
# action  "deny" refuses outright, "ask" puts it to the operator.
# tools   which tool names the rule inspects. "*" means every tool.
# match   regex over the command string (Bash) or the file path (Edit/Write/Read).
# paths   glob patterns matched against the full path and the bare filename.
# special a named check in SPECIAL_CHECKS below, for anything a regex cannot see.
#
# Kept short on purpose. A rulebook nobody can hold in their head is one that
# gets switched off wholesale the first time it is wrong.
DEFAULT_RULES = [
    # ---- always on, refused outright -------------------------------------
    {
        "id": "no-force-push",
        "level": "always", "action": "deny", "tools": ["Bash"],
        "match": r"\bgit\s+push\b[^\n;|&]*(--force\b|--force-with-lease\b|\s-f\b)",
        "why": "Force-push rewrites history other people have already pulled. "
               "If the branch really needs rewriting, do it yourself.",
    },
    {
        "id": "no-secret-writes",
        "level": "always", "action": "deny", "tools": ["Edit", "Write", "NotebookEdit"],
        "paths": ["**/.env", ".env", "**/.env.*", ".env.*", "**/*.pem", "*.pem",
                  "**/id_rsa*", "id_rsa*", "**/id_ed25519*", "id_ed25519*",
                  "**/credentials", "**/.npmrc", "**/.netrc"],
        "why": "That file holds secrets. Reading it is one thing; rewriting it "
               "can lock you out of your own accounts.",
    },
    {
        "id": "no-secret-dumps",
        "level": "always", "action": "deny", "tools": ["Bash"],
        "match": r"\b(cat|less|more|head|tail|bat|xxd|base64)\b[^\n;|&]*"
                 r"(\.ssh/id_|\.aws/credentials|\.netrc|\.npmrc|"
                 r"\.env(\s|$|\.)|secrets?\.(json|ya?ml|env))",
        "why": "Printing a secret puts it in the transcript, which is a file on "
               "disk and a copy in the model's context. It does not come back out.",
    },
    {
        "id": "no-wipe",
        "level": "always", "action": "deny", "tools": ["Bash"],
        "match": r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*[rR])\s+"
                 r"(/|~|\$HOME|/\*|~/\*|\.\s*$|\*\s*$)",
        "why": "That deletes your home directory or your root. There is no "
               "version of this task that needs it.",
    },
    {
        "id": "no-drop",
        "level": "always", "action": "deny", "tools": ["Bash", "*"],
        "match": r"\b(DROP\s+(DATABASE|TABLE|SCHEMA)|TRUNCATE\s+TABLE)\b",
        "why": "Dropping or truncating a table destroys data that no undo "
               "reaches. Take a dump first, then run it by hand.",
    },

    # ---- always on, put to you --------------------------------------------
    {
        "id": "no-push-to-main",
        "level": "always", "action": "ask", "tools": ["Bash"],
        "special": "push_touches_main",
        "why": "This looks like a push straight to main. Branch first unless "
               "you meant it.",
    },
    {
        "id": "no-history-rewrite",
        "level": "always", "action": "ask", "tools": ["Bash"],
        "match": r"\bgit\s+(rebase\b|commit\b[^\n;|&]*--amend\b|"
                 r"reset\b[^\n;|&]*--hard\b|filter-branch\b)",
        "why": "This rewrites or discards commits. Fine when you meant it, "
               "expensive when you did not.",
    },
    {
        "id": "no-ship-to-prod",
        "level": "always", "action": "ask", "tools": ["Bash"],
        "match": r"(\bnpm\s+publish\b|\byarn\s+publish\b|\bpnpm\s+publish\b|"
                 r"\bgh\s+release\s+create\b|\bvercel\b[^\n;|&]*--prod\b|"
                 r"\bnetlify\s+deploy\b[^\n;|&]*--prod\b|"
                 r"\bfly\s+deploy\b|\beas\s+submit\b)",
        "why": "This publishes to somewhere real, where other people can see it. "
               "Shipping is your call, not mine.",
    },

    # ---- admin mode only ---------------------------------------------------
    {
        "id": "no-sudo",
        "level": "admin", "action": "deny", "tools": ["Bash"],
        "match": r"(^|[;&|]\s*)sudo\b",
        "why": "Admin mode does not run anything as root. Switch to build mode "
               "if you genuinely need this.",
    },
    {
        "id": "no-global-install",
        "level": "admin", "action": "ask", "tools": ["Bash"],
        "match": r"(\bnpm\s+(i|install)\b[^\n;|&]*\s-g\b|"
                 r"\bnpm\s+(i|install)\b[^\n;|&]*--global\b|"
                 r"\bbrew\s+(install|upgrade)\b|"
                 r"\bpip3?\s+install\b(?![^\n;|&]*(-r\b|--requirement))|"
                 r"\bcargo\s+install\b|\bgo\s+install\b)",
        "why": "This changes the machine, not the project, and it outlives the "
               "session that asked for it.",
    },
    {
        "id": "no-writes-outside-project",
        "level": "admin", "action": "ask", "tools": ["Edit", "Write", "NotebookEdit"],
        "special": "path_outside_cwd",
        "why": "That path is outside the folder we are working in. Usually a "
               "mistake, occasionally on purpose.",
    },
    {
        "id": "no-bulk-upload",
        "level": "admin", "action": "ask", "tools": ["Bash"],
        "match": r"\b(curl|wget|http|httpie)\b[^\n;|&]*"
                 r"(-d\s*@|--data-binary\s*@|--upload-file|-T\s|-F\s*[\"']?[a-z_]+=@)",
        "why": "This sends a local file to an outside server. Once it leaves, "
               "you cannot take it back.",
    },
]


# ── paths and state ──────────────────────────────────────────────────────────
def _base():
    """Under the Claude config directory, so a relocated config takes Claw Bot
    with it. Its own folder, not the cost hook's: two products, two state files,
    and deleting one never disturbs the other."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    root = os.path.expanduser(env) if env else os.path.expanduser("~/.claude")
    return os.path.join(root, "clawbot")


BASE = _base()
STATE = os.path.join(BASE, "state.json")
RULES_FILE = os.path.join(BASE, "rules.json")
LOG = os.path.join(BASE, "denied.log")
PAUSED = os.path.join(BASE, "paused")
LOG_KEEP = 200                  # lines; the log is a diagnostic, not an archive


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(patch):
    try:
        st = load_state()
        st.update(patch)
        os.makedirs(BASE, exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(st, f, indent=2)
        return True
    except Exception:
        return False


def current_mode():
    m = load_state().get("mode")
    return m if m in MODES else DEFAULT_MODE


def load_rules():
    """Returns (rules, note). `note` is non-empty only when the user's rulebook
    could not be used, and it is surfaced rather than swallowed: a rulebook that
    quietly stopped applying is the worst outcome of the three."""
    if not os.path.exists(RULES_FILE):
        return DEFAULT_RULES, ""
    try:
        with open(RULES_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return DEFAULT_RULES, f"rules.json will not parse ({e}); using built-in rules"
    rules = data.get("rules") if isinstance(data, dict) else data
    if not isinstance(rules, list) or not rules:
        return DEFAULT_RULES, "rules.json has no rules in it; using built-in rules"
    clean = [r for r in rules if isinstance(r, dict) and r.get("id")]
    if not clean:
        return DEFAULT_RULES, "no usable rules in rules.json; using built-in rules"
    return clean, ""


# ── matching ─────────────────────────────────────────────────────────────────
PATH_KEYS = ("file_path", "notebook_path", "path", "filePath")


def subject(tool_name, tool_input):
    """The one string a rule is matched against.

    Bash gets its command. File tools get their path. Anything else gets its
    whole input serialised, so a rule can still reach an MCP tool's arguments
    without this file needing to know that tool's shape.
    """
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == "Bash":
        return str(ti.get("command") or "")
    for k in PATH_KEYS:
        if ti.get(k):
            return str(ti[k])
    try:
        return json.dumps(ti)
    except Exception:
        return str(ti)


def path_of(tool_input):
    ti = tool_input if isinstance(tool_input, dict) else {}
    for k in PATH_KEYS:
        if ti.get(k):
            return str(ti[k])
    return ""


def push_touches_main(tool_name, tool_input, inp):
    """True when a git push looks like it lands on main or master.

    An explicit `git push origin main` is obvious. A bare `git push` is not, and
    is the way it usually happens by accident, so the branch is read from git
    itself. When git cannot answer, the rule still fires: its action is `ask`,
    not `deny`, so an uncertain answer costs one keystroke rather than blocking
    a push that was fine.
    """
    cmd = subject(tool_name, tool_input)
    if not re.search(r"\bgit\s+push\b", cmd):
        return False
    if re.search(r"\bgit\s+push\b[^\n;|&]*\b(main|master)\b", cmd):
        return True
    # A named branch that is not main is explicit enough to leave alone.
    if re.search(r"\bgit\s+push\b[^\n;|&]*\s\S+\s+\S+", cmd):
        return False
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             cwd=inp.get("cwd") or None, capture_output=True,
                             text=True, timeout=2)
        if out.returncode == 0:
            return out.stdout.strip() in ("main", "master")
    except Exception:
        pass
    return True                 # cannot tell: ask rather than assume


def path_outside_cwd(tool_name, tool_input, inp):
    """True when a write lands outside the working folder.

    Symlinks are resolved on both sides before comparing, so a link pointing out
    of the project does not read as inside it.
    """
    p = path_of(tool_input)
    cwd = inp.get("cwd")
    if not p or not cwd:
        return False
    try:
        root = os.path.realpath(os.path.expanduser(cwd))
        target = os.path.realpath(os.path.expanduser(
            p if os.path.isabs(p) else os.path.join(cwd, p)))
        return os.path.commonpath([root, target]) != root
    except Exception:
        return False            # cannot resolve it: not grounds for stopping


SPECIAL_CHECKS = {
    "push_touches_main": push_touches_main,
    "path_outside_cwd": path_outside_cwd,
}


def rule_applies(rule, mode):
    if rule.get("enabled") is False:
        return False
    return mode == "admin" or rule.get("level", "admin") == "always"


def rule_hits(rule, tool_name, tool_input, inp):
    tools = rule.get("tools") or ["*"]
    if "*" not in tools and tool_name not in tools:
        return False

    special = rule.get("special")
    if special:
        fn = SPECIAL_CHECKS.get(special)
        if not fn:
            return False        # a rule naming a check we do not have is inert,
        try:                    # never a blanket block
            return bool(fn(tool_name, tool_input, inp))
        except Exception:
            return False

    subj = subject(tool_name, tool_input)

    pats = rule.get("paths")
    if pats:
        p = path_of(tool_input) or subj
        name = os.path.basename(p)
        for pat in pats:
            if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(name, pat):
                return True
        return False

    rx = rule.get("match")
    if rx:
        try:
            return bool(re.search(rx, subj, re.I))
        except re.error:
            return False        # a broken regex disables its own rule, nothing else
    return False


def log_hit(rule, tool_name, subj, mode):
    """Append-only, trimmed. This is how you find out the rules are too tight
    without having to remember every time one fired."""
    try:
        os.makedirs(BASE, exist_ok=True)
        line = json.dumps({
            "at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "rule": rule.get("id"),
            "action": rule.get("action", "deny"),
            "tool": tool_name,
            "subject": subj[:300],
        })
        lines = []
        if os.path.exists(LOG):
            with open(LOG, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        lines.append(line)
        with open(LOG, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[-LOG_KEEP:]) + "\n")
    except Exception:
        pass


# ── triggers ─────────────────────────────────────────────────────────────────
def on_pretooluse(inp):
    mode = current_mode()
    rules, note = load_rules()
    tool_name = inp.get("tool_name") or ""
    tool_input = inp.get("tool_input") or {}

    # Deny beats ask, so a call that trips both is refused rather than offered.
    hit = None
    for rule in rules:
        if not rule_applies(rule, mode):
            continue
        if not rule_hits(rule, tool_name, tool_input, inp):
            continue
        if rule.get("action", "deny") == "deny":
            hit = rule
            break
        if hit is None:
            hit = rule

    if not hit:
        sys.exit(0)                                  # allow, and say nothing

    action = "deny" if hit.get("action", "deny") == "deny" else "ask"
    log_hit(hit, tool_name, subject(tool_name, tool_input), mode)

    reason = f"🦞 CLAW BOT · {mode} mode · rule `{hit.get('id')}`\n{hit.get('why', '').strip()}"
    if action == "deny":
        reason += ("\n\nDo not retry this, and do not work around it with a "
                   "different command. Say what you were trying to do and let "
                   "the operator decide.")
    if note:
        reason += f"\n\n(Note: {note})"

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": action,
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


ADMIN_POSTURE = (
    "You are in ADMIN mode. Careful over quick.\n"
    "- Do what was asked and stop there. No adjacent improvements.\n"
    "- Anything hard to undo gets confirmed first, in one short question.\n"
    "- Say what you actually did. Never report work as done before you have "
    "checked it.\n"
    "- Some tool calls will be refused by rule. A refusal is a decision, not an "
    "obstacle: report it and move on, never route around it."
)

BUILD_POSTURE = (
    "You are in BUILD mode. Make the thing.\n"
    "- Take the ambitious reading of the request, not the safe one.\n"
    "- Prefer the version that does not exist yet over the version you have "
    "built before. If the obvious approach is the common one, say so and offer "
    "the better one.\n"
    "- Ship something working, then say plainly what is rough about it.\n"
    "- The hard limits still apply. Everything else is open."
)


def on_session_start(inp):
    """Announced once per session, not per prompt.

    Injecting a posture on every message would put a paragraph into the context
    dozens of times a session, which is exactly the cost the other hook in this
    repo exists to warn about. Once is enough for a standing instruction.
    """
    mode = current_mode()
    rules, note = load_rules()
    live = [r for r in rules if rule_applies(r, mode)]
    posture = ADMIN_POSTURE if mode == "admin" else BUILD_POSTURE
    extra = f"\n\nRulebook problem: {note}" if note else ""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext":
            f"🦞 CLAW BOT is on, in {mode} mode, with {len(live)} rules live.\n\n"
            f"{posture}{extra}\n\n"
            "Do not mention any of this unless asked. Switching modes is the "
            "operator's job, done by typing `claw build` or `claw admin`; never "
            "suggest it and never do it for them."
    }}))
    sys.exit(0)


COMMAND_RE = re.compile(r"^claw\s+(admin|build|status|rules|log|help)$", re.I)


def card(text):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": text +
        "\n\nPrint the block above verbatim as your whole reply. Add nothing "
        "to it and do no other work this turn."
    }}))
    sys.exit(0)


def on_prompt(inp):
    """Only mode commands. Everything else passes through untouched, so the
    normal cost of having Claw Bot installed is zero tokens per turn.

    The command must be the entire message. A substring match here would fire on
    any message that happened to quote one, which is the bug the cost hook in
    this repo already shipped once.
    """
    raw = inp.get("prompt")
    prompt = raw.strip() if isinstance(raw, str) else ""
    m = COMMAND_RE.match(prompt)
    if not m:
        sys.exit(0)

    word = m.group(1).lower()
    mode = current_mode()
    rules, note = load_rules()

    if word in MODES:
        if word == mode:
            card(f"🦞 CLAW BOT\n   Already in {mode} mode. Nothing changed.")
        ok = save_state({"mode": word, "switched": time.strftime("%Y-%m-%d %H:%M:%S")})
        if not ok:
            card(f"🦞 CLAW BOT\n   Could not write {STATE}. Still in {mode} mode.")
        live = len([r for r in rules if rule_applies(r, word)])
        moved = "Loosened" if word == "build" else "Tightened"
        card(f"🦞 CLAW BOT\n   {moved}: {mode} → {word}. {live} rules live.\n"
             f"   Takes effect on the next tool call. Switch back with `claw {mode}`.")

    if word == "status":
        live = [r for r in rules if rule_applies(r, mode)]
        deny = len([r for r in live if r.get("action", "deny") == "deny"])
        src = RULES_FILE if os.path.exists(RULES_FILE) and not note else "built-in"
        card(f"🦞 CLAW BOT\n   Mode: {mode}\n   Rules live: {len(live)} "
             f"({deny} refuse, {len(live) - deny} ask)\n   Rulebook: {src}"
             + (f"\n   Problem: {note}" if note else ""))

    if word == "rules":
        live = [r for r in rules if rule_applies(r, mode)]
        body = "\n".join(
            f"   {'✋' if r.get('action', 'deny') == 'deny' else '❓'} "
            f"{r.get('id')} — {r.get('why', '').splitlines()[0] if r.get('why') else ''}"
            for r in live)
        card(f"🦞 CLAW BOT · {mode} mode · {len(live)} rules live\n{body}\n"
             f"\n   ✋ refuses  ❓ asks first\n   Edit them: {RULES_FILE}")

    if word == "log":
        try:
            with open(LOG, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()[-10:]
        except Exception:
            lines = []
        if not lines:
            card("🦞 CLAW BOT\n   Nothing stopped yet.")
        body = []
        for ln in lines:
            try:
                e = json.loads(ln)
                body.append(f"   {e['at']}  {e['action']:<4} {e['rule']}  "
                            f"{e['subject'][:60]}")
            except Exception:
                continue
        card("🦞 CLAW BOT · last 10 stops\n" + "\n".join(body))

    card("🦞 CLAW BOT\n"
         "   claw admin    strict: every rule on\n"
         "   claw build    loose: only the hard limits\n"
         "   claw status   which mode, how many rules\n"
         "   claw rules    list what is live right now\n"
         "   claw log      what got stopped recently")


def paused():
    try:
        return os.path.exists(PAUSED)
    except Exception:
        return False


def main():
    # Checked first so a pause costs nothing, cannot half-apply, and cannot fail.
    if paused():
        sys.exit(0)
    try:
        raw = sys.stdin.read()
        inp = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)
    ev = (inp.get("hook_event_name") or "").lower()
    try:
        if ev == "pretooluse":
            on_pretooluse(inp)
        elif ev == "userpromptsubmit":
            on_prompt(inp)
        elif ev == "sessionstart":
            on_session_start(inp)
    except SystemExit:
        raise
    except Exception:
        # A crash allows the call through. The alternative, a bug in this file
        # blocking every tool in every session, is the worse failure and the
        # harder one to diagnose from inside the session it broke.
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
