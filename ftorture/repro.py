"""--repro: rebuild ONE failing test with the student's code and run it alone.

`torture -v` prints, under every failure, a command such as

    torture libft ~/libft --repro 't_part1.c#37m2@ft_strlcat'

TOKEN = FILE#IDX[mK][@SUITE[=BUFFER_SIZE]]
  FILE   test file of src/<project>/ (t_part1.c, t_printf_bonus.c, t_gnl.c...)
  IDX    __COUNTER__ of the TEST in that file (t_test.idx)
  mK     the K-th malloc between ARM() and DISARM() returns NULL
  SUITE  suite key; for gnl it also gives the part (bbs* = bonus) and
         =BUFFER_SIZE the size of that pass

The test file is compiled with src/repro.c instead of engine.c/memtrack.c:
same API, but no fork and the real malloc, so valgrind and gdb can follow the
student's code. Test data stays guarded (an over-read still crashes).
"""
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from .projects.base import Project
from .runtime import Context, RunnerError

TOKEN = re.compile(r"(?P<file>t_[\w.-]+\.c)#(?P<idx>\d+)(?:m(?P<fail>\d+))?"
                   r"(?:@(?P<suite>\w+)(?:=(?P<size>\w+))?)?")


@dataclass(frozen=True)
class Token:
    file: str
    idx: int
    fail: int
    suite: str
    size: str


def parse(raw: str) -> Token:
    match = TOKEN.fullmatch(raw.strip())
    if not match:
        raise RunnerError("--repro: FILE#IDX[mK][@SUITE[=BUFFER_SIZE]], " + raw)
    return Token(match["file"], int(match["idx"]), int(match["fail"] or 0),
                 match["suite"] or "", match["size"] or "")


def source_dir(project: Project) -> str:
    return getattr(project, "source_dir", "") or project.key


def helpers(src: Path) -> list[Path]:
    """Shared C helpers of a project: everything but tests, benchmarks and the
    descriptor (refs.c, pf.c, gnl.c, ps.c...)."""
    return [path for path in sorted(src.glob("*.c"))
            if not path.name.startswith(("t_", "b_")) and path.name != "proj.c"]


def student_objects(ctx: Context, project: Project, token: Token) -> tuple[list[str | Path], list[str]]:
    """Build the student's code for this test; returns (link inputs, extra flags)."""
    directory = ctx.options.directory
    if project.key == "gnl":
        from .projects.gnl import buffer_size
        bonus = token.suite.startswith("bbs")
        key = token.suite[1:] if bonus else token.suite      # bbs42 -> bs42
        size = buffer_size(token.size or key.removeprefix("bs")) or "42"
        suffix = "_bonus" if bonus else ""
        out = ctx.build / "repro"
        defines = [] if size == "def" else ["-D", f"BUFFER_SIZE={size}"]
        objects: list[str | Path] = []
        for name in (f"get_next_line{suffix}", f"get_next_line_utils{suffix}"):
            obj = out / f"{name}.o"
            ctx.require([*ctx.cc, "-g", "-Wall", "-Wextra", "-Werror", *defines, f"-I{directory}",
                         "-c", directory / f"{name}.c", "-o", obj], out / f"{name}.log")
            objects.append(obj)
        flags = ["-D", f"Z_BS={-1 if size == 'def' else size}", "-D", f"GNL_SUITE={token.suite or 'bs42'}"]
        return [*objects, "-Wl,--wrap=read"], flags
    # archive projects (libft, ft_printf)
    rule = "bonus" if "bonus" in token.file else "all"
    project.build_archive(ctx, rule)
    archive = directory / project.archive
    result = subprocess.run(["nm", "--defined-only", str(archive)], env=ctx.env,
                            capture_output=True, text=True, check=False)
    symbols = sorted({columns[-1] for line in result.stdout.splitlines()
                      if len(columns := line.split()) >= 3 and columns[-2] == "T"
                      and columns[-1].startswith(project.symbol_prefix)})
    return [*(f"-Wl,-u,{symbol}" for symbol in symbols), archive, *project.extra_archives(ctx)], []


def run(ctx: Context, project: Project) -> int:
    if project.custom or not project.requires_compiler or project.key == "push_swap":
        raise RunnerError(ctx.message("--repro only works for the C suites.",
                                      "--repro ne marche que pour les suites C."))
    token = parse(ctx.options.repro or "")
    src = ctx.root / "src" / source_dir(project)
    test_file = src / token.file
    if not test_file.is_file():
        raise RunnerError(ctx.message("--repro: unknown test file ", "--repro : fichier de test inconnu ")
                          + token.file)
    out = ctx.build / "repro"
    out.mkdir(parents=True, exist_ok=True)
    print("   ▶ " + ctx.message("replaying", "rejouer") + f" {token.file}#{token.idx}"
          + (ctx.message(f", malloc #{token.fail} fails", f", le malloc n°{token.fail} échoue")
             if token.fail else ""), flush=True)
    inputs, flags = student_objects(ctx, project, token)
    executable = out / "repro"
    ctx.require([*ctx.cc, "-std=gnu11", "-O0", "-g", "-w", "-fno-builtin",
                 f"-I{ctx.root / 'src'}", f"-I{src}", *flags, ctx.root / "src/repro.c", test_file,
                 *helpers(src), "-Wl,--wrap=malloc", "-Wl,--wrap=free", *inputs, "-lm",
                 "-o", executable], out / "link.log")
    args = [str(executable), str(token.idx), str(token.fail), str(ctx.options.seed)]
    env = dict(ctx.env)
    env["FTORTURE_REPRO_PATH"] = str(ctx.options.directory)
    if ctx.options.gdb:
        if not shutil.which("gdb"):
            raise RunnerError(ctx.message("gdb not found", "gdb introuvable"))
        env["FTORTURE_REPRO_GDB"] = "1"
        command = ["gdb", "-q", "--args", *args]
    elif shutil.which("valgrind"):
        command = ["valgrind", "-q", "--leak-check=full", "--show-leak-kinds=definite",
                   "--errors-for-leak-kinds=definite", "--track-origins=yes", *args]
    else:
        command = args
        print("   ▲ " + ctx.message("valgrind not found: plain run (leaks and overflows of your "
                                    "own mallocs are not reported)",
                                    "valgrind absent : exécution simple (les fuites et les "
                                    "débordements de tes mallocs ne sont pas signalés)"), flush=True)
    print("   " + ctx.message("command:", "commande :") + " " + shlex.join(command), flush=True)
    # gdb needs the terminal: no private session, no captured output
    status = subprocess.call(command, env=env, cwd=ctx.build)
    return 128 - status if status < 0 else status
