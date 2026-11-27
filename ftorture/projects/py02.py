"""python-module-02 (Garden Guardian, v3.0): exceptions for a smart garden.

ex0 input_temperature() / test_temperature(), ex1 the same with a 0-40 °C
range that raises, ex2 garden_operations() raising ValueError,
ZeroDivisionError, FileNotFoundError and TypeError, ex3 GardenError,
PlantError and WaterError, ex4 water_plant() and a finally block.
Type hints are required everywhere; the deliberate "abc" + 1 of ex2 is the
one mypy error the subject asks to keep.
"""
import ast
from pathlib import Path

from .python import (PyOutcome, PySuite, PyTestCase, PythonProject,
                     eval_module_code, expect_json_outcome, run_script_file)
from ..runtime import Context
from ..subject.python import BUILTIN_EXCEPTIONS, ExerciseSpec

EXC = BUILTIN_EXCEPTIONS   # "You may use any built-in exception types"

SPECS: tuple[ExerciseSpec, ...] = (
    ExerciseSpec("ex0", "ex0", ("ft_first_exception.py",),
                 authorized=frozenset({"int", "print"}) | EXC,
                 allow_main_block=True, require_main_block=True, require_type_hints=True,
                 expected_functions=("input_temperature", "test_temperature")),
    ExerciseSpec("ex1", "ex1", ("ft_raise_exception.py",),
                 authorized=frozenset({"int", "print"}) | EXC,
                 allow_main_block=True, require_main_block=True, require_type_hints=True,
                 expected_functions=("input_temperature", "test_temperature")),
    ExerciseSpec("ex2", "ex2", ("ft_different_errors.py",),
                 authorized=frozenset({"print", "open", "int"}) | EXC,
                 allow_main_block=True, require_main_block=True, require_type_hints=True,
                 expected_functions=("garden_operations", "test_error_types"),
                 mypy_expected=frozenset({"operator"})),
    # super() is not listed, but it is how an exception gets a default message
    ExerciseSpec("ex3", "ex3", ("ft_custom_errors.py",),
                 authorized=frozenset({"print", "super"}) | EXC,
                 allow_classes=True, allow_main_block=True, require_main_block=True, require_type_hints=True,
                 expected_classes=("GardenError", "PlantError", "WaterError")),
    ExerciseSpec("ex4", "ex4", ("ft_finally_block.py",),
                 authorized=frozenset({"print", "super"}) | EXC,
                 allow_classes=True, allow_main_block=True, require_main_block=True, require_type_hints=True,
                 expected_functions=("water_plant", "test_watering_system"), expected_classes=("PlantError",)),
)


def _silent_import(rel: str):
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        status, stdout, stderr = eval_module_code(ctx, directory, rel, "", timeout=timeout)
        if status == 124:
            return PyOutcome(False, f"timeout ({timeout}s)", timed_out=True)
        if status != 0:
            return PyOutcome(False, (stderr.strip().splitlines() or [f"exit {status}"])[-1])
        if stdout.strip():
            return PyOutcome(False, "output printed on import (guard it with if __name__ == '__main__')",
                             expected="(no output)", actual=stdout.strip()[:200])
        return PyOutcome(True)
    return runner


def _runs(rel: str, must_contain: tuple[str, ...] = (), *, at_least: dict[str, int] | None = None):
    """python3 <file>: exit 0 ("Your programs must never crash"), nothing on
    stderr, and the key parts of the subject's example output."""
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        status, stdout, stderr = run_script_file(ctx, directory, rel, timeout=timeout)
        shown = f"python3 {rel}"
        if status == 124:
            return PyOutcome(False, f"timeout ({timeout}s)", input_desc=shown, timed_out=True)
        if status != 0 or stderr.strip():
            err = (stderr.strip().splitlines() or [f"exit {status}"])[-1]
            return PyOutcome(False, f"the program crashed: {err}", input_desc=shown, actual=stderr.strip()[-400:])
        missing = [text for text in must_contain if text not in stdout]
        for text, count in (at_least or {}).items():
            if stdout.count(text) < count:
                missing.append(f"{text!r} x{count}")
        if missing:
            return PyOutcome(False, "missing from the output: " + ", ".join(missing), input_desc=shown,
                             expected=", ".join(must_contain), actual=stdout.strip()[-400:])
        return PyOutcome(True)
    return runner


