## OBR run

### Usage
```zsh
Usage: obr run [OPTIONS]

  Run specified operations

Options:
  -f, --folder TEXT
  -o, --operations TEXT  Specify the operation(s) to run. Pass multiple
                         operations after -o, separated by commata (NO space),
                         e.g. obr run -o shell,apply.  [required]
  -j, --job TEXT
  --args TEXT
  -t, --tasks INTEGER
  -a, --aggregate
  --query TEXT
  --args TEXT
  --help                 Show this message and exit.
```

### Understanding obr run

A set of operations can be passed after the `-o` flag. 

```Example: obr run -o fetchCase,runParallelSolver```

It is important to note, that there can be no whitespace in between. Otherwise, 
the `runParallelSolver` will be parsed as separate commandline argument.

To list all available operations, run `obr run --list-operations` or [`obr operations`](#obr-operations).