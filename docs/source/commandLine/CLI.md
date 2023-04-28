# Commandline Reference


<!-- obr init -->
## obr init

### Usage
Usage: obr init [OPTIONS]

Options:
  -f, --folder TEXT      Where to create the worspace and view
  -e, --execute BOOLEAN
  -c, --config TEXT      Path to configuration file.
  -t, --tasks INTEGER    Number of tasks to run concurrently.
  -u, --url TEXT         Url to a configuration yaml
  --verbose INTEGER      set verbosity
  --help                 Show this message and exit.


<!-- obr query -->
## obr query

### Usage
```zsh
Usage: obr query [OPTIONS]

Options:
  -f, --folder TEXT
  -d, --detailed
  -a, --all
  -q, --query TEXT
  --help             Show this message and exit.
```

### Understanding obr query
`obr query` recursively traverses the current directory, or the directory specified by the `--folder` argument, for `signac_statepoint.json` files.

### Common Problems

1. `obr query -q [Query]` does not return anything.
     - As of now, `obr query` ignores jobs that do not include the `obr` key in their corresponding `signac_job_document.json` file.
     - The `obr` key is only added to the `signac_job_document.json` file after running this job at least once.
     - For instance, after initializing an obr workspace via [`obr init`](init.md) and running a valid query, nothing is returned. After successfully running [`obr run`](run.md), the aforetried query should return the expected result.

<!-- obr run -->
## obr run

### Usage
Usage: obr run [OPTIONS]

  Run specified operations

Options:
  -f, --folder TEXT
  -o, --operations TEXT
  -j, --job TEXT
  --args TEXT
  -t, --tasks INTEGER
  -a, --aggregate
  --query TEXT
  --args TEXT
  --help                 Show this message and exit.


  <!-- obr status -->
## obr status

### Usage
Usage: obr status [OPTIONS]

Options:
  -f, --folder TEXT
  -d, --detailed
  --help             Show this message and exit.


<!-- obr submit -->
## obr submit

### Usage
Usage: obr submit [OPTIONS]

Options:
  -f, --folder TEXT
  -p, --pretend          Set flag to only print submission script
  -o, --operation TEXT
  --query TEXT
  --bundling_key TEXT
  -p, --partition TEXT
  --account TEXT
  --pretend
  --scheduler_args TEXT  Currently required to be in --key1 value --key2
                         value2 form
  --help                 Show this message and exit.