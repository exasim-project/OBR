<!-- refreshed: 2026-07-13 -->
# Architecture

**Analysis Date:** 2026-07-13

## System Overview

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                          CLI Layer (click commands)                       │
│  `src/obr/cli.py` — obr init | run | submit | query | status | reset |    │
│                      apply | postProcess | archive                       │
│  `src/obr/cli_util.py` — cli_cmd_setup(), query_impl(), copy_to_archive() │
└───────────────────────┬─────────────────────────────────┬────────────────┘
                         │                                 │
                         ▼                                 ▼
┌────────────────────────────────────────┐   ┌──────────────────────────────┐
│   Tree / Workspace Generation           │   │  Signac FlowProject wrapper  │
│  `src/obr/create_tree.py`               │   │ `src/obr/signac_wrapper/`    │
│  - parses `config["case"]` + variations │   │  operations.py: OpenFOAMProj-│
│  - creates signac jobs (statepoints)    │   │  ect(flow.FlowProject),      │
│  - builds `id_path_mapping` for `view/` │   │  @generate / @simulate       │
└───────────────────────┬──────────────────┘  │  operation graph, pre/post   │
                         │                     │  hooks, eligibility checks   │
                         │                     │  labels.py: FlowProject      │
                         │                     │  labels (finished, final...) │
                         │                     │  submit.py: submit_impl()    │
                         │                     └──────────────┬────────────────┘
                         ▼                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    OpenFOAM Case Abstraction Layer                        │
│  `src/obr/OpenFOAM/case.py`   — OpenFOAMCase (File wrapper, decomposePar, │
│                                  md5sum tracking, state parsing)          │
│  `src/obr/OpenFOAM/BlockMesh.py` — BlockMesh mixin (blockMesh, refineMesh)│
│  `src/obr/core/caseOrigins.py`   — CaseOnDisk, GitRepo, OpenFOAMTutorial- │
│                                     Case, MultiCase (case fetch strategy) │
└───────────────────────┬───────────────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────────────────┐
│              Cross-cutting core utilities                                 │
│  `src/obr/core/core.py`      — shell execution, logging to job.doc,       │
│                                 view-folder <-> job-id mapping, profiling  │
│  `src/obr/core/queries.py`   — Query/Predicates dataclasses, filter/query │
│                                 engine over merged statepoint+doc data     │
│  `src/obr/core/parse_yaml.py`— YAML include/variable expansion            │
│  `src/obr/core/logger_setup.py` — colored console + rotating file logger  │
└───────────────────────┬───────────────────────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────────────────────┐
│         signac data store (on disk, not part of this codebase)            │
│  `workspace/<job-id>/` — signac_statepoint.json, signac_job_document.json,│
│                           `case/` (actual OpenFOAM case files)            │
│  `view/` — human-readable symlink tree mirroring `workspace/` by schema   │
│  `.obr/obr.log` — rotating debug log                                      │
└───────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI commands | Parse click options, orchestrate the other layers, own no business logic beyond wiring | `src/obr/cli.py` |
| CLI helpers | Shared setup (`cli_cmd_setup`), query dispatch, archive copy helper | `src/obr/cli_util.py` |
| Tree builder | Turns a YAML config into a tree of signac jobs (statepoints) with parent/child links | `src/obr/create_tree.py` |
| OpenFOAMProject | Subclass of `flow.FlowProject`; declares all signac operations, job filtering, grouping | `src/obr/signac_wrapper/operations.py` |
| Signac labels | Boolean predicates over job state used for eligibility and status reporting | `src/obr/signac_wrapper/labels.py` |
| Submit wrapper | Builds cluster-submission argument set and calls `project.submit()` | `src/obr/signac_wrapper/submit.py` |
| OpenFOAM case model | Object model over an OpenFOAM case directory (controlDict, fvSolution, decomposePar, mesh state, solver logs) | `src/obr/OpenFOAM/case.py` |
| BlockMesh mixin | blockMesh/refineMesh/checkMesh operations, mixed into `OpenFOAMCase` | `src/obr/OpenFOAM/BlockMesh.py` |
| Case origins | Strategy classes for how a case is fetched/created (`CaseOnDisk`, `GitRepo`, `OpenFOAMTutorialCase`, `MultiCase`) | `src/obr/core/caseOrigins.py` |
| Query engine | Generic key/value/predicate query language used by `obr query`, filters (`--filter`), and internal statepoint traversal | `src/obr/core/queries.py` |
| YAML parsing | Loads and pre-processes workflow YAML: `${{include.*}}`, `${{env.*}}`, `${{yaml.*}}`, `${{get.*}}` substitution | `src/obr/core/parse_yaml.py` |
| Core utilities | Shell execution + job.doc history logging, view/job-id mapping, temp-folder/delink helpers, profiling | `src/obr/core/core.py` |
| Logging setup | Configures the `"OBR"` logger (console + rotating file, custom `SUCCESS` level) | `src/obr/core/logger_setup.py` |

