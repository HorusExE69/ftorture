"""Pure-Python push_swap v1.2 test suites, stack simulator, and -e score."""
from collections import deque
import itertools
import math
import os
from pathlib import Path
import random
import re
import signal
import subprocess

from ..runtime import Context, RunnerError

VALID_OPS = frozenset({"sa", "sb", "ss", "pa", "pb", "ra", "rb", "rr", "rra", "rrb", "rrr"})
OPS_LIST = ("sa", "sb", "ss", "pa", "pb", "ra", "rb", "rr", "rra", "rrb", "rrr")
KNOWN_SUITES = frozenset({
    "args", "errors", "sorted", "small", "simple", "medium",
    "complex", "adaptive", "bench", "perf100", "perf500", "checker", "ck_errors",
})


def _run_bin(binary: Path, args: list[str], *, cwd: Path, stdin: str = "",
             timeout: int = 20) -> tuple[int, int, str, str]:
    """Run a student binary in a private process group; returns (code, sig, stdout, stderr)."""
    with subprocess.Popen(
        [str(binary), *args], cwd=cwd,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    ) as proc:
        try:
            out, err = proc.communicate(stdin.encode("utf-8") if stdin is not None else None, timeout=timeout)
            rc = proc.returncode
            sig = -rc if rc < 0 else 0
            return (0 if sig else rc), sig, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")
        except (KeyboardInterrupt, subprocess.TimeoutExpired) as exc:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            if isinstance(exc, KeyboardInterrupt):
                raise
            return 124, signal.SIGALRM, "", f"timeout ({timeout}s)"


def replay(values: list[int], output: str) -> tuple[bool, int, str]:
    """Replay push_swap ops on two stacks; returns (sorted_ok, op_count, error_msg)."""
    if output and not output.endswith("\n"):
        return False, 0, "missing final newline"
    a: deque[int] = deque(values)
    b: deque[int] = deque()
    count = 0
    if output:
        for line in output[:-1].split("\n"):
            if line not in VALID_OPS:
                return False, count, f"invalid operation: {line!r}"
            count += 1
            if line == "sa":
                if len(a) >= 2:
                    a[0], a[1] = a[1], a[0]
            elif line == "sb":
                if len(b) >= 2:
                    b[0], b[1] = b[1], b[0]
            elif line == "ss":
                if len(a) >= 2:
                    a[0], a[1] = a[1], a[0]
                if len(b) >= 2:
                    b[0], b[1] = b[1], b[0]
            elif line == "pa":
                if b:
                    a.appendleft(b.popleft())
            elif line == "pb":
                if a:
                    b.appendleft(a.popleft())
            elif line == "ra":
                if len(a) >= 2:
                    a.append(a.popleft())
            elif line == "rb":
                if len(b) >= 2:
                    b.append(b.popleft())
            elif line == "rr":
                if len(a) >= 2:
                    a.append(a.popleft())
                if len(b) >= 2:
                    b.append(b.popleft())
            elif line == "rra":
                if len(a) >= 2:
                    a.appendleft(a.pop())
            elif line == "rrb":
                if len(b) >= 2:
                    b.appendleft(b.pop())
            elif line == "rrr":
                if len(a) >= 2:
                    a.appendleft(a.pop())
                if len(b) >= 2:
                    b.appendleft(b.pop())
    if b:
        return False, count, f"not sorted after {count} operations (stack b not empty: {len(b)} element(s))"
    lst = list(a)
    if any(lst[i] > lst[i + 1] for i in range(len(lst) - 1)):
        return False, count, f"not sorted after {count} operations"
    return True, count, ""


