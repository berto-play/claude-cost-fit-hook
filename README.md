# Cost & Fit

A hook for Claude Code that tells you when the model is oversized for the work,
and what each reply took out of your usage limit. I built it because I kept
finding Opus answering my rename-this-variable questions, and nothing in the
app would ever tell me.

```
💰 COST & FIT
   💸 This is Sonnet work, you're on Opus.
      Switch: `/model sonnet`
```

## Install

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Quit Claude Code completely and reopen it. Python 3.8+, macOS or Linux.

## The problems it solves

**You start hard and drift easy, and the model never follows.** Sessions open
with a real problem, so you pick Opus, and you're right to. An hour later Opus
is explaining error messages at five times Haiku's price, and no boundary was
ever marked. The hook says one line when the model doesn't fit the task.

**You have a fuel gauge but no speedometer.** Claude Code shows how much limit
is gone. It never shows what one reply consumed, or whether it was worth it.
The hook prices each reply from Claude Code's own token counts.

**Long threads quietly become the cost.** Claude re-reads the whole
conversation every turn, and that re-reading is billed. Past a point the
thread costs more than the work in it, and no model change fixes that. When
re-reading dominates, the hook tells you to `/clear` instead.

**You start every day on yesterday's model.** The hook catches drift inside a
session; `python3 install.py model sonnet` sets where sessions begin. Start
mid-tier and the nudge fires when work gets harder.

## Commands

```bash
python3 install.py status       # check status
python3 install.py stop         # pause
python3 install.py start        # resume
python3 install.py model        # set default model
python3 install.py uninstall    # remove
```

MIT. See [LICENSE](LICENSE).
