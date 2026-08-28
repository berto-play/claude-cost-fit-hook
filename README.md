# Cost & Fit

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Dependencies: none](https://img.shields.io/badge/Dependencies-none-brightgreen.svg)

A hook for Claude Code that tells you when you are spending Opus on Haiku work,
and what each reply took out of your usage limit.

Silent the rest of the time. Which is most of the time.

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

## The problem

**You pick a model once. Your work changes twenty times.**

Sessions start hard. You reach for Opus because the first thing is genuinely
difficult. Correct choice.

Then the session drifts:

```
  architecture  →  write a test  →  rename this
  ────────────────────────────────────────────────
  Opus             Opus             Opus
  right            fine             five times the price
```

Nothing marks that boundary. So Opus answers "what does this error mean," and
answers it beautifully, at five times what Haiku would have cost.

Then you forget the model is set at all. That one lasts for days.

---

## The gap

Claude Code already shows your usage and how much of the limit is left. That is
a fuel gauge, and it is useful.

It never tells you the engine is oversized for the trip.

| Already visible | Still invisible |
|---|---|
| How much of your limit is gone | Whether a reply deserved its model |
| That you are running low | Which habit is draining it |
| Which model is selected | Whether it still fits what you are doing now |

API users solved this years ago — every call returns a price. On a subscription
there is no per-call signal at all.

**I could not find a tool that closed that gap, so I built one.**

---

## What it does

**Sizes what you asked.** Not the topic, the shape. Compares it to the model
actually running. Speaks only when those disagree.

**Prices each reply, and the thread.** From the real token counts Claude Code
records, never an estimate.

**Watches long threads get expensive.** They cost more than the work in them,
for a reason that is not obvious, and no model choice fixes it. The hook is the
thing that tells you when that has taken over.

**Says nothing the rest of the time.**

---

## About the dollar figures

**Anthropic is not billing you these amounts.**

On a subscription you pay a flat fee. The dollars are the equivalent API price of
the tokens you just used — a way to measure how fast your limit is draining, in
units that mean something.

**A speedometer, not a bill.** If you use the API directly, they are your actual
spend.

---

## Can you trust the numbers

Three rules, and the hook holds all three:

**It reads, never estimates.** Every count comes from the session log Claude Code
writes itself.

**It refuses to guess.** Unknown model, missing piece, anything uncertain — no
figure at all. A wrong number said confidently is worse than no number, because
it gets believed.

**It never acts on its own.** It suggests. You decide. Your work never waits, it
says a thing once, and a no is permanent for that session.

The classifier reads your prompt with a heuristic, not a model. It will sometimes
be wrong, so it is tuned toward silence: a wrong nudge costs trust every time, a
missed one costs a few cents once.

---

## Where it runs

Claude Code — desktop app and the `claude` terminal CLI. One install covers both.

Not the API, not claude.ai. Neither runs hooks.

Python 3.8+. macOS and Linux; on Windows, WSL.

---

## Install

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Quit Claude Code completely and reopen it.

```bash
python3 install.py stop         # pause, stay installed
python3 install.py start        # resume
python3 install.py uninstall    # remove completely
python3 install.py status       # which of those am I?
```

**Stop is not uninstall.** Everything stays in place; it just goes quiet. Every
command is safe to run twice.

### What it touches

| File | Change |
|---|---|
| `~/.claude/hooks/cost-and-fit.py` | The hook |
| `~/.claude/settings.json` | Two entries |
| `~/.claude/CLAUDE.md` | One line, only if you gave a name |

**No network calls.** Everything comes from files already on your machine.
Uninstall restores `settings.json` exactly.

---

## When it speaks

| Trigger | What you get |
|---|---|
| Model does not fit the task | One line, and the command to switch |
| A reply cost real money | That reply, and the thread so far |
| The thread itself became the cost | A nudge to `/clear` |
| You ask how pricing works | A plain answer, on request only |
| Everything is fine | Nothing |

**That last row is the common case.** A warning that fires every turn stops being
read by the fourth one.

---

## Forking it

One file, heavily commented — the comments explain *why*, not what.
`docs/how-it-works.md` has the reasoning behind the design.

Start with `RATES` for prices and `shape_of()` for how requests are sized.

## Contributing

**Prices go stale.** If `RATES` is wrong, that is a real bug and a one-line fix.
Please open an issue.

**Silence is the design.** Changes that make it speak more often need to argue
for themselves. The bar is not "this is true," it is "this is worth interrupting
someone for."

---

MIT. Do what you like with it.
