# Cost & Fit

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Dependencies: none](https://img.shields.io/badge/Dependencies-none-brightgreen.svg)

A hook for Claude Code that tells you when you are spending Opus on Haiku work,
and what each reply took out of your usage limit.

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

## The gap it fills

You pick a model at the start of a session. Then you use it for everything,
because switching is friction and nothing ever reminds you.

So Opus answers "what does this error mean." It answers it well, and it costs
roughly five times what Haiku would have. Nothing tells you this happened. You
find out when you hit your limit at 3pm on a Tuesday and cannot work.

**The missing feedback is not the total. It is the fit.**

| You can already see | You cannot see |
|---|---|
| That you have used a lot today | Whether any single reply deserved the model that gave it |
| That your limit is running low | Which habit is draining it |
| Which model is selected | Whether it still suits what you are now doing |

A total tells you the tank is emptying. It never tells you the engine is oversized
for the trip.

## What you get

**You stop paying Opus prices out of habit.** The hook reads what you asked,
sizes the work, compares it to the model actually running, and says something
only when those two disagree.

**Your limit lasts longer.** Same work, cheaper model, on the tasks where the
cheaper model was always going to be enough.

**You learn where it goes.** After a few days you can see which kinds of request
actually cost you something. Most people are surprised. It is rarely the hard
work; it is the long thread of small questions.

**It costs you nothing to keep on.** No cards on a normal turn. Silence is the
default state, not a failure.

---

## A note on the dollar figures

**Anthropic is not billing you these amounts.**

On a Claude Pro or Max subscription you pay a flat monthly fee. The dollars here
are the equivalent API list price of the tokens you just used: a way to measure
*how fast you are spending your usage limit*, in units that mean something.

"$0.14 this reply" means that reply consumed roughly fourteen cents worth of your
allowance. Not a charge. A speedometer, not a bill.

If you do use the API directly, the same numbers are your actual spend.

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

## Where it runs

Claude Code, both the desktop app and the `claude` terminal CLI. They share one
config directory, so installing once covers both.

Not for the Anthropic API, and not for claude.ai — neither runs hooks.

Requires Python 3.8+. macOS and Linux; on Windows, WSL.

## Install

No dependencies, nothing to configure.

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Then quit Claude Code completely and reopen it.

The installer asks what to call you. Press Enter to skip; the hook works
identically either way, or use `--no-name` to skip the question outright.

## Commands

```bash
python3 install.py install      # set it up
python3 install.py stop         # pause it, keep it installed
python3 install.py start        # resume
python3 install.py uninstall    # remove it completely
python3 install.py status       # which of those am I?
```

**Stop is not uninstall.** Stop writes a single flag file that the hook checks
before doing anything else. Everything stays in place; it just says nothing.
Use it when you want quiet for an afternoon without reinstalling afterwards.

Every command is safe to run twice. Install replaces its own settings entries
rather than stacking them, and uninstall leaves every other setting exactly as
it was.

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

The rates live in one table at the top of `hooks/cost-and-fit.py`. They are
Anthropic's published API list prices, used here as a yardstick — see the note
above on what the dollar figures mean.

Anthropic changes prices, so this table will eventually be wrong. Edit it when
it is; it is a dozen lines.

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

## The honest limitation

Classification is a heuristic over the text of your prompt. It will sometimes
call a hard question easy. It is a nudge, not an oracle, and it is deliberately
biased toward silence: a wrong nudge costs more trust than a missed one saves
money.

---

## Contributing

Issues and pull requests are welcome. Two things worth knowing before you open
one:

**Prices go stale.** If the `RATES` table is wrong, that is a real bug and a
one-line fix. Please do open an issue.

**Silence is the design.** Changes that make the hook speak more often need to
argue for themselves. The bar is not "this information is true", it is "this is
worth interrupting someone for."

---

MIT. Do what you like with it.
