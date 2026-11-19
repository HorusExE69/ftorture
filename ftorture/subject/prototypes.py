"""Check declarations with the compiler, not guessed C type equivalence."""
import re

from ..checks import CheckSession


def expected_prototypes(session: CheckSession) -> list[tuple[str, str, str]]:
    path = session.ctx.root / "protos" / f"{session.ctx.key}.txt"
    return [tuple(line.split("|", 2)) for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def check_prototypes(session: CheckSession, header: str, subject: str, *, linked_list: bool = False) -> None:
    session.report.section(f"PROTOTYPES · {session.ctx.key} v{subject}")
    include = f'#include "{header}"\n'
    prefix = ""
    status, diagnostic = session.compiler(include + "int main(void){return 0;}\n", name="header")
    if status:
        prefix = "#include <stddef.h>\n#include <stdlib.h>\n#include <unistd.h>\n#include <stdarg.h>\n"
        status, _ = session.compiler(prefix + include + "int main(void){return 0;}\n", name="header-with-includes")
        if status:
            session.check("KO", header, header, "does not compile", "ne compile pas")
            session.details(diagnostic.splitlines(), 3)
            return
        session.check("WARN", f"{header} self-contained", f"{header} autonome",
                      "missing required include", "il manque un include")
    else:
        session.check("OK", f"{header} self-contained", f"{header} autonome", "compiles alone", "compile seul")
    if linked_list:
        probe = (prefix + include + '#include <stddef.h>\n'
                 '_Static_assert(__builtin_types_compatible_p(__typeof__(((t_list *)0)->content), void *), "content");\n'
                 '_Static_assert(__builtin_types_compatible_p(__typeof__(((t_list *)0)->next), struct s_list *), "next");\n'
                 '_Static_assert(offsetof(t_list, content) == 0, "order");\n'
                 '_Static_assert(sizeof(t_list) == 2 * sizeof(void *), "size");\n')
        status, _ = session.compiler(probe, name="list-layout")
        session.check("KO" if status else "OK", "t_list structure", "Structure t_list",
                      "expected: struct s_list { void *content; struct s_list *next; }",
                      "attendu : struct s_list { void *content; struct s_list *next; }")
    _, preprocessed = session.compiler(prefix + include, ("-E", "-P"), name="header-preprocessed")
    declarations = [re.sub(r"\s+", " ", value).strip() + ";" for value in preprocessed.split(";")]
    for name, type_, shown in expected_prototypes(session):
        found = next((value for value in declarations if re.search(r"\b" + re.escape(name) + r"\s*\(", value)), "")
        probe = prefix + include + f'_Static_assert(__builtin_types_compatible_p(__typeof__(&{name}), {type_}), "prototype");\n'
        status, _ = session.compiler(probe, name=f"prototype-{name}")
        session.report.prototype(name, "KO" if status else "OK", shown, found)
    session.report.end_prototypes()
