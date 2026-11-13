## OBR submit

### Usage
```zsh
Usage: obr submit [OPTIONS]

Options:
  -f, --folder TEXT
  -p, --pretend          Set flag to only print submission script
  -o, --operations TEXT  Specify the operation(s) to run. Pass multiple
                         operations after -o, separated by commata (NO space),
                         e.g. obr run -o shell,apply. Run with --help to list
                         available operations.  [required]
  -l, --list-operations  Prints all available operations and returns.
  --filter TEXT          Pass a <key><predicate><value> value pair per
                         occurrence of --filter. Predicates include ==, !=,
                         <=, <, >=, >. For instance, obr submit --filter
                         "solver==pisoFoam"
  --bundling_key TEXT
  -p, --partition TEXT
  --account TEXT
  --pretend
  --scheduler_args TEXT  Currently required to be in --key1 value --key2
                         value2 form
  --help                 Show this message and exit.
```

### Extra solver arguments

Arguments that the solver itself needs, e.g. the GPU memory pool of a GPU code, are given by a
`solver_args` entry (string or list) on the case or a variation `values` entry. Like `pre_cmds` it
is inherited from parent jobs:

```yaml
values:
  - code: GPU_CODE
    application: pimpleFoam
    solver_args: "-pool fixedSizeMemoryPool -poolSize 200"
```

`runParallelSolver` and `runSerialSolver` place them after the solver name:
`mpirun -np N <solver> <solver_args> -parallel -case ...`. A custom `OBR_RUN_CMD` or
`OBR_SERIAL_RUN_CMD` template must contain `{solverargs}` to pass them on.

### Running custom commands before/after the solver

Arbitrary shell lines can be executed before and after the solver within the
same submission by adding `pre_cmds` and `post_cmds` lists to the case or a
variation `values` entry in the workflow yaml:

```yaml
pre_cmds:
  - "of_watchdog.sh --loop &"
  - "watchdog_pid=${!}"
post_cmds:
  - "kill $watchdog_pid || true"
```

On `obr submit -o execute ...` the generated batch script body contains a
single line `obr run -o execute -j <jobid>`. When that line executes on the
compute node, the `runParallelSolver` operation composes one shell command
with the pre and post lines inlined verbatim around the solver call:

```sh
export OBR_JOB=<path> OBR_CASE=<path>/case OBR_NP=N OBR_TPN=M
of_watchdog.sh --loop &
watchdog_pid=${!}
mpirun -np N <solver> -parallel -case <path>/case > <path>/case/<solver>_<timestamp>.log 2>&1|| true && echo $? > <path>/case/solverExitCode.log
kill $watchdog_pid || true
```

All lines run in a single shell, so shell variables set by a pre command (such
as `watchdog_pid`) remain visible to the post commands.

The first line exports the job directory `$OBR_JOB`, its case `$OBR_CASE`, the number of MPI
ranks `$OBR_NP` (numberOfSubdomains) and the ranks per node `$OBR_TPN`, so the verbatim
commands can address the case. The commands run in the directory `obr run` is called from, not
in the case.

### Preparing the decomposed mesh in the solver job: `prepare`

Steps that change the decomposed mesh in place before the solve, e.g. `renumberMesh -overwrite` or a
solver specific preparation, are listed under `prepare` (on the case or a variation `values` entry,
inherited). They run in the solver allocation after `pre_cmds` (so with the environment loaded there)
and before the solver:

```yaml
values:
  - code: CODE_A
    pre_cmds: ["source <env>"]
    prepare:
      - parallel: renumberMesh -overwrite
  - code: CODE_B
    pre_cmds: ["source <env>"]
    prepare:
      - run: cfdPrepare --launcher "srun -n"
```

- `parallel: <app> <args>` is launched like the solver: `mpirun -np N <app> <args> -parallel -case <case>`
  (the launcher is the part of `OBR_RUN_CMD` before `{solver}` if that is set), serial runs get
  `<app> <args> -case <case>`.
- `run: <command>` runs the command as written.

Every step runs in the job's case directory, once per job (marker `case/.obr/prepare_<i>_<app>.done`,
so a resubmission skips it), with its output in `case/log.<app>`. A failing step stops the job before
the solver. The generated lines look like

```sh
mkdir -p <case>/.obr
[ -f <case>/.obr/prepare_1_renumberMesh.done ] || { ( cd <case> && mpirun -np N renumberMesh -overwrite -parallel -case <case> ) > <case>/log.renumberMesh 2>&1 && touch <case>/.obr/prepare_1_renumberMesh.done || { echo "prepare step 1 (renumberMesh) failed, see <case>/log.renumberMesh"; exit 1; }; }
```

By default the final jobs link `processor*/constant` to the decomposition they come from, so an
in-place change would write into the shared parent case. `copy_proc_constant: true` (on the case or a
variation, inherited) gives every final job its own copy of `processor*/constant`; intermediate levels
keep the links.

The OBR job keys `pre_cmds`, `post_cmds`, `solver_args`, `prepare` and `copy_proc_constant` are not
written into the controlDict.

Caveats:

1. The lines are inserted exactly as written — no log redirection and no
   `|| true` are added. The exit status of the composite command is that of
   the *last* line, and a non-zero status marks the job as errored. Append
   `|| true` to commands that may legitimately fail (e.g. `kill`).
2. Commands run under `/bin/sh` (via `subprocess` with `shell=True`), not
   necessarily bash — avoid bashisms.
3. With `OBR_SKIP_COMPLETE` set, `pre_cmds`/`post_cmds` are skipped together
   with the solver of a completed job.
4. Do not combine `-o runParallelPre,runParallelSolver` — the `execute` group
   (i.e. `runParallelSolver`) already inlines the pre and post commands. The
   standalone `runParallelPre`/`runParallelPost` operations only exist to
   (re)run those commands independently.
5. A literal `${{ ... }}` inside a command is evaluated by the yaml
   preprocessor at `obr init` time; single-brace shell constructs like
   `${!}` or `$var` pass through untouched.
