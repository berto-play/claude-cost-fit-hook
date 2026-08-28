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

## The problem

**You pick a model once. Your work changes twenty times.**

A session usually starts hard. You reach for Opus because the first thing is
genuinely difficult — an architecture question, a nasty bug, a decision with
trade-offs. Correct choice.

Then the session drifts, the way sessions do:

```
  hard          →  medium        →  easy
  architecture     write a test     rename this
  ─────────────────────────────────────────────
  Opus             Opus             Opus
  right            fine             five times the price
```

Nothing marks that boundary. There is no moment where something says *the hard
part is over.* So Opus answers "what does this error mean," and answers it
beautifully, and costs roughly five times what Haiku would have.

Then you forget the model is even set. That is the second failure, and it is
worse, because it lasts for days.

---

## The gap

If you use the **API**, cost is a solved problem. Every call returns a token
count and a price. Dashboards, budgets, alerts — the whole industry has tooling
for it.

If you use **Claude Code on a subscription**, you get a fixed monthly fee and a
usage limit, and the app already shows you a running total and progress toward
that limit. That is real, and it is useful.

But a total answers *how much is left.* It never answers the question that
actually changes what you do next:

> **Was the model that just answered me the right size for what I asked?**

| Already visible | Still invisible |
|---|---|
| How much of your limit is gone | Whether any single reply deserved its model |
| That you are running low | Which habit is draining it |
| Which model is selected | Whether it still fits what you are now doing |
| — | What one reply costs as the thread grows dense |

A fuel gauge tells you the tank is emptying. It never tells you the engine is
oversized for the trip.

**I could not find a tool that closed that gap, so I built one.**

---

## What it does

**1 · Watches the shape of each request.**
Not the topic — the shape. "Rename this variable" and "rename this database
column" are the same size of job. It sizes what you asked, compares it to the
model actually running, and speaks only when those two disagree.

**2 · Prices every reply, and the thread.**
One number for the reply you just got, one for the conversation so far. Both
from real token counts, never an estimate.

**3 · Watches the context window get expensive.**
Long threads cost more for a reason that is not obvious, and the hook is the
only thing that will tell you when that has taken over. (Explained below.)

**4 · Says nothing the rest of the time.**
Which is most turns. That silence is the feature, not a bug.

---

## A note on the dollar figures

**Anthropic is not billing you these amounts.**

On a Pro or Max subscription you pay a flat monthly fee. The dollars here are the
equivalent API list price of the tokens you just used — a way to measure *how
fast you are spending your usage limit*, in units that mean something.

`$0.14 this reply` means that reply consumed about fourteen cents worth of your
allowance. Not a charge. **A speedometer, not a bill.**

If you use the API directly, the same numbers are your actual spend.

---

## How the math works

Every figure has to survive one question: *where did that number come from?*

### Step 1 — Read the receipt, never estimate it

Claude Code writes a log of your session to disk. Every reply in it carries the
real token counts, recorded by Claude Code itself. The hook opens that file and
adds them up.

Nothing is sampled, inferred, or rounded up from a guess.

### Step 2 — Multiply by the published rate

Prices are quoted per **million** tokens, which is why the raw numbers look
strange at first. Say a reply used 1,200 tokens in and 800 out on Opus 5:

| | rate per million | this reply |
|---|---|---|
| Reading in | $5 | 1,200 ÷ 1,000,000 × $5 = **$0.006** |
| Writing out | $25 | 800 ÷ 1,000,000 × $25 = **$0.020** |
| | | **$0.026** |

Shown as `$0.03 this reply`.

### Step 3 — Add the part nobody expects

Claude re-reads the entire conversation every single turn. That re-reading is
charged, at **10%** of the normal reading rate.

Cheap per turn. Not cheap by turn sixty.

This is why a long conversation can cost more than the work inside it, and it is
the one cost no model choice fixes. When re-reading passes **85%** of a session's
spend, the hook stops talking about models and tells you to `/clear` instead.

That threshold is the difference between advice that helps and advice that
misses the real problem.

### Step 4 — Refuse to guess

Fail-closed, deliberately:

