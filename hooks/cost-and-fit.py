#!/usr/bin/env python3
"""CMFA-01 — Cost & Model-Fit Accountability, as a hook.

Reporting only. Never changes a model, effort, or setting. It surfaces
information; the operator decides. (CMFA-01 status line, and CMFA-01.7.)

TWO TRIGGERS
    user-prompt-submit   classify the shape of what was just asked, compare it
                         to the model actually running, speak ONLY when the
                         verdict changes
    stop                 after Claude finishes, report real spend if the task
                         was big enough to be worth reporting

WHY IT SPEAKS SO RARELY
    CMFA-01.1: "Between triggers, stay silent about cost." The operator's own
    coach rule: "never repeat a nudge I've already declined, stay silent when the
    fit is already right." So this watches every message and reports on almost
    none of them. A nudge that fires every turn stops being read, which is the
    same failure as a warning that never changes.

    Declines are remembered. CMFA-01.7: a recommendation the operator explicitly
    declined is a decision, note it once and move on.

INDEPENDENT OF THE SKILL  (deliberate departure from CMFA-01.8)
    CMFA-01.8 says measurement depends on the skill package and that without it
    every figure drops to [ESTIMATED]. That is not true for a hook: the numbers
    come from the transcript Claude Code writes itself, and the price table is
    four rows. Both live here. Nothing is imported, nothing breaks if the skill
    is uninstalled, and figures stay [MEASURED].

WHAT IT WILL NOT DO
    Report a cost at session start. CMFA-01.0 forbids stating a figure not
    computed from a real token count, and at session open that count is zero.
    Fit can be judged from the first prompt; spend cannot. Anything else would
    be a made-up number wearing a measurement's clothes.

FIGURE TAGS (CMFA-01.0)
    Token counts [MEASURED] from the transcript's own usage fields.
    Dollars [DERIVED] by arithmetic on those counts with the table below.
    Tags are never spoken aloud (CMFA-01.2); they govern which figures are
    trustworthy, not how they are phrased.
"""

import json
import os
import re
import sys
import time
from decimal import Decimal, ROUND_HALF_UP

# ── price table, per million tokens. CMFA-01.5 ───────────────────────────────
# Kept here on purpose so the hook has no external dependency. If this and the
# skill's cost-model.md ever disagree, the skill's copy wins and this is stale.
#
# Decimal, not float: money. Keyed by exact version, not substring, because
# substring matching prices Opus 4.1 ($15/$75) at Opus 5's rate ($5/$25) and
# under-reports by two thirds without ever saying so.
RATES = {
    "fable-5":   (Decimal("10"), Decimal("50")),
    "opus-5":    (Decimal("5"),  Decimal("25")),
    "opus-4.8":  (Decimal("5"),  Decimal("25")),
    "opus-4.6":  (Decimal("5"),  Decimal("25")),
    "opus-4.5":  (Decimal("5"),  Decimal("25")),
    "opus-4.1":  (Decimal("15"), Decimal("75")),
    "opus-4":    (Decimal("15"), Decimal("75")),
    "sonnet-5":  (Decimal("3"),  Decimal("15")),
    "sonnet-4.6": (Decimal("3"), Decimal("15")),
    "sonnet-4.5": (Decimal("3"), Decimal("15")),
    "haiku-4.5": (Decimal("1"),  Decimal("5")),
    "haiku-3.5": (Decimal("0.8"), Decimal("4")),
}

# Sonnet 5 introductory pricing, $2/$10, runs through 2026-08-31. The table above
# carries the STANDARD rate on purpose: quoting the intro rate as if permanent
# under-reports by a third the moment it lapses, and a stale price stated as
# current is the same error class as a fabricated one (CMFA-01.5).
SONNET5_INTRO_UNTIL = "2026-08-31"
SONNET5_INTRO = (Decimal("2"), Decimal("10"))

CACHE_READ_MULT = Decimal("0.10")
CACHE_WRITE_5M_MULT = Decimal("1.25")
CACHE_WRITE_1H_MULT = Decimal("2.00")


