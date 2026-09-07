# Claw Bot

Notes for anyone forking this. The README says what it does; this says why it
does it that way.

---

## Why a hook and not a prompt

Every project that has tried this has started by writing the rules into
`CLAUDE.md`. It reads well and it does not work, because a rule in a prompt is
advice, and an assistant halfway through a task has a reason to talk itself past
advice. You find out afterwards, from the git log.

A rule in a `PreToolUse` hook is not advice. The hook runs before the tool does,
returns `permissionDecision: "deny"`, and the call never happens. There is no
reasoning that gets around it, because the model is not the thing making the
decision.

That is the whole design. Everything below follows from it.

## The two modes

| | admin | build |
|---|---|---|
| Rules on | all of them | only `level: "always"` |
| Meant for | live systems, other people's repos, anything you cannot undo | a sandbox, a spike, a first draft |
| Posture given to Claude | do what was asked and stop | take the ambitious reading |

Admin is the default, and it is also what a missing, empty, or unreadable state
file resolves to. If Claw Bot cannot establish which mode it is in, it picks the
one that stops more. The opposite default fails silently and in the expensive
direction.

Switching is the operator's job. The hook tells Claude explicitly not to suggest
a switch and not to perform one, because an assistant that can widen its own
permissions when it finds them inconvenient has no permissions at all.

## The three outcomes

**deny** refuses the call. Used where there is no version of the task that needs
it: force-push, `rm -rf ~`, `DROP TABLE`, writing to `.env`.

**ask** hands the decision to you. Used where the action is usually correct and
occasionally a disaster: `git push` onto main, `git commit --amend`,
`npm publish`. A rulebook made only of denials gets switched off the first
afternoon it is wrong about something.

**no match** is silent. Nothing prints and nothing is logged, so the cost of
having Claw Bot installed on an ordinary turn is zero.

Where a call trips both a deny rule and an ask rule, deny wins. Offering a choice
that was already settled would be theatre.

## What a rule can see

| Tool | What the rule is matched against |
|---|---|
| `Bash` | the command string |
| `Edit`, `Write`, `NotebookEdit`, `Read` | the file path |
| anything else, including MCP tools | the whole tool input, serialised |

That last row is what lets a rule reach a tool this file has never heard of. It
is a blunt instrument, and it is better than a rulebook that only covers the
four tools that existed when it was written.

Two checks cannot be written as a regex and live in the hook as named `special`
values:

- **`push_touches_main`** — an explicit `git push origin main` is easy. A bare
  `git push` is not, and is how it usually happens by accident, so the branch is
  read from git itself with a two-second timeout. When git cannot answer, the
  rule still fires. It can afford to: its action is `ask`, so an uncertain answer
  costs one keystroke rather than blocking a push that was fine.
- **`path_outside_cwd`** — both sides are resolved through `realpath` before
  comparing, so a symlink pointing out of the project does not read as inside it.

## Failure modes, and which way each one falls

This is the part worth getting right, because a security tool that fails in the
wrong direction is worse than no tool.

| What breaks | What happens | Why that way |
|---|---|---|
| `rules.json` will not parse | built-in rules apply, and the breakage is printed on the next card | a rulebook that quietly stopped applying is the worst of the three outcomes |
| A rule's regex is invalid | that one rule is inert | one typo should not disable the other eleven |
| A rule names a `special` check that does not exist | that one rule is inert | never a blanket block from a spelling mistake |
| The hook itself throws | the call is allowed | a bug in this file blocking every tool in every session is the worse failure, and the harder one to diagnose from inside the session it broke |
| No state file at all | admin mode | fail closed on the mode, fail open on the crash |

The split in that last row is deliberate and is the only interesting decision in
the file. Not knowing your *intent* should make it careful. Not being able to
*run* should not make it a brick.

## State

Everything lives in one folder, `~/.claude/clawbot/`, honouring
`CLAUDE_CONFIG_DIR` when it is set:

    state.json    which mode, and when it last changed
    rules.json    your rulebook, if you made one. Absent by default.
    denied.log    the last 200 things that were stopped
    paused        an empty file; while it exists, every rule is off

Its own folder, not the cost hook's. Two products, and deleting one never
disturbs the other.

`rules.json` **replaces** the built-in rules rather than adding to them. That is
the surprising choice, so it is stated in three places: what is not in your file
is not enforced. The alternative, merging, means you can never remove a rule you
disagree with, and a rule you cannot remove is one you work around.

Nothing depends on any of these files existing. Delete the folder and Claw Bot
starts fresh in admin mode with the built-in rules.

## The log

Every deny and every ask is appended to `denied.log`, trimmed to the last 200
lines. It is a diagnostic, not an archive, and it exists to answer one question:
are the rules too tight?

A rulebook nobody reviews drifts into either paranoia or decoration. Read it with
`python3 install.py claw log`, and when a rule keeps stopping work that was
fine, change the rule.

## Why the posture is announced once

`SessionStart` injects the mode and its posture a single time per session, not on
every prompt. A paragraph re-sent on every turn is dozens of copies in the
context of a long session, which is exactly the cost the other hook in this repo
exists to warn you about. A standing instruction only needs saying once.

`UserPromptSubmit` therefore does almost nothing: it watches for the `claw ...`
commands and passes everything else through untouched.

## The whole-message rule

`claw build` switches modes only when it is the entire message. This is not
fussiness. The cost hook in this repo already shipped the other version, and
someone pasted a script that happened to contain the words "how does the pricing
work" inside its own test fixtures, which fired a pricing card at a code review.

A substring match on a 40KB paste is not a command. It is a coincidence.

## Tests

    python3 tests/test_claw_bot.py

Runs the hook the way Claude Code runs it: real JSON on stdin, decision read off
stdout, nothing mocked. Testing the function instead of the process would not
tell you whether the rule fires on the command as it is actually written, which
is the only question worth asking.

Half the cases are commands that **must be left alone**. That half is the one
that matters. `git commit -m`, `npm install`, `rm -rf ./build`, editing a file in
your own project: a rulebook that stops ordinary work gets uninstalled within a
day, and then it protects nothing.
