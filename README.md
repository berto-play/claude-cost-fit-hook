# Cost & Fit

A hook for Claude Code that reports what each reply costs and flags when the
model you are running is oversized for the work you are doing. It stays silent
unless it has something worth saying.

```
💰 COST & FIT
   💸 This is Sonnet work, you're on Opus.
      Switch: `/model sonnet`
```

```
💰 COST & FIT
   ✅ $0.14 this reply · $2.61 this thread · Sonnet, and it needed to be.
```

## The problem

You pick a model once; your work changes throughout the session. Sessions tend
to start with a hard problem, where a large model is the right call, and then
drift toward smaller tasks — writing a test, renaming a variable, asking what an
error means. Nothing marks that transition, so the expensive model keeps
answering questions a cheaper one would have handled at a fraction of the price.
Eventually you forget which model is selected at all.

Claude Code shows overall usage and progress toward your limit. What it does not
show is whether any individual reply deserved the model that produced it, or
what a single reply costs as the conversation grows. API users get per-call
pricing and can build tooling around it; subscription users have no per-reply
signal. This hook provides one.

## Who it is for

Anyone using Claude Code — the desktop app or the `claude` terminal CLI — on a
Pro or Max subscription who wants their usage limit to last longer, or API users
who want per-reply cost feedback inside the tool rather than in a dashboard.

## What it does

- **Sizes each request.** It classifies the shape of what you asked (mechanical,
  standard, or complex) and compares that to the model actually running. When
  they disagree, it prints one line with the `/model` command to switch.
- **Prices each reply and the running thread.** Figures come from the token
  counts in the session transcript Claude Code writes itself. Nothing is
  estimated.
- **Detects when the conversation itself becomes the cost.** Long threads are
  re-read on every turn, and that re-reading is billed. When it dominates the
  session's spend, the hook suggests `/clear` instead of a model change, because
  no model change fixes it.
- **Stays quiet otherwise.** It repeats nothing, and a declined suggestion is
  not raised again for the rest of the session.

The hook never changes your model and never blocks your work. It suggests; you
decide.

### About the dollar figures

On a subscription, Anthropic does not bill you these amounts. The figures are
the equivalent API list price of the tokens used — a consistent unit for
measuring how quickly you are consuming your usage limit. For direct API users,
they correspond to actual spend.

If a model is not in the price table, or any component of a figure cannot be
measured, the hook prints nothing rather than an estimate.

## Requirements

- Claude Code (desktop app or CLI). The hook does not work with the Anthropic
  API directly or with claude.ai, since neither runs hooks.
- Python 3.8 or later. No third-party dependencies.
- macOS or Linux. On Windows, use WSL.

## Installation

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Quit Claude Code completely and reopen it. The installer optionally asks what
name the hook should use when addressing you; press Enter to skip, or pass
`--no-name`.

The installer touches three files:

| File | Change |
|---|---|
| `~/.claude/hooks/cost-and-fit.py` | The hook itself, copied here |
| `~/.claude/settings.json` | Two hook entries: `UserPromptSubmit` and `Stop` |
| `~/.claude/CLAUDE.md` | One line, only if you provided a name |

The hook makes no network calls. Everything it reads is already on your
machine. If `CLAUDE_CONFIG_DIR` is set, all paths follow it.

## Usage

Once installed, there is nothing to run. Cards appear in your Claude Code
conversations when a reply was expensive enough to mention or the model does
not fit the task. Most turns produce nothing; that is the intended behavior.

### Commands

```bash
python3 install.py status       # installed, paused, or not installed
python3 install.py stop         # pause without uninstalling
python3 install.py start        # resume after a stop
python3 install.py model        # set which model sessions start on
python3 install.py uninstall    # remove the hook and its settings entries
```

`stop` writes a single flag file and touches nothing else; the hook checks it
first and exits silently. `uninstall` removes the hook and restores
`settings.json` to exactly what it had before, leaving unrelated settings
untouched. Every command is safe to run more than once.

### Setting a default model

```bash
python3 install.py model sonnet
```

Sets the model Claude Code starts each session on (`sonnet`, `haiku`, or
`opus`; run it bare for an interactive menu). Starting on a mid-tier model
means the hook's nudges fire when work gets harder rather than every time it
gets easier. The installer offers this once at the end of installation.

## Project structure

```
claude-cost-fit-hook/
├── install.py            installer and command-line interface
├── hooks/
│   └── cost-and-fit.py   the hook; single file, no dependencies
├── docs/
│   └── how-it-works.md   design notes: measurement rules, why it stays quiet
├── LICENSE               MIT
└── README.md
```

The hook is deliberately one file so it can be audited in a single sitting.
Comments explain why decisions were made rather than what each line does. The
`CMFA-01.x` tags in comments reference the internal rule set the hook was
originally written against; treat them as design notes.

Model prices live in the `RATES` table at the top of `hooks/cost-and-fit.py`.
Anthropic changes prices over time, so the table will eventually go stale; it
is a dozen lines to update. Request classification lives in `shape_of()`.

## Contributing

Issues and pull requests are welcome.

- **Stale prices are bugs.** If the `RATES` table no longer matches Anthropic's
  published pricing, please open an issue.
- **Silence is a design constraint.** Changes that make the hook speak more
  often need a strong argument. The bar is not whether the information is true,
  but whether it is worth interrupting someone for.

## License

MIT. See [LICENSE](LICENSE).
