# 🔥 ftorture — 42 tester: libft, ft_printf, get_next_line, push_swap & Python modules

🇫🇷 [Version française](README.fr.md)

> *Your code will talk.*

**ftorture** puts your project to the question: every test runs in its own process,
face to face with the **real** libc function (or an isolated Python interpreter for Python modules). It watches how it crashes, what it leaks,
and what it reads outside its memory.

| Project | Subject | What is tested |
|---|---|---|
| **libft** | v19.3 | all 43 functions (parts 1, 2 and 3), ~400 tests + fuzzing |
| **ft_printf** | v12.1 | `cspdiuxX%` + bonus `-0.`, width, `# +`, ~22,000 calls compared with `printf` |
| **get_next_line** | v14.3 | 14 `BUFFER_SIZE`s, files, stdin, pipe, `read` errors, multi-fd bonus |
| **push_swap** | v1.2 | errors, the 4 strategies, `--bench`, 100 / 500 number thresholds, valgrind, `checker` bonus |
| **py00** (`python-module-00`) | v3.0 | *Growing Code*: `ex0`–`ex7`, I/O, recursion, type annotations, `flake8`, `mypy`, AST checks |
| **py01** (`python-module-01`) | v3.2 | *Code Cultivation*: `ex0`–`ex6`, OOP, encapsulation, inheritance, `flake8`, `mypy`, AST checks |

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

1. **Project**: LIBFT, FT_PRINTF, GNL, PUSH_SWAP, **PYTHON MODULES**, then your custom
   suites (`↑ ↓`, `j/k`, or a digit, then Enter). PYTHON MODULES opens a second menu with
   each Python module (PY00, PY01…); `q` or BACK returns to the main menu. The current
   project is preselected (in the submenu for a Python module).
