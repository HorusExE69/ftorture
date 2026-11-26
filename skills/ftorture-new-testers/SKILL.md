---
name: ftorture-new-testers
description: Extend ftorture's Python project registry and native subject checks with reliable C suites for additional 42 projects, including build strategies and regression tests.
---

# Add a project tester

Use this skill when changing **ftorture**, not a student's submission. Installation, CLI, builds, checks, and pass coordination are Python-native; the process-isolated test engine and suites remain C. Read the exact subject/version first. Do not reuse another project's rules merely because its build looks similar.

## Architecture map

| Component | Responsibility |
|---|---|
| `ftorture/cli.py` | Argument validation, dependency checks, checkout lock, lifecycle and interruption handling |
| `ftorture/projects/base.py` | `Project` metadata and `validate`, `checks`, `run`, `cleanup` hooks |
| `ftorture/projects/__init__.py` | Explicit `PROJECTS` registry, aliases and header-based detection; also drives the menu (`PythonProject` subclasses appear in the PYTHON MODULES submenu of `ftorture/ui.py`, not in the main menu) |
| `ftorture/registry.py` | Unified registry, collision validation, bundled detection and custom discovery for CLI/TUI |
| `ftorture/projects/custom.py` | Versioned user manifests and command-suite lifecycle, separate from native C checks |
| `ftorture/projects/archive.py` | Makefile/archive building and linking; compare `libft.py`/`printf.py` |
| `ftorture/projects/gnl.py` | Example source-only strategy with multiple compiled test passes |
| `ftorture/projects/push_swap.py`, `push_swap_tests.py` | Pure-Python executable strategy: `make`/`make bonus` build binaries, Python runs them & replays stacks |
| `ftorture/projects/python.py` | Reusable isolated Python test runner (`PythonProject`, `PySuite`, `PyTestCase`, subprocess helpers) |
| `ftorture/projects/py00.py`, `py01.py` | Bundled 42 Python modules (*Growing Code* v3.0, *Code Cultivation* v3.2) |
| `ftorture/repro.py`, `src/repro.c` | `--repro` / `--gdb` single-test C replay without fork (valgrind/gdb friendly) |
| `ftorture/runtime.py` | `Options`, `Context`, subprocess cancellation, paths, compiler flags and C JSONL streaming |
| `ftorture/renderer.py`, `ftorture/explain.py` | Unified Python presentation, `-v` explanations/source snippets, multi-pass aggregation, efficiency gauge, `RESULT` box and `ftorture.log` backend for all suites |
| `ftorture/language.py` | English/French selection from locale and complete-message selection |
| `ftorture/checks.py` | `CheckSession` probes/localized messages (`soft=True` for `-c/--chill`) and delimiter-safe `CheckReport` records |
| `ftorture/subject/` | Native file, README, norm, include-use, symbol, prototype, `.gitignore`, Python AST/flake8/mypy (`python.py`) and project-specific checks |
| `install.py` | Managed launcher, safe update, confirmed `--delete --confirm` uninstall, shell detection and consent-based PATH configuration |
| `src/zft.h`, `src/project.h` | C test macros/helpers and suite descriptor contract |
| `src/engine.c`, `src/memtrack.c` | Lean JSONL-only C execution & benchmark shim (forked tests, `VS`/`MTEST`, `BENCH`, `hw_calibrate`) + guarded-memory allocation tracker |

## Integrate the project

1. Extract mandatory/bonus files, prototypes, allowed functions, flags, behavior, resource limits, and undefined cases from the subject. Define the oracle and which cases are speculative. Executable-based or interactive projects may need a new build/capture strategy; the existing archive strategy is not a universal harness.
2. Add `ftorture/projects/<key>.py` with a `Project` subclass and a `PROJECT` instance. Set a unique stable key, name, header, subject version, valid `parts`, aliases, `tools`, and optional `check_tools` (required only when checks run). Declare `requires_compiler=False` for command-only strategies and `requires_makefile=True` when path validation needs a Makefile (`ArchiveProject` already sets it). Import/register the instance in `PROJECTS`; retain deliberate detection priority in `Registry.detect` where headers overlap. No CLI/menu branches should be needed for an ordinary registered project.
3. Call `super().validate(ctx)` before additional validation. Implement `checks(ctx)` with the subject's own policy; the base method intentionally fails rather than pretending checks exist. Implement `run(ctx) -> int`; put cleanup in `cleanup(ctx)`, which the CLI calls in `finally`, including after errors/interruption.
4. For archives, extend `ArchiveProject`, configure `archive`, `source_dir`, and `symbol_prefix` (default `ft_`), then use `build_archive`, `link`, and `ctx.tester`. Override `extra_archives` for linked dependencies. For source-only projects, use `ctx.compile`/`require` and explicit passes as in GNL. Pass argument lists, never interpolated command strings; use `ctx.cc` to preserve compiler arguments.
5. Keep artifacts under `ctx.build`; use `ctx.root` for tester resources and `ctx.options.directory` for student files. `ctx.engine_args`/`tester` forward language, seed, flags, report paths and filters; do not reconstruct them unnecessarily. Multi-pass runs must carry `ctx.stats` with `--stats-out`/`--stats-in`, display checks once, and print one final summary. Translate project-level filters to suite keys when necessary (GNL uses `function_filter=False`). Never report skipped bonus as passed.

