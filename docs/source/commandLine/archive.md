## OBR archive

### Usage
```zsh
Usage: obr archive [OPTIONS]

Options:
  --filter TEXT      Pass a <key>=<value> value pair per occurrence of
                     --filter. For instance, obr archive --filter
                     solver=pisoFoam --filter preconditioner=IC
  -f, --folder TEXT  Path to OpenFOAMProject.  [required]
  -r, --repo TEXT    Path to data repository. If this is a valid Github
                     repository, files will be automatically added.
                     [required]
  -s, --skip-logs    If set, .log files will not be archived. This does not
                     affect .log files passed via the --file option.
  -a, --file TEXT    Path(s) to non-logfile(s) to be also added to the
                     repository.
  --campaign TEXT    Specify the campaign  [required]
  --tag TEXT         Specify prefix of branch name. Will checkout new branch
                     with timestamp <tag>-<timestamp>.
  --amend            Add to existing branch instead of creating new one.
  --push             Push changes directly to origin and switch to previous
                     branch.
  --dry-run          If set, will log which files WOULD be copied and
                     committed, without actually doing it.
  --help             Show this message and exit.
```

Make sure to have openfoam sourced. 