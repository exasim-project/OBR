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
of_watchdog.sh --loop &
watchdog_pid=${!}
mpirun -np N <solver> -parallel -case <path>/case > <path>/case/<solver>_<timestamp>.log 2>&1|| true && echo $? > <path>/case/solverExitCode.log
kill $watchdog_pid || true
```

All lines run in a single shell, so shell variables set by a pre command (such
as `watchdog_pid`) remain visible to the post commands.

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
