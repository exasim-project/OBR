## OBR query

### Usage
```zsh
Usage: obr query [OPTIONS]

Options:
  -f, --folder TEXT
  --filter TEXT      Pass a <key><predicate><value> value pair per occurrence
                     of --filter. Predicates include ==, !=, <=, <, >=, >. For
                     instance, obr query --filter "solver==pisoFoam"
  -d, --detailed
  -a, --all
  -q, --query TEXT   Pass a list of dictionary entries in the "{key: '<key>',
                     value: '<value>', predicate:'<predicate>'}, {...}"
                     syntax. Predicates include neq, eq, gt, geq, lt, leq. For
                     instance, obr query -q "{key:'maxIter', value:'300',
                     predicate:'geq'}"  [required]
  -v, --verbose      Set for additional output.
  --help             Show this message and exit.
```

### Understanding OBR query
`obr query` recursively traverses the current directory, or the directory specified by the `--folder` argument, for `signac_statepoint.json` files.

### Common Problems

1. `obr query -q [Query]` does not return anything.
     - As of now, `obr query` ignores jobs that do not include the `obr` key in their corresponding `signac_job_document.json` file.
     - The `obr` key is only added to the `signac_job_document.json` file after running this job at least once.
     - For instance, after initializing an OBR workspace via [`obr init`](init.md) and running a valid query, nothing is returned. After successfully running [`obr run`](run.md), the aforetried query should return the expected result.