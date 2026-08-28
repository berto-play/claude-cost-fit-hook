# How it works

Notes for anyone forking this. The README says what it does; this says why it
does it that way.

---

## The measurement problem

Every figure this hook prints has to survive one question: *where did that number
come from?*

Claude Code writes a JSONL transcript of every session, and each assistant
message in it carries a `usage` block with real token counts. The hook finds the
transcript for the current session, sums those blocks, and multiplies by a price
table. Nothing is sampled, inferred, or rounded up from a guess.

That constraint decides most of the design:

- **An unknown model produces no dollar figure.** Not an estimate, not the
  nearest known rate. Silence. A wrong number stated confidently is worse than
  no number, because it gets repeated.
- **Prices are matched on exact version, never substring.** `opus-4.1` costs
  three times `opus-5`. A substring match on "opus" would under-report by two
  thirds and never mention it.
- **Nothing is reported at session start.** Fit can be judged from the first
  prompt. Spend cannot: at session open the real count is zero, and any figure
  would be invention.

## The silence problem

A hook that speaks every turn gets ignored by turn four. Ignored is the same
outcome as broken, reached more slowly.

So the hook holds state per session and speaks only when something *changed*:

| State | Behaviour |
|---|---|
| Model fits the work | Silent |
| Same mismatch as last time | Silent |
| You already declined this suggestion | Silent, permanently |
| Cost below the reporting floor | Silent |

What survives that filter is rare enough to still be read.

## Classification

`shape_of()` maps a prompt to a work size, and `running_tier()` maps the current
model to the same scale. When they disagree, that is a card.

This is a heuristic over text. It is wrong sometimes, and the failure is
asymmetric: a false nudge annoys you every time, a missed nudge costs a few
cents once. So the thresholds are tuned toward saying nothing.

The pricing-question detector had to learn this the hard way. It was a loose
substring search until a pasted script containing the words "how does the pricing
work" inside its own test fixtures fired a pricing card at a code review. Now the
*whole message* must be the question, and messages over 240 characters are never
questions.

## State

One JSON file, keyed by session id, in the Claude config directory. It holds what
was already said and what was already declined. Delete it and the hook simply
starts fresh — nothing depends on its history.

## Where the wording lives

Every message is a list of alternatives, picked round-robin so repeated
situations do not produce identical text. Rewriting the tool's voice means
editing those lists and nothing else.
