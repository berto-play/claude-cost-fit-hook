# Cost & Fit

A behavior cue for Claude Code that helps you notice when the active model no longer fits the work.

A session can start with a difficult problem that needs Opus. Later, the work may become simple, but Opus is still running. Cost & Fit looks for that mismatch and shows a short warning with a copyable command when switching models may help.

I built it because I kept finding Opus answering my rename-this-variable questions, and nothing in Claude Code would tell me it was time to switch.

> Claude Code shows what you have used. Cost & Fit helps you decide what to do next.

## Example

```text
💰 COST & FIT
   💸 This is Sonnet work, you're on Opus.
      Switch: /model sonnet
```

The hook never changes the model for you. It gives you information and leaves the decision with you.

## Install

```bash
git clone https://github.com/berto-play/claude-cost-fit-hook.git
cd claude-cost-fit-hook
python3 install.py install
```

Quit Claude Code completely and reopen it.

Requires Python 3.8+ and macOS or Linux.

## The key distinction

1. **Awareness is the information:** "This reply cost approximately this much."
2. **Behavior is the intervention:** "This work fits Sonnet. Switch with this command."
3. **Savings are the possible result, not the product's guaranteed output.**

For included subscriber usage, the displayed amount is not a charge for each reply. The value is preserving usage capacity and reducing the chance of reaching a limit early.

For API users, the same feedback can help identify avoidable usage and potential cost reduction. The amount shown is an estimate, not a promise of exact savings.

## What it helps you do

### Switch when the work changes

You may start with Opus because the problem is difficult. Later, you may only be fixing a small error, but the session is still running on Opus.

Cost & Fit compares the current request with the active model. When the model may be too expensive for the task, it shows a one-line warning and a copyable `/model` command.

### See the cost while you work

Claude Code records token usage and provides an estimated session cost. Cost & Fit uses those token counts to estimate the cost of the latest reply and the current thread.

This gives you useful feedback while the session is still active, rather than only showing usage after the work is finished.

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
| Long-session user | Notice when the thread itself is becoming expensive | You know when `/clear` may help more than switching models |
| Claude Code user | Turn a cost signal into a clear next action | Awareness becomes behavior |

## What it does not do

- It does not change the model automatically.
- It does not guarantee savings.
- It does not always know which model is best.
- It does not show exact subscription billing.
- It stays silent when the current model fits the work.

## Commands

```bash
python3 install.py status       # check status
python3 install.py stop         # pause the hook
python3 install.py start        # resume the hook
python3 install.py model        # set the default model
python3 install.py uninstall    # remove the hook
```

MIT. See [LICENSE](LICENSE).