def _rate_for(model_id):
    """Exact version match. Returns None for an unknown model rather than
    guessing: no figure beats a wrong one (CMFA-01.0)."""
    toks = [t for t in re.split(r"[^a-z0-9]+", (model_id or "").lower()) if t]
    fam = None
    for i, t in enumerate(toks):
        if t in ("fable", "opus", "sonnet", "haiku"):
            fam = i
    if fam is None or fam + 1 >= len(toks) or not toks[fam + 1].isdigit():
        return None
    major = toks[fam + 1]
    minor = None
    if fam + 2 < len(toks):
        c = toks[fam + 2]
        # <=2 digits is a minor version; 8 digits is a release date suffix.
        if c.isdigit() and len(c) <= 2:
            minor = c
    key = f"{toks[fam]}-{major}" + (f".{minor}" if minor else "")
    rate = RATES.get(key)
    if rate and key == "sonnet-5" and time.strftime("%Y-%m-%d") <= SONNET5_INTRO_UNTIL:
        return SONNET5_INTRO
    return rate

TIER_ORDER = ["haiku", "sonnet", "opus", "fable"]
PRETTY = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus", "fable": "Fable"}

# Only report spend once a task is big enough to be worth interrupting for.
# CMFA-01.1 trigger 1: ">~3 tool calls or >~500 words of output".
MIN_OUTPUT_TOKENS = 700

def _state_file():
    """Durable, and out of the hooks folder so it never looks like a hook.

    CLAUDE_CONFIG_DIR is honoured when set, so a relocated Claude config takes
    its state with it.
    """
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    base = os.path.expanduser(base) if base else os.path.expanduser("~/.claude")
    return os.path.join(base, "cmfa", "cost-and-fit-state.json")


STATE = _state_file()


# ── shape classification (CMFA-01.3: route by shape, never topic) ────────────
# A keyword heuristic, not a model. It is deliberately conservative: when the
# signal is weak it returns None and the hook stays silent, because a wrong
# nudge costs more trust than a missed one.
MECHANICAL = re.compile(r"\b(rename|list|count|extract|convert|reformat|"
                        r"find and replace|search for|grep|tidy|sort|dedupe|"
                        r"strip|bulk|batch|for each|one by one)\b", re.I)
DRAFTING = re.compile(r"\b(summari[sz]e|draft|write|rewrite|explain|describe|"
                      r"read|check|look at|show me|open|compare|document)\b", re.I)
HARD = re.compile(r"\b(design|architect|debug|diagnose|why does|why is|refactor|"
                  r"audit|review|trace|root cause|figure out|work out|prove)\b", re.I)
LONG_HORIZON = re.compile(r"\b(migrate|across the (whole|entire)|end.to.end|"
                          r"the whole (repo|codebase|workspace)|every file|"
                          r"rebuild|redesign the|from scratch)\b", re.I)


def shape_of(prompt):
    """Return a tier key, or None when the signal is too weak to act on."""
    p = (prompt or "").strip()
    if len(p) < 12:
        return None
    if LONG_HORIZON.search(p):
        return "fable"
    if HARD.search(p):
        return "opus"
    if MECHANICAL.search(p) and not HARD.search(p):
        return "haiku"
    if DRAFTING.search(p):
        return "sonnet"
    return None


def tier_of(model_id):
    low = (model_id or "").lower()
    for t in TIER_ORDER:
        if t in low:
            return t
    return None


