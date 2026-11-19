"""English/French language selection; never substitute text in user data."""
import os


def default_language() -> str:
    locale = next((os.environ[key] for key in ("LC_ALL", "LC_MESSAGES", "LANG")
                   if os.environ.get(key)), "en")
    return "fr" if locale.startswith("fr") else "en"


def text(lang: str, en: str, fr: str) -> str:
    return fr if lang == "fr" else en
