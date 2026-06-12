"""
data/transform/team_aliases.py
───────────────────────────────
Canonical team naming across the three data sources.

The same country is spelled differently by each source:

    openfootball      football-data.org     StatsBomb
    USA               United States         United States
    Czech Republic    Czechia               —
    Bosnia & Herz.    Bosnia-Herzegovina    —
    Cape Verde        Cape Verde Islands    —
    DR Congo          Congo DR              —

Without normalization each spelling becomes its own row in `teams`,
splitting one country's data across two identities in every BI chart.
Apply `canonicalize()` to every team name at every ingest boundary.

Canonical forms favor common English usage; "United States" is kept
(over "USA") because historical StatsBomb data already uses it.
"""

_ALIASES: dict[str, str] = {
    # openfootball → canonical
    "USA":                 "United States",
    # football-data.org → canonical
    "Czechia":             "Czech Republic",
    "Bosnia-Herzegovina":  "Bosnia & Herzegovina",
    "Cape Verde Islands":  "Cape Verde",
    "Congo DR":            "DR Congo",
    # StatsBomb variants seen in older seasons
    "IR Iran":             "Iran",
    "Korea Republic":      "South Korea",
    "Korea DPR":           "North Korea",
    "China PR":            "China",
    "Côte d'Ivoire":       "Ivory Coast",
    # FIFA's official rebrand; openfootball/StatsBomb still use "Turkey"
    "Türkiye":             "Turkey",
    # Kaggle "Road to 2026" CSV ships with mojibake — literal '?' bytes
    # where non-ASCII characters were corrupted at export time.
    "C?te d'Ivoire":       "Ivory Coast",
    "Cura?ao":             "Curaçao",
    "T?rkiye":             "Turkey",
}


def canonicalize(name: str | None) -> str | None:
    """
    Map any source spelling to the canonical team name.
    Unknown names (and knockout placeholders like '2A') pass through.
    """
    if not name:
        return name
    return _ALIASES.get(name.strip(), name.strip())