## Pattern Overview

**Overall:** Thin CLI wrapper around a `signac`/`signac-flow` workflow (`FlowProject` subclass). OBR itself does not implement a scheduler, job graph, or persistence layer — it delegates job identity, statepoint storage (`signac_statepoint.json`), document storage (`signac_job_document.json`), and DAG execution/submission entirely to `signac`/`signac-flow`. OBR's own code is the domain layer that turns YAML case-variation definitions into signac jobs, and turns signac operations into OpenFOAM CLI invocations (`blockMesh`, `decomposePar`, `mpirun ... solver`).

**Key Characteristics:**
- **Declarative workflow definition.** Users write YAML (`case:` + `variation:` trees); `create_tree.py` recursively expands `variation` blocks into a tree of signac jobs, each job's statepoint carrying `parent_id`, `operation`, `keys`, and operation-specific args.
- **Operations as signac-flow operations.** Each OpenFOAM step (`blockMesh`, `decomposePar`, `fvSolution`, `runParallelSolver`, ...) is a `@OpenFOAMProject.operation` function in `signac_wrapper/operations.py`, gated by `@OpenFOAMProject.pre`/`@OpenFOAMProject.post` eligibility predicates and grouped into `generate` (case setup) and `simulate` (execution) `flow` groups.
- **Copy-on-write / link-based inheritance between jobs.** Child jobs do not duplicate case files; `initialize_if_required()` symlinks (or, for `shell` operations, copies) the parent job's `case/` tree into the child via `_link_path()`. This keeps large mesh/processor directories shared until a step needs to modify them (`modifies_file()` in `core.py` unlinks-then-copies on demand).
- **State machine per job.** `job.doc["state"]["global"]` drives eligibility: `""` → `started` → `tmp_lock` (already running, avoids reentrancy) → `ready` (operation done) / `completed` / `incomplete` / `failure` / `dirty`. Hooks (`dispatch_pre_hooks`/`dispatch_post_hooks`/`set_failure`) manage these transitions around every operation.
- **Generic query/filter DSL.** `obr query`/`--filter` both compile into `Query` objects (`core/queries.py`) that recursively walk merged `{**job.doc, **job.sp()}` dictionaries; the same engine is reused for `obr status`, `obr submit --filter`, and `obr postProcess`.
- **View folder as human-readable index.** `generate_view()` (`create_tree.py`) and `map_view_folder_to_job_id()` (`core/core.py`) maintain a symlinked `view/` tree whose paths are derived from each variation's `schema` string, mapping deterministically back to the signac job UID under `workspace/`.

## Layers

**CLI (`src/obr/cli.py`, `src/obr/cli_util.py`):**
- Purpose: Parse arguments (click), validate preconditions, call into the workflow layer, print/log results.
- Location: `src/obr/cli.py`, `src/obr/cli_util.py`
- Contains: One click command function per subcommand (`init`, `run`, `submit`, `query`, `status`, `reset`, `apply`, `postProcess`, `archive`); `common_params` decorator adds `--debug`/`--folder`/`--filter` to shared commands.
- Depends on: `signac_wrapper.operations.OpenFOAMProject`, `signac_wrapper.submit.submit_impl`, `create_tree.create_tree`, `core.parse_yaml.read_yaml`, `cli_util`, `core.core`, `core.logger_setup`.
- Used by: The `obr` console-script entry point (`pyproject.toml` → `obr = "obr.cli:main"`) and `python -m obr` (`src/obr/__main__.py`).

**Tree / workspace generation (`src/obr/create_tree.py`):**
- Purpose: Convert a parsed YAML config dict into a signac job tree (statepoints) and a `view/` folder.
- Location: `src/obr/create_tree.py`
- Contains: `create_tree()`, `add_variations()` (recursive expansion), `extract_from_operation()`/`get_path_from()` (schema → path derivation), `expand_generator_block()` (numeric/list generator expansion), `generate_view()`.
- Depends on: `signac_wrapper.operations.OpenFOAMProject`, `core.queries.statepoint_query`, `core.parse_yaml` (expression/query evaluation), `core.logger_setup`.
- Used by: `cli.init` command.

