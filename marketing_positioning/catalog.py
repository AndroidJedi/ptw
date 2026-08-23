"""Code-owned country and market-language catalog exposed to the owner UI."""

COUNTRIES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia",
    "DE": "Germany", "FR": "France", "ES": "Spain", "IT": "Italy", "PL": "Poland",
    "UA": "Ukraine", "NO": "Norway", "DK": "Denmark", "SE": "Sweden", "NL": "Netherlands",
}
RESEARCH_LANGUAGES = {
    "en": "English", "uk": "Ukrainian", "de": "German", "fr": "French",
    "es": "Spanish", "it": "Italian", "pl": "Polish", "no": "Norwegian",
    "da": "Danish", "sv": "Swedish", "nl": "Dutch",
}


def catalog() -> dict[str, object]:
    return {
        "default_country": "US", "default_research_language": "en",
        "countries": [{"code": code, "name": name} for code, name in COUNTRIES.items()],
        "research_languages": [{"code": code, "name": name} for code, name in RESEARCH_LANGUAGES.items()],
        "output_languages": [{"code": "uk", "name": "Українська"}, {"code": "en", "name": "English"}],
    }
