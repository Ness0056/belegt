"""Check every sentence of an answer against the passages it cites.

This is the core of the project: an AI answer is only shown as fact if each claim can be traced
back to a source. Numbers get a strict check, because a confidently wrong number in a test report
or datasheet is the most dangerous kind of hallucination.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .store import Passage

CITE = re.compile(r"\[(\d+)\]")
NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?!\d)|\d+(?:[.,]\d+)?")
STOP = set("""
the a an and or of to in on at for with from by is are was were be been this that these those it its as
der die das und oder von zu im in am an für mit aus bei ist sind war wurde wurden ein eine einer eines den dem des
not nicht after nach before vor both beide all alle also auch
""".split())
PASS = ("passed", "bestanden")
FAIL = ("failed", "nicht bestanden", "durchgefallen")


def numbers(text: str) -> set[str]:
    """Normalise '200,000' -> '200000' and '0,2' -> '0.2' so English and German formats compare."""
    found = set()
    for n in NUMBER.findall(CITE.sub("", text)):
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", n):
            n = n.replace(",", "")
        n = n.replace(",", ".")
        found.add(str(float(n)).rstrip("0").rstrip("."))
    return found


def _stems(text: str) -> set[str]:
    words = re.findall(r"[a-zäöüß]+", text.lower())
    return {w[:5] for w in words if len(w) > 2 and w not in STOP}


def _polarity(text: str) -> set[str]:
    """Which verdicts ('pass' / 'fail') a text states."""
    t = text.lower()
    found = set()
    if any(w in t for w in FAIL):
        found.add("fail")
        t = t.replace("nicht bestanden", "")
    if any(w in t for w in PASS):
        found.add("pass")
    return found


@dataclass
class SentenceCheck:
    sentence: str
    status: str                 # OK, WEAK or FAIL
    reasons: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    status: str                 # VERIFIED, NEEDS REVIEW or REJECTED
    checks: list[SentenceCheck]


def split_sentences(answer: str) -> list[str]:
    # split after . ! ? or a citation, but not after "14." (German dates and ordinals)
    parts = re.split(r"(?<!\s\d\.)(?<!\s\d\d\.)(?<=[.!?])\s+(?=[A-ZÄÖÜ])|(?<=\])\s+(?=[A-ZÄÖÜ])", answer.strip())
    return [p.strip() for p in parts if p.strip()]


def verify(answer: str, passages: dict[int, Passage], min_overlap: float = 0.5) -> Verdict:
    checks = []
    for sentence in split_sentences(answer):
        cited = [passages[int(i)] for i in CITE.findall(sentence) if int(i) in passages]
        check = SentenceCheck(sentence, "OK")
        if not cited:
            check.status, check.reasons = "FAIL", ["no valid source cited"]
            checks.append(check)
            continue
        source = " ".join(p.text for p in cited)

        missing = numbers(sentence) - numbers(source)
        if missing:
            check.status = "FAIL"
            check.reasons.append(f"number(s) not in source: {', '.join(sorted(missing))}")

        said, actual = _polarity(sentence), _polarity(source)
        if said and actual and not said & actual:
            check.status = "FAIL"
            check.reasons.append(f"says '{'/'.join(said)}' but source says '{'/'.join(actual)}'")

        words = _stems(CITE.sub("", sentence))
        overlap = len(words & _stems(source)) / max(len(words), 1)
        if overlap < min_overlap and check.status == "OK":
            check.status = "WEAK"
            check.reasons.append(f"only {overlap:.0%} of the wording found in source")
        checks.append(check)

    if any(c.status == "FAIL" for c in checks):
        status = "REJECTED"
    elif any(c.status == "WEAK" for c in checks):
        status = "NEEDS REVIEW"
    else:
        status = "VERIFIED"
    return Verdict(status, checks)
# the verifier  is rule based strict : numbers pass or fail , wording check is leninent so rephrased answeraa gets reviewed
# limits to this model is it checks that a bumber us in the source , not what it belongs to  ... 