**Signac workflow layer (`src/obr/signac_wrapper/`):**
- Purpose: Define the `OpenFOAMProject` (a `flow.FlowProject` subclass), all signac operations, eligibility/pre-post predicates, job filtering/grouping, and cluster submission.
- Location: `src/obr/signac_wrapper/operations.py`, `labels.py`, `submit.py`
- Contains: Operation functions (`controlDict`, `blockMesh`, `decomposePar`, `refineMesh`, `fetchCase`, `runParallelPre`/`runParallelSolver`/`runParallelPost`, `runSerialSolver`, `allClean`, `checkMesh`, `resetCase`, `validateState`, `archive`, `apply`), hook dispatchers (`dispatch_pre_hooks`, `dispatch_post_hooks`, `set_failure`), eligibility helpers (`basic_eligible`, `is_locked`, `is_job`, `parent_job_is_ready`, `needs_initialization`, `initialize_if_required`), FlowProject `@label`s (`labels.py`), `submit_impl()` (`submit.py`).
- Depends on: `flow` (signac-flow), `signac.job.Job`, `obr.OpenFOAM.case.OpenFOAMCase`, `obr.core.caseOrigins`, `obr.core.queries`, `obr.core.core`.
- Used by: `cli.py` (`project.run(...)`, `project.submit(...)`), `create_tree.py` (`project.open_job(...)`).

**OpenFOAM case model (`src/obr/OpenFOAM/`):**
- Purpose: Object-oriented wrapper for reading/writing OpenFOAM dictionary files, mesh decomposition, and solver-log state parsing.
- Location: `src/obr/OpenFOAM/case.py`, `src/obr/OpenFOAM/BlockMesh.py`
- Contains: `OpenFOAMCase(BlockMesh)` — composes per-file `File` objects (`controlDict`, `fvSolution`, `fvSchemes`, `transportProperties`, optional `decomposeParDict`/`turbulenceProperties`), exposes `decomposePar()`, `replaceMesh()`, `setKeyValuePair()`, `process_latest_time_stats()`, `detailed_update()`, `was_successful()`, md5sum-based dirty tracking. `File(FileParser)` (from `Owls.parser.FoamDict`) adds `get`/`set`/`md5sum`/`is_modified`. `BlockMesh` mixin adds `blockMesh`, `refineMesh`, `checkMesh`, `calculate_simple_partition`.
- Depends on: `Owls.parser.FoamDict.FileParser`, `Owls.parser.LogFile.LogFile` (external `Owls` package), `obr.core.core` (`logged_execute`, `modifies_file`, `TemporaryFolder`, `DelinkFolder`, `find_time_folder`).
- Used by: `signac_wrapper/operations.py` (nearly every operation instantiates `OpenFOAMCase(job.path + "/case", job)`), `core/core.py` (`get_latest_log`).

**Case origins (`src/obr/core/caseOrigins.py`):**
- Purpose: Strategy pattern for how the *base* case files are obtained before any variation is applied.
- Location: `src/obr/core/caseOrigins.py`
- Contains: `CaseOnDisk` (copy from local path), `OpenFOAMTutorialCase(CaseOnDisk)` (resolves `$FOAM_TUTORIALS/<domain>/<application>/<case>`), `GitRepo` (git clone/checkout, optional cache folder), `MultiCase` (placeholder for custom multi-case scripted workflows), `instantiate_origin_class()` factory.
- Depends on: `git.repo.Repo` (GitPython).
- Used by: `signac_wrapper/operations.py` (`fetchCase`, `MultiCase` operations).

**Query engine (`src/obr/core/queries.py`):**
- Purpose: Generic `<key><predicate><value>` query/filter language, used for `--filter`, `obr query`, `obr submit --filter`, `obr postProcess`, and internal statepoint traversal (`statepoint_get`, `statepoint_query`).
- Location: `src/obr/core/queries.py`
- Contains: `Query`/`Predicates`/`query_result` dataclasses, `build_filter_query()`, `flatten_jobs()`, `query_flat_jobs()`, `query_to_dict()`/`query_impl()`/`query_to_records()`/`query_to_dataframe()`, `filter_jobs()`.
- Depends on: `pandas` (for `query_to_dataframe`), `signac.job.Job` (type-only via `TYPE_CHECKING`).
- Used by: `cli_util.py` (`query_impl`), `signac_wrapper/operations.py` (`filter_jobs`, `statepoint_get`), `create_tree.py` (`statepoint_query`).

