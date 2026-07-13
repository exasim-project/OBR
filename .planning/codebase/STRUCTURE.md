# Codebase Structure

**Analysis Date:** 2026-07-13

## Directory Layout

```
OBR/
├── src/obr/                     # The installable `obr` package (src-layout)
│   ├── cli.py                   # click CLI: init, run, submit, query, status, reset, apply, postProcess, archive
│   ├── cli_util.py               # cli_cmd_setup(), query_impl(), check_cli_operations(), copy_to_archive()
│   ├── create_tree.py             # YAML config -> signac job tree + view/ folder generation
│   ├── __main__.py                # `python -m obr` entry point
│   ├── __init__.py                # exposes obr.__version__ via importlib.metadata
│   ├── core.py                    # STRAY top-level stub file (1 line, shebang only) — do not use, see Special Directories
│   ├── core/                      # cross-cutting utilities package
│   │   ├── core.py                # shell exec + logging to job.doc, view<->job-id mapping, TemporaryFolder/DelinkFolder, profiling
│   │   ├── queries.py             # Query/Predicates DSL, filter/query engine over jobs
│   │   ├── caseOrigins.py         # CaseOnDisk / GitRepo / OpenFOAMTutorialCase / MultiCase strategy classes
│   │   ├── parse_yaml.py          # YAML include + ${{...}} variable/expression expansion
│   │   ├── logger_setup.py        # "OBR" logger configuration (console + rotating file)
│   │   └── __init__.py
│   ├── OpenFOAM/                  # OpenFOAM case object model
│   │   ├── case.py                # OpenFOAMCase, File — dictionary file access, decomposePar, state parsing
│   │   ├── BlockMesh.py           # BlockMesh mixin — blockMesh/refineMesh/checkMesh, simple-decomp math
│   │   ├── solver.py              # STUB (1 line, shebang only, no content) — placeholder, unused
│   │   └── __init__.py
│   ├── signac_wrapper/            # signac-flow FlowProject wrapper (the workflow engine glue)
│   │   ├── operations.py          # OpenFOAMProject(flow.FlowProject); all @operation functions, hooks, eligibility
│   │   ├── labels.py               # FlowProject @label predicates (finished, final, owns_mesh, ...)
│   │   ├── submit.py               # submit_impl() — builds cluster submission args, calls project.submit()
│   │   ├── operations.py.bck       # STRAY backup file — not imported anywhere, should be removed
│   │   └── __init__.py
│   └── postPro/                   # placeholder package
│       ├── postPro.py              # EMPTY FILE (0 bytes) — postprocessing logic actually lives in cli.py:postProcess
│       └── __init__.py
├── tests/                         # pytest test suite (flat, one file per source module roughly)
│   ├── test_OpenFOAMCase.py
│   ├── test_caseOrigins.py
│   ├── test_core.py
│   ├── test_create_tree.py
│   ├── test_md5sum.py
│   ├── test_operations.py
│   ├── test_queries.py
│   ├── test_submit.py
│   ├── test_yaml_parser.py
│   ├── cavity.yaml                # sample workflow config used by integration/unit tests
│   ├── cavity_results.json        # expected `obr query` output for the cavity example (regression fixture)
│   └── logs/                      # sample OpenFOAM solver log files used by log-parsing tests
│       ├── icoFoamFailure.log
│       ├── icoFoamIncomplete.log
│       ├── icoFoamStartupFailure.log
│       └── icoFoamSuccess.log
├── examples/                      # example YAML workflows + auxiliary scripts (not packaged, reference only)
│   ├── airFoil2D.yaml
│   ├── multigrid.yaml
│   ├── windsorBody.yaml
│   └── preflight.py                # example script for OBR_PREFLIGHT env var usage
├── docs/                           # Sphinx documentation source (readthedocs)
│   ├── source/
│   │   ├── index.md
│   │   ├── commandLine/            # one .md per CLI subcommand
│   │   ├── yamlFiles/overview.md   # YAML config schema documentation
│   │   └── troubleshooting/troubleshooting.md
│   ├── Makefile / make.bat
├── .github/workflows/              # CI: unit_test.yaml, integration_test.yaml, test.yaml, pr-formatting.yml, valid_version_bump.yml, typo_check.yml, check_changelog.yaml
├── .planning/codebase/              # generated codebase-map documents (this file and siblings)
├── pyproject.toml                   # package metadata, dependencies, `obr` console-script entry point, black/flake8 config
├── mypy.ini                          # mypy configuration
├── .pre-commit-config.yaml           # pre-commit hook configuration
├── README.md / README.rst            # project overview and usage guide (README.rst.bck is a stray backup)
├── CHANGELOG.rst                     # manually maintained changelog (enforced via CI on PRs)
└── LICENSE                           # BSD-2-Clause
```

