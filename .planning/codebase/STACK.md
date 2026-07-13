# Technology Stack

**Analysis Date:** 2026-07-13

## Languages

**Primary:**
- Python 3 - Entire codebase (`src/obr/**/*.py`). `pyproject.toml` declares `requires-python = ">=3.6"`, but CI (`.github/workflows/unit_test.yaml`, `.github/workflows/integration_test.yaml`) actually tests against Python 3.9, and `.readthedocs.yaml` builds docs with Python 3.9. Locally the interpreter available is Python 3.12.3.

**Secondary:**
- YAML - Workflow/case definition markup consumed by OBR (`examples/*.yaml`, `tests/cavity.yaml`). Parsed via `PyYAML` in `src/obr/core/parse_yaml.py`.
- Shell / Bash - Generated job submission scripts (Jinja2 templates via signac-flow), `obr shell` operation steps, and `Allclean` scripts inside OpenFOAM cases.
- Jinja2 templates - Submission script templates (`--template` option in `obr submit`, see `src/obr/signac_wrapper/submit.py`), rendered by `signac-flow`'s environment/template system (SLURM `#SBATCH` directives, see `tests/test_submit.py`).

## Runtime

**Environment:**
- CPython 3.9-3.12 (developed/tested against 3.9 in CI; no upper bound pinned in `pyproject.toml`)
- Depends on an externally-sourced OpenFOAM installation at runtime (not a Python dependency) — see INTEGRATIONS.md.

**Package Manager:**
- pip (standard `pyproject.toml`/PEP 517 build, no `setup.py`)
- Lockfile: missing — no `requirements.txt`, `poetry.lock`, or `uv.lock`. Dependencies are unpinned or pinned only in `pyproject.toml` (see below).

## Frameworks

**Core:**
- `click` - CLI framework. Entry point `obr = "obr.cli:main"` (`pyproject.toml`), all commands defined in `src/obr/cli.py` (`init`, `run`, `submit`, `status`, `query`, `apply`, `postProcess`, `reset`, `archive`).
- `signac==2.1.0` - Underlying data/workspace management library. OBR wraps `signac.job.Job` throughout (`src/obr/core/core.py`, `src/obr/OpenFOAM/case.py`).
- `signac-flow==0.26.1` - Workflow/operation orchestration on top of signac. `OpenFOAMProject(flow.FlowProject)` in `src/obr/signac_wrapper/operations.py` defines all pipeline operations (`blockMesh`, `decomposePar`, `runParallelSolver`, etc.) and drives `obr run`/`obr submit`.

**Testing:**
- `pytest` - Test runner (`tests/test_*.py`). Invoked via `coverage run -m pytest -m "not integtest"` in CI unit tests; no `pytest.ini`/marker registration found in the repo, so the `integtest` marker used by CI is implicit/unregistered.
- `coverage` - Test coverage measurement, reported via a dynamic GitHub Gist badge (`.github/workflows/unit_test.yaml`).

**Build/Dev:**
- `black==24.10.0` - Code formatter, enforced via `.pre-commit-config.yaml` and `.github/workflows/main.yml` (`black --check`). `[tool.black] preview = true` in `pyproject.toml`.
- `autoflake` - Removes unused imports/variables (`main.yml` CI step, not a committed dependency).
- `mypy` - Static typing, config at `mypy.ini` (`ignore_missing_imports = True`); not wired into CI.
- `pre-commit` - Hooks: `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`, `black` (`.pre-commit-config.yaml`).
- Sphinx (`sphinx==6.2.1`, `sphinx-autoapi==3.0.0`, `myst_parser`, `furo` theme) - Documentation, built via Read the Docs (`.readthedocs.yaml`, `docs/source/conf.py`, `docs/Makefile`).
- `typos` (crate-ci/typos) - Spell checking CI job (`.github/workflows/typo_check.yml`, config `_typos.toml`).

## Key Dependencies

**Critical:**
- `signac==2.1.0` / `signac-flow==0.26.1` - Pinned exact versions; core data model (job state points, job documents as JSON) and operation scheduling. All CLI commands ultimately call into a `flow.FlowProject` subclass.
- `Owls @ git+https://github.com/greole/Owls.git@Owls2.0` - Git-sourced (non-PyPI) dependency for parsing OpenFOAM dictionary files and solver logs. Used in `src/obr/OpenFOAM/case.py` (`Owls.parser.FoamDict.FileParser`, `Owls.parser.LogFile.LogFile`) and in the `obr postProcess` command (`src/obr/cli.py`).
- `GitPython==3.1.31` - Wraps the `git` CLI for the `obr archive` command (commit/branch/push to a results repo) and for `GitRepo` case origins (`src/obr/core/caseOrigins.py`).
- `jsonschema==4.19.1` - Validates `obr query --validate_against` output against JSON Schema (`src/obr/cli_util.py`).
- `DeepDiff` - Alternate (non-schema) validation path for `obr query --validate_against` (`src/obr/cli_util.py`).