## Implement native checks

Use `CheckSession(ctx)` and persist `session.report.write(ctx.checks_file)` in `finally`. `session.capture` returns `(status, output)` and saves numbered diagnostics; `session.compiler` writes and compiles a C probe. `session.check` selects complete English/French labels and details. Do not translate user data or generated source.

Reuse `check_files(session, allowed_predicate)`, `check_readme`, `check_norm`, `IncludeAnalysis(session).run()`, and `check_symbols` from `ftorture/subject/` with explicit subject policies. The existing `allowed_path` and archive/GNL check orchestrators encode current projects, not arbitrary new subjects. Use `self.find_header(directory)` rather than `directory / header` (set `nested=False` on a project whose subject imposes root files), and `session.compiler` already passes every header folder as `-I`. Walk student files only through `project_files` (file, include and norminette checks do): it respects `--no-hidden` (`ctx.options.ignore_hidden`) and the folder's `.gitignore` rules (`ftorture/subject/gitignore.py`, a git-compatible matcher that needs no git or repository). Do not `rglob` the student folder for submission checks; `make clean` leftovers are the exception, since cleaning must remove ignored `.o` files too. If using `check_prototypes`, supply `protos/<key>.txt` entries as `name|function-pointer type|displayed prototype`; `linked_list=True` is specifically libft's layout requirement. Include-use analysis is heuristic: unresolved headers must not be invented into failures.

`CheckReport` writes engine records through `section`, `check` (`OK`, `KO`, `WARN`, `SKIP`), `detail`, `prototype`, and `end_prototypes`; do not hand-concatenate delimiters. Pass `soft=True` to `session.check(...)` for style/hygiene checks that `-c`/`--chill` should downgrade from `KO` to `WARN`. Missing or wrong requirements are check failures, not operational exceptions. Use `RunnerError` for an inability to build/run/check, and preserve status semantics: `0` pass, `1` tests/checks failed, `2` operational error, `130` interruption.

## Add a Python project tester

42 Python modules (`py00`, `py01`, future `py02`…) use the native Python test framework instead of the C engine:

1. Define `SPECS: tuple[ExerciseSpec, ...]` in `ftorture/projects/<key>.py` describing each exercise's directory, expected `.py` files, authorized built-ins (`frozenset[str]`), `allowed_imports`, `allow_classes`, `allow_main_block`, `require_main_block`, and `require_type_hints`.
2. Define `SUITES: tuple[PySuite, ...]` with `PyTestCase` entries. Always execute student code in isolated child `python3` subprocesses via `eval_module_code`, `expect_json_outcome`, or `run_script_file` from `ftorture/projects/python.py`: they set `PYTHONDONTWRITEBYTECODE=1` (never polluting student folders with `__pycache__`), use `start_new_session=True` for clean timeout/Ctrl-C teardown, and load modules via `importlib.util.spec_from_file_location`.
3. Instantiate `PROJECT = PythonProject(key=..., name=..., header="", subject=..., aliases=..., specs=SPECS, suites=SUITES, check_naming_conventions=...)` and register it in `ftorture/projects/__init__.py`. `PythonProject.matches()` auto-detects the project from `SPECS` marker files (no header needed), `requires_compiler=False` skips C tool checks and adapts the TUI options screen (`flake8 / mypy`, no `-e`), and `repro.py` rejects `--repro` cleanly.
4. Add menu descriptions/taglines in `ftorture/ui.py` and add unit/integration tests in `tests/test_python_projects.py` (update the custom-suite shortcut index in `tests/test_tui.py` when adding a bundled C project; a new Python module only adds a row to the PYTHON MODULES submenu).

## Write and link C suites

