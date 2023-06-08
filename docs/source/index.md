% obr documentation master file, created by
% sphinx-quickstart on Mon Jan 30 21:33:58 2023.
% You can adapt this file completely to your liking, but it should at least
% contain the root `toctree` directive.

# Welcome to obr's documentation!

## Contents
```{toctree}
:caption: ''
:maxdepth: 2

commandLine/CLI
troubleshooting/troubleshooting
```


```{warning}
This library is currently under heavy development. Things might change frequently.
```
## Workflow specification
Workflows are specified via yaml files, for which a  typical yaml file is shown next

    case:
        type: CaseOnDisk
        origin: <path_to_original_case>
    variation:
     - operation: value
       values:
         - key: value
         - key: value
       build_pre:
         - shell: interpreted as shell commands executed before
         - operation:
           key: value
       build_post:
            - same as build_pre but executed after operation
       parent:
            key: value
       variation:
            a nested block starting a new variation

Here `operation` can be either a simple key value manipulation of OpenFOAM dictionaries were like `setKeyValuePair` which parses `file` and sets `key` to `value`. Besides 'setKeyValuePair' several convinience wrapper like `controlDict`, 'fvSolution' etc exist.

## Available Operations

## Usage Example

The benchmark runner is split into several layers:
    1. case generation
    2. case run/submit
    3. case postprocessing

The [micro_benchmarks repository](https://github.com/exasim-project/micro_benchmarks/tree/case_windsor_body) provides a good point to start learning from. After cloning the repository, `cd` into the `WindsorBody` subdirectory.
### 1. Creating a tree

In general, to create a tree of case variation run

    obr init --folder [path] --config path-to-config.yaml

Within the context of the `micro_benchmarks` example, simply run

    obr init --folder . --config assets/scaling.yaml

OBR should now print a low of configuration, followed by `INFO: successfully initialized`.

### 2. Running a tree

Finally, a tree can be run with the `obr run` command-line option:

    obr run -o fetchCase --folder path-to-tree

Or, in this specific example (the default of `--folder` is `.`):

    obr run -o fetchCase

Within `WindsorBody/workspace` should now have appeared a multitude of directories (=cases).
Not all cases are afflicted by every obr operation. For instance, only the directory named `78e2de3e6205144311d04282001fe21f` should have a further subdirectory named `case`.

Inside `78e2de3e6205144311d04282001fe21f/signac_job_document.json`, the operation is summarized.

# Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
