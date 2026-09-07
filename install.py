#!/usr/bin/env python3
"""Installer for the Claude Code cost-and-fit hook.

Copies the hook into ~/.claude/hooks/, registers it on the two triggers it
needs, and leaves every other setting untouched. Safe to re-run: it replaces
its own entries and never duplicates them.

    python3 install.py install      install it (asks what to call you)
    python3 install.py stop         pause it, keeping it installed
    python3 install.py start        resume it after a stop
    python3 install.py uninstall    remove it completely
    python3 install.py status       say which of those it currently is
    python3 install.py model        set the model Claude Code starts on
    python3 install.py claw         Claw Bot: the rules that block tool calls

`install` is the default, so bare `python3 install.py` still works. Add
--no-name to skip the name question.

Stop is not uninstall. Stop leaves everything in place and writes a single
flag file; the hook reads that flag first and exits silently. Someone who
wants quiet for an afternoon should not have to reinstall afterwards.
"""

import json
import os
import shutil
import sys
from pathlib import Path

HOOK_NAME = "cost-and-fit.py"
TRIGGERS = ("UserPromptSubmit", "Stop")
REPO = Path(__file__).resolve().parent
SOURCE = REPO / "hooks" / HOOK_NAME

# Claw Bot is a second, independent hook that happens to share this installer.
# Separate name, separate triggers, separate state folder: installing or removing
# one never touches the other.
CLAW_NAME = "claw-bot.py"
CLAW_TRIGGERS = ("PreToolUse", "UserPromptSubmit", "SessionStart")
CLAW_SOURCE = REPO / "hooks" / CLAW_NAME
CLAW_RULES_SOURCE = REPO / "rules" / "claw-rules.json"
CLAW_MODES = ("admin", "build")


def claude_dir():
    """Claude Code's config directory. Honours CLAUDE_CONFIG_DIR if set."""
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(os.path.expanduser(env)) if env else Path.home() / ".claude"