# ── measurement ──────────────────────────────────────────────────────────────
def read_usage(path):
    if not path or not os.path.exists(path):
        return None
    models, turns = {}, 0
    acc = {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0}
    known = {"in": True, "out": True, "cache_read": True, "cache_write": True}
    cw5 = cw1 = 0
    split_ok = True
    # Deduplicate by API message id. Claude Code can write more than one record
    # for the same assistant message; counting each one inflates every figure.
    seen = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f):
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                msg = o.get("message") or {}
                u = msg.get("usage") or {}
                if not u:
                    continue
                key = msg.get("id") or o.get("requestId") or o.get("uuid") or f"line-{n}"
                if key in seen:
                    continue
                seen.add(key)
                turns += 1
                m = msg.get("model") or "unknown"
                models[m] = models.get(m, 0) + 1

                # A missing field is unknown, not zero. Treating it as zero
                # quietly under-reports and the figure still looks measured.
                for name, key in (("in", "input_tokens"),
                                  ("out", "output_tokens"),
                                  ("cache_read", "cache_read_input_tokens"),
                                  ("cache_write", "cache_creation_input_tokens")):
                    v = u.get(key)
                    if isinstance(v, int) and not isinstance(v, bool) and v >= 0:
                        acc[name] += v
                    else:
                        known[name] = False

                # Claude Code reports the 5-minute and 1-hour cache writes
                # separately when it has them. They bill at 1.25x and 2.0x, so
                # collapsing them under-reports any session that used the long
                # cache. When the split is absent or does not reconcile, fall
                # back to the conservative 5-minute rate and say nothing false.
                cc = u.get("cache_creation")
                tot_w = u.get("cache_creation_input_tokens")
                if isinstance(cc, dict):
                    w5 = cc.get("ephemeral_5m_input_tokens")
                    w1 = cc.get("ephemeral_1h_input_tokens")
                    if (isinstance(w5, int) and isinstance(w1, int)
                            and w5 >= 0 and w1 >= 0
                            and (not isinstance(tot_w, int) or w5 + w1 == tot_w)):
                        cw5 += w5
                        cw1 += w1
                    else:
                        split_ok = False
                elif tot_w:
                    split_ok = False
    except Exception:
        return None
    if not turns:
        return None
    return {"models": models, "turns": turns,
            "in": acc["in"], "out": acc["out"],
            "cache_read": acc["cache_read"], "cache_write": acc["cache_write"],
            "cache_write_5m": cw5, "cache_write_1h": cw1,
            "split_known": split_ok,
            "known": known,
            "total": sum(acc.values())}


def cost_usd(d):
    """[DERIVED]. Split across models by share of turns; a session that ran two
    tiers is not billed at either one's rate."""
    if not d:
        return None
    # CMFA-01.0 is fail-closed: if any component was never measured, there is no
    # honest total. Say "not determinable" rather than a number missing a piece.
    if not all(d.get("known", {}).values()):
        return None

    tt = Decimal(sum(d["models"].values()) or 1)
    M = Decimal(1_000_000)
    usd = Decimal(0)
    for mid, n in d["models"].items():
        rate = _rate_for(mid)
        if not rate:
            return None              # unknown model: no figure beats a wrong one
        ir, orate = rate
        share = Decimal(n) / tt
        usd += (Decimal(d["in"]) * share / M) * ir
        usd += (Decimal(d["out"]) * share / M) * orate
        usd += (Decimal(d["cache_read"]) * share / M) * ir * CACHE_READ_MULT

        if d.get("split_known") and (d.get("cache_write_5m") or d.get("cache_write_1h")):
            usd += (Decimal(d["cache_write_5m"]) * share / M) * ir * CACHE_WRITE_5M_MULT
            usd += (Decimal(d["cache_write_1h"]) * share / M) * ir * CACHE_WRITE_1H_MULT
        else:
            # No usable split: price at the 5-minute rate. Conservative, and the
            # only alternative is inventing a ratio.
            usd += (Decimal(d["cache_write"]) * share / M) * ir * CACHE_WRITE_5M_MULT
    return usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def subtract_usage(current, previous):
    """current minus previous, for reporting 'this reply' instead of the whole
    session. Model turn-counts are subtracted per model so cost_usd's per-model
    split still applies to just the delta, not the whole thread."""
    if not current:
        return None
    if not previous:
        return current
    models = {}
    for mid, n in current.get("models", {}).items():
        d = n - previous.get("models", {}).get(mid, 0)
        if d > 0:
            models[mid] = d
    if not models:
        return None
    out = {"models": models,
           "turns": max(0, current["turns"] - previous.get("turns", 0)),
           "in": max(0, current["in"] - previous.get("in", 0)),
           "out": max(0, current["out"] - previous.get("out", 0)),
           "cache_read": max(0, current["cache_read"] - previous.get("cache_read", 0)),
           "cache_write": max(0, current["cache_write"] - previous.get("cache_write", 0)),
           "cache_write_5m": max(0, current.get("cache_write_5m", 0) - previous.get("cache_write_5m", 0)),
           "cache_write_1h": max(0, current.get("cache_write_1h", 0) - previous.get("cache_write_1h", 0)),
           "split_known": current.get("split_known", True) and previous.get("split_known", True),
           "known": current.get("known", {})}
    out["total"] = out["in"] + out["out"] + out["cache_read"] + out["cache_write"]
    return out