## Directory Purposes

**`src/obr/` (package root):**
- Purpose: All installable Python source for the `obr` package, using the `src/` layout (package not importable from repo root without install).
- Contains: CLI entry modules (`cli.py`, `cli_util.py`, `__main__.py`), tree-generation logic (`create_tree.py`), and three subpackages (`core/`, `OpenFOAM/`, `signac_wrapper/`).
- Key files: `cli.py` (all click commands), `create_tree.py` (YAML → signac job tree).

**`src/obr/core/`:**
- Purpose: Utilities shared across the CLI, signac-flow layer, and OpenFOAM case model — nothing here is specific to OpenFOAM or to signac-flow's operation decorators.
- Contains: shell-execution helpers, the query/filter DSL, case-origin fetch strategies, YAML pre-processing, logger configuration.
- Key files: `core/core.py`, `core/queries.py`, `core/caseOrigins.py`, `core/parse_yaml.py`, `core/logger_setup.py`.

**`src/obr/OpenFOAM/`:**
- Purpose: Domain object model for an individual OpenFOAM case directory (reading/writing dictionary files, mesh operations, decomposition, solver-log-derived state).
- Contains: `OpenFOAMCase` (composed of `File` objects per dict file) and the `BlockMesh` mixin it inherits from.
- Key files: `OpenFOAM/case.py`, `OpenFOAM/BlockMesh.py`.

**`src/obr/signac_wrapper/`:**
- Purpose: The signac-flow integration layer — defines `OpenFOAMProject(flow.FlowProject)`, every signac operation, eligibility/pre-post predicates, `@label`s, and cluster submission logic.
- Contains: `operations.py` (largest file in the codebase, ~1000 lines — all operation functions and hook dispatch), `labels.py`, `submit.py`.
- Key files: `signac_wrapper/operations.py`.

**`src/obr/postPro/`:**
- Purpose: Nominally the home for postprocessing logic, but currently unused — `postPro.py` is a 0-byte stub. Actual postprocessing (`obr postProcess`) is implemented inline in `cli.py` (imports `Owls.parser.LogFile` directly).
- Contains: empty stub only.
- Generated: No. Committed: Yes (tracked, but dead code).

**`tests/`:**
- Purpose: pytest unit/integration test suite, one `test_<module>.py` file roughly per corresponding `src/obr/**/<module>.py`.
- Contains: test modules, a sample workflow YAML (`cavity.yaml`), a regression-comparison JSON fixture (`cavity_results.json`), and sample solver log fixtures (`logs/`).
- Key files: `tests/test_operations.py`, `tests/test_OpenFOAMCase.py`, `tests/test_create_tree.py`.

**`examples/`:**
- Purpose: Reference/example workflow YAML files and auxiliary scripts demonstrating OBR features (custom operations, preflight checks); not imported by the package or tests.
- Contains: `.yaml` workflow examples, `preflight.py` (example for `OBR_PREFLIGHT` env var).

