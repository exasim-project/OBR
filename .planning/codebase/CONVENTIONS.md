# Coding Conventions

**Analysis Date:** 2026-07-13

## Naming Patterns

**Files:**
- Modules use `snake_case.py` (`create_tree.py`, `parse_yaml.py`, `logger_setup.py`, `case_origins.py`).
- One notable exception: `caseOrigins.py` and `case.py` under `src/obr/OpenFOAM/` mix conventions (`caseOrigins.py` uses camelCase to mirror OpenFOAM dictionary naming).
- Module names mirror their primary export/domain: `queries.py` -> `Query`/query functions, `labels.py` -> signac label predicates, `submit.py` -> `submit_impl`.
- Test files mirror the module under test: `tests/test_core.py` <-> `src/obr/core/core.py`, `tests/test_queries.py` <-> `src/obr/core/queries.py`, `tests/test_yaml_parser.py` <-> `src/obr/core/parse_yaml.py`.

**Functions:**
- Standard Python code (helpers, CLI plumbing, internals) uses `snake_case`: `parse_variables_impl`, `logged_execute`, `filter_jobs`, `map_view_folder_to_job_id`.
- **Signac operation functions** (`src/obr/signac_wrapper/operations.py`) are deliberately named to match the OpenFOAM dictionary/utility they wrap, using OpenFOAM's own casing: `controlDict`, `fvSolution`, `fvSchemes`, `blockMesh`, `decomposePar`, `checkMesh`, `runParallelSolver`. One dummy operation uses PascalCase to match a virtual "type": `MultiCase`. **Do not rename these to snake_case** — the operation name is used as the CLI `-o` argument and as a matching key in YAML configs (e.g. `obr run -o controlDict`).
- Private/internal helpers are prefixed with a single underscore: `_link_path`, `_exec_operation`, `_md5sum`.
- Predicate helper functions used as signac `@OpenFOAMProject.pre`/`@OpenFOAMProject.post` callables return booleans and are named descriptively: `basic_eligible`, `operation_complete`, `needs_initialization`, `is_locked`, `is_case`.

**Variables:**
- `snake_case` throughout for locals and parameters (`case_path`, `job_doc`, `target_folder`).
- OpenFOAM dictionary keys are kept in their native camelCase when stored in dicts/kwargs (e.g. `numberOfSubdomains`, `writeFormat`, `startTime`) because they round-trip into actual OpenFOAM dictionary files — do not snake_case these keys.
- Module-level "constants" are `UPPER_SNAKE_CASE`: `SIGNAC_PATH_TOKEN`, `PATH_TOKEN`, `GLOBAL_INIT_COUNT`, `OF_HEADER_REGEX`.
- Walrus operator (`:=`) is used for compact existence checks, e.g. `if sel := kwargs.get("job"):` in `src/obr/cli_util.py:120`, `if m_regex := matcher_regex.get(matcher_name):` in `src/obr/cli.py:557`.

**Types/Classes:**
- Classes use `PascalCase`: `OpenFOAMCase`, `OpenFOAMProject`, `TemporaryFolder`, `DelinkFolder`, `BlockMesh`, `Query`, `Predicates` (enum).
- `dataclass`-based value objects are used for structured data: `Query` and `query_result` in `src/obr/core/queries.py:18` and `:37`.
- `Enum` is used for closed sets of string values: `Predicates` in `src/obr/core/queries.py:28` (maps names like `eq`/`neq` to operator strings `==`/`!=`).

## Code Style

**Formatting:**
- **Black** is the enforced formatter (`.pre-commit-config.yaml`, `.github/workflows/main.yml` runs `psf/black@stable` with `version: "24.10.0"` and `--check`).
- `pyproject.toml` sets `[tool.black] preview = true`.
- Effective line length is 88 characters (Black default, reinforced by `[tool.flake8] max-line-length = 88`).
- A repo-comment workflow (`.github/workflows/*OnCommentPR*` referencing `format.sh`) lets maintainers trigger `black` auto-formatting via a PR comment `format!`.