2. **Path**: editable default, Tab completion, and validation with retry.
3. **Options**: Space/Enter toggles strict mode, verbose, efficiency, checks, norminette, and
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
torture gnl -f 3,77,4096             # any BUFFER_SIZE, even outside the list
torture gnl -f 1,42 --file mine.txt  # only your file, with these BUFFER_SIZEs
torture gnl --file 64k,2M            # generated files of 64 KB and 2 MB
torture push_swap ~/push_swap -e     # a push_swap (+ checker), with efficiency
torture ps -f errors,perf500 -v      # a few push_swap suites, every detail
torture py00 ~/python-module-00 -v   # python-module-00 (Growing Code)
torture py01 ~/python-module-01 -c   # python-module-01 (Code Cultivation), chill mode
```

| Option | Effect |
|---|---|
| `-s`, `--speculative` | speculative errors (▲) make the run fail |
| `-v`, `--verbose` | every failure in full: why it fails, the test's code, the call, a `main.c`, the `--repro` command |
| `--repro TEST` | rebuild one failing test alone with your code and run it under valgrind (`TEST` is printed by `-v`) |
| `--gdb` | with `--repro`: run the test under gdb |
| `-e`, `--efficiency [N]` | compare each function with a "perfect" time computed for this machine, gauge at the bottom, target N% (default 50) |
| `-t`, `--target N` | efficiency target in % (1–100); turns `-e` on |
| `-f`, `--func LIST` | libft: `ft_split,itoa` · printf: `%d,%s,flag -,précision .` · gnl: any BUFFER_SIZEs, `1,42,77,100k,def` · push_swap: `errors,simple,bench,perf100,checker…` · python: `ex0,ex7,ft_plot_area` |
| `-p`, `--part N` | libft: 1, 2 or 3 · printf / gnl / push_swap: 1 (mandatory) or 2 (bonus) |
| `--file F\|SIZE` | gnl: test only your file (compared line by line with its content), or a generated file of that size (`64k`, `2M`, 256M max); repeatable, comma-separated |
| `-c`, `--chill` | downgrade style/hygiene check KOs (norminette, flake8/mypy, extra files, README, includes, Makefile hygiene) to warnings (▲) |
| `--no-checks` | skip Makefile / norm / nm / prototype / Python AST checks |
| `--no-norm` | skip norminette (C) or flake8 / mypy (Python) |
| `--no-sanitize` | skip the `-fsanitize=address,undefined` pass |
| `--no-hidden` | ignore hidden files/folders in extra-file, include-use and norminette checks |
| `--seed N` | fuzzing seed (default 42) |
| `--timeout S` | per-test timeout (default 3 s, 10 s for gnl, 20 s for push_swap) |
| `--no-color` | no colors |
| `--lang en\|fr` | override the detected output language |
| `--list-projects` | list supported project modules and subject versions |
| `--custom-tests-dir DIR` | use user test manifests from this directory instead of the default config location |

After installation, use `torture` from your project directory or any other folder;
you do not need to start it from the ftorture checkout. Paths containing spaces
are supported. The launcher is Python-only; no shell wrappers are provided.
Keep the checkout in place: the installed launcher loads its Python code and C suites.

At the end, ftorture runs your project's `make fclean` (libft, ft_printf, push_swap), even after an
error or a Ctrl-C: no `.o` file, archive or binary is left behind. get_next_line is compiled in the
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

**Subfolders**: libft, ft_printf and push_swap may keep their sources and headers in
subfolders (`srcs/`, `includes/`…); the header is looked for at the root, then in
subfolders, and every folder holding a `.h` is a `-I` for include and prototype checks. The
`Makefile`, `README.md` and the archive stay at the root. get_next_line keeps its 3 files at
the root, as its subject requires.

In every project, what the folder's `.gitignore` files ignore (at the root or in a
subfolder, with `!`, `**` and `/` as in git) is not part of your submission: extra-file,
include and norminette checks skip it. The "Extra files" line says how many entries were
left out this way.

| Area | Details |
|---|---|
| **Makefile** | rules `$(NAME) all clean fclean re` (+ `bonus` for printf), **bonus file names** (with a `bonus` rule, every `.c` built by `make bonus` but not by `make all`, and every header only those files include, must end in `_bonus.c` / `_bonus.h`; shared files keep their name; only ▲ for push_swap, whose subject lists `*.c` / `*.h` for the checker), `cc`, `-Wall -Wextra -Werror` on every file (read with `make -nB`, even with `@`), `ar` and not libtool, no `-std=c99`, **relink** (including `make bonus`), `clean` / `fclean` |
| **Files** | files to submit, **extra files are KO** (hidden files except `.git` / `.gitignore`, unexpected extensions such as `.py` `.cpp` `.txt` `.o`, empty folders), `README.md` (italic first line, Description / Instructions / Resources, + algorithm explanation for printf) |
| **Code** | norminette (if installed), **unused `#include`** (a `<lib.h>` must give something the file uses, a project `"x.h"` one of its functions, structs, macros or libs; duplicates too), **forbidden external functions** (anything but `malloc`, `free`, `write`, with the offending file; for ft_printf, the functions of your `libft/` are allowed and its own external calls checked the same way, and **libft in the archive** is KO when `libftprintf.a` calls a function of `libft/libft.a` without containing it: the evaluation links `libftprintf.a` alone, so `cp libft/libft.a $(NAME)` before `ar rcs`), **global variables**, non-`static` helpers (libft), functions present in the archive |
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
  fuzzing (random formats of up to 8 conversions).
- **Arguments read as an `int`**: every `%c %d %i %u %x %X` also gets an argument whose
  64-bit slot has **non-zero upper 32 bits**, in a register and on the stack (past the
  6th argument). `va_arg(ap, int)` reads the right value; `va_arg(ap, unsigned long)`
  prints `5a5a5a5affffffff` instead of `ffffffff` for `%x` and `-1`. That is the bug
  the moulinette finds and a plain `printf("%x", -1)` call hides (the register's upper
  bits are often 0). Same check through the bonus flags.
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
- **More**: `\r\n` line endings, empty lines at the start, the 255 non-zero bytes,
  `read()` returning less than asked, the same fd number reused after the end (nothing
  of the old file may come back), a write-only fd, `/dev/null`, very large fds (1024,
  10 000, 65 535, `INT_MAX`, negatives: an unbounded `stash[fd]` crashes there).
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