def load_settings(path):
    """Existing settings, or an empty dict. Never silently discards a file it
    cannot parse: a broken settings.json is a stop, not something to overwrite."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"\n  settings.json exists but is not valid JSON ({e}).")
        print(f"  Fix or move {path}, then run this again. Nothing was changed.")
        sys.exit(1)


def strip_ours(entries, hook_name=HOOK_NAME):
    """Drop one hook's own entries from a trigger's list, keeping everything
    else exactly as it was. Matched on filename, so the two hooks in this repo
    never strip each other."""
    kept = []
    for entry in entries:
        inner = entry.get("hooks", []) if isinstance(entry, dict) else []
        if any(hook_name in h.get("command", "") for h in inner if isinstance(h, dict)):
            continue
        kept.append(entry)
    return kept


def register(settings, command, triggers=TRIGGERS, hook_name=HOOK_NAME):
    hooks = settings.setdefault("hooks", {})
    for trigger in triggers:
        existing = hooks.get(trigger, [])
        if not isinstance(existing, list):
            existing = []
        cleaned = strip_ours(existing, hook_name)
        # No matcher: on PreToolUse an absent matcher means every tool, which is
        # what Claw Bot needs. Narrowing it here would silently exempt whichever
        # tool the matcher forgot.
        cleaned.append({"hooks": [{"type": "command", "command": command}]})
        hooks[trigger] = cleaned
    return settings


def unregister(settings, command, triggers=TRIGGERS, hook_name=HOOK_NAME):
    hooks = settings.get("hooks", {})
    for trigger in triggers:
        if trigger in hooks and isinstance(hooks[trigger], list):
            cleaned = strip_ours(hooks[trigger], hook_name)
            if cleaned:
                hooks[trigger] = cleaned
            else:
                del hooks[trigger]
    if not hooks:
        settings.pop("hooks", None)
    return settings


def ask_name():
    """Optional. The hook works fine without it; this only changes how the
    cards address you. Empty input, EOF, or a piped stdin all mean 'skip'."""
    if not sys.stdin.isatty():
        return None
    print()
    print("  Optional: what should the cost cards call you?")
    print("  Press Enter to skip and keep them neutral.")
    try:
        name = input("  Name: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return name or None


def write_greeting(cfg_dir, name):
    """One line in CLAUDE.md is all personalisation needs. Anything more would
    be this installer editing files it does not own."""
    md = cfg_dir / "CLAUDE.md"
    line = f"Cost cards from the cost-and-fit hook should address me as {name}."
    existing = md.read_text(encoding="utf-8") if md.exists() else ""
    if "cost-and-fit hook should address me" in existing:
        return False
    with md.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"\n{line}\n")
    return True


def pause_flag(cfg):
    return cfg / "cmfa" / "paused"


def is_installed(cfg, settings_path, hook_name=HOOK_NAME, triggers=TRIGGERS):
    if not (cfg / "hooks" / hook_name).exists():
        return False
    hooks = load_settings(settings_path).get("hooks", {})
    for trigger in triggers:
        for entry in hooks.get(trigger, []) or []:
            inner = entry.get("hooks", []) if isinstance(entry, dict) else []
            if any(hook_name in h.get("command", "") for h in inner if isinstance(h, dict)):
                return True
    return False


def cmd_stop(cfg):
    """Pause without uninstalling. The hook checks this file before doing
    anything else, so a pause is free and cannot half-apply."""
    flag = pause_flag(cfg)
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()
    print("\n  Paused. The hook stays installed and says nothing.")
    print("  Resume with:  python3 install.py start\n")
    return 0


def cmd_start(cfg):
    flag = pause_flag(cfg)
    if flag.exists():
        flag.unlink()
        print("\n  Resumed.\n")
    else:
        print("\n  Already running.\n")
    return 0


def cmd_status(cfg, settings_path):
    installed = is_installed(cfg, settings_path)
    if not installed:
        print("\n  Not installed.  →  python3 install.py install\n")
    elif pause_flag(cfg).exists():
        print("\n  Installed, paused.  →  python3 install.py start\n")
    else:
        print("\n  Installed and running.\n")
    return 0


MODELS = [
    ("sonnet", "claude-sonnet-5", "Balanced. The right default for most people."),
    ("haiku", "claude-haiku-4-5-20251001", "Fast and cheap. Simple, mechanical work."),
    ("opus", "claude-opus-5", "Strongest, priciest. Hard problems only."),
]


def cmd_model(settings_path, preset=None):
    """Set the model Claude Code starts every session on.

    This is the other half of the problem: the hook can tell you a session has
    drifted, but if you always begin on Opus you will keep having the same
    conversation. Starting lower means the nudge fires when work gets harder,
    which is the direction worth being interrupted in.
    """
    settings = load_settings(settings_path)
    current = settings.get("model")

    if preset is None:
        if not sys.stdin.isatty():
            print("\n  Usage: python3 install.py model <sonnet|haiku|opus>\n")
            return 1
        print()
        print(f"  Claude Code currently starts on:  {current or 'no default set'}")
        print()
        for i, (short, _, why) in enumerate(MODELS, 1):
            print(f"    {i}. {short:<7} {why}")
        print()
        print("  Enter to leave it unchanged.")
        try:
            choice = input("  Choose 1-3: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not choice:
            print("\n  Unchanged.\n")
            return 0
        by_name = {s: (s, mid, w) for s, mid, w in MODELS}
        if choice in by_name:
            preset = choice
        elif choice.isdigit() and 1 <= int(choice) <= len(MODELS):
            preset = MODELS[int(choice) - 1][0]
        else:
            print(f"\n  Not one of the options: {choice}\n")
            return 1

    match = next((m for m in MODELS if m[0] == preset.lower()), None)
    if not match:
        names = " · ".join(m[0] for m in MODELS)
        print(f"\n  Unknown model: {preset}\n  Choose one of: {names}\n")
        return 1

    short, model_id, _ = match
    settings["model"] = model_id
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    print(f"\n  Claude Code will now start on {short}  ({model_id})")
    print("  Restart Claude Code for it to take effect.")
    print("  Switch mid-session any time with  /model <name>\n")
    return 0


def cmd_uninstall(cfg, settings_path, dest, command):
    settings = load_settings(settings_path)
    unregister(settings, command)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    if dest.exists():
        dest.unlink()
    flag = pause_flag(cfg)
    if flag.exists():
        flag.unlink()
    print(f"\n  Removed. {settings_path} keeps everything else it had.")
    print("  Restart Claude Code to finish.\n")
    return 0


# ── Claw Bot ─────────────────────────────────────────────────────────────────
# A second hook with a different job. The cost hook reports and never acts;
# Claw Bot acts and never reports. They share an installer and nothing else.

def claw_dir(cfg):
    return cfg / "clawbot"


def claw_mode(cfg):
    """Admin unless the state file clearly says otherwise. A missing, empty, or
    unreadable file means admin, matching the hook: when the mode cannot be
    established, the strict one is the safe answer."""
    try:
        d = json.loads((claw_dir(cfg) / "state.json").read_text(encoding="utf-8"))
        m = d.get("mode")
        return m if m in CLAW_MODES else "admin"
    except Exception:
        return "admin"


def claw_set_mode(cfg, mode):
    d = claw_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    state = {}
    try:
        state = json.loads((d / "state.json").read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    state["mode"] = mode
    (d / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def claw_rules(cfg):
    """(rules, where). The user's copy wins when it parses; otherwise the copy
    shipped in this repo, which is what the hook falls back to as well."""
    user = claw_dir(cfg) / "rules.json"
    for path, where in ((user, str(user)), (CLAW_RULES_SOURCE, "built-in")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rules = data.get("rules") if isinstance(data, dict) else data
            if isinstance(rules, list) and rules:
                return rules, where
        except Exception:
            continue
    return [], "none found"


def claw_live(rules, mode):
    return [r for r in rules
            if r.get("enabled") is not False
            and (mode == "admin" or r.get("level", "admin") == "always")]


def claw_pause_flag(cfg):
    return claw_dir(cfg) / "paused"


def cmd_claw(cfg, settings_path, words, argv=()):
    """`words` is argv with flags filtered out, `argv` is the whole thing.

    Both are needed: `claw mode build` reads a positional, `claw rules --copy`
    reads a flag, and main() strips flags out of `words` before this is called.
    Reading only `words` silently ignored --copy and printed the list instead.
    """
    sub = words[1].lower() if len(words) > 1 else "status"
    dest = cfg / "hooks" / CLAW_NAME
    command = f"python3 {dest}"

    if sub == "install":
        if not CLAW_SOURCE.exists():
            print(f"\n  Cannot find {CLAW_SOURCE}")
            print("  Run this from inside the repo folder.\n")
            return 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CLAW_SOURCE, dest)
        os.chmod(dest, 0o755)
        settings = load_settings(settings_path)
        register(settings, command, CLAW_TRIGGERS, CLAW_NAME)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        flag = claw_pause_flag(cfg)
        if flag.exists():
            flag.unlink()
        mode = claw_mode(cfg)
        rules, _ = claw_rules(cfg)
        print()
        print("  Claw Bot installed.")
        print(f"    hook      {dest}")
        print(f"    triggers  {', '.join(CLAW_TRIGGERS)}")
        print(f"    mode      {mode}   ({len(claw_live(rules, mode))} rules live)")
        print()
        print("  Quit Claude Code completely and reopen it.")
        print()
        print("  From inside Claude Code, type these as a whole message:")
        print("    claw admin    strict: every rule on")
        print("    claw build    loose: only the hard limits")
        print("    claw rules    list what is live right now")
        print()
        return 0

    if sub == "uninstall":
        settings = load_settings(settings_path)
        unregister(settings, command, CLAW_TRIGGERS, CLAW_NAME)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        if dest.exists():
            dest.unlink()
        # The mode, the rulebook and the log stay. Someone reinstalling next week
        # wants their edits back, and nothing here is large enough to be litter.
        print(f"\n  Claw Bot removed. Your rules and log are still in {claw_dir(cfg)}.")
        print("  Restart Claude Code to finish.\n")
        return 0

    if sub == "stop":
        flag = claw_pause_flag(cfg)
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()
        print("\n  Claw Bot paused. Every rule is off until you start it again.")
        print("  Resume with:  python3 install.py claw start\n")
        return 0

    if sub == "start":
        flag = claw_pause_flag(cfg)
        if flag.exists():
            flag.unlink()
            print("\n  Claw Bot resumed.\n")
        else:
            print("\n  Claw Bot is already running.\n")
        return 0

    if sub == "mode":
        want = words[2].lower() if len(words) > 2 else None
        if want not in CLAW_MODES:
            print(f"\n  Usage: python3 install.py claw mode <{' | '.join(CLAW_MODES)}>\n")
            return 1
        claw_set_mode(cfg, want)
        rules, _ = claw_rules(cfg)
        print(f"\n  Claw Bot is now in {want} mode. "
              f"{len(claw_live(rules, want))} rules live.")
        print("  Takes effect on the next tool call; no restart needed.\n")
        return 0

    if sub == "rules":
        mode = claw_mode(cfg)
        rules, where = claw_rules(cfg)
        wants_copy = ("--copy" in argv
                      or (len(words) > 2 and words[2].lower() in ("copy", "mine")))
        if wants_copy:
            target = claw_dir(cfg) / "rules.json"
            if target.exists():
                print(f"\n  You already have your own copy: {target}")
                print("  Delete it to go back to the built-in rules.\n")
                return 0
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CLAW_RULES_SOURCE, target)
            print(f"\n  Your copy: {target}")
            print("  Edit it freely. What is not in that file is not enforced,")
            print("  so it replaces the built-in rules rather than adding to them.\n")
            return 0
        live = claw_live(rules, mode)
        print(f"\n  Claw Bot · {mode} mode · {len(live)} of {len(rules)} rules live")
        print(f"  Rulebook: {where}\n")
        for r in rules:
            on = r in live
            mark = "  " if on else "· "
            act = "refuses" if r.get("action", "deny") == "deny" else "asks   "
            why = (r.get("why") or "").split(".")[0]
            print(f"  {mark}{act}  {r.get('id'):<26} {why}")
        if len(live) != len(rules):
            print("\n  · = stands down in this mode")
        print(f"\n  Make your own: python3 install.py claw rules --copy\n")
        return 0

    if sub == "log":
        path = claw_dir(cfg) / "denied.log"
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        except Exception:
            lines = []
        if not lines:
            print("\n  Claw Bot has not stopped anything yet.\n")
            return 0
        print("\n  Last 20 stops\n")
        for ln in lines:
            try:
                e = json.loads(ln)
            except Exception:
                continue
            print(f"  {e.get('at')}  {e.get('action'):<4} {e.get('rule'):<26} "
                  f"{(e.get('subject') or '')[:50]}")
        print()
        return 0

    if sub == "status":
        installed = is_installed(cfg, settings_path, CLAW_NAME, CLAW_TRIGGERS)
        mode = claw_mode(cfg)
        rules, where = claw_rules(cfg)
        print()
        if not installed:
            print("  Claw Bot: not installed.  →  python3 install.py claw install")
        elif claw_pause_flag(cfg).exists():
            print("  Claw Bot: installed, paused.  →  python3 install.py claw start")
        else:
            print(f"  Claw Bot: running in {mode} mode, "
                  f"{len(claw_live(rules, mode))} rules live.")
            print(f"  Rulebook: {where}")
        print()
        return 0

    print(f"\n  Unknown: claw {sub}")
    print("  Use: install · uninstall · status · mode · rules · log · stop · start\n")
    return 1


def main():
    argv = sys.argv[1:]
    args = set(argv)
    words = [a for a in argv if not a.startswith("-")]
    cmd = words[0].lower() if words else "install"

    # --uninstall kept working alongside the word form: the flag shipped first.
    if "--uninstall" in args:
        cmd = "uninstall"

    cfg = claude_dir()
    settings_path = cfg / "settings.json"
    dest = cfg / "hooks" / HOOK_NAME
    command = f"python3 {dest}"

    if cmd not in ("install", "stop", "start", "uninstall", "status", "model", "claw"):
        print(f"\n  Unknown command: {cmd}")
        print("  Use: install · stop · start · uninstall · status · model · claw\n")
        return 1

    if cmd == "claw":
        return cmd_claw(cfg, settings_path, words, argv)
    if cmd == "stop":
        return cmd_stop(cfg)
    if cmd == "start":
        return cmd_start(cfg)
    if cmd == "status":
        return cmd_status(cfg, settings_path)
    if cmd == "model":
        return cmd_model(settings_path, words[1] if len(words) > 1 else None)
    if cmd == "uninstall":
        return cmd_uninstall(cfg, settings_path, dest, command)

    if not SOURCE.exists():
        print(f"\n  Cannot find {SOURCE}")
        print("  Run this from inside the repo folder.\n")
        return 1

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, dest)
    os.chmod(dest, 0o755)

    settings = load_settings(settings_path)
    register(settings, command)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    # A fresh install clears any leftover pause, so "install" always means running.
    flag = pause_flag(cfg)
    if flag.exists():
        flag.unlink()

    name = None if "--no-name" in args else ask_name()
    if name:
        write_greeting(cfg, name)

    print()
    print("  Installed.")
    print(f"    hook      {dest}")
    print(f"    settings  {settings_path}")
    print(f"    triggers  {', '.join(TRIGGERS)}")
    if name:
        print(f"    name      {name}")
    print()
    print("  Quit Claude Code completely and reopen it.")
    print("  Nothing will appear until a reply is expensive enough to be worth")
    print("  mentioning, or the model does not fit the task. That silence is the")
    print("  feature.")
    print()
    print("  stop · start · uninstall · status · model  →  python3 install.py <command>")
    print("  Claw Bot, the rules that block tool calls  →  python3 install.py claw")

    # Offered here rather than buried in the docs: the hook nudges you when a
    # session drifts, but a high default means that drift starts every day.
    current = load_settings(settings_path).get("model")
    if sys.stdin.isatty() and current != "claude-sonnet-5":
        shown = current or "whatever Claude Code picks"
        print()
        print(f"  One more thing. Sessions currently start on: {shown}")
        print("  Starting on sonnet means the nudge fires when work gets harder,")
        print("  rather than every time it gets easier.")
        try:
            if input("  Set the default to sonnet? [y/N]: ").strip().lower() in ("y", "yes"):
                cmd_model(settings_path, "sonnet")
                return 0
        except (EOFError, KeyboardInterrupt):
            pass

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