**Core utilities (`src/obr/core/core.py`):**
- Purpose: Cross-cutting helpers not specific to any one layer — shell execution with job.doc history logging, view↔job-id mapping, mesh-stat parsing, temp-folder/symlink-delink management, profiling.
- Location: `src/obr/core/core.py`
- Contains: `logged_execute`, `logged_func`, `execute_shell`, `get_mesh_stats`, `merge_job_documents`, `get_latest_log`, `find_solver_logs`, `map_view_folder_to_job_id`, `TemporaryFolder`/`DelinkFolder` (RAII-style context helpers), `find_time_folder`, `profile_call`.
- Depends on: standard library only (+ `signac.job.Job` for typing); imports `OpenFOAMCase` lazily inside `get_latest_log` to avoid a circular import with `OpenFOAM/case.py`.
- Used by: Nearly every other layer (`signac_wrapper/operations.py`, `OpenFOAM/case.py`, `OpenFOAM/BlockMesh.py`, `cli.py`).

**YAML parsing (`src/obr/core/parse_yaml.py`):**
- Purpose: Load a workflow YAML file (or URL) and pre-process template expressions before `yaml.safe_load`.
- Location: `src/obr/core/parse_yaml.py`
- Contains: `read_yaml()` (file/URL + `${{include.*}}` resolution), `parse_special_variables()` (`${{env.*}}`, `${{yaml.*}}`), `parse_queries()` (`${{get.*}}` against the parsed config dict), `eval_generator_expressions()` (raw `eval()` of `${{ ... }}` arithmetic/boolean expressions).
- Depends on: standard library only.
- Used by: `cli.py` (`init`, `postProcess`), `create_tree.py` (`add_variations`).

## Data Flow

### Primary Request Path: `obr init --config X.yaml [-g/--generate]`

1. CLI parses `--config`/`--url`, ensures `.obr/` exists, calls `read_yaml()` to load + expand includes/variables (`cli.py:301-329` → `core/parse_yaml.py:23`).
2. `OpenFOAMProject.init_project(path=ws_fold)` creates/loads the signac project (`cli.py:331`).
3. `create_tree(project, config, kwargs)` is called (`cli.py:332` → `create_tree.py:304`):
   - Opens the base job from `config["case"]` (`project.open_job(base_case_state)`).
   - Recursively walks `config["variation"]` (`add_variations()`), for every leaf value: derives `path` from `schema` or `key`, builds a `statepoint` dict (`keys`, `parent_id`, `operation`, `has_child`, `pre_build`, `post_build`, operation args), opens a signac job (`project.open_job(statepoint)`), initializes `job.doc` (`setup_job_doc`), and records `id_path_mapping[job.id]`.
   - Calls `generate_view()` to build the symlinked `view/` tree from `id_path_mapping`.
4. If `-g/--generate` was passed, `project.run(names=["generate"], ...)` executes every `@generate`-grouped operation whose `pre`/`post` predicates are satisfied, in dependency order determined by signac-flow.

### Primary Request Path: `obr run -o <op1,op2,...>`

