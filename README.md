**[Workflow specification](#Workflow_specification)** |
**[Usage](#Usage)** |
**[Example](#Example)** 

---

# OBR - OpenFOAM Benchmark Runner

The OpenFOAM Benchmark Runner (OBR) is an experimental workflow manager for simple provisioning of complex parameter studies and reproducible simulations. A typical OpenFOAM workflow of seting up a case and various parameter manipulations can be defined using the yaml markup language.


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

