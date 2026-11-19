# 🔥 ftorture — 42 tester: libft, ft_printf & get_next_line

🇫🇷 [Version française](README.fr.md)

> *Your code will talk.*

**ftorture** puts your project to the question: every test runs in its own process,
face to face with the **real** libc function. It watches how it crashes, what it leaks,
and what it reads outside its memory.

| Project | Subject | What is tested |
|---|---|---|
| **libft** | v19.3 | all 43 functions (parts 1, 2 and 3), ~400 tests + fuzzing |
| **ft_printf** | v12.1 | `cspdiuxX%` + bonus `-0.`, width, `# +`, ~22,000 calls compared with `printf` |
| **get_next_line** | v14.3 | 14 `BUFFER_SIZE`s, files, stdin, pipe, `read` errors, multi-fd bonus |

Inspired by [Caesarovich/zft](https://github.com/Caesarovich/zft): a C test engine
with modular Python orchestration. Requires **Linux**, **Python 3.10+**, `cc`,
`make`, and `nm`. Installation, orchestration, and subject checks use Python only.
No pip packages are needed; norminette is optional.

## Installation

```bash
git clone https://github.com/HorusExE69/ftorture.git ~/ftorture
cd ~/ftorture && python3 install.py
```

`install.py` creates the executable Python launcher `~/.local/bin/torture` directly.
No shell aliases are needed. You need `~/.local/bin` on PATH. The installer detects
the running shell (falling back to `$SHELL`) and checks its configuration: `.zshrc`
for zsh (`$ZDOTDIR` supported), `.bashrc` for bash, `config.fish` for fish
(`$XDG_CONFIG_HOME` supported), or `.profile` for sh/dash/ksh. If the entry is missing,
it shows the line to add and **asks permission** to append it. Declining or installing
non-interactively leaves configuration untouched; add the displayed line yourself.
Existing PATH entries are not duplicated. Reinstalling removes
old launchers in `~/.local/applications` only if they are ftorture-managed.
Ensure `~/.local/bin` is on your `PATH` (restart your shell if necessary).
The launcher keeps your current directory and passes all arguments through.
To fast-forward a clean `main` checkout from the **original** repository
(`https://github.com/HorusExE69/ftorture.git`), run `python3 install.py --update`.
Updates never overwrite local changes or merge divergent histories.
Remove any old `torture` alias from your shell configuration if one still exists.

To uninstall the command, run `python3 install.py --delete --confirm`.
Both flags are required. Only the managed
`~/.local/bin/torture` launcher and its managed legacy symlink target are removed.
Unrelated files are refused; PATH entries, other commands, the checkout and custom
tests are kept. Repeating the command is safe.

Terminal output follows your locale (French for `fr_*`, English otherwise).
Use `--lang en` or `--lang fr` to override it for any run, including the
interactive menu and the plain-text report.

## Usage

### Interactive menu

```bash
torture
```

The original retro TUI is preserved in Python, with its pixel logo, green scanlines,
and three screens:

1. **Project**: LIBFT, FT_PRINTF, GNL (`↑ ↓`, `j/k`, or `1/2/3`, then Enter).
   The current project's header determines the default selection.
2. **Path**: editable default, Tab completion, and validation with retry.
3. **Options**: Space/Enter toggles strict mode, verbose, checks, norminette, and
   ignore-hidden; select **START TESTING** to run. `q` quits either menu.

Command-line options supplied without a target initialize the menu. `--lang fr`
restores the original French labels; `--no-color` preserves the layout without colors.
Terminal settings and cursor visibility are restored on exit or interruption.

### Command line

```bash
torture libft ~/libft                # a libft
torture printf ~/ft_printf           # a ft_printf (mandatory + bonus)
torture gnl ~/get_next_line          # a get_next_line (every BUFFER_SIZE)
torture ~/ft_printf -s               # project detected automatically
torture libft -f split,itoa -v       # a few functions, with every detail
torture printf -f %d,"flag -"        # a few conversions / flags
torture printf -p 1                  # mandatory part only
torture gnl -f 1,42,9999             # only these BUFFER_SIZEs
```

| Option | Effect |
|---|---|
| `-s`, `--speculative` | speculative errors (▲) make the run fail |
| `-v`, `--verbose` | show the details of every failure |
| `-f`, `--func LIST` | libft: `ft_split,itoa` · printf: `%d,%s,flag -,précision .` · gnl: `1,42,def` (BUFFER_SIZE) |
| `-p`, `--part N` | libft: 1, 2 or 3 · printf / gnl: 1 (mandatory) or 2 (bonus) |
| `--no-checks` | skip Makefile / norm / nm / prototype checks |
| `--no-norm` | skip norminette |
| `--no-hidden` | ignore hidden files/folders in extra-file and include-use checks |
| `--seed N` | fuzzing seed (default 42) |
| `--timeout S` | per-test timeout (default 3 s, 10 s for gnl) |
| `--no-color` | no colors |
| `--lang en\|fr` | override the detected output language |
| `--list-projects` | list supported project modules and subject versions |
| `--custom-tests-dir DIR` | use user test manifests from this directory instead of the default config location |

After installation, use `torture` from your project directory or any other folder;
you do not need to start it from the ftorture checkout. Paths containing spaces
are supported. The launcher is Python-only; no shell wrappers are provided.
Keep the checkout in place: the installed launcher loads its Python code and C suites.

At the end, ftorture runs your project's `make clean` (libft, ft_printf), even after an
error or a Ctrl-C: no `.o` file is left behind. get_next_line is compiled in the
ftorture folder, so your repository stays clean. A full plain-text report is written to `ftorture.log`, in
the ftorture folder, never inside your project.

### Custom tests

Write your own tests without editing ftorture: put versioned JSON manifests and
scripts in `${XDG_CONFIG_HOME:-$HOME/.config}/ftorture/tests/`. They appear after
the bundled projects in the main menu with a distinct cyan **[CUSTOM]** label.
Each suite supports build/cleanup commands, named tests, filters, parts, timeouts,
expected exit codes, speculative verdicts, and logs. Only run trusted suites:
commands execute with your permissions and are not sandboxed.

```bash
torture --custom-tests-dir ~/ftorture/examples/custom-tests custom-readme /path/to/project -v
```

See the [custom-test guide](docs/custom-tests.md) for the schema, example, and
limitations. Native C projects remain independently extensible through `Project`.

### Python architecture and contributor interface

The Python runner owns argument validation, project detection, compilation,
mandatory/bonus passes, C tester invocation, exit statuses, and cleanup. The
existing C test behavior is retained, including bilingual reports. Native subject checks in
`ftorture/subject/` produce `build/<project>/checks.txt`; compiler and tool probe
diagnostics are saved in `build/<project>/checks/`. Runs lock the checkout to
prevent concurrent executions from corrupting build files and reports.
Include-use analysis is heuristic: unresolved headers get no verdict. Review
findings involving complex macros or conditional compilation against the subject.

`ftorture/registry.py` combines bundled project modules and validated custom
manifests for CLI listing, selection, and the TUI. Add a project module under `ftorture/projects/`, implement the `Project` interface
(`validate`, `checks`, `run`, `cleanup`), and register its `PROJECT` in
`ftorture/projects/__init__.py`. The CLI/menu discover it from that registry.
Project metadata declares `requires_compiler` and `requires_makefile`; command-only
strategies need not inherit C tool dependencies or Makefile path validation.
Use `ArchiveProject` for Makefile archives or implement a source build strategy
like `GnlProject`. Reuse the native checks in `ftorture/subject/` with policies
appropriate to the new subject; `CheckReport` in `ftorture/checks.py` writes engine check
records without hand-building delimiters. See [the tester authoring skill](skills/ftorture-new-testers/SKILL.md).

```text
ftorture/cli.py           CLI, validation, lock, lifecycle
ftorture/registry.py      unified bundled/custom project registry
ftorture/runtime.py       options, subprocesses, artifacts, C-engine interface
ftorture/projects/       project registry and build/test strategies
ftorture/projects/custom.py  user manifest loading and command-suite strategy
ftorture/checks.py        check records and compiler/tool probes
ftorture/subject/        native file, Makefile, include, symbol and prototype checks
ftorture/ui.py, language.py  menu and English/French language selection
src/                     existing C engine, helpers, and test suites
```

Validate changes with `python3 -m unittest discover -s tests -v`. The tests use
temporary student fixtures. Integration cases compile/run the real C engine and
overwrite the checkout's `build/` files and `ftorture.log`; pseudo-terminal tests
exercise menu navigation, completion, and restoration. Exit codes: `0`
for passing selected tests, `1` for failed tests/checks, `2` for runner/build
errors, `130` for interruption. Skipped bonus tests are never reported as passes.
See [validation instructions](docs/validation.md) for a safe legacy-Bash/Python
comparison using temporary copies of a real libft project.

## Checks (libft and ft_printf)

| Area | Details |
|---|---|
| **Makefile** | rules `$(NAME) all clean fclean re` (+ `bonus` for printf), `cc`, `-Wall -Wextra -Werror` on every file (read with `make -nB`, even with `@`), `ar` and not libtool, no `-std=c99`, **relink** (including `make bonus`), `clean` / `fclean` |
| **Files** | files to submit, **extra files are KO** (hidden files except `.git` / `.gitignore`, unexpected extensions such as `.py` `.cpp` `.txt` `.o`, empty folders), `README.md` (italic first line, Description / Instructions / Resources, + algorithm explanation for printf) |
| **Code** | norminette (if installed), **unused `#include`** (a `<lib.h>` must give something the file uses, a project `"x.h"` one of its functions, structs, macros or libs; duplicates too), **forbidden external functions** (anything but `malloc`, `free`, `write`, with the offending file), **global variables**, non-`static` helpers (libft), functions present in the archive |
| **Prototypes** | every prototype in the header compared by the compiler against the **Linux man pages** / subject, exact `t_list` (libft), header compiles on its own |

## libft

- **Guarded memory**: test strings sit right before a forbidden page, so any read past
  the end crashes (`strlcat`, `strnstr`, `substr`, `memchr`…).
- **Instrumented malloc** (`-Wl,--wrap=malloc,--wrap=free`):
  - one byte written outside a block: crash; use after `free`: crash
  - **double free**: reported; **leaks**: any block not freed at the end of the test
  - allocation size checked (`strdup`, `itoa`, `split`…)
  - fresh blocks filled with `0xA5`: a `calloc` that doesn't zero shows up
  - **malloc protection** (`M`): the test is replayed with the 1st, 2nd, 3rd… malloc
    failing; it must return `NULL` with no crash and no leak (`ft_split`, `ft_lstmap`)
- **Fuzzing** against glibc (or BSD for `strlcpy`, `strlcat`, `strnstr`).

## ft_printf

Each call runs **your `ft_printf`**, then the **real `printf`** with the same
arguments, each with its output redirected to a file. ftorture compares the **output
byte by byte** (including the `\0` of `%c`) and the **return value**.

- **Mandatory part** (archive from `make`): every conversion `c s p d i u x X %`
  (limit values, `NULL` → `(null)` / `(nil)`, all 256 characters, `INT_MIN`,
  `UINT_MAX`, 64-bit pointers…), mixes, 24 arguments, outputs over 10,000 bytes, and
  fuzzing.
- **Bonus** (archive from `make bonus`, tested in a second pass): each flag (`-`, `0`,
  `.`, width, `#`, space, `+`), their interactions (`'-'` cancels `'0'`, `'+'` beats
  `' '`, `.0` with value 0…) and **5,000 random combinations** that are valid in C.
- **Undefined cases** (`%05s`, `%.3c`, `%#d`, `%+u`, `%s` NULL with precision, flags on
  `%%`…): ▲ only, when they differ from glibc.
- **Memory**: leaks detected, and failing mallocs (no crash, no leak).
- **`NULL` format**: compared with the real function's crash (rule below).

If your Makefile has no `bonus` rule, only the mandatory part is tested and the summary
says so.

## get_next_line

This project has no Makefile: ftorture compiles your files itself, in its `build/`
folder (nothing is written in your repository), **once per `BUFFER_SIZE`**. Each size
is one line of the report: 1, 2, 3, 5, 7, 10, 42, 100, 1024, 9999, 100,000,
10,000,000, the default value (no `-D`), and 0.

- **Contents**: empty file, one line with or without `\n`, only `\n`, lines of
  `BUFFER_SIZE - 1`, `BUFFER_SIZE` and `BUFFER_SIZE + 1` characters, lines of 10,000 and
  100,000 characters, 5,000 one-character lines, a ~80 KB file, non-ASCII characters.
- **Every returned line** is compared with the expected one and must be a large enough
  `malloc` block (not a pointer into a `static` buffer); after the last line,
  `get_next_line` must return `NULL`, then `NULL` again.
- **Other fds**: standard input, a **pipe** fed in small chunks (partial `read`s), fd
  `-1`, never opened or closed, a directory.
- **Errors**: a `read()` returning `-1` in the middle of the file (it must return
  `NULL`, then start cleanly on a new file), failing mallocs, leaks.
- **"Reads as little as possible"**: `read` is instrumented; reading the whole file to
  return the first line is an error.
- **Bonus** (`_bonus` files): files read in turn, one file ending before the others,
  fd 1000, stdin, 50 files open at once, invalid fds between two reads, and **a single
  `static` variable** (checked with `nm`). The mandatory tests also run on the bonus
  version.
- **Checks**: the 3 files to submit (+ the 3 `_bonus` ones), compilation with
  `-Wall -Wextra -Werror -D BUFFER_SIZE=42` **and without `-D`**, only `read`, `malloc`,
  `free` (`lseek` and the libft are forbidden), no global variable, norminette,
  prototype, README with the algorithm.

`BUFFER_SIZE=0` and `BUFFER_SIZE=10000000` count as ▲: the subject asks the question
(a 10 MB buffer on the stack crashes); you need to be able to explain it.

## Your function vs the real one

For twisted inputs (NULL, `n = 0`, overflows…), ftorture runs **your** function and the
**real** one in two separate processes, then compares:

| yours | the real one | verdict |
|---|---|---|
| crashes | crashes | ✔ OK: same behavior as the original |
| crashes | doesn't crash | ✘ **error**, even without `-s` (e.g. `ft_memcpy(NULL, NULL, 0)`) |
| doesn't crash | crashes | ▲ **speculative**: you protect where the libc doesn't |
| doesn't crash | doesn't crash | results must be identical |

For libft parts 2 and 3 (no libc original), the reference is a simple implementation
with no NULL protection.

▲ are warnings: they don't make ftorture fail, except with `-s`. It's up to you to
defend them during your evaluation.

## Legend

| | |
|---|---|
| `✔` | ok |
| `✔` (cyan) | crashed exactly like the libc (accepted) |
| `✘` | error |
| `S` | crash (segfault, bus error, abort) |
| `T` | timeout, probably an infinite loop |
| `L` | memory leak |
| `M` | malloc protection test |
| `▲` | speculative |

## Adding a test

```
src/engine.c, memtrack.c, zft.h   shared engine (fork, guarded memory, report)
src/libft/                        libft tests (t_part1-3.c) + references
src/printf/                       ft_printf tests (t_printf.c, t_printf_bonus.c)
src/gnl/                          get_next_line tests (t_gnl.c, t_gnl_bonus.c)
protos/                           expected prototypes
```

**libft:**

```c
TEST(ft_strlen, "my test")
{
	EQ_SZ(ft_strlen("abc"), 3);
}

VS(ft_strlen, "compared to the libc")
{
	OUT("%zu", PICK(ft_strlen, r_strlen)("abc"));
}
```

**ft_printf** (`pf_d`, `pf_s`, `pf_minus`…: the suite the test belongs to):

```c
TEST(pf_d, "my test")
{
	PF("%d|%d", 42, -42);       /* same output + same return value as printf */
}

SPEC_TEST(pf_undef, "undefined case")
{
	PF("%05s", "ab");           /* ▲ only if it differs from glibc */
}
```

**get_next_line** (`GNL_SUITE` = the line of the current BUFFER_SIZE):

```c
TEST(GNL_SUITE, "my test")
{
	static const char	d[] = "a\nb\n";
	int					fd = gnl_file(d, sizeof(d) - 1);

	EXPECT_FD(fd, d, sizeof(d) - 1, "my file");   /* every line + NULL */
	close(fd);
}
```

- **Assertions**: `CHECK`, `EQ_INT`, `EQ_SZ`, `EQ_PTR`, `EQ_STR`, `EQ_MEM`, `PF`
- **Variants**: `SPEC_TEST` (▲), `VS` / `VS_SPEC` (compared to the real function),
  `MTEST` (failing malloc, between `ARM()` and `DISARM()`)
- **Helpers**: `gstr`, `gmem`, `gbuf` (guarded memory), `alloc_size`,
  `cap_open` / `cap_read`, `INPUT` (describes the input on failure)

## License

GPL-3.0, like the original project.
