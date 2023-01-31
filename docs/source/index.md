% obr documentation master file, created by
% sphinx-quickstart on Mon Jan 30 21:33:58 2023.
% You can adapt this file completely to your liking, but it should at least
% contain the root `toctree` directive.

# Welcome to obr's documentation!

```{toctree}
:caption: 'Contents:'
:maxdepth: 2
```

```{warning}
This library is currently under heavy development. Things might change frequently.
```
## Workflow specification
A typical yaml file is shown next

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

## Usage

The benchmark runnner is split into several layers:
    1. case generation
    2. case run/submig
    3. case postprocessing

### 1. Creating a tree

To create a tree of case variation run


    obr create --execute False --folder lidDrivenCavity3D --parameters assets/lidDrivenCavity.yaml

### 2. Running a tree

    obr run -o runParallelSolver --folder

# Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`