"""A deterministic check that the answer's numbers came from the sources.

The model sometimes states a figure the search results never supported (it once
said a MacBook was $1,099 when the results said "From $1299"). This catches that
without a second model call: we already gathered the evidence during the run, so
we just check every number in the answer actually appears in that evidence.

Pure Python, zero tokens, and it cannot itself hallucinate -- a number is either
in the gathered text or it isn't. It is a guardrail for exact figures like
prices, not a universal truth detector: a figure the model *computed* (e.g. two
items summed) or a claim that was paraphrased is out of scope, so we deliberately
keep it narrow to avoid crying wolf.

The structure generalises. Today it extracts numbers; the same shape (pull a
claim out of the answer, confirm it appears in the evidence) would extend to
cited URLs or named people if we ever see those failures.
"""

import re

# A run of digits, optionally with thousands commas and a decimal part:
# matches 1299, 1,299, and 1,299.00.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _normalize(raw: str) -> str:
    """Reduce a number to a canonical form so 1,299 == 1299 == 1299.00.

    Strips thousands commas, then trims a trailing decimal so 1299.00 and 1299
    compare equal (while 19.99 keeps its cents).
    """
    n = raw.replace(",", "")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def _numbers(text: str) -> set[str]:
    """Every meaningful number in a blob of text, normalized.

    Single-digit numbers are dropped as noise: things like "M3" or "iPhone 5"
    would otherwise flag constantly and teach the user to ignore the warning.
    """
    found = set()
    for match in _NUMBER.finditer(text):
        norm = _normalize(match.group())
        if len(norm.replace(".", "")) >= 2:
            found.add(norm)
    return found


def ground_answer(answer: str, evidence: str) -> str:
    """Return the answer, appending a caution note for any unsupported numbers.

    evidence is the concatenated text the tools returned this run. If it is
    empty the model never retrieved anything, so there is nothing to check
    against and we leave the answer untouched rather than flag every figure.
    """
    if not evidence.strip():
        return answer

    supported = _numbers(evidence)
    unverified = []
    seen = set()
    for match in _NUMBER.finditer(answer):
        norm = _normalize(match.group())
        if len(norm.replace(".", "")) < 2:
            continue
        if norm not in supported and norm not in seen:
            unverified.append(match.group())
            seen.add(norm)

    if not unverified:
        return answer

    figures = ", ".join(unverified)
    note = (
        f"\n\nNote: I couldn't confirm these figures from my sources "
        f"({figures}) - please double-check them."
    )
    return answer + note
