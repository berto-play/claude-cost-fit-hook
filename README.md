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

**The model you need changes. Yours doesn't.** You start a session with a hard
problem. You pick Opus. Good call. An hour later, Opus is explaining a simple
error message, at five times Haiku's price. Nobody told you to switch. The hook
does: one line, only when the model stops fitting the task.

**Claude Code shows a fuel gauge. Not a speedometer.** It tells you how much
of your limit is left. It never tells you what one reply just cost, or if that
reply was worth it. The hook prices every reply, using Claude Code's own token
counts.

**Long conversations get expensive on their own.** Claude re-reads the whole
thread every single turn. That re-reading costs money. Past a point, the
thread costs more than the actual work. No model switch fixes this. The hook
notices, and tells you to run `/clear` instead.

**Every session starts on whatever model you used last.** The hook only
catches drift once a session is running. `python3 install.py model sonnet`
fixes the starting point. Start on a mid-tier model, and the hook only speaks
up when the work gets harder, not easier.

## Commands

```bash
python3 install.py status       # check status
python3 install.py stop         # pause
python3 install.py start        # resume
python3 install.py model        # set default model
python3 install.py uninstall    # remove
```

MIT. See [LICENSE](LICENSE).