**`docs/`:**
- Purpose: Sphinx/MyST documentation source, built and published via readthedocs (`.readthedocs.yaml`).
- Contains: one Markdown file per CLI subcommand under `commandLine/`, YAML schema overview, troubleshooting guide.

## Key File Locations

**Entry Points:**
- `src/obr/cli.py`: All CLI subcommands (`init`, `run`, `submit`, `query`, `status`, `reset`, `apply`, `postProcess`, `archive`); `main()` at bottom is the console-script target.
- `src/obr/__main__.py`: `python -m obr` entry point, forwards to `obr.cli.main()`.
- `pyproject.toml`: `[project.scripts] obr = "obr.cli:main"` — the actual installed CLI entry point.

**Configuration:**
- `pyproject.toml`: package metadata, dependencies, `[tool.black]`/`[tool.flake8]` settings.
- `mypy.ini`: mypy type-checking configuration.
- `.pre-commit-config.yaml`: pre-commit hooks (formatting/linting run before commit).
- User workflow config: arbitrary `*.yaml` files passed via `obr init -c <file>` (examples in `examples/`, `tests/cavity.yaml`); not a fixed filename/location — path is a CLI argument.

**Core Logic:**
- `src/obr/create_tree.py`: config → job tree generation.
- `src/obr/signac_wrapper/operations.py`: all executable operations.
- `src/obr/OpenFOAM/case.py`: OpenFOAM case file manipulation.
- `src/obr/core/queries.py`: query/filter engine.

**Testing:**
- `tests/*.py`: pytest test modules (see naming convention below).
- Run via `pytest` (declared as an optional dependency under `[project.optional-dependencies] test`, alongside `coverage`, `gitpython`).
- CI: `.github/workflows/unit_test.yaml` (pytest suite) and `.github/workflows/integration_test.yaml` (full `obr init`/`run` against a real OpenFOAM install inside the `greole/ofbase` container).

## Naming Conventions