**Infrastructure:**
- `pandas` - DataFrame handling of parsed log data during `obr postProcess` (`src/obr/cli.py`).
- `coloredlogs` - Colorized console log formatting (`src/obr/core/logger_setup.py`).
- `PyYAML` - Parses OBR workflow/case-definition YAML files (`src/obr/core/parse_yaml.py`, `src/obr/cli.py`).
- `tqdm` - Progress bars when collecting eligible jobs for submission (`src/obr/signac_wrapper/submit.py`).
- `click` - see Frameworks above.

## Configuration

**Environment:**
- Configuration is driven almost entirely by environment variables read via `os.environ`/`os.getenv`, not config files:
  - `OBR_RUN_CMD` / `OBR_SERIAL_RUN_CMD` - Override the mpirun/serial solver launch command template (`src/obr/signac_wrapper/operations.py`).
  - `OBR_CUSTOM_SOLVER_CMD` - Replaces the solver binary in generated run commands (set via `--solver-cmd` CLI flag).
  - `OBR_PREFLIGHT` - Path to a script run immediately before solver execution (e.g. `examples/preflight.py`).
  - `OBR_SKIP_COMPLETE` - Skips already-completed jobs.
  - `OBR_JOB` - Restricts `obr run` to a single job id.
  - `OBR_CALL_ARGS` - Passed through to the `archive` operation.
  - `OBR_APPLY_FILE` / `OBR_APPLY_CAMPAIGN` - Used by `obr apply` to locate and execute a user-supplied post-processing script.
  - `OBR_PROFILE` - Enables `cProfile` profiling of CLI calls (`src/obr/core/core.py:profile_call`).
  - `FOAM_TUTORIALS`, `FOAM_ETC`, `WM_PROJECT_DIR` - Standard OpenFOAM environment variables OBR reads to locate tutorials, verify OpenFOAM is sourced, and detect ESI vs. non-ESI OpenFOAM builds (`src/obr/core/caseOrigins.py`, `src/obr/create_tree.py`, `src/obr/OpenFOAM/case.py`).
  - `USER`, `HOST`, `HOSTNAME` - Recorded in job history/logs and used by `examples/preflight.py` for machine-specific validation.
- Workflow YAML files support `${{env.VAR}}` substitution (resolved against `os.environ`) and `${{yaml.location}}` substitution (resolved to the config file's directory) — implemented in `src/obr/core/parse_yaml.py` and `src/obr/core/core.py:parse_variables`.
- `.env` files: none present/used — all env-var configuration is expected to be exported in the shell (typically via sourcing an OpenFOAM `etc/bashrc` and setting `OBR_*` vars, per `README.md`).

**Build:**
- `pyproject.toml` - Single source of package metadata, dependencies, optional extras (`doc`, `test`), and tool config (`[tool.black]`, `[tool.flake8]`).
- `mypy.ini` - mypy settings.
- `.readthedocs.yaml` - Docs build environment (Ubuntu 20.04, Python 3.9, installs `.[doc]`).

## Platform Requirements

**Development:**
- Linux (tested on `ubuntu-latest`/`ubuntu-20.04` in CI); `src/obr/OpenFOAM/BlockMesh.py` has a `sys.platform == "darwin"` branch for `sed -i` syntax, indicating macOS is also informally supported for the non-OpenFOAM-execution parts.
- Requires a working OpenFOAM installation sourced into the shell (`WM_PROJECT_DIR`, `FOAM_TUTORIALS`, `FOAM_ETC`, solver binaries such as `blockMesh`, `decomposePar`, `checkMesh`, `refineMesh` on `PATH`).
- Requires `git` installed (used both via `GitPython` and directly via `check_output(["git", ...])` in `src/obr/core/caseOrigins.py`).
- Requires `mpirun` (OpenMPI or similar) for parallel solver execution.

**Production:**
- No containerized/cloud deployment target — OBR is a CLI tool installed via `pip install -e .` (or `pip install .`) directly on HPC login/compute nodes or workstations (`README.md` Installation section).
- CI integration tests run inside the `greole/ofbase` Docker container (which bundles an OpenFOAM build) purely for testing purposes (`.github/workflows/integration_test.yaml`); no Dockerfile is shipped in this repository for end users.
- Designed to run under HPC job schedulers (SLURM primarily, others in principle) via `signac-flow`'s environment detection and templated submission scripts (`obr submit`).

---

*Stack analysis: 2026-07-13*