def _json(rel: str, code: str, desc: str):
    return lambda ctx, directory, timeout: expect_json_outcome(ctx, directory, rel, code, timeout=timeout,
                                                               input_desc=desc)


# the harness lines shared by the behaviour tests (they run in the student's module)
HELPERS = """
import io, json, inspect, contextlib
def call(fn, *args):
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            value = fn(*args)
        return 'ok', value, out.getvalue()
    except BaseException as exc:
        return type(exc).__name__, str(exc), out.getvalue()
def done(problems, **extra):
    print(json.dumps({'ok': not problems, 'detail': '; '.join(problems), **extra}))
"""


def _converts(rel: str, ranged: bool):
    checks = [("25", 25), ("0", 0), ("40", 40)] + ([] if ranged else [("-5", -5), ("100", 100)])
    bad = ["abc", "", "12.5"] + (["41", "100", "-1", "-50"] if ranged else [])
    code = HELPERS + f"""
problems = []
fn = getattr(mod, 'input_temperature', None)
if not callable(fn):
    done(['missing input_temperature()'])
    raise SystemExit(0)
for text, want in {checks!r}:
    state, value, _ = call(fn, text)
    if state != 'ok':
        problems.append(f'input_temperature({{text!r}}) raised {{state}}: {{value}}')
    elif value != want or type(value) is not int:
        problems.append(f'input_temperature({{text!r}}) returned {{value!r}}, expected the int {{want}}')
for text in {bad!r}:
    state, value, _ = call(fn, text)
    if state == 'ok':
        problems.append(f'input_temperature({{text!r}}) returned {{value!r}} instead of raising')
done(problems)
"""
    return _json(rel, code, "input_temperature('25' / 'abc'" + (" / '41' / '-1')" if ranged else ")"))


def _range_messages(rel: str):
    code = HELPERS + """
problems = []
fn = getattr(mod, 'input_temperature', None)
for text, part in (('100', 'too hot'), ('-50', 'too cold')):
    state, value, _ = call(fn, text) if callable(fn) else ('missing', '', '')
    if state == 'ok' or part not in value:
        problems.append(f"input_temperature({text!r}): {state} {value!r}, expected a message with '{part}'")
done(problems, expected="100°C is too hot for plants (max 40°C) / -50°C is too cold for plants (min 0°C)")
"""
    return _json(rel, code, "input_temperature('100') / ('-50')")


def _test_function(rel: str, name: str, needles: tuple[str, ...]):
    """The demo function itself catches every error and keeps running."""
    code = HELPERS + f"""
fn = getattr(mod, {name!r}, None)
if not callable(fn):
    done(['missing {name}()'])
    raise SystemExit(0)
required = [p for p in inspect.signature(fn).parameters.values() if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
if required:
    done([], detail='takes parameters: run through the script instead')
    raise SystemExit(0)
state, value, out = call(fn)
problems = [] if state == 'ok' else [f'{name}() let {{state}} escape: {{value}}']
problems += [f'{{n!r}} not printed' for n in {needles!r} if n not in out]
done(problems, actual=out[-300:])
"""
    return _json(rel, code, f"{name}()")


def _operations(rel: str):
    code = HELPERS + """
problems = []
fn = getattr(mod, 'garden_operations', None)
if not callable(fn):
    done(['missing garden_operations()'])
    raise SystemExit(0)
want = {0: 'ValueError', 1: 'ZeroDivisionError', 2: 'FileNotFoundError', 3: 'TypeError'}
for number, error in want.items():
    state, value, _ = call(fn, number)
    if state != error:
        problems.append(f'garden_operations({number}): {state} instead of {error}')
for number in (4, 5, -1, 42):
    state, value, _ = call(fn, number)
    if state != 'ok':
        problems.append(f'garden_operations({number}) raised {state}: {value} (must simply return)')
done(problems)
"""
    return _json(rel, code, "garden_operations(0..3) and (4, 5, -1, 42)")


