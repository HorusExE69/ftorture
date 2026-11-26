"""Failure explanations, C test source snippets, --repro tokens, and localization."""
from pathlib import Path
import signal

from .language import text

TEST_MACROS = ("TEST(", "SPEC_TEST(", "VS(", "VS_SPEC(", "MTEST(")

# French -> English phrase translation table for static C test names.
TRANSLATIONS: tuple[tuple[str, str], ...] = (
    ("ton fichier : ", "your file: "),
    ("fichier généré : ", "generated file: "),
    ("tableau ", "array "), ("taille ", "size "), ("chaîne ", "string "),
    ("chaînes ", "strings "), ("vide", "empty"), ("vides", "empty"),
    ("négatif", "negative"), ("positif", "positive"), ("entier", "integer"),
    ("entiers", "integers"), ("débordement", "overflow"), ("chevauchement", "overlap"),
    ("sens inverse", "reverse"), ("identique", "identical"), ("différent", "different"),
    ("plus grand", "larger"), ("plus petit", "smaller"), ("plus court", "shorter"),
    ("plus long", "longer"), ("espaces", "spaces"), ("espace", "space"),
    ("chiffres", "digits"), ("lettres", "letters"), ("majuscules", "uppercase"),
    ("minuscules", "lowercase"), ("caractère", "char"), ("caractères", "chars"),
    ("octets", "bytes"), ("octet", "byte"), ("lignes", "lines"), ("ligne", "line"),
    ("fichier", "file"), ("fichiers", "files"), ("sans ", "without "),
    ("avec ", "with "), ("dans ", "in "), ("vers ", "to "), ("depuis ", "from "),
    ("début", "start"), ("milieu", "middle"), ("fin", "end"),
    ("avant", "before"), ("après", "after"), ("tous les ", "all "),
    ("aléatoires", "random"), ("aléatoire", "random"), ("inversé", "reversed"),
    ("nombres", "numbers"), ("nombre", "number"), ("trié", "sorted"),
    ("désordre", "disorder"), ("coups", "moves"), ("croissance", "growth"),
    ("échec malloc", "malloc failure"), ("fuite", "leak"),
    ("non trouvé", "not found"), ("trouvé", "found"), ("absent", "missing"),
    ("erreur", "error"), ("erreurs", "errors"), ("invalide", "invalid"),
    ("longue", "long"), ("long", "long"), ("court", "short"),
    ("et ", "and "), ("ou ", "or "), ("au ", "at "), ("en ", "in "),
)


def localize_name(name: str, lang: str) -> str:
    if lang != "en" or not name:
        return name
    out = name
    for fr, en in TRANSLATIONS:
        if fr in out:
            out = out.replace(fr, en)
    return out


def sig_hint(sig: int, lang: str) -> str:
    def t(en: str, fr: str) -> str:
        return text(lang, en, fr)
    if sig == signal.SIGSEGV:
        return t(
            "SIGSEGV (invalid memory access): either a NULL pointer dereference, "
            "or a 1-byte over-read/over-write caught by ftorture's guard page right "
            "after each malloc/test buffer.",
            "SIGSEGV (accès mémoire invalide) : soit un déréférencement de pointeur "
            "NULL, soit une lecture/écriture 1 octet trop loin piégée par la page de "
            "garde placée par ftorture juste après chaque bloc malloc ou buffer de test.",
        )
    if sig == signal.SIGABRT:
        return t(
            "SIGABRT (abort): usually heap corruption, a double free, or a free() "
            "of an invalid pointer.",
            "SIGABRT (abort) : en général une corruption du tas, un double free ou "
            "un free() sur un pointeur invalide.",
        )
    if sig == signal.SIGBUS:
        return t(
            "SIGBUS: misaligned or out-of-bounds memory access.",
            "SIGBUS : accès mémoire non aligné ou hors limites.",
        )
    if sig == signal.SIGFPE:
        return t(
            "SIGFPE: division or modulo by zero (or INT_MIN / -1).",
            "SIGFPE : division ou modulo par zéro (ou INT_MIN / -1).",
        )
    if sig == signal.SIGALRM:
        return t(
            "Timeout: infinite loop, blocking read(), or an algorithm too slow for "
            "this input (e.g. quadratic stash in get_next_line).",
            "Timeout : boucle infinie, read() bloquant, ou algorithme trop lent pour "
            "cette entrée (ex. stash quadratique dans get_next_line).",
        )
    return t(
        f"Killed by signal {sig}.",
        f"Tué par le signal {sig}.",
    )


