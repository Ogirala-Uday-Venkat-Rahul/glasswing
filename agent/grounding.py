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

Two allowances keep it from crying wolf on legitimate answers:
  - Rounding: the model routinely rounds ("about 62 miles" for 62.14). We accept
    a number when it is the actual rounding of a source number to the answer's
    own precision -- but NOT when it is merely close, so a wrong-but-near figure
    is still flagged.
  - Magnitude words: "$1.2 million" is expanded to 1200000 before comparing, so a
    spelled magnitude still matches the plain number a tool returned.

The structure generalises. Today it extracts numbers; the same shape (pull a
claim out of the answer, confirm it appears in the evidence) would extend to
cited URLs or named people if we ever see those failures.
"""

import re

# A run of digits, optionally with thousands commas and a decimal part:
# matches 1299, 1,299, and 1,299.00.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Magnitude words the model writes in place of trailing zeros ("$1.2 million").
# We expand these to the full number before comparing. Limited to unambiguous
# forms -- the full words plus "k" -- and deliberately not bare "m"/"b", which
# collide with metres and other units.
_MAGNITUDE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion|k)\b", re.IGNORECASE
)
_MULTIPLIER = {
    "thousand": 1_000,
    "k": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}


def _expand_magnitudes(text: str) -> str:
    """Rewrite "1.2 million" as "1200000" so magnitudes compare as plain numbers."""

    def repl(match: re.Match) -> str:
        value = float(match.group(1).replace(",", "")) * _MULTIPLIER[match.group(2).lower()]
        return str(int(value)) if value == int(value) else str(value)

    return _MAGNITUDE.sub(repl, text)


def _normalize(raw: str) -> str:
    """Reduce a number to a canonical form so 1,299 == 1299 == 1299.00.

    Strips thousands commas, then trims a trailing decimal so 1299.00 and 1299
    compare equal (while 19.99 keeps its cents).
    """
    n = raw.replace(",", "")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def _decimals(norm: str) -> int:
    """How many decimal places a normalized number carries (62 -> 0, 62.1 -> 1)."""
    return len(norm.split(".")[1]) if "." in norm else 0


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


def _supported(norm: str, exact: set[str], values: list[float]) -> bool:
    """True if this answer number matches a source number exactly or as a rounding.

    Exact match is the common case. Otherwise we accept the number only if it is
    the actual rounding of some source number to the answer's own precision:
    "62" is allowed by "62.14" because round(62.14) == 62. This deliberately does
    NOT accept a number that is merely close -- "1199" is not the rounding of
    "1299" to any precision, so a wrong-but-near figure is still flagged.
    """
    if norm in exact:
        return True
    target = float(norm)
    places = _decimals(norm)
    return any(abs(round(value, places) - target) < 1e-9 for value in values)


def ground_answer(answer: str, evidence: str, asked: str = "") -> str:
    """Return the answer, appending a caution note for any unsupported numbers.

    evidence is the concatenated text the tools returned this run. If it is
    empty the model never retrieved anything, so there is nothing to check
    against and we leave the answer untouched rather than flag every figure.

    asked is the user's own question. Numbers the user supplied there count as
    supported: echoing back a figure the user gave us (like the operands in
    "4823 * 197") is not a hallucination, and a tool result only carries the
    answer it computed, not the inputs. We still key the whole check off tool
    evidence, so a plain knowledge answer with no tools is left untouched.
    """
    if not evidence.strip():
        return answer

    supported_text = _expand_magnitudes(evidence + "\n" + asked)
    exact = _numbers(supported_text)
    values = [float(n) for n in exact]

    answer_text = _expand_magnitudes(answer)
    unverified = []
    seen = set()
    for match in _NUMBER.finditer(answer_text):
        norm = _normalize(match.group())
        if len(norm.replace(".", "")) < 2:
            continue
        if norm in seen or _supported(norm, exact, values):
            continue
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