def _multi_catch(rel: str):
    """One try: catching several error types (a tuple, or several except)."""
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        try:
            tree = ast.parse((directory / rel).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError) as exc:
            return PyOutcome(False, str(exc))
        tuples = any(isinstance(h, ast.ExceptHandler) and isinstance(h.type, ast.Tuple) and len(h.type.elts) > 1
                     for h in ast.walk(tree))
        several = any(isinstance(t, ast.Try) and len(t.handlers) > 1 for t in ast.walk(tree))
        uses_type = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "type"
                        for n in ast.walk(tree))
        if uses_type:
            return PyOutcome(False, "type() is used (the subject forbids it)")
        return PyOutcome(tuples or several, "" if tuples or several else
                         "no try: catches several error types (except (ValueError, TypeError) as e:)")
    return runner


def _custom_errors(rel: str):
    code = HELPERS + """
problems = []
G, P, W = (getattr(mod, n, None) for n in ('GardenError', 'PlantError', 'WaterError'))
names = {'GardenError': G, 'PlantError': P, 'WaterError': W}
missing = [n for n, c in names.items() if not inspect.isclass(c)]
if missing:
    done(['missing class(es): ' + ', '.join(missing)])
    raise SystemExit(0)
if not issubclass(G, Exception):
    problems.append('GardenError must inherit from Exception')
for n, c in (('PlantError', P), ('WaterError', W)):
    if not issubclass(c, G):
        problems.append(f'{n} must inherit from GardenError')
for n, c in names.items():
    try:
        default = str(c())
    except BaseException as exc:
        problems.append(f'{n}() without a message: {type(exc).__name__}: {exc}')
        continue
    if not default.strip():
        problems.append(f'{n}() has no default message')
    if 'special message 42' not in str(c('special message 42')):
        problems.append(f'{n}(message) does not keep its message')
for c in (P, W):
    try:
        raise c('x')
    except G:
        pass
    except BaseException:
        problems.append(f'except GardenError does not catch {c.__name__}')
done(problems)
"""
    return _json(rel, code, "GardenError / PlantError(GardenError) / WaterError(GardenError)")


def _water_plant(rel: str):
    code = HELPERS + """
problems = []
fn = getattr(mod, 'water_plant', None)
if not callable(fn):
    done(['missing water_plant()'])
    raise SystemExit(0)
for name in ('Tomato', 'Lettuce'):
    state, value, out = call(fn, name)
    if state != 'ok':
        problems.append(f'water_plant({name!r}) raised {state}: {value}')
    elif name not in out:
        problems.append(f'water_plant({name!r}) printed no success message')
for name in ('lettuce', 'tOMATO', 'carrots'):
    state, value, _ = call(fn, name)
    if state != 'PlantError':
        problems.append(f'water_plant({name!r}): {state} instead of PlantError')
done(problems)
"""
    return _json(rel, code, "water_plant('Tomato') / ('lettuce')")


def _finally_block(rel: str):
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        try:
            tree = ast.parse((directory / rel).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError) as exc:
            return PyOutcome(False, str(exc))
        function = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                         and n.name == "test_watering_system"), None)
        if function is None:
            return PyOutcome(False, "missing test_watering_system()")
        ok = any(isinstance(t, ast.Try) and t.finalbody and t.handlers for t in ast.walk(function))
        return PyOutcome(ok, "" if ok else "test_watering_system() has no try/except/finally")
    return runner


def _stops_on_error(rel: str):
    """After an invalid name the test stops, the system is still closed."""
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        status, stdout, stderr = run_script_file(ctx, directory, rel, timeout=timeout)
        if status != 0:
            return PyOutcome(False, "the program crashed", actual=stderr.strip()[-300:])
        blocks = stdout.split("Opening")[1:]
        if len(blocks) < 2:
            return PyOutcome(False, "expected two runs of the watering system (valid, then invalid plants)",
                             actual=stdout.strip()[-300:])
        failing = next((b for b in blocks if "PlantError" in b or "Error" in b), None)
        if failing is None:
            return PyOutcome(False, "no PlantError caught in the invalid-plants run", actual=stdout.strip()[-300:])
        after = failing.split("Error", 1)[1]
        closing = "Closing" in after
        more = "Watering" in after.split("Closing", 1)[0]
        if not closing:
            return PyOutcome(False, "the watering system is not closed after the error", actual=failing.strip())
        if more:
            return PyOutcome(False, "plants are still watered after the error (it must stop at once)",
                             actual=failing.strip())
        return PyOutcome(True)
    return runner