def disorder(values: list[int]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    inv = 0
    for i in range(n):
        vi = values[i]
        for j in range(i + 1, n):
            if vi > values[j]:
                inv += 1
    return inv / (n * (n - 1) / 2)


def random_list(rng: random.Random, n: int) -> list[int]:
    vals = list(range(1, n + 1))
    rng.shuffle(vals)
    return vals


def disorder_list(rng: random.Random, n: int, lo: float, hi: float) -> list[int]:
    if hi <= 0.25:
        vals = list(range(1, n + 1))
        for _ in range(n // 5):
            i = rng.randrange(n)
            j = min(n - 1, i + rng.randrange(1, max(2, n // 4)))
            vals[i], vals[j] = vals[j], vals[i]
            d = disorder(vals)
            if lo <= d < hi:
                return vals
    elif lo >= 0.5:
        vals = list(range(n, 0, -1))
        for _ in range(n):
            i, j = rng.randrange(n), rng.randrange(n)
            vals[i], vals[j] = vals[j], vals[i]
            d = disorder(vals)
            if lo <= d < hi:
                return vals
    else:
        vals = list(range(1, n + 1))
        for _ in range(n * 2):
            i, j = rng.randrange(n), rng.randrange(n)
            vals[i], vals[j] = vals[j], vals[i]
            d = disorder(vals)
            if lo <= d < hi:
                return vals
    return vals


def _has_word(haystack: str, word: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])", haystack, re.I))


def _check_official(checker: Path | None, values: list[int], output: str, cwd: Path, timeout: int) -> str:
    if checker is None:
        return ""
    args = [str(v) for v in values]
    _, sig, out, _ = _run_bin(checker, args, cwd=cwd, stdin=output, timeout=timeout)
    if sig or out != "OK\n":
        ans = out.strip() or f"signal {sig}"
        return f"checker_linux (the official checker) answers {ans}"
    return ""


def run_push_swap_suites(ctx: Context, *, bonus: bool, checker: Path | None,
                         note: str | None) -> int:
    renderer = ctx.renderer
    directory = ctx.options.directory
    ps_bin = directory / "push_swap"
    ck_bin = directory / "checker"
    timeout = ctx.options.timeout or 20
    t = ctx.message

    if ctx.options.checks:
        renderer.render_checks(ctx.checks_file)
    renderer.render_legend(c_mode=False)

    wanted = ({s.strip().lower() for s in ctx.options.functions.split(",") if s.strip()}
              if ctx.options.functions else None)
    if wanted is not None and (unknown := wanted - KNOWN_SUITES):
        raise RunnerError(t("Unknown push_swap suite: ", "Suite push_swap inconnue : ") + ", ".join(sorted(unknown)))
    part_filter = ctx.options.part

    def is_selected(key: str, part: int) -> bool:
        if part_filter and part_filter != part:
            return False
        if part == 2 and not bonus:
            return False
        return wanted is None or key in wanted

    def ps_sorts(flags: list[str], values: list[int], *, use_official: bool = False) -> tuple[bool, int, str, str, str]:
        args = [*flags, *(str(v) for v in values)]
        _, sig, out, err = _run_bin(ps_bin, args, cwd=directory, timeout=timeout)
        if sig == signal.SIGALRM:
            return False, 0, f"timeout ({timeout}s)", out, err
        if sig:
            return False, 0, f"crash (signal {sig})", out, err
        ok, cnt, reason = replay(values, out)
        if not ok:
            return False, cnt, reason, out, err
        if use_official:
            off_err = _check_official(checker, values, out, directory, timeout)
            if off_err:
                return False, cnt, off_err, out, err
        return True, cnt, "", out, err

    def ps_error_case(args: list[str], *, spec: bool = False) -> tuple[str, str, str, bool, str, str, str]:
        label = " ".join(repr(a) if (not a or " " in a) else a for a in args)
        _, sig, out, err = _run_bin(ps_bin, args, cwd=directory, timeout=timeout)
        if sig == signal.SIGALRM:
            return ("▲" if spec else "T"), label, f"timeout ({timeout}s)", spec, label, "Error\\n", ""
        if sig:
            return ("▲" if spec else "✘"), label, f"crash (signal {sig})", spec, label, "Error\\n", ""
        if err != "Error\n" or out:
            return ("▲" if spec else "✘"), label, "expected 'Error\\n' on stderr and empty stdout", spec, label, "Error\\n", f"stdout={out!r} stderr={err!r}"
        return "✔", label, "", spec, "", "", ""

    def run_suite(part: int, part_title_en: str, part_title_fr: str, short_en: str, short_fr: str,
                  key: str, label_en: str, label_fr: str, outcomes: list, eff: dict | None = None) -> None:
        renderer.render_part(part, t(part_title_en, part_title_fr), t(short_en, short_fr))
        renderer.record_suite(part=part, short_name=t(short_en, short_fr),
                              label=t(label_en, label_fr), outcomes=outcomes,
                              label_width=16, eff=eff)

    # ---------------- PART 1: MANDATORY ----------------
    if is_selected("args", 1):
        outcomes = []
        _, sig, out, err = _run_bin(ps_bin, [], cwd=directory, timeout=timeout)
        ok = (not sig and not out and not err)
        outcomes.append(("✔" if ok else "✘", "./push_swap", "" if ok else f"stdout={out!r} stderr={err!r}", False, "./push_swap", "", out or err))
        for lbl, vals in (("1 2147483647 -2147483648 0", [1, 2147483647, -2147483648, 0]),
                          ("-5 -1 -3 -2 -4", [-5, -1, -3, -2, -4])):
            ok, _, msg, _, _ = ps_sorts([], vals)
            outcomes.append(("✔" if ok else "✘", lbl, msg, False, lbl, "sorted", msg))
        for lbl, raw_args, vals in (('"3 2 1"', ["3 2 1"], [3, 2, 1]),
                                    ("+3 2 007", ["+3", "2", "007"], [3, 2, 7])):
            _, sig, out, err = _run_bin(ps_bin, raw_args, cwd=directory, timeout=timeout)
            ok, _, msg = (False, 0, f"crash (signal {sig})") if sig else replay(vals, out)
            outcomes.append(("✔" if ok else "▲", lbl, msg, True, lbl, "sorted", msg))
        run_suite(1, "PART 1 · Mandatory · push_swap", "PARTIE 1 · Obligatoire · push_swap",
                  "mandatory", "obligatoire", "args", "args", "args", outcomes)

    if is_selected("errors", 1):
        hard = [
            ["1", "a", "3"], ["one"], ["1.5", "2"], ["12a", "3"], ["+", "1"], ["-", "1"],
            ["1-", "2"], ["--5", "1"], ["2147483648"], ["-2147483649", "0"], ["4294967296", "1"],
            ["99999999999999999999"], ["1", "2", "1"], ["--simple", "3", "2", "3"],
            ["--adaptive", "0", "one", "2", "3"], ["5", "4", "3", "2", "1", "5"],
            ["-2147483648", "-2147483648"],
        ]
        soft = [["", "1"], [" "], ["+1", "1"], ["0", "-0"], ["--foo", "1", "2"], ["--simple", "--complex", "2", "1"]]
        outcomes = [ps_error_case(a, spec=False) for a in hard] + [ps_error_case(a, spec=True) for a in soft]
        run_suite(1, "PART 1 · Mandatory · push_swap", "PARTIE 1 · Obligatoire · push_swap",
                  "mandatory", "obligatoire", "errors", "errors", "erreurs", outcomes)

    if is_selected("sorted", 1):
        outcomes = []
        for lbl, flags, n in (
            ("42", [], 1), ("2 numbers", [], 2), ("3 numbers", [], 3), ("10 numbers", [], 10),
            ("500 numbers", [], 500), ("--simple 100", ["--simple"], 100), ("--medium 100", ["--medium"], 100),
            ("--complex 100", ["--complex"], 100), ("--adaptive 100", ["--adaptive"], 100),
        ):
            vals = list(range(1, n + 1)) if n > 1 else [42]
            ok, cnt, msg, _, _ = ps_sorts(flags, vals)
            if ok and cnt != 0:
                ok, msg = False, f"already sorted: expected 0 ops, got {cnt}"
            outcomes.append(("✔" if ok else "✘", lbl, msg, False, lbl, "0 ops", f"{cnt} ops" if not msg else msg))
        run_suite(1, "PART 1 · Mandatory · push_swap", "PARTIE 1 · Obligatoire · push_swap",
                  "mandatory", "obligatoire", "sorted", "sorted", "déjà trié", outcomes)

    if is_selected("small", 1):
        outcomes = []
        ok, cnt, msg, _, _ = ps_sorts([], [2, 1])
        outcomes.append(("✔" if (ok and cnt == 1) else "▲", "2 1", msg or f"{cnt} ops", True, "2 1", "1 op", f"{cnt}"))
        for n, max_moves in ((3, 3), (4, None), (5, 12)):
            worst = 0
            bad_msg = ""
            for perm in itertools.permutations(range(1, n + 1)):
                ok, cnt, msg, _, _ = ps_sorts([], list(perm))
                if not ok:
                    bad_msg = f"{list(perm)}: {msg}"
                    break
                if cnt > worst:
                    worst = cnt
            outcomes.append(("✔" if not bad_msg else "✘", f"{n} numbers", bad_msg, False, "", "all sorted", bad_msg))
            if max_moves is not None:
                ok_m = (not bad_msg) and worst <= max_moves
                outcomes.append(("✔" if ok_m else "▲", f"{n} numbers <= {max_moves}",
                                 "" if ok_m else f"worst case {worst} moves (expected <= {max_moves})",
                                 True, "", f"<= {max_moves}", str(worst)))
        run_suite(1, "PART 1 · Mandatory · push_swap", "PARTIE 1 · Obligatoire · push_swap",
                  "mandatory", "obligatoire", "small", "small", "petits", outcomes)

    def run_strategy(key: str, flag: str, max_exp: float | None, cls_name: str, check_distinct: bool) -> None:
        if not is_selected(key, 1):
            return
        rng = random.Random(ctx.options.seed)
        outcomes = []
        cases = [
            ("2 1", [2, 1]),
            ("3 random", random_list(rng, 3)),
            ("5 random", random_list(rng, 5)),
            ("10 random", random_list(rng, 10)),
            ("INT_MIN INT_MAX", [0, 2147483647, -2147483648, -1, 1, 2147483646, -2147483647]),
            ("50 random", random_list(rng, 50)),
            ("100 random", random_list(rng, 100)),
            ("100 reversed", list(range(100, 0, -1))),
            ("500 random", random_list(rng, 500)),
            ("500 reversed", list(range(500, 0, -1))),
        ]
        for lbl, vals in cases:
            ok, _, msg, _, _ = ps_sorts([flag], vals)
            outcomes.append(("✔" if ok else "✘", lbl, msg, False, f"{flag} ({len(vals)})", "sorted", msg))
        if key == "adaptive":
            for lbl, lo, hi in (("disorder < 0.2", 0.02, 0.2), ("disorder 0.2-0.5", 0.25, 0.45),
                                ("disorder >= 0.5", 0.5, 1.01)):
                vals = disorder_list(rng, 500, lo, hi)
                ok, _, msg, _, _ = ps_sorts(["--adaptive"], vals)
                outcomes.append(("✔" if ok else "✘", lbl, msg, False, lbl, "sorted", msg))
            vals = random_list(rng, 100)
            ok1, _, m1, out1, _ = ps_sorts([], vals)
            ok2, _, m2, out2, _ = ps_sorts(["--adaptive"], vals)
            same = ok1 and ok2 and out1 == out2
            outcomes.append(("✔" if same else "✘", "default == --adaptive",
                             "" if same else (m1 or m2 or "default output differs from --adaptive"),
                             False, "100 random", "identical", ""))
        if max_exp is not None:
            a_vals = [random_list(rng, 100) for _ in range(2)]
            b_vals = [random_list(rng, 400) for _ in range(2)]
            a_ops = [ps_sorts([flag], v) for v in a_vals]
            b_ops = [ps_sorts([flag], v) for v in b_vals]
            if all(x[0] for x in a_ops + b_ops):
                avg_a = sum(x[1] for x in a_ops) / 2
                avg_b = sum(x[1] for x in b_ops) / 2
                exp = math.log(avg_b / avg_a) / math.log(4.0) if avg_a > 0 and avg_b > 0 else 0.0
                ok_g = exp <= max_exp
                outcomes.append(("✔" if ok_g else "▲", f"growth {cls_name}",
                                 "" if ok_g else f"ops grow like n^{exp:.2f} (expected <= n^{max_exp:.2f})",
                                 True, f"100:{avg_a:.0f} 400:{avg_b:.0f}", f"<= n^{max_exp:.2f}", f"n^{exp:.2f}"))
            else:
                outcomes.append(("▲", f"growth {cls_name}", "sort failed", True, "", "", ""))
        if check_distinct:
            vals = random_list(rng, 100)
            ok_m, _, _, out_m, _ = ps_sorts([flag], vals)
            dup = ""
            for other in ("--simple", "--medium", "--complex"):
                if other == flag:
                    continue
                ok_o, _, _, out_o, _ = ps_sorts([other], vals)
                if ok_m and ok_o and out_m == out_o:
                    dup = f"{flag} and {other} produce identical operations"
                    break
            outcomes.append(("✔" if (ok_m and not dup) else "▲", "distinct strategy", dup, True, "", "distinct", dup))
        run_suite(1, "PART 1 · Mandatory · push_swap", "PARTIE 1 · Obligatoire · push_swap",
                  "mandatory", "obligatoire", key, key, key, outcomes)

    run_strategy("simple", "--simple", None, "O(n²)", True)
    run_strategy("medium", "--medium", 1.75, "O(n√n)", True)
    run_strategy("complex", "--complex", 1.4, "O(n log n)", True)
    run_strategy("adaptive", "--adaptive", 1.4, "O(n log n)", False)

    if is_selected("bench", 1):
        rng = random.Random(ctx.options.seed)
        outcomes = []
        vals = random_list(rng, 100)
        ok_b, cnt_b, msg_b, out_b, err_b = ps_sorts(["--bench", "--complex"], vals)
        ok_q, _, _, out_q, _ = ps_sorts(["--complex"], vals)
        same = ok_b and ok_q and bool(err_b) and out_b == out_q
        outcomes.append(("✔" if same else "✘", "stdout = operations", "" if same else (msg_b or "stdout changed or empty stderr"),
                         False, "--bench --complex", "same stdout + stderr", ""))
        d = disorder(vals) * 100.0
        r1, r2 = f"{d:.2f}", f"{math.floor(d * 100.0) / 100.0:.2f}"
        ok_d = ok_b and (r1 in err_b or r2 in err_b)
        outcomes.append(("✔" if ok_d else "✘", "disorder %", "" if ok_d else f"expected {r1}% in stderr", False, "", r1, err_b[:120]))
        ok_t = ok_b and _has_word(err_b, str(cnt_b))
        outcomes.append(("✔" if ok_t else "✘", "total ops", "" if ok_t else f"total {cnt_b} missing from stderr", False, "", str(cnt_b), err_b[:120]))
        miss_ops = [op for op in OPS_LIST if not _has_word(err_b, op)]
        outcomes.append(("✔" if (ok_b and not miss_ops) else "✘", "per-op counts",
                         "" if not miss_ops else "missing: " + ", ".join(miss_ops), False, "", "all 11 ops", ""))
        for flag, name in (("--simple", "simple"), ("--medium", "medium"), ("--complex", "complex"), ("--adaptive", "adaptive")):
            ok_n, _, _, _, err_n = ps_sorts(["--bench", flag], vals)
            good = ok_n and (name in err_n.lower()) and ("O(" in err_n)
            outcomes.append(("✔" if good else "✘", f"name {flag}", "" if good else f"missing {name} or O(...)", False, flag, name, err_n[:120]))
        ok_a, _, _, _, err_a = ps_sorts(["--simple", "--bench"], random_list(rng, 50))
        outcomes.append(("✔" if (ok_a and bool(err_a)) else "▲", "--simple --bench", "", True, "", "stderr", ""))
        ok_s, cnt_s, _, _, err_s = ps_sorts(["--bench"], list(range(1, 21)))
        outcomes.append(("✔" if (ok_s and cnt_s == 0 and bool(err_s)) else "▲", "sorted + --bench", "", True, "", "0 ops + stderr", ""))
        run_suite(1, "PART 1 · Mandatory · push_swap", "PARTIE 1 · Obligatoire · push_swap",
                  "mandatory", "obligatoire", "bench", "bench", "bench", outcomes)

    def run_perf(key: str, label_en: str, label_fr: str, n: int, limit: int,
                 good_lim: int, exc_lim: int, tier_sets: int, eff_sets: int) -> None:
        if not is_selected(key, 1):
            return
        rng = random.Random(ctx.options.seed)
        outcomes = []
        for idx in range(1, 6):
            vals = random_list(rng, n)
            d = disorder(vals)
            # Ensure both medium (0.2..0.5) and complex (>=0.5) regimes are covered.
            if (idx % 2 == 1 and d < 0.5) or (idx % 2 == 0 and d >= 0.5):
                vals.reverse()
                d = disorder(vals)
            ok, cnt, msg, _, _ = ps_sorts([], vals, use_official=True)
            lbl = f"{n} random #{idx}"
            if not ok:
                outcomes.append(("✘", lbl, msg, False, lbl, "sorted", msg))
            elif cnt >= limit and 0.2 <= d < 0.5:
                outcomes.append(("▲", lbl,
                                 f"{cnt} operations for {n} numbers (minimum: fewer than {limit}), "
                                 f"but the disorder is {d:.4f}: the subject's medium regime (0.2 to 0.5)",
                                 True, lbl, f"< {limit}", str(cnt)))
            elif cnt >= limit:
                outcomes.append(("✘", lbl, f"{cnt} operations for {n} numbers (minimum: fewer than {limit})",
                                 False, lbl, f"< {limit}", str(cnt)))
            else:
                outcomes.append(("✔", lbl, "", False, "", "", ""))
        for tier_name, tlim in ((t("good", "bien"), good_lim), ("excellent", exc_lim)):
            worst = 0
            bad_msg = ""
            for _ in range(tier_sets):
                vals = random_list(rng, n)
                ok, cnt, msg, _, _ = ps_sorts([], vals, use_official=True)
                if not ok:
                    bad_msg = msg
                    break
                worst = max(worst, cnt)
            ok_t = (not bad_msg) and worst < tlim
            outcomes.append(("✔" if ok_t else "▲", f"< {tlim} ({tier_name})",
                             "" if ok_t else (bad_msg or f"worst case {worst} ops (expected < {tlim})"),
                             True, "", f"< {tlim}", str(worst)))
        eff = None
        if ctx.options.efficiency:
            total_ops = 0
            valid = True
            for _ in range(eff_sets):
                vals = random_list(rng, n)
                ok, cnt, _, _, _ = ps_sorts([], vals, use_official=True)
                if not ok:
                    valid = False
                    break
                total_ops += cnt
            if valid:
                avg = max(1.0, total_ops / eff_sets)
                pct = max(1, min(9999, int(exc_lim / avg * 100.0 + 0.5)))
                eff = {"label": t(label_en, label_fr), "pct": pct, "ideal": float(exc_lim),
                       "real": avg, "bound": False, "score": True}
        run_suite(1, "PART 1 · Mandatory · push_swap", "PARTIE 1 · Obligatoire · push_swap",
                  "mandatory", "obligatoire", key, label_en, label_fr, outcomes, eff=eff)

    run_perf("perf100", "100 random", "100 aléatoires", 100, 2000, 1500, 700, 10, 20)
    run_perf("perf500", "500 random", "500 aléatoires", 500, 12000, 8000, 5500, 5, 8)

    # ---------------- PART 2: BONUS (checker) ----------------
    if is_selected("checker", 2):
        rng = random.Random(ctx.options.seed)
        outcomes = []

        def ck_verdict(lbl: str, args: list[str], ops: str, exp: str) -> None:
            _, sig, out, err = _run_bin(ck_bin, args, cwd=directory, stdin=ops, timeout=timeout)
            ok = (not sig and out == exp)
            outcomes.append(("✔" if ok else "✘", lbl, "" if ok else (f"crash (signal {sig})" if sig else f"got {out!r}"),
                             False, " ".join(args), exp.strip(), out.strip() or err.strip()))

        ck_verdict("3 2 1 0 -> OK", ["3", "2", "1", "0"], "rra\npb\nsa\nrra\npa\n", "OK\n")
        ck_verdict("3 2 1 0 -> KO", ["3", "2", "1", "0"], "sa\nrra\npb\n", "KO\n")
        ck_verdict("1 2 3, empty -> OK", ["1", "2", "3"], "", "OK\n")
        ck_verdict("2 1, empty -> KO", ["2", "1"], "", "KO\n")
        ck_verdict("2 1, sa -> OK", ["2", "1"], "sa\n", "OK\n")
        ck_verdict("b non-empty -> KO", ["1", "2", "3"], "pb\n", "KO\n")
        ck_verdict("pb pa -> OK", ["1", "2", "3"], "pb\npa\n", "OK\n")
        ck_verdict("ops on empty stack", ["1"], "sa\nsb\nss\npa\nra\nrb\nrr\nrra\nrrb\nrrr\n", "OK\n")
        ck_verdict("-1 -2 INT_MIN", ["-1", "-2", "-2147483648"], "rra\nra\nsa\nrra\n", "OK\n")
        for idx, (n, op_len) in enumerate(((6, 30), (8, 60), (20, 200)), 1):
            vals = random_list(rng, n)
            ops = "".join(rng.choice(OPS_LIST) + "\n" for _ in range(op_len))
            ok_r, _, _ = replay(vals, ops)
            ck_verdict(f"random ops #{idx}", [str(v) for v in vals], ops, "OK\n" if ok_r else "KO\n")
        vals = random_list(rng, 100)
        ok_p, _, _, out_p, _ = ps_sorts([], vals)
        ck_verdict("with ./push_swap 100", [str(v) for v in vals], out_p if ok_p else "", "OK\n")
        _, sig, out, err = _run_bin(ck_bin, [], cwd=directory, stdin="", timeout=timeout)
        ok_e = (not sig and not out and not err)
        outcomes.append(("✔" if ok_e else "✘", "./checker", "" if ok_e else f"stdout={out!r} stderr={err!r}", False, "./checker", "", out or err))
        run_suite(2, "PART 2 · Bonus · checker", "PARTIE 2 · Bonus · checker",
                  "bonus", "bonus", "checker", "checker", "checker", outcomes)

    if is_selected("ck_errors", 2):
        outcomes = []

        def ck_err(lbl: str, args: list[str], ops: str, *, spec: bool = False) -> None:
            _, sig, out, err = _run_bin(ck_bin, args, cwd=directory, stdin=ops, timeout=timeout)
            ok = (not sig and err == "Error\n" and "OK" not in out and "KO" not in out)
            outcomes.append(("✔" if ok else ("▲" if spec else "✘"), lbl,
                             "" if ok else f"stdout={out!r} stderr={err!r}", spec, lbl, "Error\\n", f"{out!r} / {err!r}"))

        for lbl, args, ops in (
            ("3 2 one 0", ["3", "2", "one", "0"], ""),
            ('"" 1', ["", "1"], ""),
            ("1 2 1", ["1", "2", "1"], ""),
            ("2147483648", ["2147483648"], ""),
            ("-2147483649", ["-2147483649"], ""),
            ("1a 2", ["1a", "2"], ""),
            ("instruction foo", ["2", "1"], "foo\n"),
            ("instruction SA", ["2", "1"], "SA\n"),
            ('instruction " sa"', ["2", "1"], " sa\n"),
            ('instruction "sa "', ["2", "1"], "sa \n"),
            ("instruction rrrr", ["2", "1"], "rrrr\n"),
            ("sa pb xx pa", ["2", "1"], "sa\npb\nxx\npa\n"),
        ):
            ck_err(lbl, args, ops)
        ck_err("empty line", ["2", "1"], "sa\n\n", spec=True)
        _, sig, out, err = _run_bin(ck_bin, ["2", "1"], cwd=directory, stdin="sa", timeout=timeout)
        ok_nl = (not sig and (out == "OK\n" or err == "Error\n"))
        outcomes.append(("✔" if ok_nl else "▲", '"sa" without \\n', "" if ok_nl else f"stdout={out!r} stderr={err!r}", True, "", "OK\\n or Error\\n", ""))
        run_suite(2, "PART 2 · Bonus · checker", "PARTIE 2 · Bonus · checker",
                  "bonus", "bonus", "ck_errors", "ck_errors", "ck_errors", outcomes)

    if note:
        renderer.add_note(note)
    return renderer.finish(item_en="suites", item_fr="suites")