**Files:**
- Package modules: `lowerCamelCase` or `snake_case` matching the concept they wrap, mirroring OpenFOAM's own naming where relevant — e.g. `caseOrigins.py`, `parse_yaml.py`, `BlockMesh.py` (capitalized because it mirrors the OpenFOAM `blockMesh` utility/class name, not a strict convention).
- Test modules: `test_<ModuleOrClassUnderTest>.py`, matching the primary class/module they exercise (e.g. `test_OpenFOAMCase.py` tests `OpenFOAM/case.py`'s `OpenFOAMCase` class, `test_operations.py` tests `signac_wrapper/operations.py`).
- Stray/backup files exist in the tree with `.bck` suffixes (`signac_wrapper/operations.py.bck`, `README.rst.bck`) — not a naming convention to follow, but a pattern to be aware of (leftover manual backups, not consumed by tooling).

**Directories:**
- Subpackages are named after their responsibility, not their file type: `core/` (utilities), `OpenFOAM/` (domain model, capitalized to match the OpenFOAM product name), `signac_wrapper/` (integration-layer naming pattern: `<library>_wrapper/` for code that wraps a third-party library's API — follow this pattern if wrapping another external tool in the future).

**Functions/operations:**
- signac-flow operation functions are named to match the OpenFOAM concept they configure or the utility they invoke, in the SAME casing OpenFOAM itself uses (`blockMesh`, `decomposePar`, `checkMesh`, `fvSolution`, `fvSchemes`, `transportProperties`, `turbulenceProperties`) — this lets YAML `operation:` values map 1:1 onto Python function names via `getattr(sys.modules[__name__], operation)` (see `execute_operation()` in `operations.py`). When adding a new operation, name the Python function to exactly match its YAML `operation:` key.

## Where to Add New Code

**New signac operation (new OpenFOAM step, e.g. wrapping a new utility):**
- Implementation: add a new `@generate`/`@simulate`-decorated function to `src/obr/signac_wrapper/operations.py`, following the existing pattern: `@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)` / `on_success(dispatch_post_hooks)` / `on_exception(set_failure)`, `@OpenFOAMProject.pre(lambda job: basic_eligible(job, "<opName>"))`, `@OpenFOAMProject.post(lambda job: operation_complete(job, "<opName>"))`, `@OpenFOAMProject.operation`. Name the function to match the YAML `operation:` key exactly.
- If the operation needs new OpenFOAM-file-level logic, add a method to `OpenFOAMCase` in `src/obr/OpenFOAM/case.py` (or the `BlockMesh` mixin in `src/obr/OpenFOAM/BlockMesh.py` if mesh-related) and call it from the operation function — operation functions should stay thin wrappers over `OpenFOAMCase` methods.
- Tests: add/extend `tests/test_operations.py` (operation eligibility/dispatch) and `tests/test_OpenFOAMCase.py` (case-level file logic).

**New case-origin type (new way to fetch/create a base case):**
- Implementation: add a new class to `src/obr/core/caseOrigins.py` implementing `.__init__(self, ...)` + `.init(self, path)`, then register it in `instantiate_origin_class()`'s if/elif chain in the same file.
- Tests: `tests/test_caseOrigins.py`.

**New query predicate / filter behavior:**
- Implementation: extend `Predicates` enum and `Query.execute()`'s `predicate_map` in `src/obr/core/queries.py`.
- Tests: `tests/test_queries.py`.

**New CLI subcommand:**
- Implementation: add a new `@cli.command()` function in `src/obr/cli.py`, reuse `cli_cmd_setup()` / `common_params` from `cli_util.py` and `cli.py` respectively for shared `--folder`/`--filter`/`--debug` handling and project/job setup.
- Documentation: add a corresponding `docs/source/commandLine/<name>.md` and include it from `docs/source/commandLine/CLI.md`.

**Utilities/helpers:**
- Shared, non-OpenFOAM-specific helpers (shell exec, path mapping, logging, generic file/temp-folder handling): `src/obr/core/core.py`.
- YAML/template expansion helpers: `src/obr/core/parse_yaml.py`.
- Do not add new code to `src/obr/core.py` (the stray top-level file) or `src/obr/postPro/postPro.py` (empty stub) — both appear to be dead/leftover files; prefer `src/obr/core/core.py` and `src/obr/cli.py`'s `postProcess` command respectively.

## Special Directories

**`workspace/` (generated at runtime under the `--folder` target, not in the repo):**
- Purpose: signac's per-job data store — one directory per job UID, each containing `signac_statepoint.json`, `signac_job_document.json`, and a `case/` subfolder with the actual OpenFOAM case files.
- Generated: Yes, by `obr init` (`create_tree()` → `project.open_job(...).init()`).
- Committed: No (project-specific; not part of this repository — this describes the runtime layout OBR produces in a *user's* project folder).

**`view/` (generated at runtime, not in the repo):**
- Purpose: Human-readable symlink tree mirroring `workspace/` job UIDs, with paths derived from each variation's `schema` string (e.g. `view/base/linear_solver/PCGnoneCPU/decomposition/scotch-9/`).
- Generated: Yes, by `generate_view()` in `create_tree.py`, rebuilt (via `rm -rf`) on every `obr init`.
- Committed: No.

**`.obr/` (generated at runtime, not in the repo):**
- Purpose: Holds `obr.log`, the rotating debug log file written by `setup_logging()`.
- Generated: Yes, created by `cli_cmd_setup()`/`init` before any project operation.
- Committed: No.

**`src/obr/__pycache__/`, `src/obr/signac_wrapper/__pycache__/`:**
- Purpose: Python bytecode cache directories present in this checkout.
- Generated: Yes, automatically by CPython.
- Committed: No (covered by `.gitignore`'s `__pycache__` entry).

---

*Structure analysis: 2026-07-13*
