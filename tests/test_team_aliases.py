"""
tests/test_team_aliases.py
───────────────────────────
Cross-source team-name canonicalization. Without this, the same country
splits into multiple rows across openfootball / football-data / StatsBomb /
Kaggle, fragmenting every chart.
"""
import pytest

from data.transform.team_aliases import canonicalize

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("raw,canonical", [
    ("USA", "United States"),
    ("Czechia", "Czech Republic"),
    ("Bosnia-Herzegovina", "Bosnia & Herzegovina"),
    ("Cape Verde Islands", "Cape Verde"),
    ("Congo DR", "DR Congo"),
    ("Türkiye", "Turkey"),
    ("Korea Republic", "South Korea"),
])
def test_known_aliases(raw, canonical):
    assert canonicalize(raw) == canonical


@pytest.mark.parametrize("mojibake,canonical", [
    ("C?te d'Ivoire", "Ivory Coast"),
    ("Cura?ao", "Curaçao"),
    ("T?rkiye", "Turkey"),
])
def test_kaggle_mojibake(mojibake, canonical):
    assert canonicalize(mojibake) == canonical


def test_unknown_passes_through():
    assert canonicalize("Brazil") == "Brazil"


def test_knockout_placeholder_passes_through():
    # '2A', 'W73' etc must survive untouched for bracket resolution.
    assert canonicalize("2A") == "2A"
    assert canonicalize("W73") == "W73"


def test_strips_whitespace():
    assert canonicalize("  USA  ") == "United States"


def test_handles_none_and_empty():
    assert canonicalize(None) is None
    assert canonicalize("") == ""
