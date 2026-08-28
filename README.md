# Cost & Fit

A hook for Claude Code that tells you what a reply cost, and when you are paying
Opus prices for Haiku work.

It stays quiet the rest of the time. That is most of the time, and it is the
point.

```
💰 COST & FIT
   💸 This is Sonnet work, you're on Opus.
      Switch: `/model sonnet`
```

```
💰 COST & FIT
   ✅ $0.14 this reply · $2.61 this thread · Sonnet, and it needed to be.
```

---

## Why this exists

Claude Code shows you a running total. A total is not a decision.

Knowing you have spent $40 today tells you nothing about whether that was
reasonable. The number you actually need is the one you never see: **was the
model I used the right size for the thing I asked?** A refactor across nine
files earns Opus. "What does this error mean" does not, and costs five times
more than it should when Opus answers it.

This hook answers that question, and only that question. It reads what you asked,
classifies the shape of the work, compares it to the model actually running, and
speaks when those two disagree.

Then it goes quiet again.

---

## What it will not do

It **never changes your model.** It says what it thinks and gets out of the way.
A tool that silently downgraded you mid-task would be worse than no tool.

It **never invents a number.** Token counts come from the transcript Claude Code
writes itself. Dollars are arithmetic on those counts. When it cannot measure
something honestly, it says nothing rather than estimating.

It **never repeats itself.** Tell it no once and that answer holds for the rest
of the session. A nudge that fires every turn stops being read, which is the
same failure as a warning that never fires at all.

---

## Install

Requires Python 3.8+ and Claude Code. No dependencies, nothing to configure.

```bash
git clone https://github.com/YOUR-USERNAME/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py
```

Then quit Claude Code completely and reopen it.

The installer asks what to call you. Press Enter to skip; the hook works
identically either way.

To remove it:

```bash
python3 install.py --uninstall
```

Both commands are safe to run twice. Install replaces its own entries rather
than stacking them, and uninstall leaves every other setting exactly as it was.

---

## What the installer touches

| File | Change |
|---|---|
| `~/.claude/hooks/cost-and-fit.py` | The hook. Copied here. |
| `~/.claude/settings.json` | Two entries added: `UserPromptSubmit` and `Stop`. |
| `~/.claude/CLAUDE.md` | One line, only if you gave a name. |

Nothing else is read, written, or sent anywhere. The hook makes no network
calls. Everything it knows comes from files already on your machine.

If `CLAUDE_CONFIG_DIR` is set, all three paths follow it.

---

## When it speaks

| Trigger | What you get |
|---|---|
| Model does not fit the task | One line, plus the `/model` command to switch |
| A reply cost real money | Cost of that reply, and of the thread so far |
| Most of the context is cache | A nudge to `/clear`, because no model choice fixes that |
| You ask how pricing works | A plain explanation, on request only |
| Everything is fine | Nothing |

That last row is the common case.

---

## Prices

The rates live in one table at the top of `hooks/cost-and-fit.py`. Anthropic
changes prices; this file will eventually be wrong. Edit that table when it is.

An unknown model produces no dollar figure at all, rather than a guessed one.

---

## Forking it

The hook is one file, about 600 lines, heavily commented — most comments explain
*why* a decision was made rather than what a line does. Places worth editing:

- **`RATES`** — the price table
- **`shape_of()`** — how a prompt is classified into a work size
- **the message lists** — the exact wording of every card

The `CMFA-01.x` tags in the comments reference the internal rule set this was
originally built against. They are kept because they mark which decisions were
deliberate. Ignore them, or read them as design notes.

---

## Prior art, and the honest limitation

Classification is a heuristic over the text of your prompt. It will sometimes
call a hard question easy. It is a nudge, not an oracle, and it is deliberately
biased toward silence: a wrong nudge costs more trust than a missed one saves
money.

---

MIT. Do what you like with it.
