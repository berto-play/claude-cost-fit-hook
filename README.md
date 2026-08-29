# Cost & Fit

A hook for Claude Code that tells you when the model you're running no longer fits the work you're doing.

A session can start with a difficult problem that needs Opus. Later, the work may become simple, but Opus is still running. Cost & Fit looks for that mismatch and shows a short warning with a copyable command when switching models may help.

I built it because I kept finding Opus answering my rename-this-variable questions, and nothing in Claude Code would tell me it was time to switch.

> Claude Code shows your usage. Cost & Fit helps you turn that information into a decision.

## Example

```text
💰 COST & FIT
   💸 This is Sonnet work, you're on Opus.
      Switch: /model sonnet
```

The hook never changes the model for you. It gives you information and leaves the decision with you.

## What it gives you, and what it doesn't

1. **Awareness is the information:** "This reply cost approximately this much."
2. **Behavior is the intervention:** "This work fits Sonnet. Switch with this command."
3. **Savings are the possible result, not the product's guaranteed output.**

On a Pro or Max subscription, the displayed amount is not a charge. It shows how much of your usage allowance a reply consumed, so the limit arrives later, not sooner.

For API users, the same feedback can help identify avoidable usage and potential cost reduction. The amount shown is an estimate, not a promise of exact savings.

## Install

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Quit Claude Code completely and reopen it.

Requires Python 3.8+ and macOS or Linux.

## What it helps you do

### Switch when the work changes

Cost & Fit compares each request with the model that's running. When the model is oversized for the task, it shows a one-line warning with a copyable `/model` command.

### See the cost while you work

Claude Code records token usage and provides an estimated session cost. Cost & Fit uses those token counts to estimate the cost of the latest reply and the current thread.

This puts the estimate in context while you are still working.

### Know when the thread is the problem

Long threads can become expensive even when the model is appropriate. Prompt caching reduces repeated processing, but context still grows, and some actions can make the cache more expensive to rebuild.

When the thread itself becomes the main source of usage, switching models will not solve the problem. Cost & Fit tells you to start fresh:

```text
/clear
```

### Start new sessions at a better default

New sessions use the model configured in Claude Code. Set the default model with:

```bash
python3 install.py model sonnet
```

Starting with Sonnet gives the hook room to suggest Opus when the work becomes more difficult.

## Who it helps

| If you use Claude Code as a... | Cost & Fit helps you... | The honest benefit is... |
|---|---|---|
| API user | Switch away from an expensive model when simpler work begins | You may reduce avoidable spend |
| Pro or Max subscriber | Avoid unnecessary use of limited usage capacity | Your allowance may last longer |
| Long-session user | Notice when the thread itself is becoming expensive | You know when `/clear` helps more than switching models |

## Good to know before you install

- The model switch is always yours to make; the hook only ever suggests.
- The dollar figures are estimates for awareness, not your bill, and savings
  depend on what you do with the nudges.
- It reads your request with a simple heuristic, not a model. A short question
  can hide a hard problem, so it can misjudge. That is why it only suggests,
  and why it says nothing when the signal is weak.

And if you install it and hear nothing for a while: silence is the product
working. No card means the model fits the work.

## Commands

```bash
python3 install.py status       # check status
python3 install.py stop         # pause the hook
python3 install.py start        # resume the hook
python3 install.py model        # set the default model
python3 install.py uninstall    # remove the hook
```

## Still on the workbench

This is a fun project, more shop than showroom. I built it because I needed it,
and I'm sharing it for anyone who might need something like it too. A few
things are still being workshopped:

- **A smarter judge of task size.** Today it reads keywords. The better version
  measures the reply after it lands — a short answer with no tools was small
  work as a matter of fact, not a guess. Designed, not built.
- **Prices that keep themselves fresh.** The rate table goes stale whenever
  Anthropic changes pricing; right now the fix is a hand edit.
- **The wording of the cards.** Nudges live or die on tone. If one reads wrong
  to you, that's worth hearing.

If you try it and something feels off, or you can see how to make it better,
[open an issue](../../issues) and share your thinking. Feedback about where it
was wrong is the most useful thing this project can receive.

---

MIT. See [LICENSE](LICENSE).
