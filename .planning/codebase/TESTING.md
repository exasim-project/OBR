# Testing Patterns

**Analysis Date:** 2026-07-13

## Test Framework

**Runner:**
- `pytest` (declared under `[project.optional-dependencies] test` in `pyproject.toml` alongside `coverage` and `gitpython`).
- No `pytest.ini` / `conftest.py` / `[tool.pytest.ini_options]` section exists anywhere in the repo — pytest runs with defaults (default test discovery: `test_*.py` files, `test_*` functions, in `tests/`).
- No custom pytest markers are registered, but CI invokes `pytest -m "not integtest"` (`.github/workflows/unit_test.yaml:29`) implying an `integtest` marker convention is expected for slow/integration-style tests, even though no test in `tests/` currently declares `@pytest.mark.integtest`. If you add a test that requires network access, a real OpenFOAM install, or is otherwise slow/environment-dependent, mark it `@pytest.mark.integtest` so the unit-test CI job can exclude it (note: since the marker isn't registered in a config, pytest will emit an "unknown marker" warning — register it in a `pyproject.toml` `[tool.pytest.ini_options]` `markers` list if you introduce it, to keep CI clean).

**Assertion Library:**
- Plain `assert` statements (pytest's built-in assertion rewriting). No `unittest.TestCase`-style `self.assertEqual` anywhere.

**Run Commands:**
```bash
# Run all unit tests (mirrors CI unit_test.yaml)
coverage run -m pytest -m "not integtest"
coverage report

# Run a single test file
pytest tests/test_core.py

# Run a single test
pytest tests/test_queries.py::test_execute_query

# Run everything, including tests that require FOAM_TUTORIALS / real OpenFOAM
pytest tests/
```

## Test File Organization

**Location:**
- All tests live in a single top-level `tests/` directory (not co-located with source). No `tests/unit/` vs `tests/integration/` split — separation between "unit" and "integration" tests is intended to be done via the (currently unused) `integtest` pytest marker, not by directory.
- Fixture data/logs used by tests live in `tests/logs/` (sample OpenFOAM solver log files: `icoFoamFailure.log`, `icoFoamIncomplete.log`, `icoFoamStartupFailure.log`, `icoFoamSuccess.log`) and `tests/cavity.yaml` / `tests/cavity_results.json` (a full OBR config + its expected query-validation output, used by the integration test workflow, not the pytest unit suite).

**Naming:**
- Test files: `test_<module_or_feature>.py`, one file roughly per source module: `test_core.py` <-> `core/core.py`, `test_queries.py` <-> `core/queries.py`, `test_caseOrigins.py` <-> `core/caseOrigins.py`, `test_yaml_parser.py` <-> `core/parse_yaml.py`, `test_OpenFOAMCase.py` <-> `OpenFOAM/case.py`, `test_create_tree.py` <-> `create_tree.py`, `test_submit.py` <-> `signac_wrapper/submit.py`, `test_operations.py` <-> `signac_wrapper/operations.py`, `test_md5sum.py` is a focused, cross-cutting test (md5sum caching behavior spanning `create_tree` + `OpenFOAMCase`).
- Test functions: `def test_<behavior_under_test>():`, e.g. `test_ansa_owner`, `test_TemporaryFolder` (PascalCase suffix mirrors the class name it tests — acceptable exception to snake_case for clarity), `test_expand_generator_block`.

**Structure:**
```
tests/
├── cavity.yaml                 # full OBR config fixture (integration test)
├── cavity_results.json         # expected `obr query` output (integration test validation)
├── logs/                       # sample solver .log fixtures
│   ├── icoFoamFailure.log
│   ├── icoFoamIncomplete.log
│   ├── icoFoamStartupFailure.log
│   └── icoFoamSuccess.log
├── test_caseOrigins.py
├── test_core.py
├── test_create_tree.py
├── test_md5sum.py
├── test_OpenFOAMCase.py
├── test_operations.py
├── test_queries.py
├── test_submit.py
└── test_yaml_parser.py
```

## Test Structure

**Suite Organization:**
Tests are flat functions (no test classes), each self-contained, often with a `pytest.fixture` supplying setup data. A common pattern builds a real `OpenFOAMProject` against a `tmpdir`, drives it through `create_tree()` + `project.run(names=[...])`, then asserts on the resulting filesystem/job state — these are largely functional/integration-style tests running against the real `signac`/`signac-flow` stack rather than isolated unit tests with mocks:

```python
# tests/test_queries.py
@pytest.fixture()
def get_project(tmpdir):
    config = { "case": { "type": "GitRepo", "solver": "pisoFoam", ... } }
    os.chdir(tmpdir)
    project = OpenFOAMProject.init_project(path=tmpdir)
    create_tree(project, config, {"folder": tmpdir}, skip_foam_src_check=True)
    project.run(names=["fetchCase"])
    return project


def test_filters(get_project: OpenFOAMProject):
    filters = ["maxIter!=0"]
    jobs = get_project.filter_jobs(filters)
    assert len(jobs) > 0
```

**Patterns:**
- Setup: `pytest`'s built-in `tmpdir` (`py.path.local`) or `tmp_path` (`pathlib.Path`) fixture provides an isolated working directory per test; both spellings are used interchangeably across files (`tmpdir` is more common, `tmp_path` appears in `tests/test_caseOrigins.py`).
- Fixtures are defined locally within each test file (no shared `conftest.py`); duplication of the same fixture (e.g. `emit_test_config`) across `tests/test_create_tree.py`, `tests/test_md5sum.py`, and similar config dicts inline in `tests/test_queries.py`/`tests/test_submit.py` is accepted/expected in this codebase rather than centralized.
- Teardown: relies on pytest's automatic `tmpdir` cleanup; classes with explicit resource management (`TemporaryFolder`, `DelinkFolder`) test their own `__del__`/`tear_down()` behavior directly rather than needing teardown fixtures (`tests/test_core.py:91-154`).
- Assertion style: multiple plain `assert` statements per test body, often with a short inline `#` comment above each assertion explaining what's being checked (`tests/test_core.py:97-100`, `tests/test_operations.py`).
- `os.chdir(tmpdir)` is used directly inside fixtures/tests to change the working directory for code that assumes CWD == workspace root (`tests/test_queries.py:135`) — be aware this mutates global process state for the duration of the test; no cleanup back to the original directory is performed, matching the project's ad hoc process-global patterns.

## Mocking

**Framework:** No mocking library (`unittest.mock`, `pytest-mock`, `MagicMock`) is used anywhere in `tests/`. The project favors lightweight hand-rolled stub classes and real integration setups over mocks/patches.

**Patterns:**
```python
# tests/test_create_tree.py — minimal hand-written stand-ins instead of MagicMock
class MockJob:
    id = "0"
    sp = {}
    doc = {}

    def init(self):
        pass


class MockProject:
    def open_job(self, statepoint):
        return MockJob()
```
```python
# tests/test_OpenFOAMCase.py — a bare class satisfying the minimal `job.doc` contract
class mock_job:
    doc = {"state": {}}

of_case = OpenFOAMCase(set_up_of_case, mock_job())
```

**What to Mock:**
- Only the smallest possible surface needed to satisfy an object's constructor contract (e.g. `job.doc`, `job.sp`, `job.id`) is stubbed with a plain class — not full behavioral mocks.
- `flow.environment.TestEnvironment` (from `signac-flow`) is used as the library-provided test double for `project._environment` when testing submission scripts, instead of a custom mock (`tests/test_submit.py:47-53`).

**What NOT to Mock:**
- Real `OpenFOAMProject` (signac `FlowProject`) instances, real `create_tree()` workspace generation, and real filesystem operations under `tmpdir` are used directly rather than mocked — most tests are effectively integration tests against the signac library and the local filesystem.
- Network-dependent operations (`GitRepo` cloning from `https://github.com/exasim-project/hpc.git`, OpenFOAM tutorial cloning from `https://github.com/OpenFOAM/OpenFOAM-10.git`) are NOT mocked; tests that need them either genuinely hit the network (`tests/test_queries.py`, `tests/test_create_tree.py`, `tests/test_submit.py`, `tests/test_md5sum.py`) or are skipped via `@pytest.mark.skipif` when a required environment variable is absent (see below). This means part of the "unit" suite actually requires network access to fully pass.

## Fixtures and Factories

**Test Data:**
```python
# tests/test_create_tree.py — realistic nested OBR YAML-equivalent config dict
@pytest.fixture
def emit_test_config():
    return {
        "case": {
            "type": "GitRepo",
            "solver": "pisoFoam",
            "url": "https://github.com/exasim-project/hpc.git",
            "folder": "Lid_driven_cavity-3d/S",
            "commit": "f9594d16aa6993bb3690ec47b2ca624b37ea40cd",
            "cache_folder": "None/S",
            "uses": [{"fvSolution": "fvSolution.fixedNORM"}],
            "post_build": [ ... ],
        }
    }
```
```python
# tests/test_core.py — fixture that writes a real fixture file to tmpdir
@pytest.fixture
def create_ansa_owner(tmpdir):
    fn = "owner"
    owner_content = """... FoamFile header text ..."""
    with open(Path(tmpdir) / fn, "a") as fh:
        fh.write(owner_content)
```

**Location:**
- Inline `@pytest.fixture` functions at the top of each test file — no shared `tests/conftest.py` and no separate `tests/fixtures/` Python package.
- Binary/text fixture *files* (as opposed to fixture functions) live in `tests/logs/` and are referenced by path relative to `Path(__file__).parent` (`tests/test_OpenFOAMCase.py:122-124`).
- `tests/cavity.yaml` / `tests/cavity_results.json` serve as fixture data for the integration workflow (`.github/workflows/integration_test.yaml`) rather than the pytest suite, but `tests/test_submit.py:55` also loads `tests/cavity.yaml` via `read_yaml()` directly in a unit test.

**Environment-gated tests:**
```python
# tests/test_caseOrigins.py
@pytest.mark.skipif(
    not os.environ.get("FOAM_TUTORIALS"), reason="Cannot determine $FOAM_TUTORIALS path"
)
def test_OpenFOAMTutorialCase(tmp_path):
    ...
```
Use `@pytest.mark.skipif(not os.environ.get("VAR"), reason="...")` for tests that require a real OpenFOAM installation to be sourced (`$FOAM_TUTORIALS`). `tests/test_create_tree.py`'s `set_up_of_case` fixture instead falls back to a live `git clone` of OpenFOAM-10 tutorials when `FOAM_TUTORIALS` isn't set, rather than skipping — follow whichever pattern matches your test's tolerance for network calls.

## Coverage

**Requirements:** No enforced minimum/threshold. CI (`unit_test.yaml`) runs `coverage run -m pytest -m "not integtest"` then `coverage report`, extracts the total percentage, and publishes it to a dynamic Shields.io badge gist (`schneegans/dynamic-badges-action`) — informational only, does not fail the build on low coverage.

**View Coverage:**
```bash
coverage run -m pytest -m "not integtest"
coverage report
coverage html   # optional, for a browsable report (no CI step does this, but the `coverage` package supports it)
```

## Test Types

**Unit Tests:**
- Narrowly-scoped pure-function tests exist for parsing/utility logic with no I/O or minimal `tmpdir` I/O: `test_input_to_query`, `test_execute_query`, `test_flatten_jobs` (`tests/test_queries.py`), `test_extract_from_operation`, `test_expand_generator_block` (`tests/test_create_tree.py`), `test_includes` (`tests/test_yaml_parser.py`).

**Integration Tests:**
- Most test files are effectively integration tests: they spin up a real signac project in a `tmpdir`, run real signac-flow operations (`project.run(names=[...])`), and assert on the resulting workspace directory tree, job documents, and generated files — e.g. `test_create_tree`, `test_call_generate_tree`, `test_cache_folder`, `test_group_jobs` in `tests/test_create_tree.py`; `test_md5sum_calculation` in `tests/test_md5sum.py`; `test_submit` in `tests/test_submit.py`.
- A separate, heavier integration suite is driven entirely through the CLI binary inside a container with a real OpenFOAM installation, defined in `.github/workflows/integration_test.yaml` (not pytest-based): `obr init --config tests/cavity.yaml` -> `obr run -o generate` -> `obr run -o runSerialSolver` -> `obr status` -> `obr query -q global --filter global==completed --validate_against tests/cavity_results.json`. This is the closest thing to an end-to-end test in the repo.

**E2E Tests:**
- No Selenium/Playwright-style E2E framework (not applicable — OBR is a CLI tool). The CLI-driven integration workflow described above is the de facto E2E test.

## Common Patterns

**Async Testing:**
- Not applicable. The codebase is entirely synchronous (subprocess-based execution via `subprocess.check_output`); no `asyncio`/`async def` anywhere in `src/obr` or `tests/`.

**Error Testing:**
```python
# tests/test_submit.py — asserting a specific exception type is raised
with pytest.raises(FileNotFoundError):
    submit_impl(
        project,
        [j for j in project],
        ["generate"],
        template=tmpdir / "does_not_exists.sh",
        account=account,
        partition=partition,
        time="60",
        pretend=True,
        bundling_key=None,
        max_queue_size=10,
        scheduler_args="",
    )
```
```python
# tests/test_OpenFOAMCase.py — asserting on state written into job.doc after a failure,
# rather than on a raised exception (this codebase logs+records failures instead of raising)
assert of_case.process_latest_time_stats() == False
assert of_case.finished == False
assert of_case.job.doc["state"]["global"] == "failure"
```
- Prefer asserting on the resulting `job.doc["state"]` / `job.doc["cache"]` side effects over asserting exceptions, since most of the production error-handling strategy (see CONVENTIONS.md) swallows exceptions into logged failure states rather than propagating them.
- CLI output can be captured and asserted on via `contextlib.redirect_stdout` into a real file, then re-read and grep'd with `assert "text" in log_content` (`tests/test_submit.py:98-123`).

---

*Testing analysis: 2026-07-13*
