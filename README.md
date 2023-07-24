**[Documentation](https://obr.readthedocs.io/)**
---
# OBR - OpenFOAM Benchmark Runner
![Tests](https://github.com/hpsim/obr/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/greole/70b77e941a906fc3863661697ea8e864/raw/covbadge.json)
[![Documentation Status](https://readthedocs.org/projects/obr/badge/?version=latest)](https://obr.readthedocs.io/en/latest/?badge=latest)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
<!-- Overview -->
The OpenFOAM Benchmark Runner (OBR) is an experimental workflow manager for
simple provisioning of complex parameter studies and reproducible simulations.
A typical OpenFOAM workflow of setting up a case and various parameter
manipulations can be defined using the yaml markup language. OBR is build on
top of signac.

<!-- Installation -->
## Installation
As of now, we recommend to clone the repository and to perform a symlink install of OBR into your virtual environment via pip:

```
pip install -e .
```

## Usage


The benchmark runner is split into several layers:
1. case generation
2. case run/submit
3. case postprocessing

The [micro_benchmarks repository](https://github.com/exasim-project/micro_benchmarks/tree/case_windsor_body) provides a good point to start learning from. After cloning the repository, `cd` into the `LidDrivenCavity3D` directory, where a example yaml file can be found in the assets folder.

### 1. Creating a tree

In general, to create a tree of case variations run

    obr init --folder [path] --config path-to-config.yaml

Within the context of the `micro_benchmarks` example, simply run

    obr init --folder . --config assets/scaling.yaml

OBR should now print some output, followed by `INFO: successfully initialized`.

### 2. Running a tree

Finally,  operations on a tree can be run with the `obr run` command-line option, for example `fetchCase`, which is responsible for copying the base case into the workspace:

    obr run -o fetchCase --folder path-to-tree

Or, in this specific example (the default of `--folder` is `.`):

    obr run -o fetchCase

Within `LidDrivenCavity3D/workspace` should now have appeared a multitude of directories (=jobs), which are in the form of a UID eg. `78e2de3e6205144311d04282001fe21f`. Each job represents a distinct operation such as modifying the blockMeshDict and call blockMesh including its depencies. The order in which operations can be applied are defined by the `config.json`, however, runnning

    obr run -o generate

also runs all defined operations in the appropriate order.


## Contributing

To contribute to this project, we suggest creating an issue. From then on, we can discuss further development.