For personal command/script tests rather than an official C tester, prefer a
version-1 manifest in `${XDG_CONFIG_HOME:-$HOME/.config}/ftorture/tests/`.
Follow `docs/custom-tests.md` and `examples/custom-tests/`; no ftorture source
edits are needed. These suites are deliberately namespaced `custom-<key>`, marked
`[CUSTOM]` in the original menu, and never auto-detected or presented as subject
validation. Discovery must remain data-only. Validate argument arrays/placeholders,
never implicitly invoke a shell, and use the shared cancellation/timeout lifecycle.
Do not promise C memory instrumentation for plain command suites. Regression tests
live in `tests/test_custom_tests.py` and custom-menu PTY coverage in `tests/test_tui.py`.

- Add `src/<key>/proj.c` defining exactly one `g_proj` and suites with stable keys, labels, part numbers, and student function addresses. Weak declarations let missing symbols be reported; archive symbols must still be force-linked via the correct prefix. Audit the engine before expanding it: part arrays currently allow parts 1–3, statistics storage is bounded, and localization contains project-specific assumptions.
- **Executable projects** (push_swap): the suites run the student's program from `zft_path()` (the `--path` directory) with `ps_exec` in `src/push_swap/ps.c`: pipes for stdin/stdout/stderr, `PR_SET_PDEATHSIG` so a looping binary dies with the test, signals reported as crashes. Validate outputs with an independent oracle (push_swap: the stack simulator `ps_replay`), never with the student's own checker. Test names are static strings registered before arguments are parsed: write them in French and add the words to `localize()` in `src/engine.c`; messages use `T(fr, en)` (`zft_en()`). Every test child restarts from `--seed`, so tests meant to use different random lists must skip ahead themselves (`perf_one(n, limit, set)`). The descriptor points `addr` at a dummy (`&g_present`); the Python side passes `-p 1` plus a `--note` when there is no bonus rule. Inside a test, use `malloc`/`free` only (memtrack wraps them, not `realloc`). Use the `.o` set produced by the Makefile (snapshot after `fclean`) for `nm` checks, not every `.o` in the folder.
- Put tests in `src/<key>/t_*.c`. Match each `TEST` suite key to the descriptor. Use `SPEC_TEST` for non-required behavior, `VS`/`VS_SPEC` with an independent justified reference, and `MTEST` for allocation failures. For comparisons, use `PICK(student, reference)` and `OUT(...)` on both reference paths; libc is not an oracle for every subject requirement.
- Record `INPUT(...)` before risky calls. Assert exact values/bytes with `CHECK`, `EQ_INT`, `EQ_SZ`, `EQ_STR`, or `EQ_MEM`. Capture bytes **and** return values for output projects; see `src/printf/pf.h`. Use `gstr`/`gmem`/`gbuf` and `alloc_size` when relevant; free allocations and close descriptors. Use `XFREE` when an allocation may originate from either reference path.
- Bracket only relevant student allocations with `ARM()`/`DISARM()` in `MTEST`; failure replays must not crash or leak. Use `zrand()`/`--seed` for deterministic fuzzing, not timing-dependent randomness. Link the engine, memory tracker, suite sources and student objects with appropriate wrappers and `-lm` (the efficiency summary uses `log`/`exp`); current suites wrap `malloc`/`free`, and GNL additionally wraps `read`. `ArchiveProject.link` globs `src/<source_dir>/*.c`; `GnlProject` lists its C files explicitly in `ftorture/projects/gnl.py`, so a new file there must be added to `tests`. Tests can also be registered at run time by calling `zft_register` from a constructor (GNL `--file`: `src/gnl/t_gnl_custom.c`, list passed in `FTORTURE_GNL_FILES`), and the engine's `--name A,B` keeps only tests whose raw (untranslated) name contains one of the items. Keep a test's worst case well under its timeout: cap inputs whose cost explodes for some parameters (GNL `LONG()`), and measure the full case in a ▲ test that arms its own `alarm()` and fails with an explanation instead of a bare `T`.

## Verbose details and `--repro`

- With `-v`, `make_detail` appends (after `DETAIL_SEP`) why the test fails (`explain()`, chosen by the `why()` call placed before each `make_detail`), the test's source read from `t->file`, a call/`main.c`, and `<--repro-cmd> --repro FILE#IDX[mK]@SUITE[=BS]`. Set a `why()` for any new failure path.
- `IDX` is the `__COUNTER__` of the `TEST` in its file (`t_test.idx`, last argument of `zft_register`); runtime-registered tests pass `-1` and get no replay line.
- `ftorture/repro.py` compiles that single test file with `src/repro.c` (same `zft.h` API, no fork, real malloc, guarded test buffers) plus the project's helper files (every `src/<project>/*.c` except `t_*`, `b_*`, `proj.c`) and the student's code, then runs it under valgrind or `--gdb`. Any new function added to `zft.h` must also be implemented in `src/repro.c`; any new build strategy needs a branch in `student_objects()`.