**Any buffer size, your own files**: `-f` takes any list of `BUFFER_SIZE`s
(`3,77,4096`, `100k` = 100 000, `10M`, `def`); a size outside the usual list gets its own
line (8 at most) and runs in the bonus too. `--file` replaces the usual tests with your
inputs: a text file of yours, read line by line and compared with its content, or a size
(`64k`, `2M`) that generates random lines of 0 to 200 characters, one of 10 000, the last
one without `\n`. With `--file`, the default timeout grows with the file size and shrinks
with the `BUFFER_SIZE` (10 s + ~10 µs per `read()`, 10 min at most); `--timeout` overrides it.

**The Bible**: every pass also reads the King James Bible (4.3 MB, 99 594 lines, public
domain, `data/bible-kjv.txt.gz`), a real big text file, with a size that makes sense for
the buffer: the whole book from 32 to 10 000 (and without `-D`), its first
`BUFFER_SIZE × 50 000` bytes below 32, its first 100 KB above 10 000 (a stash that size
copied after every line would mean gigabytes of copies).

**Small `BUFFER_SIZE`s without waiting 10 minutes**: very long lines (100 000 and 300 000
characters) are cut to 4096 `read()` calls, so 4096 characters with `BUFFER_SIZE=1`, still
far beyond the buffer. A stash rebuilt by a `strjoin` after every `read()` is quadratic:
`BUFFER_SIZE=1` used to spend minutes there and end in `T`. The real 100 000 character line
is kept in a ▲ "in less than 3 s" test that stops after 3 s and says why, and `-e` measures
that cost.

`BUFFER_SIZE=0` and `BUFFER_SIZE=10000000` count as ▲: the subject asks the question
(a 10 MB buffer on the stack crashes); you need to be able to explain it.

## push_swap

Subject v1.2 (the new one, with `--simple`, `--medium`, `--complex`, `--adaptive` and
`--bench`). ftorture runs `make`, then `make bonus` when there is a bonus rule, and executes
**your binaries** `./push_swap` and `./checker`. Every output is replayed on a built-in
stack simulator: stdout must hold only operations (`sa sb ss pa pb ra rb rr rra rrb rrr`),
one per line, that leave `a` sorted and `b` empty.

- **Arguments**: no argument (nothing is printed), `INT_MIN` / `INT_MAX`, negatives;
  ▲ a single string `"3 2 1"`, `+3`, `007`.
- **Errors** (`Error\n` on stderr, nothing on stdout): not an integer, `1.5`, `12a`, `+`,
  `-`, overflows (`2147483648`, `-2147483649`, 20 digits), duplicates, with or without a
  selector; ▲ `""`, `" "`, `+1 1`, `0 -0`, unknown flag, two selectors.
- **Already sorted**: no operation, whatever the strategy.
- **2 to 5 numbers**: every permutation of 3, 4 and 5 numbers; ▲ 3 numbers in at most 3
  moves, 5 numbers in at most 12 (what the evaluation expects), `2 1` in one `sa`.
- **Each strategy** (`--simple`, `--medium`, `--complex`, `--adaptive`): 2 to 500 numbers,
  random, reversed, `INT_MIN` / `INT_MAX`. `--adaptive`: one input per regime of the subject
  (disorder < 0.2, 0.2–0.5, ≥ 0.5), and no flag = `--adaptive`. ▲ **growth**: the operation
  count is measured at 100 then 400 numbers (`ops ~ n^e`); `--medium` must stay under
  n^1.75, `--complex` and `--adaptive` under n^1.4. ▲ the strategies must give different
  outputs.