def running_tier(d):
    if not d or not d["models"]:
        return None
    return tier_of(max(d["models"].items(), key=lambda kv: kv[1])[0])


def find_transcript(inp):
    tp = inp.get("transcript_path")
    if tp and os.path.exists(tp):
        return tp
    sid = inp.get("session_id")
    if sid:
        import glob
        hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{sid}.jsonl"))
        if hits:
            return hits[0]
    return None


# ── state: what we already said, and what was declined ───────────────────────
def load(sid):
    # A missing or unreadable state file means "nothing said yet", never an
    # error: the hook must never break a session over its own bookkeeping.
    try:
        with open(STATE) as f:
            d = json.load(f) or {}
        return d.get(sid, {})
    except Exception:
        return {}


def save(sid, patch):
    try:
        all_ = {}
        if os.path.exists(STATE):
            with open(STATE) as f:
                all_ = json.load(f) or {}
        today = time.strftime("%Y-%m-%d")
        all_ = {k: v for k, v in all_.items() if v.get("day") == today}   # self-pruning
        rec = all_.get(sid, {})
        rec.update(patch)
        rec["day"] = today
        all_[sid] = rec
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w") as f:
            json.dump(all_, f, indent=2)
    except Exception:
        pass


def pick(sid, bucket, options):
    """Choose the next phrasing WITHOUT committing to it.

    CMFA-01.2: rotate, never the same sentence twice running. Split from the
    commit on 2026-08-26: the old version advanced the counter the moment a
    line was chosen, including on the many turns where the hook then decided to
    stay silent. Variants were being consumed without ever being seen, so the
    rotation skipped. Call commit() only once a message is genuinely emitted.
    """
    st = load(sid)
    i = (st.get(f"rot_{bucket}", -1) + 1) % len(options)
    return options[i], i


def commit(sid, bucket, i):
    save(sid, {f"rot_{bucket}": i})


def rotate(sid, bucket, options):
    """Back-compat shim: pick and commit in one step, for call sites that always
    emit what they pick."""
    line, i = pick(sid, bucket, options)
    commit(sid, bucket, i)
    return line


PRICING_HELP_RE = re.compile(
    r"^(?:how (?:does|do) (?:the |cmfa )?(?:pricing|cost(?:ing)?) work|"
    r"explain (?:the |cmfa )?(?:pricing|cost(?:ing)?)|"
    r"what (?:is|are) (?:the |cmfa )?(?:pricing|rates?|standard[- ]rate equivalent)|"
    r"how (?:is|do you) (?:the )?cost (?:calculated|worked out)|"
    r"where does that number come from)$",
    re.IGNORECASE,
)

_POLITE_PREFIXES = ("can you please ", "could you please ", "would you please ",
                    "can you ", "could you ", "would you ", "please ", "tell me ")


def is_pricing_question(prompt):
    """True only when the WHOLE message is the question.

    Was a loose re.search once. Then someone pasted a script that happened to
    contain the literal string 'How does the pricing work?' inside its own test
    fixtures, and the hook fired a pricing card at a message that was asking for
    a code review. A substring match on a 40KB paste is not a question, it is a
    coincidence.
    """
    if not isinstance(prompt, str) or len(prompt) > 240:
        return False
    t = " ".join(re.sub(r"[^a-z0-9 -]+", " ", prompt.lower()).split())
    changed = True
    while changed:
        changed = False
        for pre in _POLITE_PREFIXES:
            if t.startswith(pre):
                t = t[len(pre):].strip()
                changed = True
                break
    return bool(PRICING_HELP_RE.fullmatch(t))