## Efficiency workloads (`-e`)

- Add `src/<project>/b_*.c` with `BENCH(key) { COST(...); BENCH_LOOP { … } }` (see `src/zft.h`). The key matches a suite key of the descriptor (`ft_strlen`, GNL's `GNL_SUITE`); a key that matches no suite (`ft_printf`) is a project-level benchmark, run once per pass after the suites and labelled ` (bonus)` with `-p 2`. Call the student function directly (no reference implementation). Feed results to `SINK(x)` so nothing is optimised away; build fixtures once with a `static` guard (the first call is a warm-up, and is when `COST()` is read). Free with `free` (malloc is not instrumented during a benchmark).
- `COST()` declares, per repetition, the **minimal** work a perfect implementation cannot avoid, in the `t_cost` units: `iters` (harness loop turns), `calls` and `ops` (priced **on top** of the loop turn they sit in), `scan`/`copy`/`store`/`cmp` bytes (each includes its own loop turn), `digits`, `nodes`, `allocs`, `big_allocs`, `sys`, `rbytes`. Count the harness work inside the loop too (callbacks, the frees of what the student allocated, an `lseek`), but not cheap libc helpers used for setup. It may depend on runtime data (GNL computes it from the file and `Z_BS`). Do not invent work a perfect version would skip (one `write()` per string, not per char; one pass when one is enough), and write the reasoning in a comment above the `BENCH`.
- `hw_calibrate()` in `src/engine.c` prices each unit once per process: tightest `-O0` loop, L1-sized data (`HW_N` 4 KiB, `HW_NODES` 1024), fastest of several loop shapes (index `int`/`size_t`, pointer), best of 20; `calls`/`ops` are measured against an empty loop. When adding a unit, add its field to `t_cost`, a calibration, `ideal_time()`, the debug/log lines, and keep the stats file layout (`g_fs`, `g_ck`, `g_nbr`, `g_br`, `g_hw_ok`, `g_hw`, appended in that order).
- An efficiency that is not a time uses `SCORE(key) { … SCORE_SET(ideal, real); }`: it runs once in a child (no calibration, 120 s limit), `pct = ideal / real`, and the log line prints "reference / yours" instead of µs. push_swap uses it with the subject's "excellent" thresholds as `ideal` and the average operation count as `real`; the machine-cost line is only shown when a timed benchmark ran.
- The student side is calibrated to ~15 ms of repetitions in its own process, best time per repetition of 3 runs, killed after 2 s (shown as `<N%`). Check a new workload with `FTORTURE_BENCH_DEBUG=1`: a clean implementation should land near 100% (not far above: that means the `COST()` overcounts), a slow-on-purpose fixture low, and reruns within a few %.

## Memory tracker limits

`memtrack.c` gives every malloc its own guarded mapping in a 131 072-entry table; past 3/4 full it falls back to the real malloc, and after 20 000 frees it `munmap`s blocks (state 3) whose address range the libc may reuse. Tests that make hundreds of thousands of allocations (GNL with `BUFFER_SIZE=1`) exercise this path: keep `is_mapped` checks on state-3 entries, or "free in the middle of a block" / "double free" false positives come back.

## Validate and document

```bash
python3 -m unittest discover -s tests -v
torture --list-projects
torture <key> /path/to/known-good-project --no-norm
```

For migration parity use `python3 tests/compare_legacy_libft.py /path/to/libft`.
It compares legacy Bash and Python behavior on independent temporary copies,
including all 43 function summaries; do not run it concurrently with integration
tests. See `docs/validation.md` for the reference revision, observed results, and
the distinction between behavioral parity and native subject-check validation.
User-facing commands must use the installed Python launcher `~/.local/bin/torture`;
do not add shell wrappers or require users to run from the ftorture checkout.
Direct Python entry points are retained for internal tests and development only.

Add native-check regressions in `tests/test_subject_checks.py` and real-engine integration coverage in `tests/test_python_runner.py`, or focused new test modules. Use temporary student fixtures. Cover known-good and broken behavior, wrong/missing symbols/prototypes, build errors, complete/partial bonus support, filters/parts, speculative mode, repeatable seeds, language, spaces in paths, and interruption cleanup. Validate checks on a deliberately messy fixture too: unused `<stdio.h>`, a duplicate include, a project header nothing uses, `.py`/`.txt`/`.o`/hidden files and an empty folder must all be KO, while a header used only through its includers stays OK. Run full mandatory/bonus suites as well as focused tests. Tests overwrite shared checkout artifacts/reports; run serially. Update both READMEs with the subject version, commands and limitations. Never weaken an oracle to accommodate one student's code.
