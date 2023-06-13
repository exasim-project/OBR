## OBR archive

### Usage
```zsh
Usage: obr archive [OPTIONS]

Options:
  --filter TEXT
  -f, --folder TEXT  Path to OpenFOAMProject.  [required]
  -r, --repo TEXT    Path to data repository. If this is a valid Github
                     repository, files will be automatically added.
                     [required]
  -s, --skip-logs    If set, .log files will not be archived. This does not
                     affect .log files passed via the --file option.
  -a, --file TEXT    Path(s) to non-logfile(s) to be also added to the
                     repository.
  --help             Show this message and exit.
```

Make sure to have openfoam sourced. 