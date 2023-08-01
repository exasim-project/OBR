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