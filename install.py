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


def strip_ours(entries, command):
    """Drop this hook's own entries from one trigger's list, keeping everything
    else exactly as it was."""
    kept = []
    for entry in entries:
        inner = entry.get("hooks", []) if isinstance(entry, dict) else []
        if any(HOOK_NAME in h.get("command", "") for h in inner if isinstance(h, dict)):
            continue
        kept.append(entry)
    return kept


def register(settings, command):
    hooks = settings.setdefault("hooks", {})
    for trigger in TRIGGERS:
        existing = hooks.get(trigger, [])
        if not isinstance(existing, list):
            existing = []
        cleaned = strip_ours(existing, command)
        cleaned.append({"hooks": [{"type": "command", "command": command}]})
        hooks[trigger] = cleaned
    return settings


def unregister(settings, command):
    hooks = settings.get("hooks", {})
    for trigger in TRIGGERS:
        if trigger in hooks and isinstance(hooks[trigger], list):
            cleaned = strip_ours(hooks[trigger], command)
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


def is_installed(cfg, settings_path):
    if not (cfg / "hooks" / HOOK_NAME).exists():
        return False
    hooks = load_settings(settings_path).get("hooks", {})
    for trigger in TRIGGERS:
        for entry in hooks.get(trigger, []) or []:
            inner = entry.get("hooks", []) if isinstance(entry, dict) else []
            if any(HOOK_NAME in h.get("command", "") for h in inner if isinstance(h, dict)):
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

    if cmd not in ("install", "stop", "start", "uninstall", "status"):
        print(f"\n  Unknown command: {cmd}")
        print("  Use: install · stop · start · uninstall · status\n")
        return 1

    if cmd == "stop":
        return cmd_stop(cfg)
    if cmd == "start":
        return cmd_start(cfg)
    if cmd == "status":
        return cmd_status(cfg, settings_path)
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
    print("  stop · start · uninstall · status  →  python3 install.py <command>")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
