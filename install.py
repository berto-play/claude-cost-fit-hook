#!/usr/bin/env python3
"""Installer for the Claude Code cost-and-fit hook.

Copies the hook into ~/.claude/hooks/, registers it on the two triggers it
needs, and leaves every other setting untouched. Safe to re-run: it replaces
its own entries and never duplicates them.

    python3 install.py                install, asking what to call you
    python3 install.py --no-name      install, skip the name question
    python3 install.py --uninstall    remove the hook and its settings entries
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


def main():
    args = set(sys.argv[1:])
    cfg = claude_dir()
    settings_path = cfg / "settings.json"
    dest = cfg / "hooks" / HOOK_NAME
    command = f"python3 {dest}"

    if "--uninstall" in args:
        settings = load_settings(settings_path)
        unregister(settings, command)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        if dest.exists():
            dest.unlink()
        print(f"\n  Removed. {settings_path} keeps everything else it had.")
        print("  Restart Claude Code to finish.\n")
        return 0

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