- **Unknown model → no dollar figure at all.** Not the nearest known rate.
- **Prices match on exact version.** Opus 4.1 costs three times Opus 5. A loose
  match on the word "opus" would under-report by two thirds and never say so.
- **Nothing is reported at session start.** Fit can be judged from your first
  message. Spend cannot: the real count is zero, and any figure would be
  invention.

A wrong number said confidently is worse than no number, because it gets
believed and repeated.

---

## How the recommendation is made

**Is it legitimate?** Partly, and the honest answer matters.

The classifier is a keyword heuristic over the text of your prompt, not a model
judging your work. It maps requests to three sizes:

| Shape of the request | Expects |
|---|---|
| Rename, list, count, extract, reformat | Haiku |
| Explain, write, review, debug | Sonnet |
| Architect, refactor across files, weigh trade-offs | Opus |

**It will sometimes be wrong.** A short question can hide a hard problem. So the
whole thing is tuned toward silence: when the signal is weak it says nothing at
all, because the two failures are not equal.

> A wrong nudge costs trust every time it fires.
> A missed nudge costs a few cents, once.

**And it never acts on its own.**

- It **never switches your model.** A tool that silently downgraded you mid-task
  would be worse than no tool.
- Your work **never waits.** The card appears, your answer follows immediately.
- It **says a thing once.** Same mismatch next turn: silence.
- **A no is permanent.** Decline once and that suggestion is gone for the
  session.

The bar for speaking is not "this is true." It is **"this is worth interrupting
someone for."**

---

## Where it runs

Claude Code — both the desktop app and the `claude` terminal CLI. They share one
config directory, so installing once covers both.

Not the API, not claude.ai. Neither runs hooks.

Requires Python 3.8+. macOS and Linux; on Windows, WSL.

---

## Install

No dependencies, nothing to configure.

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Then quit Claude Code completely and reopen it.

The installer asks what to call you. Press Enter to skip, or pass `--no-name`.

### Commands

```bash
python3 install.py install      # set it up
python3 install.py stop         # pause it, keep it installed
python3 install.py start        # resume
python3 install.py uninstall    # remove it completely
python3 install.py status       # which of those am I?
```

**Stop is not uninstall.** Stop writes one flag file that the hook checks before
it reads anything. Everything stays in place; it just goes quiet. For when you
want silence this afternoon without reinstalling tomorrow.

Every command is safe to run twice.

### What it touches

| File | Change |
|---|---|
| `~/.claude/hooks/cost-and-fit.py` | The hook. Copied here. |
| `~/.claude/settings.json` | Two entries: `UserPromptSubmit` and `Stop`. |
| `~/.claude/CLAUDE.md` | One line, only if you gave a name. |

Nothing else is read or written. **The hook makes no network calls.** Everything
it knows comes from files already on your machine. Uninstall restores
`settings.json` exactly as it was.

If `CLAUDE_CONFIG_DIR` is set, all three paths follow it.

---

## When it speaks

| Trigger | What you get |
|---|---|
| Model does not fit the task | One line, plus the `/model` command |
| A reply cost real money | That reply, and the thread so far |
| Re-reading passed 85% of spend | A nudge to `/clear` |
| You ask how pricing works | A plain explanation, on request only |
| Everything is fine | Nothing |

**That last row is the common case.** A warning that fires every turn stops being
read by the fourth one, and ignored is the same outcome as broken.

---

## Forking it

One file, about 640 lines, heavily commented — most comments explain *why* a
decision was made rather than what a line does. Worth editing:

- **`RATES`** — the price table. Anthropic changes prices; this will go stale.
- **`shape_of()`** — how a request is sized.
- **the message lists** — the exact wording of every card.

`docs/how-it-works.md` has the design reasoning.

The `CMFA-01.x` tags in the comments reference the internal rule set this was
first built against. They are kept because they mark which decisions were
deliberate. Read them as design notes, or ignore them.

---

## Contributing

Issues and pull requests welcome. Two things worth knowing:

**Prices go stale.** If `RATES` is wrong, that is a real bug and a one-line fix.
Please open an issue.

**Silence is the design.** Changes that make the hook speak more often need to
argue for themselves. The bar is not "this information is true," it is "this is
worth interrupting someone for."

---

MIT. Do what you like with it.