def pricing_help(model_id):
    """Answer 'how does the pricing work' using the model actually running.

    Rates for cache are multipliers on the input rate, not separate published
    numbers, so they are derived here rather than stored: read 0.1x, 5-minute
    write 1.25x, 1-hour write 2.0x (CMFA-01.5).
    """
    rate = _rate_for(model_id)
    head = (
        "Every number comes from the token counts Claude Code already writes into "
        "the transcript. Nothing is estimated. The sum is: input + output + cache "
        "reads + cache writes, each at that model's rate."
    )
    if not rate:
        return (head + " Right now the model is not identifiable, so cost is not "
                "determinable this session.")

    ir, orate = rate
    name = PRETTY.get(tier_of(model_id), "this model")
    intro = ""
    if tier_of(model_id) == "sonnet" and time.strftime("%Y-%m-%d") <= SONNET5_INTRO_UNTIL:
        intro = (f" Sonnet is on introductory pricing until {SONNET5_INTRO_UNTIL}; "
                 "after that it goes to $3 and $15 and the same work costs more.")

    return (
        f"{head}\n\n"
        f"For {name}, per million tokens: ${ir} in, ${orate} out, "
        f"${ir * CACHE_READ_MULT:.2f} for cache reads, "
        f"${ir * CACHE_WRITE_5M_MULT:.2f} for 5-minute cache writes, "
        f"${ir * CACHE_WRITE_1H_MULT:.2f} for 1-hour cache writes.\n\n"
        "Two things worth knowing: output costs five times input on every model, "
        "and cache reads are a tenth of the price, which is why a long thread is "
        "cheap to re-read but expensive to keep growing."
        + intro +
        "\n\nThese are list rates, used as a yardstick. On a Pro or Max plan nothing "
        "here is billed to you; it measures how fast you are spending your limit."
    )


DECLINE = re.compile(r"\b(no|don'?t|leave it|stay|keep .*(model|it)|not now|"
                     r"stop asking|i know)\b", re.I)


# ── the two triggers ─────────────────────────────────────────────────────────
def on_prompt(inp):
    sid = inp.get("session_id", "")
    prompt = (inp.get("prompt") or "").strip()
    st = load(sid)

    # A decline is a decision, not a pause. CMFA-01.7.
    if st.get("pending") and DECLINE.search(prompt) and len(prompt) < 60:
        save(sid, {"declined": st["pending"], "pending": None})
        sys.exit(0)

    d = read_usage(find_transcript(inp))

    # A direct question about pricing outranks everything else, and is the one
    # case where speaking is always right (CMFA-01.1 trigger 4, "on request").
    if is_pricing_question(prompt):
        mid = max(d["models"].items(), key=lambda kv: kv[1])[0] if d and d["models"] else None
        save(sid, {"last_report_signature": "help:pricing"})
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext":
                "💰 PRICING · they asked how it works\n" + pricing_help(mid) +
                "\n\nAnswer with this, in your own words, in their voice. Keep it short. "
                "Do not paste it back verbatim and do not turn it into a table unless asked."
        }}))
        sys.exit(0)

    want = shape_of(prompt)
    if not want:
        sys.exit(0)                                  # weak signal, say nothing

    have = running_tier(d)
    if not have or want == have:
        save(sid, {"last_want": want})
        sys.exit(0)                                  # fit is right: stay silent

    # Already said this, or already told no.
    if st.get("last_flagged") == want or st.get("declined") == want:
        sys.exit(0)

    save(sid, {"last_flagged": want, "pending": want, "last_want": want})

    hi, lo = PRETTY[have], PRETTY[want]
    down = TIER_ORDER.index(want) < TIER_ORDER.index(have)

    # Offered, never imposed. CMFA-01.7 forbids changing the model itself, and a
    # hook that blocked the prompt to ask would make the cheap path the annoying
    # one. Told once, given the command, and the work proceeds regardless.
    if down:
        line, ri = pick(sid, "mismatch", [
            f"This is {lo} work, you're on {hi}.",
            f"This is {lo} work, you're on {hi}.",
        ])
    else:
        line, ri = pick(sid, "upshift", [
            f"This is {lo} work, you're on {hi}.",
            f"This is {lo} work, you're on {hi}.",
        ])
    commit(sid, "mismatch" if down else "upshift", ri)

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext":
            "💰 COST & FIT\n"
            f"   💸 {line}\n"
            f"      Switch: `/model {want}`\n\n"
            "Print those three lines verbatim at the TOP of your reply, before anything "
            "else, then do the work on the model you are actually running. Do not wait "
            "for an answer, do not ask a question, do not mention it again this session."
    }}))
    sys.exit(0)


