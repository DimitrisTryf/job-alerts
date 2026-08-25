"""Recruitment-platform connectors."""

from .enterprise import (
    fetch_eightfold,
    fetch_oracle_recruiting,
    fetch_successfactors,
    fetch_workday,
    resolve_workday_locations,
    fetch_zoho_recruit,
)
from .standard import (
    fetch_ashby,
    fetch_greenhouse,
    fetch_lever,
    fetch_smartrecruiters,
    fetch_teamtailor,
    fetch_workable,
)

__all__ = [
    "fetch_ashby",
    "fetch_eightfold",
    "fetch_greenhouse",
    "fetch_lever",
    "fetch_oracle_recruiting",
    "fetch_smartrecruiters",
    "fetch_successfactors",
    "fetch_teamtailor",
    "fetch_workable",
    "fetch_workday",
    "resolve_workday_locations",
    "fetch_zoho_recruit",
]