**Linting:**
- `flake8` config exists in `pyproject.toml` (`max-line-length = 88`, `extend-ignore = ["E203"]`) — E203 (whitespace before `:`) is ignored because Black's slicing style conflicts with it.
- `autoflake` is run in CI (`.github/workflows/main.yml`) with `--remove-all-unused-imports --ignore-init-module-imports --remove-unused-variables` against `src/`. Keep imports actually used; unused imports will be stripped in CI review, not necessarily locally.
- `mypy.ini` exists but is minimal: `ignore_missing_imports = True` only. Type checking is not strictly enforced (no CI job runs mypy) — type hints are present but partial/best-effort, not a hard requirement.
- `_typos.toml` config plus a `typos` CI job (`.github/workflows/typo_check.yml`) checks spelling — avoid uncommon misspellings in identifiers/comments/docs.

## Import Organization

**Order (observed, not enforced by isort/ruff):**
1. Standard library imports first (`os`, `sys`, `re`, `json`, `logging`, `shutil`, `subprocess`, `pathlib`, `typing`, `datetime`, `copy`).
2. Third-party imports next (`click`, `yaml`, `flow`, `signac.job.Job`, `git.repo.Repo`, `pandas`).
3. Local package imports last, using **relative imports** within the package: `from .core.core import ...`, `from ..OpenFOAM.case import OpenFOAMCase`, `from .signac_wrapper.operations import OpenFOAMProject`.
- Groups are separated by a single blank line; see `src/obr/cli.py:18-46`, `src/obr/core/core.py:1-16`, `src/obr/OpenFOAM/case.py:1-25`.
- No import aliasing conventions beyond stdlib norms (no `import numpy as np`-style project convention observed since numpy isn't used).
- `# type: ignore[import]` comments are used for stub-less third-party imports, e.g. `import yaml  # type: ignore[import]` (`src/obr/cli.py:19`, `tests/test_submit.py:2`).
- Deferred/local imports are used deliberately inside functions to avoid heavy/optional dependencies at module load time, e.g. `from Owls.parser.LogFile import LogFile, transportEqn, customMatcher` inside `postProcess()` (`src/obr/cli.py:509`), `from jsonschema import validate` and `from deepdiff import DeepDiff` inside `query_impl()` (`src/obr/cli_util.py:51,55`), `import cProfile` inside `profile_call()` (`src/obr/core/core.py:447`).

**Path Aliases:**
- None. The project uses standard relative package imports (`from .x import y`, `from ..x.y import z`); no `sys.path` hacking or import aliasing config is used.

## Error Handling

**Patterns:**
- Prefer built-in exception types over custom exception classes — no custom `Exception` subclasses exist anywhere in `src/obr`. Common choices:
  - `FileNotFoundError` for missing files/templates (`src/obr/OpenFOAM/case.py:63`, `:315`; `src/obr/signac_wrapper/submit.py:32`).
  - `AssertionError` for programmer/config invariant violations, often with a descriptive message (`src/obr/cli_util.py:118`, `src/obr/create_tree.py:154`, `src/obr/signac_wrapper/operations.py:418`, `src/obr/OpenFOAM/case.py:295`).
  - `ValueError` for bad/unusable state (`src/obr/OpenFOAM/case.py:223`).
- Broad `except Exception as e:` blocks are common at operation boundaries (subprocess calls, log parsing, git operations) to keep one job's failure from crashing the whole batch run; the exception is logged via `logging.error(...)`/`logger.error(e)` and a `state = "failure"` sentinel is recorded into the signac job document (`src/obr/core/core.py:79`, `src/obr/OpenFOAM/case.py:533`, `src/obr/signac_wrapper/operations.py:306`, `src/obr/cli.py:609`, `:912`).
- Bare `except:` appears in a few narrow, intentional spots for best-effort parsing where any failure should fall back silently, e.g. `src/obr/core/core.py:435` (`is_time` float-cast check), `src/obr/cli.py:607` (per-column aggregation fallback), `src/obr/OpenFOAM/case.py:57` (`File.get` eval fallback). Follow this pattern only for truly best-effort, non-critical parsing — do not use bare `except:` for I/O or state-mutating code.
- Domain-specific subprocess errors are caught by type and translated into a logged failure record rather than propagated: `subprocess.SubprocessError`, `FileNotFoundError` in `logged_execute()` (`src/obr/core/core.py:67-84`).
- CLI-level fatal errors call `logger.error(...)` followed by `sys.exit(1)` rather than raising (`src/obr/cli.py:453-454`, `src/obr/cli_util.py:126-128`).
- When an operation should stop a signac job pipeline but not crash the process, functions return early (e.g. `return False`, `return None`) after logging a warning — see `execute_shell()` (`src/obr/core/core.py:269-291`), `get_latest_log()` (`:200-223`).
- All signac operations are wrapped by shared hook decorators (`@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)`, `@OpenFOAMProject.operation_hooks.on_exception(set_failure)`) that centralize success/failure bookkeeping into `job.doc` — new operations in `src/obr/signac_wrapper/operations.py` should reuse this decorator stack rather than adding ad hoc try/except.

## Logging

**Framework:** Python standard `logging`, configured centrally in `src/obr/core/logger_setup.py`.

**Patterns:**
- Always obtain the shared logger via `logger = logging.getLogger("OBR")` at module top — never instantiate a new/independent logger. This exact string `"OBR"` is required for the central config in `setup_logging()` to pick it up.
- A custom `SUCCESS` log level (25, between INFO and WARNING) is registered and monkey-patched onto `logging.Logger` as `.success(...)` (`src/obr/core/logger_setup.py:7-16`). Use `logger.success(...)` to signal a completed high-level user action (e.g. `logger.success("Completed all operations")` in `src/obr/cli.py:280`, `logger.success("Successfully initialised")` at `:334`).
- Standard levels used consistently: `logger.debug` for verbose diagnostic info gated behind `--debug`, `logger.info` for normal progress, `logger.warning`/`logger.warn` for recoverable problems requiring user attention, `logger.error` for failures.
- `setup_logging(log_fold="")` must be called once before any CLI command logic runs (see every `@cli.command()` in `src/obr/cli.py` calling `cli_cmd_setup()` -> `setup_logging()`). It configures both a colored stdout handler (`coloredlogs.ColoredFormatter`) and a rotating file handler writing to `<workspace>/.obr/obr.log` (10 KB x 3 backups).
- `--debug` CLI flag raises the `"OBR"` logger to `DEBUG` at runtime via `common_params` wrapper (`src/obr/cli.py:49-72`), rather than reconfiguring the whole logging dict.
- Avoid bare `print()` for user-facing output — it bypasses the log file and coloring. It does appear in a couple of legacy spots (`print(f"setting {domain}.{inst} to {args.get(inst)}")` in `src/obr/core/parse_yaml.py:70`, `print(e)` in `src/obr/cli.py:610`) but new code should use `logger.*` instead.

## Comments

**When to Comment:**
- Comments explain *why*, not *what* — especially around OpenFOAM/signac quirks and non-obvious workarounds, e.g. `src/obr/core/core.py:88-93` ("Only write log files above a certain size... otherwise the log is stored directly in the job doc"), `src/obr/OpenFOAM/case.py:370` ("Some openfoam versions refuse to decompose files if content of zero folder are symlinks...").
- `# NOTE ...` is used to flag important behavioral caveats for future readers (`src/obr/cli_util.py:145` `# NOTE do _not_ do repo.git.add(all=True)`; `src/obr/core/queries.py:75-76`).
- `# TODO ...` and `# FIXME ...` mark known gaps/simplifications that should be addressed later — see Concerns doc for the current list. New code should use the same `# TODO` / `# FIXME` markers (not `@todo`, not issue links) so they remain grep-able (`grep -rn "TODO\|FIXME"`).
- Inline comments clarify sanitization/edge-case handling right above the code they describe, kept short (one to three lines).

**Docstrings:**
- Triple-quoted `"""docstrings"""` are used on most public functions/methods and many classes, but not universally enforced — helper/internal functions sometimes omit them.
- Style is informal prose, first line is a short imperative/descriptive summary, optionally followed by a blank line and more detail; a `Returns:` section is used sometimes but not via strict Google/NumPy style (see `src/obr/core/core.py:49-57`, `src/obr/OpenFOAM/case.py:491-496`).
- Class docstrings are one-liners describing purpose: `"""A class to handle temporary folder, taking care of copying and deleting the resulting folder"""` (`src/obr/core/core.py:395-396`).
- No module-level docstrings except `src/obr/cli.py:1-16`, which explains a click/`__main__` gotcha — follow that pattern only when there's a genuinely non-obvious reason a file exists where it does.

## Function Design

**Size:** No hard limit; functions range from a few lines (property getters) to ~80 lines for orchestration logic (`decomposePar` in `src/obr/OpenFOAM/case.py:317-455`, `archive` CLI command in `src/obr/cli.py:739-913`, `postProcess` CLI command in `src/obr/cli.py:508-616`). Prefer extracting nested closures for repeated logic within a function (see `safe_delete` inside `reset_workspace()` at `src/obr/cli.py:473-480`, `is_job_sub_document` inside `merge_job_documents()` at `src/obr/core/core.py:178-181`).

**Parameters:**
- Signac operation functions follow a fixed 2-parameter signature: `def operation_name(job: Job, args={})`. **Mutable default `args={}` is used intentionally and consistently** across `src/obr/signac_wrapper/operations.py` (30+ occurrences) — this diverges from the usual Python "never use mutable defaults" rule; the codebase relies on it never being mutated in place (args is always reassigned via `args = get_args(job, args)` at the top of each operation). Follow this exact idiom when adding a new operation rather than switching to `Optional[dict] = None`.
- CLI command functions (`@cli.command()`) take `**kwargs` and pull values via `kwargs.get("key", default)` rather than named parameters, because `click` injects all options as kwargs — see any command in `src/obr/cli.py`.
- Type hints are added opportunistically on "core"/library functions (`src/obr/core/core.py`, `src/obr/core/queries.py`, `src/obr/cli_util.py`) using `typing.Union`, `Optional`, `Generator`, PEP 585 generics (`list[str]`, `dict[str, str]`), but are frequently omitted in `src/obr/signac_wrapper/operations.py` operation bodies and CLI commands.

**Return Values:**
- Boolean-returning predicate functions (used as signac `pre`/`post` conditions) return `True`/`False` directly, never `None` — e.g. `is_locked`, `basic_eligible`, `operation_complete`.
- Functions that "may not find a result" return a falsy sentinel matching the expected type rather than raising: `""` for missing log paths (`get_latest_log`, `src/obr/core/core.py:223`), `{}` for missing dict results (`map_view_folder_to_job_id`, `:339`), `False` for missing recursive lookups (`statepoint_get`, `src/obr/core/queries.py:336`).
- Functions performing an external command/log write return `Path` (or `None`) pointing to a produced artifact, e.g. `logged_execute(...) -> Path`, so callers can act on the log file location.

## Module Design

**Exports:**
- No `__all__` lists are used; modules rely on explicit `from module import name1, name2` at call sites (see every test file's import block).
- Public API surface of a module = every top-level `def`/`class` without a leading underscore; underscore-prefixed helpers (`_link_path`, `_exec_operation`) are implementation details not meant for cross-module import (though tests do import `_link_path` directly in `tests/test_operations.py:1` to unit-test it — acceptable for white-box testing).

**Barrel Files:**
- Not used. `__init__.py` files are empty except `src/obr/__init__.py`, which only exposes `__version__` via `importlib.metadata.version("obr")`. Package `__init__.py` files under `core/`, `OpenFOAM/`, `signac_wrapper/`, `postPro/` are all empty (0 lines) — always import from the concrete submodule (`from obr.core.core import ...`), never rely on package-level re-exports.
- `src/obr/__main__.py` exists solely to invoke `cli.main()` for `python -m obr` support; see the docstring in `src/obr/cli.py:1-16` for why command logic lives in `cli.py` and not `__main__.py`.

---

*Convention analysis: 2026-07-13*
