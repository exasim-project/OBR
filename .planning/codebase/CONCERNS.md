# Codebase Concerns

**Analysis Date:** 2026-07-13

## Tech Debt

**Dead / stub modules:**
- Issue: `src/obr/core.py` and `src/obr/OpenFOAM/solver.py` contain only a shebang line (`#!/usr/bin/env python3`); `src/obr/postPro/postPro.py` is completely empty (0 bytes). The real post-processing logic lives inline in `cli.py` (`postProcess` command) instead of in the `postPro` package that appears to exist for that purpose.
- Files: `src/obr/core.py`, `src/obr/OpenFOAM/solver.py`, `src/obr/postPro/postPro.py`
- Impact: Confusing package layout — a top-level `src/obr/core.py` module coexists with the real `src/obr/core/` package, which risks import ambiguity and misleads readers looking for postprocessing code in `postPro/`.
- Fix approach: Delete the stub files or fill them with their intended contents; move the `postProcess` CLI body out of `cli.py` into `postPro/postPro.py`.

**Pervasive mutable default arguments (`args={}`):**
- Issue: ~25 operation functions across the codebase declare `def op(job, args={})` / `def op(self, args={})`, the classic Python mutable-default-argument anti-pattern (flagged by flake8-bugbear's B006).
- Files: `src/obr/signac_wrapper/operations.py` (`controlDict`, `MultiCase`, `blockMesh`, `replaceMesh`, `shell`, `initialConditions`, `fvSolution`, `fvSchemes`, `transportProperties`, `turbulenceProperties`, `setKeyValuePair`, `decomposePar`, `fetchCase`, `refineMesh`, `allClean`, `checkMesh`, `resetCase`, `validateState`, `runParallelPre`, `runParallelSolver`, `runParallelPost`, `runSerialSolver`, `archive`, `apply`), `src/obr/OpenFOAM/case.py:317` (`decomposePar`), `src/obr/OpenFOAM/BlockMesh.py:141,151` (`blockMesh`, `checkMesh`)
- Impact: Currently mitigated in most call sites because `get_args()` (`signac_wrapper/operations.py:274-287`) always returns a fresh dict before use, but `BlockMesh.blockMesh()` and `copy_on_uses()` call `.pop()` directly on whatever `args` dict they are handed. Any future refactor that removes the `get_args()` indirection re-introduces cross-call state leakage through the shared default dict object.
- Fix approach: Use `args: Optional[dict] = None` and default to `{}` inside the function body; avoid `.pop()` on caller-supplied dicts (copy first).

**Duplicate/dead CLI option decorators:**
- Issue: `status` defines `-S/--summarize` twice (`cli.py:348` and `cli.py:349-356`); `run` defines `--args` twice (`cli.py:213` and `cli.py:216`). Both are harmless today (the decorator closer to the function wins) but are dead, confusing duplication.
- Files: `src/obr/cli.py:213-216`, `src/obr/cli.py:348-356`
- Impact: Anyone editing one copy's `default`/`help` text silently has no effect if they edit the "losing" decorator; increases risk of the same class of bug that caused the `-p` collision below.
- Fix approach: Remove the duplicate decorator in each command.

**Stale `requires-python` constraint:**
- Issue: `pyproject.toml:16` declares `requires-python = ">=3.6"`, but the codebase uses PEP 585 builtin generics (`list[str]`, `dict[str, Job]`, `tuple[OpenFOAMProject, list[Job]]`) directly in type annotations, which require Python ≥3.9.
- Files: `pyproject.toml:16`; usage e.g. `src/obr/cli_util.py:22-23,68,96,108,116`, `src/obr/core/core.py:269,329,428`, `src/obr/OpenFOAM/case.py:130,174,179,245,262`, `src/obr/OpenFOAM/BlockMesh.py:92`, `src/obr/signac_wrapper/submit.py:16-17,61`
- Impact: Installing/importing OBR on Python 3.6–3.8 fails with a runtime `TypeError`/`SyntaxError` rather than a clear dependency-resolution error. CI only tests Python 3.9 (`.github/workflows/unit_test.yaml`), so the mismatch is not caught anywhere.
- Fix approach: Bump `requires-python` to `>=3.9` to match actual usage and CI matrix.

**Static analysis tooling configured but not enforced:**
- Issue: `mypy.ini` and a `[tool.flake8]` section in `pyproject.toml` exist, but no CI workflow runs `mypy` or `flake8`. Only `black` (formatting), `autoflake` (unused-import removal), and `pytest` run in CI (`.github/workflows/main.yml`, `.github/workflows/unit_test.yaml`).
- Files: `mypy.ini`, `pyproject.toml:34-36`, `.github/workflows/main.yml`, `.github/workflows/unit_test.yaml`
- Impact: Type errors and lint violations (including the mutable-default-argument and bare-`except:` patterns documented in this file) are never caught automatically.
- Fix approach: Add a `mypy src` and `flake8 src` step to `.github/workflows/unit_test.yaml` or a dedicated lint workflow.

**Inconsistent shell-out vs. stdlib file operations:**
- Issue: File/directory copy, move, remove, and symlink operations are implemented inconsistently — some via `subprocess.check_output(["cp"/"mv"/"mkdir"/"rm"/"ln", ...])`, others via Python's `shutil`/`os`/`pathlib` (e.g. `shutil.rmtree`, `shutil.copytree` in `cli.py:478`, `caseOrigins.py:50`, but `check_output(["rm", fn])` in `core/core.py:302,320`, `check_output(["cp", "-r", ...])` throughout `core/core.py` and `signac_wrapper/operations.py`).
- Files: `src/obr/core/core.py` (widespread), `src/obr/signac_wrapper/operations.py:154-231,373-386,979`, `src/obr/OpenFOAM/case.py:65,71,478,553`, `src/obr/create_tree.py:96`
- Impact: Slower (process spawn overhead per file/folder), Linux-only (relies on GNU coreutils being on `PATH`), and error messages from `CalledProcessError` are far less specific than Python's built-in `OSError` subclasses (`FileNotFoundError`, `PermissionError`, etc.), making failures harder to diagnose.
- Fix approach: Standardize on `shutil`/`pathlib`/`os` for all local filesystem operations; reserve `subprocess` calls for actual external OpenFOAM binaries (`blockMesh`, `decomposePar`, `checkMesh`, ...).

**Inconsistent `job.sp()` vs `job.sp.get(...)` usage:**
- Issue: The codebase calls the statepoint accessor both as a method (`job.sp()`) and as a plain dict-like attribute (`job.sp.get(...)`, `job.sp["key"]`) in different places (24 call sites total; both styles found in `signac_wrapper/operations.py`, `signac_wrapper/labels.py`, `cli.py`, `core/core.py`).
- Files: e.g. `src/obr/signac_wrapper/operations.py:102,121,146,236,248,264,266` (`job.sp()`) vs. `src/obr/signac_wrapper/operations.py:320,330` (`job.sp.get(...)`); `src/obr/signac_wrapper/labels.py:66` (`job.sp.get(...)`); `src/obr/cli.py:266` (`job.sp()`)
- Impact: `job.sp()` (signac's backward-compatible callable form) returns a plain-dict *snapshot*, while `job.sp.get(...)` reads the live synced-dict view. Mixing both styles makes it unclear at each call site whether stale data could be read, and increases the chance of subtly different behavior if signac's compatibility shim is ever removed.
- Fix approach: Standardize on one accessor style project-wide (prefer the non-callable `job.sp` attribute form going forward, per current signac API guidance) and document the convention.

**Global/environment-variable-based control flow:**
- Issue: OBR uses process-wide environment variables (`OBR_JOB`, `OBR_CALL_ARGS`, `OBR_CUSTOM_SOLVER_CMD`, `OBR_SKIP_COMPLETE`, `OBR_RUN_CMD`, `OBR_SERIAL_RUN_CMD`, `OBR_PREFLIGHT`, `OBR_PROFILE`, `OBR_APPLY_FILE`, `OBR_APPLY_CAMPAIGN`, `GLOBAL_UNINIT_COUNT`) plus a bare module-level global (`obr.cli.filtered_jobs`, set in `cli.py:456-457` and read from `signac_wrapper/operations.py:990`) as an ad hoc side-channel for passing data into operation functions invoked by `signac-flow`.
- Files: `src/obr/cli.py:154,225,234,237,459-463`, `src/obr/signac_wrapper/operations.py:94,732,775,893,963,973,990-991`, `src/obr/core/core.py:22-23`
- Impact: Not thread/process-safe if operations ever run concurrently within one interpreter; hard to unit test in isolation; hard to trace data flow when debugging (state is set in `cli.py` and consumed several call-frames away in `operations.py`).
- Fix approach: Thread explicit parameters/config objects through `project.run(...)` instead of environment variables and CLI-module globals where feasible.

**Changelog out of sync with released version:**
- Issue: `CHANGELOG.rst` latest heading is `0.4.0 (Unreleased)`, but `pyproject.toml:3` declares `version = "0.4.3"`.
- Files: `CHANGELOG.rst`, `pyproject.toml:3`
- Impact: Consumers checking the changelog for what changed in `0.4.1`–`0.4.3` find nothing recorded.
- Fix approach: Update `CHANGELOG.rst` on each version bump (the `valid_version_bump.yml` CI check only enforces that the version number itself changes, not that the changelog is updated).

**Leftover dead debug code:**
- Issue: `basic_eligible()` contains an always-false debug block `if False and (operation == job.sp().get("operation")):` guarding several `logger.info` diagnostic calls that can never execute.
- Files: `src/obr/signac_wrapper/operations.py:129-139`
- Impact: Dead code adds noise and confuses readers trying to understand eligibility logic; the diagnostics it guards may have been useful during a prior debugging session and are effectively lost since the block never runs.
- Fix approach: Remove the block or convert it to a real `logger.debug(...)`-gated path.

## Known Bugs

**Pre/post-build operation failures are never recorded (silent failure swallowing):**
- Symptoms: When a `pre_build`/`post_build` sub-operation raises an exception, the traceback and error are logged, but the job's failure state is never actually set. `execute_operation()` unconditionally `return True` regardless of whether an exception occurred, so `dispatch_pre_hooks`/`dispatch_post_hooks` proceed as if the job succeeded, and `basic_eligible()`/`operation_complete()` treat the job as healthy on the next run.
- Files: `src/obr/signac_wrapper/operations.py:290-311`, specifically line 310
- Trigger: Any `pre_build`/`post_build` entry in a YAML config that references an operation which raises (e.g. `controlDict` called with a malformed args dict, a missing `uses` source file, etc.).
- Root cause: `job.doc["state"]["global"] == "failure"` uses the equality operator (`==`) instead of assignment (`=`). The comparison result is computed and discarded; nothing is written to `job.doc`.
- Workaround: None currently; failures must be discovered by manually inspecting `logger.error` output/log files rather than via `obr status`/`obr query --filter global==failure`.
- History: Introduced in commit `a0f14a96` (2023-07-26) and unchanged since; not covered by any test in `tests/test_operations.py`.

**`OpenFOAMCase.replaceMesh()` crashes with `NameError` — missing `shutil` import:**
- Symptoms: `NameError: name 'shutil' is not defined` raised whenever `replaceMesh` is invoked on a case whose `constant/polyMesh` already exists.
- Files: `src/obr/OpenFOAM/case.py:304-315`, specifically the `shutil.rmtree(polyMeshPath)` call at line 309; `shutil` is never imported anywhere in `case.py` (verified — only `os`, `re`, `logging`, `Path`, `check_output`, `Job`, `datetime`, `Owls` classes, and local `core`/`BlockMesh` imports are present).
- Trigger: `obr run -o replaceMesh` (operation defined at `src/obr/signac_wrapper/operations.py:438-451`) on a job that already owns a `constant/polyMesh` directory.
- Workaround: None. Not covered by any test (`replaceMesh` does not appear in `tests/`).

**`MultiCase.init()` crashes with `NameError` — `os` module not imported:**
- Symptoms: `NameError: name 'os' is not defined` raised whenever a `MultiCase`-type case origin is initialized into a directory that doesn't already contain a `case` subfolder.
- Files: `src/obr/core/caseOrigins.py:1-28`, specifically `os.makedirs(os.path.join(path, "case"))` at line 28; only `from os import environ` and `from os.path import expandvars, isdir` are imported — the bare `os` module is never imported.
- Trigger: `obr init --config <cfg>` where a `type: MultiCase` case entry's target path exists but has no `case/` subfolder yet (see `fetchCase`/`MultiCase` operations at `src/obr/signac_wrapper/operations.py:413-424,593-611`).
- Workaround: None. `MultiCase` has zero test coverage (`tests/test_caseOrigins.py` only exercises `OpenFOAMTutorialCase`, both tests skipped unless `$FOAM_TUTORIALS` is set).

**CLI short-option collision breaks `obr submit -p`:**
- Symptoms: Running `obr submit -p` (documented as the short form of `--pretend`) fails with `click.exceptions.BadOptionUsage: Option '-p' requires an argument.` instead of enabling pretend mode.
- Files: `src/obr/cli.py:87-149` — `-p`/`--pretend` is declared at line 90-91, then `-p`/`--partition` is declared again at line 139; click resolves `-p` to whichever option's long name comes last in its internal option map (`--partition`, which requires a value), not `--pretend`.
- Trigger: Any invocation of `obr submit -p` (without also passing `--partition`'s value in the same position).
- Root cause: Reused short flag `-p` for two different options within the same command. Verified interactively with `click==8.1.6`: `-p` alone raises `BadOptionUsage`; `-p foo` sets `partition='foo'` and leaves `pretend=False`; only the long-form `--pretend` reliably works.
- Workaround: Always use `--pretend` (long form) instead of `-p`.

**Cosmetic path-formatting bugs (`.absolute` used as a value instead of calling `.absolute()`):**
- Symptoms: Log/warning messages meant to show an absolute path instead print a Python bound-method repr, e.g. `<bound method PurePath.absolute of PosixPath('...')>`.
- Files: `src/obr/cli.py:883` (`f"Would copy {f} to {f.absolute}."`), `src/obr/core/caseOrigins.py:25` and `:44` (`f"{self.path.absolute} or some parent directory does not exist!"`)
- Trigger: `obr archive --dry-run` with `--file` entries; `CaseOnDisk`/`MultiCase` origin initialization against a path that doesn't exist.
- Workaround: None needed functionally (cosmetic only), but the diagnostic message is unhelpful for troubleshooting missing-path errors.

**`execute_shell()` can raise `IndexError` on trailing line-continuation:**
- Symptoms: `IndexError: list index out of range` if the *last* shell step in a `shell` operation's list ends with a line-continuation backslash (`\`).
- Files: `src/obr/core/core.py:269-291`, specifically `steps[i + 1] = cleaned + steps[i + 1]` at line 282, executed for `i == len(steps) - 1`.
- Trigger: A YAML `shell` operation whose last command string ends in `\`.
- Workaround: Don't end the final shell step with a trailing backslash.

**`logged_execute()`'s generic exception handler references undefined names:**
- Symptoms: When `check_output(...)` raises an exception that is neither `subprocess.SubprocessError` nor `FileNotFoundError` (e.g. a `PermissionError`, `UnicodeDecodeError` from `.decode("utf-8")`, or an `OSError` variant), the `except Exception as e:` branch tries to read `e.output` (which most exception types don't have) and `ret` (only ever assigned on the success path) — raising a *second*, unrelated exception (`AttributeError`/`NameError`/`UnboundLocalError`) that masks the original error.
- Files: `src/obr/core/core.py:49-84`, specifically lines 79-83.
- Trigger: Any non-`SubprocessError`/non-`FileNotFoundError` exception during `logged_execute()` (used by every `OpenFOAMCase._exec_operation` call, i.e. `blockMesh`, `decomposePar`, `checkMesh`, `refineMesh`, `Allclean`, log removal, mesh replacement).
- Workaround: None; root-cause exceptions in this path are effectively unrecoverable/undiagnosable from the logged output.

## Security Considerations

**Remote/templated YAML configs can execute arbitrary Python via `eval()`:**
- Risk: `obr init` supports fetching the workspace config from a remote URL (`-u/--url`, `src/obr/cli.py:299`, `src/obr/core/parse_yaml.py:24-26` via `urllib.request.urlopen`). The fetched (or local) YAML is later processed by `eval_generator_expressions()`, which runs `eval(inst)` on the contents of every `${{ ... }}` template expression found in the config (`src/obr/core/parse_yaml.py:88-101`). Any YAML config — local or remote — containing a crafted `${{ }}` expression executes arbitrary Python with the privileges of the `obr` process.
- Files: `src/obr/core/parse_yaml.py:24-26,88-101`, invoked from `src/obr/create_tree.py:218` inside `add_variations()`.
- Current mitigation: None. `urlopen` uses plain HTTP/HTTPS with no integrity check (no hash pinning), so a config fetched over HTTP is also vulnerable to MITM tampering.
- Recommendations: Replace `eval()` with a restricted expression evaluator (e.g. `ast.literal_eval` plus a small allow-listed arithmetic parser), or require explicit user opt-in (`--allow-eval`) before evaluating expressions from configs not authored locally. At minimum, warn loudly when `--url` is combined with expression templating.

**Path traversal in YAML `${{include...}}` directive:**
- Risk: `add_includes()`'s regex (`r"([ \t]*)\${{include.([_/\w.]*)}}"`, `src/obr/core/parse_yaml.py:50`) allows both `.` and `/` inside the include filename with no normalization or containment check, so a config can reference `${{include../../../../etc/passwd}}` to splice arbitrary local file contents into the parsed configuration.
- Files: `src/obr/core/parse_yaml.py:48-61`
- Current mitigation: None.
- Recommendations: Resolve the requested include path and verify it stays within an allowed base directory (e.g. `Path.resolve()` + `is_relative_to()` check) before reading; reject paths that escape the config's own directory tree.

**`eval()` on OpenFOAM dictionary file contents:**
- Risk: `File.get()` (`src/obr/OpenFOAM/case.py:50-58`) calls `eval(super().get(name))` to parse values out of OpenFOAM dictionary files (`controlDict`, `fvSolution`, `transportProperties`, etc.). These files can originate from a cloned git repository (`GitRepo` case origin, `src/obr/core/caseOrigins.py:75-152`) or an arbitrary path on disk (`CaseOnDisk`). A malicious/compromised upstream case repository can embed a value that executes code when OBR next reads that key (e.g. via `job.doc`-triggered re-reads during `controlDict`, `blockMesh`, `checkMesh`, etc.).
- Files: `src/obr/OpenFOAM/case.py:50-58`
- Current mitigation: A bare `except:` silently falls back to the raw string if `eval()` raises, but this does not prevent successful malicious payloads from executing.
- Recommendations: Replace `eval()` with a proper OpenFOAM-dictionary value parser (numeric/bool/string coercion via explicit rules) instead of executing file contents as Python.

**`eval()` in CLI-query parsing (currently dead code, but latent risk):**
- Risk: `input_to_query()` (`src/obr/core/queries.py:106-114`) builds a `Query` object via `eval(inp)` on a user-supplied string. It is exported and unit-tested (`tests/test_queries.py`) but is **not** called anywhere in the shipped CLI — `obr query`/`obr run --filter` go through the safe `build_filter_query()` path instead (`src/obr/core/queries.py:301-322`).
- Files: `src/obr/core/queries.py:106-120`
- Current mitigation: Not reachable from the current CLI surface.
- Recommendations: Remove `eval()` from `input_to_query()` (use `ast.literal_eval` or explicit key/value parsing) before this function is ever wired up to user input again, and consider deleting it if truly unused.

**Supply-chain risk: `Owls` dependency pinned to a mutable git branch:**
- Risk: `Owls @ git+https://github.com/greole/Owls.git@Owls2.0` (`pyproject.toml:26`) pins to a branch name, not a commit hash or tag. A force-push or account compromise on the upstream `Owls` repository silently changes the code installed by every future `pip install .` of OBR, with no way to detect the change from OBR's own repo history.
- Files: `pyproject.toml:26`
- Current mitigation: None.
- Recommendations: Pin to a specific commit SHA (`@<commit>`) or, ideally, a released package on PyPI.

## Performance Bottlenecks

**Per-file subprocess calls when linking parent case files into child jobs:**
- Problem: `_link_path()` shells out to `mkdir -p` / `ln -s` via `subprocess.check_output` **once per file and once per directory** when materializing a child job's case tree from its parent (used on every job whose statepoint has a `parent_id`, i.e. every non-base-case job).
- Files: `src/obr/signac_wrapper/operations.py:154-231`, called from `initialize_if_required()` at line 262
- Cause: Each `check_output([...])` call forks and execs a new OS process; OpenFOAM case trees (`system`, `constant`, mesh/time folders) commonly contain hundreds to thousands of files, so job initialization for large parameter studies incurs proportional process-spawn overhead instead of using `os.symlink()`/`Path.mkdir()` directly.
- Improvement path: Replace the `mkdir`/`ln -s` subprocess calls with `os.makedirs(..., exist_ok=True)` and `os.symlink(...)`, keeping `shutil.copytree` for the `copy_instead_link=True` path (already stdlib-based).

**Deep-copy-heavy query evaluation:**
- Problem: `query_flat_jobs()` performs a `deepcopy(q)` for every `(job, query, key)` combination while scanning merged job documents, plus an additional `deepcopy(res_tmp)` per matching job.
- Files: `src/obr/core/queries.py:164-224`, specifically lines 187 and 223
- Cause: O(jobs × queries × keys-per-job) deep copies of `Query` dataclass instances; for large parameter sweeps (OBR's primary use case — HPC benchmark campaigns with potentially thousands of jobs) this can dominate `obr query`/`obr status`/`obr postProcess` runtime.
- Improvement path: Avoid `deepcopy` where the `Query` object isn't actually mutated across iterations, or restructure `execute()` to be side-effect-free so copies aren't needed.

**Subprocess-based folder copies for non-ESI OpenFOAM delink handling:**
- Problem: `TemporaryFolder`/`DelinkFolder`/`link_folder_to_copy()` copy folder trees via `subprocess.check_output(["cp", "-r", ...])` and per-file `check_output(["cp", ...])` rather than `shutil.copytree`/`shutil.copy2`.
- Files: `src/obr/core/core.py:353-425`
- Cause: These helpers run on every `decomposePar` call for non-ESI OpenFOAM builds (`src/obr/OpenFOAM/case.py:336-341`) and every `refineMesh` call — process-spawn overhead is paid per file, compounding with case size.
- Improvement path: Replace with native `shutil` calls; reserve `subprocess` for actual OpenFOAM binaries.

**Repeated disk I/O for parent-readiness checks:**
- Problem: `parent_job_is_ready()` re-opens and JSON-parses the parent job's `signac_job_document.json` from disk on every call.
- Files: `src/obr/signac_wrapper/operations.py:144-151`, called from `basic_eligible()` (line 122) which itself runs as an eligibility pre-check for nearly every operation.
- Cause: No caching of the parent's readiness state within a single `obr run`/`obr submit` invocation; for deep variation trees with many siblings sharing a parent, the same parent document is re-read redundantly.
- Improvement path: Cache parent-state lookups per `obr run` invocation (e.g. keyed by `parent_id`), invalidating only when a parent's state actually changes during that run.

## Fragile Areas

**Pre/post-build hook dispatch (`operations.py`):**
- Files: `src/obr/signac_wrapper/operations.py:290-359`
- Why fragile: `execute_operation()` catches all exceptions from sub-operations and always returns `True` (see Known Bugs — the `==`/`=` typo). Any new operation type wired into `pre_build`/`post_build` inherits this silent-failure behavior automatically.
- Safe modification: When fixing the `==`/`=` bug, add an explicit test asserting that a raising sub-operation causes `job.doc["state"]["global"] == "failure"` to be true afterward, and that `basic_eligible()`/`operation_complete()` correctly treat such jobs as not-ready.
- Test coverage: None (`tests/test_operations.py` only covers `_link_path`).

**`__del__`-based cleanup (`TemporaryFolder`, `DelinkFolder`):**
- Files: `src/obr/core/core.py:394-425`
- Why fragile: Both classes rely on `__del__` to call `shutil.rmtree`/`tear_down()`. `__del__` timing is governed by CPython's garbage collector (not deterministic on reference cycles), exceptions raised inside `__del__` are printed to stderr and swallowed rather than propagated, and cleanup does not run at all on interpreter crash/`os._exit`. Failed cleanup silently leaves `.bck` folders and partially-restored symlink trees behind.
- Safe modification: Convert both classes to context managers (`__enter__`/`__exit__`) and require explicit `with` usage at every call site (`OpenFOAMCase.decomposePar`, `BlockMesh.refineMesh`) instead of depending on garbage collection.
- Test coverage: Indirect only, via `tests/test_OpenFOAMCase.py`'s `decomposePar` tests; no test verifies cleanup actually occurs or handles cleanup failure.

**`merge_job_documents()` cache merging:**
- Files: `src/obr/core/core.py:174-197`
- Why fragile: When multiple sharded `signac_job_document_*.json` files exist for a job, the function keeps only the *first* non-empty `cache` value it encounters (`if not cache: cache = job_doc["cache"]`) and silently discards any differing caches from the remaining shards (`# TODO handle inconsistent cache`).
- Safe modification: Explicitly merge/reconcile cache dictionaries (e.g. last-write-wins by timestamp) instead of picking the first one found; log a warning when shards disagree.
- Test coverage: Not found in `tests/`.

**Global CLI-module state coupling `cli.py` and `operations.py`:**
- Files: `src/obr/cli.py:456-457` (sets `obr.cli.filtered_jobs`), `src/obr/signac_wrapper/operations.py:983-998` (`apply()` reads `obr.cli.filtered_jobs`)
- Why fragile: The `apply` aggregator operation bypasses signac-flow's normal job-filtering mechanism by reading a module-level global set by the CLI layer moments earlier. This only works because `obr apply` runs the `apply` operation synchronously in the same process right after `cli_cmd_setup()`; it would break under any concurrent or out-of-process execution model.
- Safe modification: Pass the filtered job list through `project.run(...)`'s own arguments/aggregator mechanism instead of a cross-module global.
- Test coverage: Not found in `tests/`.

## Scaling Limits

**Job-count-proportional overhead in initialization and querying:**
- Current capacity: Not benchmarked/documented anywhere in the repo; the per-file subprocess linking (`_link_path`) and deepcopy-heavy querying (`query_flat_jobs`) documented under Performance Bottlenecks both scale with job count × case file count with no batching or caching.
- Limit: For large HPC benchmark campaigns (OBR's stated purpose — parameter sweeps across solver/mesh/decomposition configurations), `obr init --generate`, `obr query`, and `obr status` runtimes are expected to grow significantly as workspace size increases; no upper bound or guidance is documented for operators.
- Scaling path: Address the per-file subprocess and deepcopy hotspots above; consider adding a documented "expected job count" guideline once benchmarked.

**Bundle-size computation can still exceed `max_queue_size`:**
- Current capacity: `submit_impl()` computes `bundle_size = int(len(eligible_jobs) / max_queue_size)` (floor division) once `len(eligible_jobs) > max_queue_size` (`src/obr/signac_wrapper/submit.py:100-108`).
- Limit: Floor division can under-estimate the required bundle size — e.g. 201 eligible jobs with `max_queue_size=100` yields `bundle_size=2`, producing `ceil(201/2)=101` submissions, one more than the requested `max_queue_size`. The intended invariant ("never submit more than `max_queue_size` bundles") is not strictly guaranteed.
- Scaling path: Use ceiling division for the number of *bundles* (`math.ceil(len(eligible_jobs) / max_queue_size)`) and derive `bundle_size` from that, or document that `max_queue_size` is a soft/approximate limit.

## Dependencies at Risk

**`Owls` (git branch dependency):**
- Risk: Installed from `git+https://github.com/greole/Owls.git@Owls2.0` — a branch reference, not a pinned commit or released version.
- Impact: Non-reproducible builds; a change to the upstream branch (intentional or malicious) silently changes OBR's parsing/log-processing behavior for every fresh install without any corresponding change in OBR's own git history.
- Migration plan: Pin to a specific commit SHA, or work with upstream to publish tagged releases to PyPI.

**Exact-pinned core dependencies:**
- Risk: `signac==2.1.0`, `signac-flow==0.26.1`, `GitPython==3.1.31`, `jsonschema==4.19.1` (`pyproject.toml:20-27`) are pinned to exact versions rather than compatible ranges.
- Impact: Blocks picking up upstream security/bug fixes automatically; increases the chance of dependency-resolution conflicts when OBR is installed alongside other tools that require different versions of these shared libraries (signac/signac-flow in particular are commonly shared across scientific-computing tooling).
- Migration plan: Relax to compatible-release specifiers (e.g. `signac~=2.1`) once compatibility with newer patch/minor releases is verified in CI.

## Missing Critical Features

**`obr reset --case` is explicitly partial:**
- Problem: The command's own runtime warning states: "`obr reset --case`, is not fully implemented and will only remove log solver logs." (`src/obr/cli.py:653-656`). Other case artifacts (decomposed processor folders, generated meshes, modified dictionaries) are not reset.
- Blocks: Operators cannot fully reset a case to its pre-run state via the CLI; must manually clean up additional artifacts.

**`obr reset --view <path>` is a no-op:**
- Problem: The `--view` flag is accepted by the CLI but always logs `"Resetting by view path is not yet supported"` and performs no action (`src/obr/cli.py:668-669`).
- Blocks: There is no supported way to reset a case by its human-readable view path; users must know the underlying job id instead.

**`archive` does not filter out failed jobs:**
- Problem: The intended "skip archival of failed jobs" logic is present only as commented-out code (`src/obr/cli.py:846-853`, `# TODO: implement archival only of non-failed jobs`), referencing `OpenFOAMCase.was_successful()` which exists (`src/obr/OpenFOAM/case.py:565-595`) but is never called from `archive`.
- Blocks: `obr archive` currently commits logs/artifacts from failed runs into the target data repository indiscriminately, requiring manual curation after the fact.

## Test Coverage Gaps

**`cli.py` has no dedicated test file:**
- What's not tested: None of the `run`, `submit`, `init`, `status`, `query`, `apply`, `postProcess`, `reset`, `archive` commands (`src/obr/cli.py`, 921 lines) have automated test coverage — there is no `tests/test_cli.py`.
- Files: `src/obr/cli.py`
- Risk: This is precisely why the `-p` option collision (`submit`) and duplicate `-S`/`--args` decorators (`status`, `run`) went unnoticed until manual code review.
- Priority: High

**`signac_wrapper/operations.py` operation functions are almost entirely untested:**
- What's not tested: Of the ~25 operation functions defined in this 998-line file, only `_link_path` is covered (`tests/test_operations.py`, 25 lines). `controlDict`, `blockMesh`, `replaceMesh` (contains the confirmed `NameError` bug), `decomposePar`, `refineMesh`, `checkMesh`, `runParallelPre/Solver/Post`, `archive`, `apply`, and the pre/post-build hook dispatch (`execute_operation`, containing the confirmed silent-failure bug) are untested.
- Files: `src/obr/signac_wrapper/operations.py`
- Risk: Both confirmed bugs in this file (the `replaceMesh` `NameError` and the `execute_operation` `==`/`=` typo) would have been caught by even minimal unit tests of these functions.
- Priority: High

**`MultiCase` case origin has zero coverage:**
- What's not tested: `src/obr/core/caseOrigins.py:14-28` (`MultiCase.init()`, contains the confirmed `os` `NameError` bug).
- Files: `src/obr/core/caseOrigins.py`
- Risk: The bug is completely unguarded; any config using `type: MultiCase` on a fresh workspace will crash.
- Priority: High

**`GitRepo` case origin (git clone/cache/checkout logic) has no unit tests:**
- What's not tested: `src/obr/core/caseOrigins.py:75-152` — cache-folder reuse, commit/branch checkout, and the subprocess-based clone/copy fallback paths.
- Files: `src/obr/core/caseOrigins.py`
- Risk: Regressions in case-fetching logic (a core, frequently-exercised code path for real benchmark campaigns) would only surface via the single-scenario integration test in CI.
- Priority: Medium

**`eval()`-based YAML templating engine is untested:**
- What's not tested: `eval_generator_expressions()` (`src/obr/core/parse_yaml.py:88-101`), the function responsible for evaluating `${{ }}` expressions as Python.
- Files: `src/obr/core/parse_yaml.py`
- Risk: Given the security implications documented above, the complete absence of tests (positive or negative/malicious-input) means there is no regression protection if this function's behavior changes, and no documented expectation of what expressions are "safe" to support.
- Priority: High

**`obr postProcess` is untested:**
- What's not tested: `src/obr/cli.py:508-616` — the largest single CLI command body (log-matching, per-column aggregation modes `average`/`diff_mean`/`diff_mean_skipN`/`diff_mean_useN`, JSON export).
- Files: `src/obr/cli.py`
- Risk: The aggregation-mode branch logic (regex-matched `diff_mean_(skip|use)(\d+)` mode) is intricate and entirely unverified by tests; a bare `except: pass` around per-column aggregation (`cli.py:606-608`) would silently hide any regression here.
- Priority: Medium

**Integration tests cover only a single happy-path scenario:**
- What's not tested: `.github/workflows/integration_test.yaml` runs `obr init` → `obr run -o generate` → `obr run -o runSerialSolver` → `obr status` → `obr query --validate_against` against a single `tests/cavity.yaml` config. No integration coverage exists for `obr submit`, `obr archive`, multi-case/`generator` variations, parallel solver runs, or any failure/error path.
- Files: `.github/workflows/integration_test.yaml`, `tests/cavity.yaml`
- Risk: Regressions in submission bundling, archival, or generator-based parameter sweeps (core advertised features) would not be caught by CI.
- Priority: Medium

---

*Concerns audit: 2026-07-13*