def explain_failure(why: str, *, sig: int = 0, msg: str = "", lang: str = "en") -> str:
    def t(en: str, fr: str) -> str:
        return text(lang, en, fr)
    low = msg.lower()
    if why == "sig":
        return sig_hint(sig, lang)
    if why == "exit":
        return t(
            "Your function called exit() instead of returning normally.",
            "Ta fonction a appelé exit() au lieu de retourner normalement.",
        )
    if why == "leak":
        return t(
            "Memory allocated with malloc() was not freed before the test ended.",
            "De la mémoire allouée avec malloc() n'a pas été libérée avant la fin du test.",
        )
    if why == "vs_crash":
        return t(
            "The real function handles this input without crashing: yours must not crash either. "
            "\"expected\" shows what the original returns. Often: a size of 0 must prevent any read, "
            "even with a NULL pointer.",
            "La vraie fonction gère cette entrée sans crasher : la tienne ne doit pas crasher non plus. "
            "« attendu » montre ce que renvoie l'originale. Souvent : une taille à 0 doit empêcher "
            "toute lecture, même avec un pointeur NULL.",
        )
    if why == "vs_spec":
        return t(
            "The real function crashes on this input, yours does not: a protection the subject "
            "does not ask for. Not an error, but in evaluation you may be asked why your behavior "
            "differs from the original.",
            "La vraie fonction crash sur cette entrée, pas la tienne : c'est une protection que le "
            "sujet ne demande pas. Ce n'est pas une erreur, mais en correction on peut te demander "
            "pourquoi ton comportement diffère de l'original.",
        )
    if why == "vs_diff":
        return t(
            "Same input, different results: \"expected\" is what the real function returns, "
            "\"actual\" what yours returns (values are separated by |, one per call of the test).",
            "Même entrée, résultats différents : « attendu » est ce que renvoie la vraie fonction, "
            "« obtenu » ce que renvoie la tienne (les valeurs sont séparées par |, une par appel).",
        )
    if why == "vs_diff_spec":
        return t(
            "Result differs from the original on an undefined-behavior case: ▲ only, be ready to explain it.",
            "Résultat différent de l'original sur un cas indéfini : ▲ seulement, à savoir expliquer.",
        )
    if why == "vs_timeout":
        return sig_hint(signal.SIGALRM, lang)
    if why == "malloc":
        if sig:
            return t(
                "The test is replayed with one malloc failing (returning NULL) and your function crashes: "
                "a malloc return value is used without being checked.",
                "Le test est rejoué en faisant échouer un malloc précis (il renvoie NULL) et ta fonction "
                "crash : un retour de malloc n'est pas vérifié avant d'être utilisé.",
            )
        if "fuite" in low or "leak" in low:
            return t(
                "The test is replayed with one malloc failing: your function reports the error "
                "but does not free what it had already allocated before the failure.",
                "Le test est rejoué en faisant échouer un malloc précis : ta fonction renvoie bien une "
                "erreur mais ne libère pas ce qu'elle avait déjà alloué avant l'échec.",
            )
        return t(
            "The test is replayed with one malloc failing: your function must free what it already "
            "allocated and return NULL (or the error expected by the subject).",
            "Le test est rejoué en faisant échouer un malloc précis : ta fonction doit alors libérer "
            "ce qu'elle a déjà alloué et renvoyer NULL (ou l'erreur prévue par le sujet).",
        )
    if why == "assert":
        if "double free" in low or "free()" in low:
            return t(
                "You free the same block twice, or a pointer that is not the start of a malloc block.",
                "Tu libères deux fois le même bloc, ou un pointeur qui n'est pas le début d'un bloc malloc.",
            )
        if any(word in low for word in ("bloc", "block", "malloc")):
            return t(
                "Allocation problem: the returned block must come from malloc and hold at least "
                "the string + 1 byte for '\\0'.",
                "Problème d'allocation : le bloc renvoyé doit venir de malloc et contenir au moins "
                "la chaîne + 1 octet pour le '\\0'.",
            )
        return t(
            "A check of the test failed: compare \"expected\" and \"actual\" for the given input.",
            "Une vérification du test a échoué : compare « attendu » et « obtenu » pour l'entrée indiquée.",
        )
    return ""


def _brace_delta(line: str) -> tuple[int, bool]:
    delta = 0
    seen = False
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == quote:
                quote = ""
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        elif ch == "{":
            delta += 1
            seen = True
        elif ch == "}":
            delta -= 1
        i += 1
    return delta, seen


def read_test_source(file_path: str, line_no: int, max_lines: int = 18) -> list[str]:
    if not file_path or line_no < 1:
        return []
    path = Path(file_path)
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if line_no > len(lines):
        return []
    first = lines[line_no - 1]
    if not any(first.lstrip().startswith(macro) for macro in TEST_MACROS):
        return [first.replace("\t", " ")]
    result: list[str] = []
    depth = 0
    seen = False
    for raw in lines[line_no - 1:]:
        clean = raw.replace("\t", " ")
        if len(result) < max_lines:
            result.append(clean)
        elif len(result) == max_lines:
            result.append("…")
        d, s = _brace_delta(raw)
        depth += d
        seen |= s
        if seen and depth <= 0:
            break
    return result


def build_repro_command(repro_prefix: str, *, file_path: str, idx: int,
                        fail_at: int = 0, suite: str = "", z_bs: int | None = None) -> str:
    if not repro_prefix or idx < 0 or not file_path:
        return ""
    base = Path(file_path).name
    if not base.startswith("t_"):
        return ""
    token = f"{base}#{idx}"
    if fail_at > 0:
        token += f"m{fail_at}"
    if suite:
        token += f"@{suite}"
        if z_bs is not None:
            token += f"={'def' if z_bs < 0 else z_bs}"
    return f"{repro_prefix} --repro '{token}'"
