"""The classification rules behind the enrichment model.

`classify` is the one piece of business logic in the pipeline that someone
non-technical on your team will have an opinion about. That is exactly the kind
of thing to pin down in tests, so changing it is a conversation about rules
rather than a gamble.

These are pytest tests, not dbt unit tests. dbt unit tests do not support Python
models: dbt hands the model's source to the SQL engine, which reads the first
comment as SQL and fails with `[PARSE_SYNTAX_ERROR] Syntax error at or near '#'`.
Keeping the rules in a plain function means they are testable anyway, with no
warehouse and no credentials, which is why `model()` holds no logic of its own.
"""

import pytest
from fct_postings_enriched import DISCIPLINES, UNCLASSIFIED, classify


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Senior Data Engineer", "data"),
        ("Backend Developer (Java)", "backend"),
        ("Site Reliability Engineer / SRE", "devops"),
        ("React Native Developer", "mobile"),
        ("Sales Manager", UNCLASSIFIED),
        ("", UNCLASSIFIED),
    ],
)
def test_classify(title, expected):
    assert classify(title) == expected


def test_classify_ignores_case_and_padding():
    assert classify("   SENIOR DATA ENGINEER   ") == "data"


def test_react_native_is_mobile_not_frontend():
    """The rules are checked in order, and `react` would match this title first.
    Mobile is declared before frontend so the more specific rule wins. Plain
    React stays frontend."""
    assert classify("React Native Developer") == "mobile"
    assert classify("React Developer") == "frontend"


def test_ios_does_not_match_the_middle_of_a_word():
    """`ios` unpadded is inside "bios", so a BIOS role came out as mobile."""
    assert classify("BIOS Firmware Engineer") == UNCLASSIFIED
    assert classify("iOS Engineer") == "mobile"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # Every one of these was wrong before the rules matched whole words.
        ("JavaScript Developer", "frontend"),
        ("Senior JavaScript Engineer", "frontend"),
        ("Capital Markets Analyst", UNCLASSIFIED),
        ("Rapid Prototyping Lead", UNCLASSIFIED),
        ("Therapist", UNCLASSIFIED),
        ("Automobile Designer", UNCLASSIFIED),
        ("Ambitious Frontend Developer", "frontend"),
    ],
)
def test_keywords_match_whole_words_only(title, expected):
    """Substring matching put `api` inside "Therapist" and `java` inside
    "JavaScript". A word boundary is what stops a keyword hiding in the middle
    of an unrelated word."""
    assert classify(title) == expected


def test_punctuation_still_counts_as_a_boundary():
    """ "React.js" has no space after `react`, so space padding would miss it
    where a word boundary does not."""
    assert classify("React.js Developer") == "frontend"


def test_every_discipline_is_reachable():
    """A keyword list nothing can match is a rule that quietly does nothing."""
    for discipline, keywords in DISCIPLINES.items():
        assert classify(keywords[0]) == discipline


def test_unclassified_is_not_a_discipline():
    """`other` must stay outside the dictionary, or the fallback becomes a rule
    that shadows whichever discipline is declared after it."""
    assert UNCLASSIFIED not in DISCIPLINES