- **`--bench`**: stdout unchanged; on stderr the disorder in % with 2 decimals (checked
  against the subject's formula), the strategy name and its `O(...)` class, the total and
  the count of each of the 11 operations; ▲ `--simple --bench` in the other order,
  `--bench` on a sorted input.
- **Performance** (default strategy, random lists): 5 lists of 100 numbers under 2000
  operations and 5 of 500 under 12000 (the subject's minimum); ▲ "good" (< 1500 / < 8000)
  and "excellent" (< 700 / < 5500) on the worst of 10 / 5 lists. A random list has a
  disorder close to 0.5: when it falls in the subject's medium regime (0.2 to 0.5),
  `--adaptive` must use its O(n√n) there, so going over the limit is only a ▲. Every sort is
  also confirmed by the **official checker** `checker_linux` when one is found (`--checker
  PATH`, else the project folder, then `~/Downloads`): it is copied executable into
  `build/`, your file is left as it is.
- **`checker` bonus**: the subject's examples, `OK` / `KO` (b not empty, empty list),
  operations on empty stacks, random lists of the 11 operations compared with the
  simulator, sorting 100 and 500 numbers, your push_swap's output, no argument; errors
  (invalid arguments, duplicates, overflows, instructions `foo`, `SA`, `" sa"`, `"sa "`,
  `rrrr`); ▲ empty line, `sa` without a final `\n`.
- **Checks**: files (`Makefile`, `*.c`, `*.h`, `README.md`, a `libft/` folder), rules
  `$(NAME) all clean fclean re` (+ `bonus`), `cc -Wall -Wextra -Werror`, relink,
  `make clean` / `fclean` (`push_swap` and `checker`), README (algorithm, both logins and
  each one's contribution), norminette, includes, only `read`, `write`, `malloc`, `free`,
  `exit` (`nm` on the `.o` files your Makefile made), no global variable (nor a `static`
  global, ▲), and **valgrind** on sorts, errors, `--bench` and the checker: a leak or an
  invalid access = ✘, still reachable = ▲. Without valgrind the line is skipped.

With `-e`, push_swap's efficiency is not a time: it is your **average operation count**
on 20 lists of 100 and 8 lists of 500 numbers, compared with the subject's "excellent"
threshold (100 % = 700 or 5500 operations). The 50 % target (default) therefore means
1400 and 11 000 operations.

## Understanding a failure (`-v`) and replaying it (`--repro`)

With `-v`, every ✘ / ▲ comes with everything needed to understand and reproduce it:

```
      ✘ #12 « dst NULL, size = 0 »  t_part1.c:429
        your function crashes (SIGSEGV · segmentation fault), but the reference does not
        expected  3
        actual    CRASH
        why       The real function (glibc, BSD, or the reference for functions
                  without an original) handles this input without crashing: …
        test      │ VS(ft_strlcat, "dst NULL, size = 0")
                  │ {
                  │  OUT("%zu", PICK(ft_strlcat, r_strlcat)(NULL, "abc", 0));
                  │ }
        call      ft_strlcat(NULL, "abc", 0);
        main.c    │ #include "libft.h"
                  │ …
                  │  ft_strlcat(NULL, "abc", 0);  /* expected: 3 · actual: CRASH */
                  cc -g main.c libft.a && valgrind ./a.out
        replay    torture libft ~/libft --repro 't_part1.c#97@ft_strlcat'
```

- **why**: what the error means and what to look at in your code, by kind of failure
  (segfault, read past the end of a guarded buffer, abort, timeout, leak, double free,
  unprotected malloc, result different from the original, ▲ protection…).
- **test**: the source of the test (or the macro line that generates it).
- **call** and **main.c**: the call that triggers the failure and a main to paste into
  your project (for get_next_line: a main that reads `test.txt`).
- **replay**: `--repro` rebuilds **only that test** with your code, without fork and with
  the real malloc, then runs it under **valgrind** when installed: the faulty line of
  your code is shown. The test data stays glued to a forbidden page (an over-read still
  crashes), the same failing malloc is reproduced (`mK` in the token), and so is the
  random seed. Add `--gdb` to debug it step by step.

```bash
torture libft ~/libft --repro 't_part1.c#97@ft_strlcat'          # valgrind
torture libft ~/libft --repro 't_part1.c#97@ft_strlcat' --gdb    # gdb
```

Without `-v`, the report stays compact; `ftorture.log` always contains the full details.

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

## Efficiency (`-e`)

```bash
torture libft ~/libft -e        # target 50% (default)
torture gnl ~/get_next_line -t 30
```

Also a box in the menu, right under verbose. There is no reference implementation:
each workload declares the **minimal work** one repetition needs, what a perfect
implementation cannot avoid (`ft_strlen` on 1000 chars = 1 call + 1000 bytes read;
`ft_putstr_fd` = the length + **one** `write()`; get_next_line = one `read()` per
`BUFFER_SIZE` bytes, each byte searched and copied once, one `malloc` per line).
ftorture measures once, **on your machine**, the cost of each unit with the tightest
loop that does it (compiled like the tester, `-O0`, data in the L1 cache, fastest of
several loop shapes, best of 20): loop turn, byte read / copied / written /
compared, call, comparison, digit, list node, `malloc`+`free`, big `malloc`, system
call, byte brought by `read()`. The **perfect time** is the sum.

**efficiency = perfect time / your real time**: 100% = no wasted work. Your function
runs in its own process (malloc not instrumented), calibrated to ~15 ms of
repetitions, best time per repetition of 3 runs. Each function gets `⚡ N%` on its
line; the bottom gauge shows the geometric mean (each value kept between 1% and
200%) with a `┃` mark at the target, the functions below it, and the main machine
costs. A little over 100% can happen (the -O0 code of your loop may be a bit
tighter than the calibration loop, or you compile with `-O2`). Efficiency is
information only: it never turns the run KO.

What usually costs: a `write()` per character (a system call costs hundreds of byte
operations: `ft_putstr_fd`, `ft_printf`), scanning or copying the same data twice
(`ft_strlcpy` that computes the length then copies, `ft_split`), walking a list again
for each node (`ft_lstmap`), a get_next_line stash rebuilt by a `strjoin` after every
`read()` (quadratic in the length of a line) or a `BUFFER_SIZE` buffer allocated at
every call. GNL is not measured without `-D BUFFER_SIZE`.

The workloads and their `COST()` are in `src/*/b_*.c`; `ftorture.log` gives the
perfect and real time of each function and every machine cost
(`FTORTURE_BENCH_DEBUG=1` prints them live).

## Sanitizers (`-fsanitize`)

After the tests, libft, ft_printf, get_next_line and push_swap run again with **your code
rebuilt with `-fsanitize=address,undefined`** (AddressSanitizer + UndefinedBehaviorSanitizer),
without ftorture's malloc tracker so ASan sees the real heap. The same tests run silently
(for push_swap: each strategy from 3 to 500 numbers, `INT_MIN` / `INT_MAX`, errors,
`--bench`, the checker); only the reports count, in a **SANITIZERS** section before the
result:

- **signed integer overflow**, the classic "negation overflow": `-n` on `INT_MIN` in
  `ft_itoa`, `res * 10 + d` overflowing while reading `-2147483648` in `ft_atoi`,
  `ft_putnbr`…
- **out-of-bounds** accesses on the stack, globals and heap (even one byte, even without a
  crash), use after free, double free;
- invalid shifts (`1 << 32`), division by zero, invalid values.

Each problem gives `file.c:line`, the function and the first test that triggered it; ✘
in general, ▲ when it only happens in speculative tests (undefined inputs).

**Overflows that cancel out**: UBSan does not stop the program, so every test runs to its
end. When a signed integer overflow only happens in tests that get **the right result** in
the normal pass (for push_swap: exactly the output of your normal binary), it is noticed
but not an error: a ✔ "signed overflow that cancels out" line. Example:
`ft_atoi("-2147483648")` accumulating `2147483640 + 8` then multiplying by `-1` lands on
`INT_MIN` again. An overflow in a test with a wrong result stays ✘; an out-of-bounds
access never cancels out. `NULL`
dereferences stay with the normal tests (compared with the libc's crash). `--no-sanitize`
skips this pass; without the ASan/UBSan runtimes, the line is skipped.

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
src/push_swap/                    push_swap tests (t_push_swap.c, t_checker.c, simulator ps.c)
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
