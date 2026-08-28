# Cost & Fit

A hook for Claude Code that tells you when the model is oversized for the work,
and what each reply took out of your usage limit. I built it because I kept
finding Opus answering my rename-this-variable questions, and nothing in the
app would ever tell me.

It stays silent unless it has something worth saying. Most turns, it says
nothing. That's the design, not a gap in it.

```
💰 COST & FIT
   💸 This is Sonnet work, you're on Opus.
      Switch: `/model sonnet`
```

```
💰 COST & FIT
   ✅ $0.14 this reply · $2.61 this thread · Sonnet, and it needed to be.
```

## Try it in two minutes

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Quit Claude Code completely, reopen it, and work as usual. You need Python 3.8+
and Claude Code (desktop app or the `claude` CLI; one install covers both).
macOS or Linux; on Windows, WSL.

Then forget about it. The first card appears when a reply was expensive enough
to mention or the model doesn't fit the task. If you want it gone:

```bash
python3 install.py uninstall
```

That restores your settings exactly as they were.

## The itch it scratches

**You start hard and drift easy, and the model never follows.** Sessions open
with a real problem, so you pick Opus, and you're right to. An hour later Opus
is explaining error messages at five times Haiku's price, and no boundary was
ever marked. The hook watches the shape of each request against the model
running and says one line when they disagree, with the switch command ready to
copy.

**You have a fuel gauge but no speedometer.** Claude Code shows how much of
your limit is gone. It never shows what one reply consumed, or whether it was
worth it. The hook prices each reply and the running thread from the token
counts Claude Code itself records. On a subscription these dollars are not a
bill; they're the API-equivalent price of what you just used, which is the
honest way to see how fast your limit is draining. On the API, they're your
actual spend.

**Long threads quietly become the cost.** Claude re-reads the whole
conversation every turn, and that re-reading is billed. Past a point, the
thread costs more than the work in it, and no model change fixes that. When
re-reading dominates, the hook stops talking about models and tells you to
`/clear` instead.

**You start every day on yesterday's model.** The hook catches drift inside a
session; `install.py model sonnet` sets where sessions begin. Start mid-tier
and the nudge fires when work gets harder, which is the direction worth being
interrupted in.

## What it won't do

It won't switch models for you, ever. It suggests once and your work continues
immediately; decline and that suggestion is dead for the session.

It won't always be right. The classifier is a keyword heuristic over your
prompt, not a model judging your work, and a short question can hide a hard
problem. So it's tuned toward silence: a wrong nudge costs trust every time,
a missed one costs a few cents once.

It won't guess. Unknown model, unmeasurable piece: no figure at all. And it
makes no network calls; everything it reads is already on your machine.

## Commands

```bash
python3 install.py status       # installed, paused, or absent
python3 install.py stop         # pause; everything stays in place
python3 install.py start        # resume
python3 install.py model        # set which model sessions start on
python3 install.py uninstall    # remove completely, settings restored
```

Every command is safe to run twice. `stop` writes one flag file and touches
nothing else, so pausing for an afternoon never risks your settings.

## Under the hood

| | |
|---|---|
| `hooks/cost-and-fit.py` | The whole hook. One file so you can audit it in a sitting. |
| `install.py` | Installer and the commands above. |
| `docs/how-it-works.md` | Why it measures the way it does, and why it stays quiet. |

The installer registers two entries in `~/.claude/settings.json`
(`UserPromptSubmit` and `Stop`), copies the hook to `~/.claude/hooks/`, and
adds one line to `~/.claude/CLAUDE.md` only if you gave it a name to call you.
`CLAUDE_CONFIG_DIR` is honored throughout.

Prices live in the `RATES` table at the top of the hook. Anthropic changes
prices, so that table will go stale; it's a dozen lines to fix, and a stale
rate is a bug I want an issue for. Classification lives in `shape_of()`. Hack
around with both; the comments explain why, not what.

Pull requests welcome, with one house rule: changes that make the hook speak
more often need a strong argument. The bar is not "this is true," it's "this
is worth interrupting someone for."

MIT. Do what you like with it.