T0, T1 = "ex0/ft_first_exception.py", "ex1/ft_raise_exception.py"
T2, T3, T4 = "ex2/ft_different_errors.py", "ex3/ft_custom_errors.py", "ex4/ft_finally_block.py"

SUITES: tuple[PySuite, ...] = (
    PySuite("ex0", "ex0 · ft_first_exception", (T0,), aliases=("0", "first"), cases=(
        PyTestCase("silent on import", "silencieux à l'import", _silent_import(T0)),
        PyTestCase("int, or raises", "int, ou lève une erreur", _converts(T0, ranged=False)),
        PyTestCase("test_temperature() catches", "test_temperature() rattrape",
                   _test_function(T0, "test_temperature", ("25", "abc"))),
        PyTestCase("runs without crashing", "s'exécute sans planter",
                   _runs(T0, ("Input data is '25'", "Input data is 'abc'", "Temperature is now 25°C",
                              "All tests completed"))),
    )),
    PySuite("ex1", "ex1 · ft_raise_exception", (T1,), aliases=("1", "raise"), cases=(
        PyTestCase("silent on import", "silencieux à l'import", _silent_import(T1)),
        PyTestCase("0-40 °C, limits included", "0-40 °C, bornes comprises", _converts(T1, ranged=True)),
        PyTestCase("too hot / too cold messages", "messages trop chaud / trop froid", _range_messages(T1),
                   speculative=True),
        PyTestCase("test_temperature() catches", "test_temperature() rattrape",
                   _test_function(T1, "test_temperature", ("25", "abc", "100", "-50"))),
        PyTestCase("runs without crashing", "s'exécute sans planter",
                   _runs(T1, ("Input data is '100'", "Input data is '-50'", "All tests completed"))),
    )),
    PySuite("ex2", "ex2 · ft_different_errors", (T2,), aliases=("2", "different"), cases=(
        PyTestCase("silent on import", "silencieux à l'import", _silent_import(T2)),
        PyTestCase("4 error types, then return", "4 types d'erreurs, puis return", _operations(T2)),
        PyTestCase("one try: catches several types", "un try: attrape plusieurs types", _multi_catch(T2)),
        PyTestCase("test_error_types() catches", "test_error_types() rattrape",
                   _test_function(T2, "test_error_types",
                                  ("ValueError", "ZeroDivisionError", "FileNotFoundError", "TypeError"))),
        PyTestCase("runs without crashing", "s'exécute sans planter",
                   _runs(T2, ("ValueError", "ZeroDivisionError", "FileNotFoundError", "TypeError",
                              "Operation completed successfully"))),
    )),
    PySuite("ex3", "ex3 · ft_custom_errors", (T3,), aliases=("3", "custom"), cases=(
        PyTestCase("silent on import", "silencieux à l'import", _silent_import(T3)),
        PyTestCase("hierarchy & default messages", "héritage & messages par défaut", _custom_errors(T3)),
        PyTestCase("runs without crashing", "s'exécute sans planter",
                   _runs(T3, ("PlantError", "WaterError", "GardenError"))),
    )),
    PySuite("ex4", "ex4 · ft_finally_block", (T4,), aliases=("4", "finally"), cases=(
        PyTestCase("silent on import", "silencieux à l'import", _silent_import(T4)),
        PyTestCase("water_plant() & PlantError", "water_plant() & PlantError", _water_plant(T4)),
        PyTestCase("try/except/finally", "try/except/finally", _finally_block(T4)),
        PyTestCase("stops, then always closes", "s'arrête, puis ferme toujours", _stops_on_error(T4)),
        PyTestCase("runs without crashing", "s'exécute sans planter",
                   _runs(T4, ("Opening watering system", "Watering Tomato: [OK]"),
                         at_least={"Closing watering system": 2})),
    )),
)

PROJECT = PythonProject(
    key="py02",
    name="python-module-02",
    header="",
    subject="3.0",
    aliases=("python02", "python-module-02", "garden_guardian"),
    specs=SPECS,
    suites=SUITES,
    check_naming_conventions=True,
)
