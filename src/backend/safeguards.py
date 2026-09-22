"""Curated emergency phrases, matched in the owner's own words.

This is phrase matching, not triage and not language understanding. It can miss a real emergency
and it can fire on misleading wording. A veterinarian would have to review both the phrases and
the notice they produce before any real-world use. The four categories come from Cornell's
emergency guidance, which does not endorse this matcher:
https://www.vet.cornell.edu/hospitals/services/emergency-and-critical-care-0

The module imports nothing from the rest of the project: what counts as a warning phrase does not
depend on how a turn is run. `workflow.py` decides which text reaches `find_emergency` and what to
do when it matches.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# Two heuristics keep the rules from firing on the wrong sentence. Both look at the words just
# before a matched phrase; neither is a parser.

# "not", "no" and friends within this many words before a phrase count as the owner denying it.
DENIAL_WINDOW_WORDS = 2
DENIAL_WORDS = frozenset(
    {
        "not",
        "no",
        "never",
        "nothing",
        "without",
        "don't",
        "doesn't",
        "didn't",
        "isn't",
        "wasn't",
        "hasn't",
        "haven't",
        "hadn't",
        "aren't",
        "weren't",
    }
)

# Skipped while looking back for who the matched verb is about: "she has suddenly collapsed".
FILLER_WORDS = frozenset(
    {"has", "have", "had", "is", "was", "been", "being", "just", "suddenly", "now", "then",
     "also", "again", "already", "apparently"}
)

# Who counts as the pet in "<subject> collapsed".
PET_WORDS = frozenset(
    {"dog", "dogs", "cat", "cats", "puppy", "kitten", "pet", "she", "he", "it", "they", "her",
     "him", "them"}
)

_WORD = re.compile(r"[a-z']+")


@dataclass(frozen=True)
class EmergencyRule:
    """One warning category and the phrases that count as reporting it."""

    name: str
    patterns: tuple[re.Pattern[str], ...]
    # On by default: "is not having difficulty breathing" must not escalate.
    honour_denials: bool = True
    # Only fires when the pet is the subject, so "the sofa collapsed near my dog" does not match.
    needs_pet_subject: bool = False


@dataclass(frozen=True)
class EmergencyMatch:
    """Which rule fired, and the phrase that fired it."""

    rule: str
    phrase: str


def _compile(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


EMERGENCY_RULES: tuple[EmergencyRule, ...] = (
    EmergencyRule(
        name="breathing_difficulty",
        patterns=_compile(
            r"struggl\w*\s+to\s+breathe",
            r"(?:difficulty|trouble|struggling|problems?)\s+breathing",
            r"(?:can'?t|cannot|can\s+not|unable\s+to)\s+breathe",
            r"(?:stopped|not)\s+breathing",
            r"gasping\s+for\s+(?:air|breath)",
            r"labou?red\s+breathing",
        ),
    ),
    EmergencyRule(
        name="collapse",
        patterns=_compile(
            r"collaps\w+",
            r"passed\s+out",
            r"unresponsive",
            r"fainted",
        ),
        needs_pet_subject=True,
    ),
    EmergencyRule(
        name="suspected_ingestion",
        # The phrase must name a substance, and denials are ignored on purpose: "I don't think
        # she swallowed any pills, but the packet is open" is uncertainty, not an all-clear. The
        # ASPCA advises contacting a vet or poison control for suspected ingestion:
        # https://www.aspca.org/pet-care/general-pet-care/emergency-care-your-pet
        patterns=_compile(
            r"(?:swallow\w*|ingest\w*|ate|eaten|chewed|got\s+into)\b[^.!?]{0,40}?\b"
            r"(?:medication|medicine|pills?|tablets?|capsules?|poison\w*|toxin\w*|"
            r"rat\s+bait|antifreeze|chocolate|xylitol|batter(?:y|ies)|drugs?)",
        ),
        honour_denials=False,
    ),
    EmergencyRule(
        name="cannot_urinate",
        patterns=_compile(
            r"(?:can'?t|cannot|can\s+not|unable\s+to|trying\s+to|straining\s+to|struggling\s+to)"
            r"[^.!?]{0,20}?\b(?:urinate|pee|wee|pass\s+urine)",
            r"(?:no|not\s+any)\s+urine",
            r"blocked\s+bladder",
        ),
    ),
)


def _words_before(text: str, index: int) -> list[str]:
    return _WORD.findall(text[:index].lower())


def _is_denied(text: str, phrase_start: int) -> bool:
    return any(
        word in DENIAL_WORDS
        for word in _words_before(text, phrase_start)[-DENIAL_WINDOW_WORDS:]
    )


def _subject_is_the_pet(text: str, phrase_start: int) -> bool:
    for word in reversed(_words_before(text, phrase_start)):
        if word in FILLER_WORDS:
            continue
        return word in PET_WORDS
    return False  # nothing before the phrase, so nobody was named


def _match_in(rule: EmergencyRule, text: str) -> EmergencyMatch | None:
    for pattern in rule.patterns:
        for found in pattern.finditer(text):
            if rule.honour_denials and _is_denied(text, found.start()):
                continue
            if rule.needs_pet_subject and not _subject_is_the_pet(text, found.start()):
                continue
            return EmergencyMatch(rule=rule.name, phrase=found.group(0))
    return None


def find_emergency(texts: Iterable[str]) -> EmergencyMatch | None:
    """Return the first rule that fires across `texts`, in the order given, or `None`.

    Pass only owner-written text. Scanning the assistant's own questions would let the demo
    escalate on wording it produced itself.
    """
    for text in texts:
        for rule in EMERGENCY_RULES:
            match = _match_in(rule, text)
            if match is not None:
                return match
    return None
