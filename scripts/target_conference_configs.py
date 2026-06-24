"""Roster-diff configuration for target-conference transfer expansion."""

from __future__ import annotations


SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]


CONFERENCE_LABELS = {
    "mwc": "Mountain West",
    "a10": "Atlantic 10",
    "aac": "American",
    "mvc": "Missouri Valley",
}


TEAM_NAMES = {
    "air-force": "Air Force",
    "boise-state": "Boise State",
    "colorado-state": "Colorado State",
    "fresno-state": "Fresno State",
    "nevada": "Nevada",
    "new-mexico": "New Mexico",
    "san-diego-state": "San Diego State",
    "san-jose-state": "San Jose State",
    "nevada-las-vegas": "UNLV",
    "utah-state": "Utah State",
    "wyoming": "Wyoming",
    "davidson": "Davidson",
    "dayton": "Dayton",
    "duquesne": "Duquesne",
    "fordham": "Fordham",
    "george-mason": "George Mason",
    "george-washington": "George Washington",
    "la-salle": "La Salle",
    "loyola-il": "Loyola Chicago",
    "massachusetts": "Massachusetts",
    "rhode-island": "Rhode Island",
    "richmond": "Richmond",
    "st-bonaventure": "St. Bonaventure",
    "saint-josephs": "Saint Joseph's",
    "saint-louis": "Saint Louis",
    "virginia-commonwealth": "VCU",
    "central-florida": "UCF",
    "charlotte": "Charlotte",
    "cincinnati": "Cincinnati",
    "east-carolina": "East Carolina",
    "florida-atlantic": "Florida Atlantic",
    "houston": "Houston",
    "memphis": "Memphis",
    "north-texas": "North Texas",
    "rice": "Rice",
    "south-florida": "South Florida",
    "southern-methodist": "SMU",
    "temple": "Temple",
    "tulane": "Tulane",
    "tulsa": "Tulsa",
    "alabama-birmingham": "UAB",
    "texas-san-antonio": "UTSA",
    "wichita-state": "Wichita State",
    "belmont": "Belmont",
    "bradley": "Bradley",
    "drake": "Drake",
    "evansville": "Evansville",
    "illinois-chicago": "UIC",
    "illinois-state": "Illinois State",
    "indiana-state": "Indiana State",
    "missouri-state": "Missouri State",
    "murray-state": "Murray State",
    "northern-iowa": "Northern Iowa",
    "southern-illinois": "Southern Illinois",
    "valparaiso": "Valparaiso",
}


MWC = [
    "air-force",
    "boise-state",
    "colorado-state",
    "fresno-state",
    "nevada",
    "new-mexico",
    "san-diego-state",
    "san-jose-state",
    "nevada-las-vegas",
    "utah-state",
    "wyoming",
]

A10_2022 = [
    "davidson",
    "dayton",
    "duquesne",
    "fordham",
    "george-mason",
    "george-washington",
    "la-salle",
    "massachusetts",
    "rhode-island",
    "richmond",
    "st-bonaventure",
    "saint-josephs",
    "saint-louis",
    "virginia-commonwealth",
]
A10_WITH_LOYOLA = A10_2022 + ["loyola-il"]
A10_2026 = [team for team in A10_WITH_LOYOLA if team != "massachusetts"]

AAC_OLD = [
    "central-florida",
    "cincinnati",
    "east-carolina",
    "houston",
    "memphis",
    "south-florida",
    "southern-methodist",
    "temple",
    "tulane",
    "tulsa",
    "wichita-state",
]
AAC_NEW = [
    "charlotte",
    "east-carolina",
    "florida-atlantic",
    "memphis",
    "north-texas",
    "rice",
    "south-florida",
    "temple",
    "tulane",
    "tulsa",
    "alabama-birmingham",
    "texas-san-antonio",
    "wichita-state",
]

MVC_OLD = [
    "bradley",
    "drake",
    "evansville",
    "illinois-state",
    "indiana-state",
    "missouri-state",
    "northern-iowa",
    "southern-illinois",
    "valparaiso",
]
MVC_NEW = MVC_OLD + ["belmont", "illinois-chicago", "murray-state"]
MVC_2026 = [team for team in MVC_NEW if team != "missouri-state"]


TEAMS_BY_CONFERENCE_SEASON = {
    "mwc": {season: MWC for season in SEASONS},
    "a10": {
        "2021-22": A10_2022,
        "2022-23": A10_WITH_LOYOLA,
        "2023-24": A10_WITH_LOYOLA,
        "2024-25": A10_WITH_LOYOLA,
        "2025-26": A10_2026,
    },
    "aac": {
        "2021-22": AAC_OLD,
        "2022-23": AAC_OLD,
        "2023-24": AAC_NEW,
        "2024-25": AAC_NEW,
        "2025-26": AAC_NEW,
    },
    "mvc": {
        "2021-22": MVC_OLD,
        "2022-23": MVC_NEW,
        "2023-24": MVC_NEW,
        "2024-25": MVC_NEW,
        "2025-26": MVC_2026,
    },
}


TEAM_ALIASES = {
    "american": "american",
    "atlantic 10": "atlantic 10",
    "charlotte": "charlotte",
    "florida atlantic": "florida atlantic",
    "george washington": "george washington",
    "gw": "george washington",
    "loyola il": "loyola chicago",
    "loyola chicago": "loyola chicago",
    "missouri st": "missouri state",
    "mountain west": "mountain west",
    "saint bonaventure": "st bonaventure",
    "saint joseph s": "saint joseph s",
    "san diego st": "san diego state",
    "san jose st": "san jose state",
    "southern ill": "southern illinois",
    "st bonaventure": "st bonaventure",
    "st joseph s": "saint joseph s",
    "ucf": "ucf",
    "central florida": "ucf",
    "unlv": "unlv",
    "vcu": "vcu",
    "virginia commonwealth": "vcu",
}


def season_end_year(season: str) -> int:
    return int(season.split("-", 1)[0]) + 1
