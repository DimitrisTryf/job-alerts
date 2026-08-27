"""Employer source configuration, grouped by recruitment platform."""

GREENHOUSE_SOURCES = [
    ("stripe", "Stripe", "stripe"),
    ("five9", "Five9", "five9"),
    ("ujet", "UJET", "ujet"),
    ("cresta", "Cresta", "cresta"),
    ("invoca", "Invoca", "invoca"),
    ("assemblyai", "AssemblyAI", "assemblyai"),
    ("callrail", "CallRail", "callrail"),
    ("talkdesk", "Talkdesk", "talkdesk2"),
    ("vonage", "Vonage", "vonage"),
    ("dialpad", "Dialpad", "dialpad"),
    ("aircall", "Aircall", "aircallioinc"),
    ("ada", "Ada", "ada18"),
    ("polyai", "PolyAI", "polyai"),
    ("remote", "Remote", "remotecom"),
    ("twilio", "Twilio", "twilio"),
    ("nice", "NICE", "nice"),
]

SMARTRECRUITERS_SOURCES = [("devexperts", "Devexperts", "Devexperts")]

ASHBY_SOURCES = [
    ("docker", "Docker", "Docker"),
    ("replicant", "Replicant", "Replicant"),
    ("snowflake", "Snowflake", "snowflake"),
]

WORKABLE_SOURCES = [
    ("epignosis", "Epignosis", "epignosis"),
    ("cloudtalk", "CloudTalk", "cloudtalk"),
    ("remofirst", "Remofirst", "remofirst"),
    ("cognigy", "Cognigy", "cognigy"),
    ("qualco", "QUALCO", "qualco"),
]

LEVER_SOURCES = [
    ("netomi", "Netomi", "netomi"),
    ("sugarcrm", "SugarCRM", "sugarcrm"),
]

TEAMTAILOR_SOURCES = [
    ("puzzel", "Puzzel", "puzzel"),
    ("sumsub", "Sumsub", "sumsub"),
    ("pactum", "Pactum", "https://careers.pactum.com/jobs.json"),
]

WORKDAY_SOURCES = [
    ("8x8", "8x8", "8x8inc", "wd5", "8x8_External_Careers"),
    ("ringcentral", "RingCentral", "ringcentral", "wd1", "RingCentral_Careers"),
    ("genesys", "Genesys", "genesys", "wd1", "Genesys"),
    ("sprinklr", "Sprinklr", "sprinklr", "wd1", "careers"),
    ("zendesk", "Zendesk", "zendesk", "wd1", "zendesk"),
    ("zoom", "Zoom", "zoom", "wd5", "Zoom"),
    ("cisco", "Cisco", "cisco", "wd5", "Cisco_Careers"),
]

EIGHTFOLD_SOURCES = [
    ("microsoft", "Microsoft", "https://apply.careers.microsoft.com", "microsoft.com"),
]

SUCCESSFACTORS_SOURCES = [
    ("avaya", "Avaya", "https://careers.avaya.com"),
    ("atos", "Atos", "https://jobs.atos.net"),
]

ORACLE_RECRUITING_SOURCES = [
    (
        "oracle",
        "Oracle",
        "https://eeho.fa.us2.oraclecloud.com",
        "CX_45001",
        "https://careers.oracle.com/en/sites/jobsearch/job/",
    ),
]

ZOHO_RECRUIT_SOURCES = [
    ("itmagination", "ITMAGINATION", "https://itmagination.zohorecruit.eu/careers"),
]

SOURCE_GROUPS = (
    GREENHOUSE_SOURCES,
    SMARTRECRUITERS_SOURCES,
    ASHBY_SOURCES,
    WORKABLE_SOURCES,
    LEVER_SOURCES,
    TEAMTAILOR_SOURCES,
    WORKDAY_SOURCES,
    EIGHTFOLD_SOURCES,
    SUCCESSFACTORS_SOURCES,
    ORACLE_RECRUITING_SOURCES,
    ZOHO_RECRUIT_SOURCES,
)


def configured_source_ids() -> set[str]:
    return {source[0] for group in SOURCE_GROUPS for source in group}


def configured_source_names() -> dict[str, str]:
    return {source[0]: source[1] for group in SOURCE_GROUPS for source in group}