1. `cli_cmd_setup(kwargs)` (`cli_util.py:108`) chdirs into `--folder`, loads the project (`OpenFOAMProject.get_project()`), resolves the job list via `--filter`/`--job` (`project.filter_jobs()` → `core/queries.filter_jobs`), and validates the workspace is non-empty.
2. `check_cli_operations()` validates requested operation names against `project.operations` (signac-flow's registry populated by `@OpenFOAMProject.operation` decorators in `operations.py`).
3. For `runParallelSolver`, `-t/--tasks` defaults to `1` to avoid CPU oversubscription, then `project.run(names=["runParallelSolver"], np=ntasks)` is called directly.
4. Otherwise `project.run(names=operations, jobs=jobs, np=tasks)` is called; signac-flow evaluates each job's `@pre`/`@post` predicates (in `operations.py`) to determine eligibility, then invokes the matching operation function.
5. Every operation is wrapped by `OpenFOAMProject.operation_hooks`: `on_start` → `dispatch_pre_hooks` (sets `job.doc["state"]["global"]`, runs `pre_build` steps), the operation body itself (usually instantiates `OpenFOAMCase` and calls a case method, e.g. `case.blockMesh(args)`), `on_success` → `dispatch_post_hooks` (`post_build` steps, md5sum recalculation, sets state `"ready"`), `on_exception` → `set_failure`.
6. `cmd=True` operations (`runParallelPre`, `runParallelSolver`, `runParallelPost`, `runSerialSolver`) instead **return a shell command string** (`run_cmd_builder()`) that signac-flow executes as a subprocess; `directives={"np": ..., "tpn": ...}` tell signac-flow how many cores/tasks-per-node the job needs.

### Case-Generation Pipeline (per job)

1. `fetchCase` (pre: no `parent_id`) — instantiates a `caseOrigins.*` class based on `job.sp["type"]` (`GitRepo`/`CaseOnDisk`/`OpenFOAMTutorialCase`/`MultiCase`) and calls `.init(job.path)` to materialize `case/` on disk.
2. For child jobs, `initialize_if_required()` (called from `basic_eligible()`) symlinks (or copies, for `shell` ops) the parent's `case/` tree via `_link_path()` before any operation body executes — this is how variations "inherit" files cheaply.
3. Individual operations (`controlDict`, `fvSolution`, `fvSchemes`, `transportProperties`, `turbulenceProperties`, `setKeyValuePair`, `blockMesh`, `refineMesh`, `replaceMesh`, `decomposePar`, `shell`, `initialConditions`) each mutate exactly one aspect of the case via `OpenFOAMCase` / `File.set()`, which internally calls `modifies_file()` to unlink-then-copy any symlinked file before writing.
4. `dispatch_post_hooks` → `case.perform_post_md5sum_calculations()` stores an md5sum + mtime per config file into `job.doc["cache"]["md5sum"]`, used later by `is_tree_modified()`/`is_file_modified()`.

### Run/Solve Pipeline

1. `runParallelPre` (optional, gated on `pre_cmds` in the statepoint) builds and returns one shell line per `pre_cmds` entry via `run_cmd_builder()`.
2. `runParallelSolver` (in the `simulate` group; `@pre.after(runParallelPre)`) resolves `np`/`tasksPerNode` (`get_number_of_procs`/`get_tasks_per_node`, cached in `job.doc["cache"]`), chooses parallel (`mpirun -np {np} ...`) vs serial template via `select_solver_cmd()`, honors `OBR_CUSTOM_SOLVER_CMD`/`OBR_RUN_CMD`/`OBR_SERIAL_RUN_CMD` env overrides, appends `|| true` + exit-code capture so a failing run doesn't abort the whole batch, and appends a history entry to `job.doc["history"]`.
3. `runParallelPost` (optional, gated on `post_cmds`) mirrors `runParallelPre` for post-processing shell commands.
4. On operation exit, `operation_hooks.on_exit(validate_state_impl)` re-parses the latest solver log (`OpenFOAMCase.detailed_update()` → `process_latest_time_stats()`) to update `job.doc["state"]` (`completed`/`incomplete`/`failure`) and time-stepping metrics (`latestTime`, `continuityErrors`, `CourantNumber`, `ExecutionTime`, `ClockTime`).

### Query / Postprocessing Path (`obr query`, `obr postProcess`, `obr apply`)

1. `obr query` → `query_impl()` (`cli_util.py:20`) builds `Query` objects from `--query`/`--filter` strings (`build_filter_query`), filters jobs, then `project.query()` → `core/queries.query_impl()` flattens `{**job.doc, **job.sp()}` per job and matches queries recursively (descending into nested dicts), optionally exports JSON and validates against a JSON-schema or via `DeepDiff`.
2. `obr postProcess` reads a YAML describing `matcher`/`log` sections, uses the external `Owls.parser.LogFile.LogFile` to parse solver logs matched via `get_latest_log()`, aggregates columns (`average`/`diff_mean`/`diff_mean_skipN`/`diff_mean_useN`) per job, and writes `postpro.json`.
3. `obr apply --file script.py` sets `OBR_APPLY_FILE`/`OBR_APPLY_CAMPAIGN` env vars and invokes the aggregator operation `apply()` (`operations.py:983`), which dynamically imports the user's script and calls `apply_functor.call(jobs)` — jobs are pulled from the module-level `obr.cli.filtered_jobs` global rather than the operation's own arguments (documented workaround for signac-flow aggregator job filtering).
4. `obr archive` copies statepoint/job-document JSON and solver logs from each job's `case/` folder into an external git-backed data repository, optionally creating/checking out a `<campaign>/<timestamp>` branch and committing/pushing.

**State Management:**
- Primary state lives in signac's per-job `job.doc` (JSON, `signac_job_document.json`) and `job.sp()` (immutable statepoint, `signac_statepoint.json`) — both are files on disk, managed by the `signac` library, not by OBR directly.
- OBR's own state machine is the string at `job.doc["state"]["global"]` (see Pattern Overview) plus an operation `job.doc["history"]` list (each shell/func call logged with cmd, state, timestamp, log-file reference) and `job.doc["cache"]` (memoized derived values: `nCells`, `nFaces`, `numberOfSubdomains`, `tasksPerNode`, per-file md5sums).
- No in-memory application state persists between CLI invocations; every `obr` command starts a fresh Python process, re-opens the signac project from disk (`OpenFOAMProject.get_project()`), and exits.

## Key Abstractions

**`OpenFOAMProject` (`flow.FlowProject` subclass):**
- Purpose: The signac-flow project — owns the operation registry, group definitions (`generate`, `simulate`), job iteration/filtering, and submission.
- Examples: `src/obr/signac_wrapper/operations.py:30-79`
- Pattern: Subclassing + decorator-based operation registration (signac-flow convention: `@OpenFOAMProject.operation`, `@OpenFOAMProject.pre`, `@OpenFOAMProject.post`, `@OpenFOAMProject.operation_hooks.on_start/on_success/on_exception/on_exit`).

**`OpenFOAMCase` / `File`:**
- Purpose: Typed accessors over OpenFOAM dictionary files (`controlDict`, `fvSolution`, etc.), hiding raw file I/O and providing `get`/`set` with md5sum-based change tracking.
- Examples: `src/obr/OpenFOAM/case.py:36-98` (`File`), `:99-596` (`OpenFOAMCase`)
- Pattern: Composition (case "has-a" `File` per dict) + mixin inheritance (`OpenFOAMCase(BlockMesh)` adds mesh operations without a deep class hierarchy).

**Statepoint tree (`job.sp()` with `parent_id`/`parent`/`has_child`):**
- Purpose: Encodes the variation DAG directly inside signac statepoints so any job can look up its ancestry (`parent_job_is_ready`, `statepoint_get` recursion into `statepoint["parent"]`) without a separate database.
- Examples: `src/obr/create_tree.py:238-247`, `src/obr/core/queries.py:325-336`
- Pattern: Recursive-lookup value inheritance — a key not present on a job's own statepoint is looked up on `statepoint["parent"]`, recursively, so child jobs implicitly inherit ancestor configuration.

**Query / Predicate DSL (`Query`, `Predicates`):**
- Purpose: A single mini-language (`<key><predicate><value>`, e.g. `solver==pisoFoam`) reused across `--filter`, `--query`, and internal traversal.
- Examples: `src/obr/core/queries.py:18-104` (`Query`, `query_result`, `Predicates`), `:301-322` (`build_filter_query`)
- Pattern: Command/interpreter pattern — a string is compiled once into `Query` objects, then executed against arbitrary flattened dict data.

**Case-origin strategy classes:**
- Purpose: Decouple "how do I get the initial case files" from the rest of the pipeline.
- Examples: `src/obr/core/caseOrigins.py:14-177`
- Pattern: Strategy pattern with a factory (`instantiate_origin_class`) keyed by the `type` string in YAML (`CaseOnDisk`, `GitRepo`, `OpenFOAMTutorialCase`, `MultiCase`).

**`TemporaryFolder` / `DelinkFolder`:**
- Purpose: RAII-style helpers that convert symlinked file trees into real copies for the duration of an operation (some OpenFOAM/MPI operations refuse to run on symlinked content), then restore/clean up in `__del__`/`tear_down()`.
- Examples: `src/obr/core/core.py:394-425`
- Pattern: Context-manager-like resource wrapper (note: relies on `__del__` rather than `__enter__`/`__exit__`, see Anti-Patterns).

## Entry Points

**`obr` console script:**
- Location: `pyproject.toml` (`[project.scripts] obr = "obr.cli:main"`) → `src/obr/cli.py:916` (`main()`) → `cli(obj={})` (the click group at `cli.py:80`).
- Triggers: Direct shell invocation (`obr init ...`, `obr run ...`, etc.).
- Responsibilities: Registers all subcommands (`submit`, `run`, `init`, `status`, `query`, `apply`, `postProcess`, `reset`, `archive`) on the click group `cli`.

**`python -m obr`:**
- Location: `src/obr/__main__.py:12-15`
- Triggers: `python -m obr ...`
- Responsibilities: Imports and calls `obr.cli.main()`; exists only to avoid double-execution issues with click + `__main__` (documented in the module docstring of `cli.py`).

**signac-flow operation dispatch (indirect entry point):**
- Location: `src/obr/signac_wrapper/operations.py` (every `@OpenFOAMProject.operation`-decorated function).
- Triggers: `project.run(names=[...])` or `project.submit(names=[...])`, called from `cli.py`, or (for submitted cluster jobs) the generated submission script re-invoking `obr run -o <op>` per job (via `project.set_entrypoint({"executable": "", "path": "obr"})` in `submit.py:42`).
- Responsibilities: Each operation performs exactly one OpenFOAM setup/execution step and is individually eligible/ineligible based on `@pre`/`@post` predicates.

## Architectural Constraints

- **Process model:** Single-threaded, single-process per `obr` CLI invocation. Parallelism for solver runs comes from `mpirun -np {np}` shelling out, not from Python threads/processes; `project.run(..., np=tasks)` controls signac-flow's *own* worker-process concurrency for running/generating multiple jobs concurrently (separate from MPI ranks).
- **Global state:** `sys.argv` is mutated at runtime in `cli.py` (`run`, `apply` commands append `-t`/`--aggregate` flags) to influence how signac-flow's own CLI parsing behaves downstream — a hidden coupling between OBR's click layer and signac-flow's argument parsing. `obr.cli.filtered_jobs` is set as a **module-level global** and read from inside `signac_wrapper/operations.py:apply()` to work around signac-flow aggregator operations not receiving filtered job lists directly (`operations.py:983-998`). `GLOBAL_INIT_COUNT`/`GLOBAL_UNINIT_COUNT` in `core/core.py` and `operations.py` are process-global counters used for progress logging during initialization, partially read via `os.environ` instead of true globals (inconsistent pattern, see Anti-Patterns).
- **Circular imports (avoided via lazy import):** `core/core.py:get_latest_log()` imports `OpenFOAMCase` from `..OpenFOAM.case` **inside the function body** rather than at module scope, because `OpenFOAM/case.py` imports from `core/core.py` at module scope — a true circular import at the top level. `signac_wrapper/operations.py:apply()` similarly imports `obr.cli` inside the function body to read the `filtered_jobs` global without creating an import cycle with `cli.py` (which imports `operations.py` at module scope).
- **Environment-variable-driven configuration:** Several runtime behaviors are controlled exclusively through environment variables rather than CLI flags or config, because they need to reach deep into signac-flow's own subprocess/command-generation path: `OBR_CUSTOM_SOLVER_CMD`, `OBR_RUN_CMD`, `OBR_SERIAL_RUN_CMD`, `OBR_PREFLIGHT`, `OBR_SKIP_COMPLETE`, `OBR_CALL_ARGS`, `OBR_JOB`, `OBR_APPLY_FILE`, `OBR_APPLY_CAMPAIGN`, `OBR_PROFILE`, `GLOBAL_UNINIT_COUNT`. `obr.core.parse_yaml` also reads arbitrary `${{env.*}}` references from user YAML.
- **External dependency on OpenFOAM being sourced:** `create_tree()` checks `os.environ.get("FOAM_ETC")` and exits with an error if unset (unless `skip_foam_src_check=True`); `OpenFOAMCase.esi_version` requires `WM_PROJECT_DIR` to be set. OBR cannot generate/run cases without an active OpenFOAM environment.
- **Filesystem is the primary data store.** There is no database; job identity, statepoints, and results live entirely under `workspace/<job-id>/` on disk (signac's convention), with `view/` as a derived, disposable symlink index (regenerated wholesale on every `obr init`, `generate_view()` calls `rm -rf` on the existing view path first).

## Anti-Patterns

### Reliance on `__del__` for cleanup

**What happens:** `TemporaryFolder.__del__` (`core/core.py:407`) and `DelinkFolder.__del__` (`core/core.py:424`) perform filesystem cleanup/restoration in `__del__` instead of an explicit context manager (`__enter__`/`__exit__`).
**Why it's wrong:** `__del__` timing is not guaranteed by CPython on all code paths (e.g., reference cycles, exceptions during construction before assignment, interpreter shutdown), risking leftover `.bck` folders or un-restored symlinks if an exception occurs between construction and expected teardown.
**Do this instead:** When adding new temp-folder logic, wrap usage in `try/finally` explicitly or convert these classes to proper context managers (`__enter__`/`__exit__`) and use `with TemporaryFolder(...) as tmp:` at call sites (currently call sites in `OpenFOAM/case.py:decomposePar()` rely on variables simply going out of scope).

### Module-level global mutated from inside decorated aggregator operation

**What happens:** `signac_wrapper/operations.py:apply()` (the `flow.aggregator()`-decorated operation) ignores its own `*jobs` argument and instead reads `obr.cli.filtered_jobs`, a global set by the `apply` CLI command (`cli.py:456-457`) via `global filtered_jobs`.
**Why it's wrong:** Breaks the operation's declared signature/contract, makes the data flow implicit and hard to trace, and only works because `obr apply` is always a single, synchronous, single-process invocation — it would break under any concurrent or multi-process execution of `apply`.
**Do this instead:** If job filtering must reach an aggregator operation, prefer passing filtered job ids through an environment variable (as is already done for `OBR_APPLY_FILE`/`OBR_APPLY_CAMPAIGN`) and re-resolve jobs inside the operation from `project`, rather than mutating a cross-module global.

### Bare `except:`/broad `except Exception` swallowing errors silently

**What happens:** Several hot paths catch broad exceptions and continue without re-raising, e.g. `cli.py:606-608` (`except: pass` inside the postProcess column-aggregation loop), `execute_operation()` in `operations.py:306-310` (logs and sets `job.doc["state"]["global"] == "failure"` — note this is a comparison, not an assignment, see next anti-pattern), `File.get()` in `OpenFOAM/case.py:56-58` (`except: return super().get(name)`).
**Why it's wrong:** Failures are hidden from the caller; a mistyped key, a parsing bug, or a genuine data error look identical to "value legitimately absent," making debugging parameter studies (the whole point of this tool) harder.
**Do this instead:** Catch specific exception types where the failure mode is understood (`KeyError`, `ValueError`, `subprocess.SubprocessError`), and log at `warning`/`error` level with enough context (job id, key, file) even when continuing is the right behavior.

### Comparison instead of assignment in error handler

**What happens:** `src/obr/signac_wrapper/operations.py:310`: `job.doc["state"]["global"] == "failure"` inside the `except` block of `execute_operation()` uses `==` instead of `=`, so the failure state is never actually persisted to the job document.
**Why it's wrong:** A pre/post-build step that raises will be logged (`logger.error(e)`) but the job's `state.global` will silently remain whatever it was before, meaning downstream eligibility checks (`operation_complete`, `parent_job_is_ready`) may treat a failed job as still in-progress or ready.
**Do this instead:** Fix to `job.doc["state"]["global"] = "failure"`. When adding new hook/exception handlers elsewhere, prefer the existing `set_failure()` pattern (`operations.py:362-364`) which correctly assigns.

## Error Handling

**Strategy:** Defensive, operation-local try/except around shell/file operations, translated into the per-job `state.global` string and an append-only `job.doc["history"]` log rather than raised exceptions propagating to the CLI. The `|| true` suffix on solver commands (`run_cmd_builder`, `operations.py:787`) ensures one failing OpenFOAM run does not abort a batch `obr run` covering many jobs.

**Patterns:**
- `logged_execute()` (`core/core.py:49`) wraps subprocess calls, captures stdout+stderr, classifies into `state: "success"/"failure"`, and stores either the inline output or a path to a written log file (depending on size) into `job.doc["history"]`.
- signac-flow's own `operation_hooks.on_exception(set_failure)` is attached to every `@generate`-group operation, guaranteeing `job.doc["state"]["global"] = "failure"` is set on unhandled exceptions raised from the operation body itself (distinct from the broken comparison-only handler inside `execute_operation()` used for `pre_build`/`post_build` sub-steps — see Anti-Patterns).
- `OpenFOAMCase.process_latest_time_stats()` (`OpenFOAM/case.py:491-536`) parses solver log footers for MPI startup errors (`"There are not enough slots available"`) and generic `"ERROR"`/`"error"` strings to set `failureState`, then falls back to `except Exception: state = "failure"` if log parsing itself throws.

## Cross-Cutting Concerns

**Logging:** Centralized through a single named logger `"OBR"` (`logging.getLogger("OBR")`), configured once via `setup_logging()` (`core/logger_setup.py`) with two handlers: a colored console handler (`coloredlogs.ColoredFormatter`, INFO+) and a rotating file handler writing to `<folder>/.obr/obr.log` (DEBUG+, 10KB × 3 backups). A custom `SUCCESS` level (25, between INFO and WARNING) is monkey-patched onto `logging.Logger` for user-facing "operation completed" messages (`logger.success(...)`).

**Validation:** Two forms: (1) Query-result validation against either a JSON Schema (`jsonschema.validate`) or `DeepDiff` comparison, used by `obr query --validate_against` (`cli_util.py:41-64`) — primarily for regression-testing benchmark outputs in CI. (2) Ad-hoc precondition checks scattered through `cli.py`/`cli_util.py` (e.g., `is_valid_workspace()`, `check_cli_operations()`, YAML `required=True` click options) rather than a schema-driven config validator for the workflow YAML itself.

**Authentication:** Not applicable to the core tool. `obr archive` uses `GitPython` to interact with a git remote (`repo.git.push(...)`), relying on the user's ambient git/SSH credentials — OBR performs no credential management itself.