def on_stop(inp):
    sid = inp.get("session_id", "")
    d = read_usage(find_transcript(inp))
    if not d:
        sys.exit(0)

    st = load(sid)
    out_since = d["out"] - st.get("reported_out", 0)
    if out_since < MIN_OUTPUT_TOKENS:
        sys.exit(0)                     # too small to be worth interrupting for

    session_usd = cost_usd(d)
    if session_usd is None:
        sys.exit(0)                     # CMFA-01.0: no honest figure, no report

    # "This reply" is the delta since the last report, not the whole thread.
    # Asked directly whether the number meant one prompt or the whole session,
    # the answer is both, always labelled, never one bare figure.
    prev = st.get("last_usage_snapshot")
    delta = subtract_usage(d, prev) if prev else None
    reply_usd = cost_usd(delta) if delta else None

    save(sid, {"reported_out": d["out"], "last_usage_snapshot": d})

    have = running_tier(d)
    name = PRETTY.get(have, "this model")

    # "this thread", never "session": people read "session so far" as a running
    # total across days. It is one conversation, and saying so is the difference
    # between a number they trust and one they argue with.
    if reply_usd is not None:
        both = f"${reply_usd:,.2f} this reply · ${session_usd:,.2f} this thread"
    else:
        both = f"${session_usd:,.2f} so far"

    models = " + ".join(PRETTY[t] for t in
                        dict.fromkeys(tier_of(m) for m in d["models"]) if t)
    models = models or name

    cw_share = d["cache_write"] / d["total"] if d["total"] else 0
    cr_share = d["cache_read"] / d["total"] if d["total"] else 0
    wanted = st.get("last_want")

    # Order matters. The true cause first, the model second. CMFA-01.4 lever 0:
    # once the thread itself dominates, no model change reaches the cost, and
    # saying "switch models" there would be advice that cannot work.
    if cw_share + cr_share > 0.85 and session_usd > 20:
        pct = min(99, round((cw_share + cr_share) * 100))
        line, ri = pick(sid, "hygiene", [
            f"🔥 {both}. {pct}% of that bought memory, not work. `/clear` before the next thing.",
            f"🔥 {both}. You're paying rent on this conversation now. A fresh thread is the only lever left.",
            f"🔥 {both}. The thread is the bill. The model barely shows up. `/clear`.",
            f"🔥 {both}. {pct}% went on re-reading what we already said. No model fixes that.",
        ])
        bucket = "hygiene"
    elif wanted and wanted != have:
        line, ri = pick(sid, "wrong", [
            f"💸 {both} · {PRETTY[wanted]} work, {models} prices.",
            f"💸 {both} · {models} took the long way round.",
            f"💸 {both} · {PRETTY[wanted]} would have shrugged at that.",
            f"💸 {both} · paid for judgment, used muscle memory.",
        ])
        bucket = "wrong"
    else:
        line, ri = pick(sid, "good", [
            f"✅ {both} · {models}, and it needed to be.",
            f"✅ {both} · {models} earned it.",
            f"✅ {both} · right tool, no notes.",
            f"✅ {both} · well spent.",
            f"✅ {both} · nothing to fix here.",
        ])
        bucket = "good"
    commit(sid, bucket, ri)

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "Stop",
        "additionalContext":
            f"💰 COST & FIT\n   {line}\n\n"
            "Print the two lines above verbatim, once, at the very end of your reply. "
            "EXACTLY ONE cost card per reply. Cards from earlier turns are already in the "
            "conversation and must never be repeated: this one supersedes every previous "
            "one. Do not paraphrase, do not drop the header, do not add commentary after it."
    }}))
    sys.exit(0)


def _paused():
    """`install.py stop` writes this file. Checked before anything else so a
    pause costs nothing and cannot fail: no transcript is read, no state is
    written, and an unreadable flag simply means not paused."""
    try:
        return os.path.exists(os.path.join(os.path.dirname(STATE), "paused"))
    except Exception:
        return False


def main():
    if _paused():
        sys.exit(0)
    try:
        raw = sys.stdin.read()
        inp = json.loads(raw) if raw.strip() else {}
    except Exception:
        sys.exit(0)
    ev = (inp.get("hook_event_name") or "").lower()
    if "userpromptsubmit" in ev:
        on_prompt(inp)
    elif ev == "stop":
        on_stop(inp)
    sys.exit(0)


if __name__ == "__main__":
    main()
