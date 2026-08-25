# External Integrations

**Analysis Date:** 2026-07-13

## APIs & External Services

**Workflow Management:**
- signac / signac-flow (`signac==2.1.0`, `signac-flow==0.26.1`) - OBR is fundamentally a domain-specific wrapper around signac. Every `obr` CLI command (`init`, `run`, `submit`, `status`, `query`, `reset`, `apply`) ultimately creates or loads a `signac` project (`OpenFOAMProject(flow.FlowProject)` in `src/obr/signac_wrapper/operations.py`) and iterates its `Job` objects. signac itself is a local, file-based workspace manager — it is not a network service. Project state lives under `workspace/` (one directory per job, keyed by a UID hash of the job's state point) plus `.signac/` project metadata (`src/obr/cli.py:reset_workspace`).
  - No external signac server / signac-dashboard integration detected.

**OpenFOAM (simulation engine):**
- Not a Python package — OBR shells out to OpenFOAM CLI binaries via `subprocess.check_output`/`cmd=True` signac-flow operations. Binaries invoked include: `blockMesh`, `decomposePar`, `checkMesh`, `refineMesh` (`src/obr/OpenFOAM/BlockMesh.py`, `src/obr/OpenFOAM/case.py`), plus arbitrary solver executables (e.g. `pimpleFoam`, `simpleFoam`) resolved from the case's `system/controlDict` `application` entry (`OpenFOAMCase.solver` property in `src/obr/OpenFOAM/case.py`).
  - OBR expects OpenFOAM to already be "sourced" into the environment (`WM_PROJECT_DIR`, `FOAM_TUTORIALS`, `FOAM_ETC` environment variables) before any of these commands are run; `src/obr/core/caseOrigins.py:OpenFOAMTutorialCase.resolve_of_path` reads `FOAM_TUTORIALS` directly and raises a `KeyError` if unset. `src/obr/create_tree.py` checks `FOAM_ETC` presence as a sanity check unless `skip_foam_src_check` is set.
  - `OpenFOAMCase.esi_version` (`src/obr/OpenFOAM/case.py`) inspects `WM_PROJECT_DIR/META-INFO` to distinguish ESI-OpenFOAM builds from Foundation/foam-extend builds, changing decomposition/symlink behavior accordingly.
  - Solver log parsing (dictionary files, transport equation residuals, etc.) is delegated to the external `Owls` library (`Owls.parser.FoamDict.FileParser`, `Owls.parser.LogFile.LogFile`), pulled from git (`Owls @ git+https://github.com/greole/Owls.git@Owls2.0` in `pyproject.toml`).

**MPI runtime:**
- `mpirun` - Invoked as a plain shell command template for parallel solver runs (`src/obr/signac_wrapper/operations.py:runParallelSolver`/`runParallelPre`/`runParallelPost`). Default template: `mpirun -np {np} {solver} -parallel -case {path}/case > {path}/case/{solver}_{timestamp}.log 2>&1`. Fully overridable via the `OBR_RUN_CMD` / `OBR_SERIAL_RUN_CMD` environment variables (documented in `README.md` under "Environmental variables").

## Data Storage

**Databases:**
- None — no SQL, MongoDB, or other database engine is used. All state is stored as flat JSON on disk by signac: `signac_statepoint.json` (immutable job parameters) and `signac_job_document.json` (mutable job state/history/cache) per job directory under `workspace/<job-id>/` (referenced throughout `src/obr/cli.py`, `src/obr/signac_wrapper/operations.py`, `src/obr/core/core.py`).
- `job.doc["cache"]`, `job.doc["state"]`, and `job.doc["history"]` act as an ad hoc embedded document store per job (no external DB server, no MongoDB despite signac's optional MongoDB-backed indexing feature — that feature is not used here).

**File Storage:**
- Local filesystem only. Case files are copied or symlinked between parent/child jobs in the workspace tree (`_link_path` in `src/obr/signac_wrapper/operations.py`). `view/` is a signac "view" — a human-readable symlink tree mirroring `workspace/` (`map_view_folder_to_job_id` in `src/obr/core/core.py`).
- Query/validation results can be exported to flat JSON files via `obr query --export_to` (`src/obr/cli_util.py:query_impl`).
- `obr postProcess` writes aggregated results to `postpro.json` in the working directory (`src/obr/cli.py`).

**Caching:**
- `GitRepo.cache_folder` (`src/obr/core/caseOrigins.py`) - Optional local directory used to cache a cloned case repository so subsequent `obr init` runs `git pull` instead of re-cloning.
- `job.doc["cache"]` - Per-job cache of expensive-to-recompute values (`numberOfSubdomains`, `tasksPerNode`, mesh cell counts, file md5sums) to avoid re-parsing OpenFOAM dictionaries (`get_number_of_procs`, `get_tasks_per_node` in `src/obr/signac_wrapper/operations.py`).
- No external caching service (Redis, memcached, etc.).

## Authentication & Identity

**Auth Provider:**
- None — OBR has no user authentication/authorization layer of its own; it runs as whatever OS user invokes the CLI, inheriting that user's filesystem permissions and any HPC-scheduler/git credentials already configured in the shell.
- Git authentication (for `obr archive --push` and `GitRepo` case origins) is delegated entirely to the ambient git/SSH/credential-helper configuration on the host; OBR does not manage or store credentials (`GitPython`'s `Repo` object is used purely for local git operations plus `repo.git.push`).

## Monitoring & Observability

**Error Tracking:**
- None — no Sentry/Bugsnag/etc. integration. Failures are caught locally and written into `job.doc["state"]["global"] = "failure"` plus a traceback logged via the `OBR` logger (`execute_operation` in `src/obr/signac_wrapper/operations.py`).

**Logs:**
- Custom Python `logging` setup (`src/obr/core/logger_setup.py`): a named `"OBR"` logger with a custom `SUCCESS` level, colorized console output via `coloredlogs.ColoredFormatter`, and a rotating file handler writing to `<workspace>/.obr/obr.log` (10KB per file, 3 backups).
- Per-operation shell command history/logs are additionally persisted inside each job's `signac_job_document.json` under `history` (`logged_execute` / `logged_func` in `src/obr/core/core.py`), and solver stdout/stderr are redirected to timestamped `.log` files inside each case folder.

## CI/CD & Deployment

**Hosting:**
- No production hosting — OBR is installed directly onto HPC login/compute nodes or developer workstations via `pip install -e .` / `pip install .` (no PyPI package publish step detected in workflows).
- Documentation is hosted on Read the Docs (`https://obr.readthedocs.io/`, built per `.readthedocs.yaml`).

**CI Pipeline:**
- GitHub Actions (`.github/workflows/`):
  - `test.yaml` - Dispatches `unit_test.yaml` and `integration_test.yaml` on push to `dev`/`main` and on PR sync.
  - `unit_test.yaml` - Installs the package, runs `pytest -m "not integtest"` under `coverage`, and publishes a coverage badge to a GitHub Gist via `schneegans/dynamic-badges-action` (requires `secrets.GIST_TOKEN`).
  - `integration_test.yaml` - Runs inside the `greole/ofbase` Docker container (pre-built OpenFOAM v2212 image), sources OpenFOAM env vars, then runs `obr init`, `obr run -o generate`, `obr run -o runSerialSolver`, `obr status`, and validates results with `obr query --validate_against tests/cavity_results.json`.
  - `main.yml` (black-action) - Runs `black --check` and `autoflake` on every push/PR.
  - `pr-formatting.yml` - Comment-triggered (`format!`) auto-formatting bot that commits `black`-formatted code back to the PR branch (requires `secrets.BOT_TOKEN`).
  - `typo_check.yml` - Runs `crate-ci/typos` spell checker on PRs.
  - `valid_version_bump.yml` - Enforces a semver bump in `pyproject.toml` on PRs targeting `dev` (`rayepps/require-semver-bump`).
  - `check_changelog.yaml` - Enforces a `CHANGELOG.rst` update on PRs (`dangoslen/changelog-enforcer`).
- No CD/deployment automation (no PyPI publish workflow, no container registry push for OBR itself).

## Environment Configuration

**Required env vars:**
- OpenFOAM environment (must be sourced before use): `WM_PROJECT_DIR`, `FOAM_TUTORIALS`, `FOAM_ETC`, plus the full `WM_*`/`FOAM_*` variable set OpenFOAM's `etc/bashrc` exports (see `.github/workflows/integration_test.yaml` for the full list used in CI: `WM_PROJECT`, `WM_OPTIONS`, `WM_COMPILER_TYPE`, `WM_COMPILER`, `WM_PRECISION_OPTION`, `WM_LABEL_SIZE`, `WM_COMPILE_OPTION`, `WM_OSTYPE`, `WM_ARCH`, `WM_ARCH_OPTION`, `WM_LINK_LANGUAGE`, `WM_LABEL_OPTION`).
- OBR-specific (all optional, documented in `README.md`): `OBR_RUN_CMD`, `OBR_SERIAL_RUN_CMD`, `OBR_CUSTOM_SOLVER_CMD`, `OBR_PREFLIGHT`, `OBR_SKIP_COMPLETE`, `OBR_JOB`, `OBR_CALL_ARGS`, `OBR_APPLY_FILE`, `OBR_APPLY_CAMPAIGN`, `OBR_PROFILE`.
- MPI-related (used only inside CI containers): `OMPI_ALLOW_RUN_AS_ROOT`, `OMPI_ALLOW_RUN_AS_ROOT_CONFIRM`, `OMPI_MCA_btl_vader_single_copy_mechanism`.

**Secrets location:**
- No secrets are stored in the repository. CI secrets (`secrets.GIST_TOKEN`, `secrets.BOT_TOKEN`) are managed via GitHub Actions repository secrets, referenced only from workflow YAML.
- No `.env` file usage was found in the codebase.

## Webhooks & Callbacks

**Incoming:**
- None — OBR is a CLI tool with no HTTP server component.

**Outgoing:**
- `obr init --url <url>` fetches a workflow YAML config over HTTP(S) via `urllib.request.urlopen` (`src/obr/core/parse_yaml.py:read_yaml`) — a one-shot GET, not a persistent integration.
- `obr archive --push` pushes commits to a git remote (`repo.git.push("origin", ...)` in `src/obr/cli.py`) — the target repository is user-specified via `--repo`, not a fixed external service.
- signac-flow's scheduler detection (used by `obr submit`) shells out to the local HPC scheduler's CLI (e.g. `sbatch`/`squeue` for SLURM) to submit and query jobs; no direct API/network integration is implemented by OBR itself — this is signac-flow's built-in environment/scheduler abstraction (see `README.md`: "OBR detects the installed job queuing system, eg. slurm, pbs, etc.").

---

*Integration audit: 2026-07-13*
