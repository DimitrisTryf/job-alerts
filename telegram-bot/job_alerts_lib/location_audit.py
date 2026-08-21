"""Conservative Europe and global-remote location classification."""

from __future__ import annotations

import re

from job_alerts_lib.locations import is_global_remote_location, is_remote_location

EUROPE_TERMS = (
    "albania", "andorra", "armenia", "austria", "azerbaijan", "belarus",
    "belgium", "bosnia", "bulgaria", "croatia", "cyprus", "czech republic",
    "czechia", "denmark", "estonia", "europe", "european union", "finland",
    "france", "germany", "greece", "hungary", "iceland", "ireland", "italy",
    "kosovo", "latvia", "liechtenstein", "lithuania", "luxembourg", "malta",
    "moldova", "monaco", "montenegro", "netherlands", "north macedonia",
    "norway", "poland", "portugal", "romania", "san marino", "serbia",
    "slovakia", "slovenia", "spain", "sweden", "switzerland", "turkey",
    "türkiye", "ukraine", "united kingdom", "vatican", "emea", "eu remote",
    "remote - eu", "remote — eu", "amsterdam", "athens", "barcelona",
    "belgrade", "berlin", "bratislava", "brussels", "bucharest", "budapest",
    "copenhagen", "dublin", "helsinki", "lisbon", "limassol", "london",
    "madrid", "munich", "oslo", "paris", "prague", "sofia", "stockholm",
    "tallinn", "tbilisi", "batumi", "vienna", "vilnius", "warsaw", "zagreb",
    "zurich",
)

# Ambiguous names such as Georgia are intentionally absent.
OUTSIDE_EUROPE_TERMS = (
    "united states", "usa", "u.s.", "us only", "remote - us", "remote — us",
    "canada", "mexico", "brazil", "argentina", "colombia", "chile", "peru",
    "india", "pakistan", "bangladesh", "philippines", "singapore", "malaysia",
    "indonesia", "china", "japan", "south korea", "taiwan", "thailand",
    "vietnam", "australia", "new zealand", "south africa", "egypt", "morocco",
    "nigeria", "kenya", "saudi arabia", "united arab emirates", "uae", "israel",
    "latin america", "latam", "north america", "apac", "asia-pacific",
    "atlanta", "austin", "bangalore", "bengaluru", "boston", "chicago",
    "denver", "los angeles", "mexico city", "minneapolis", "new york",
    "phoenix", "raleigh", "san francisco", "san jose", "san ramon", "seattle",
    "sydney", "são paulo", "tashkent", "tempe", "tokyo", "toronto", "vancouver",
)


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text.casefold()))


def classify_location(location: str) -> tuple[str, list[str]]:
    """Return a classification plus safe exclusion terms found in a location."""
    if is_global_remote_location(location):
        return "GLOBAL_REMOTE", []
    if any(_contains_term(location, term) for term in EUROPE_TERMS):
        return "EUROPE", []
    outside_matches = [
        term for term in OUTSIDE_EUROPE_TERMS if _contains_term(location, term)
    ]
    if outside_matches:
        return "OUTSIDE_EUROPE", outside_matches
    if is_remote_location(location):
        return "UNKNOWN_REMOTE", []
    return "UNKNOWN", []
