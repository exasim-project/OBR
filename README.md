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

In general, to create a tree of case variation run

    obr init --folder [path] --config path-to-config.yaml

Within the context of the `micro_benchmarks` example, simply run

    obr init --folder . --config assets/scaling.yaml

OBR should now print some output, followed by `INFO: successfully initialized`.

### 2. Running a tree

Finally,  operations on a tree can be run with the `obr run` command-line option:

    obr run -o fetchCase --folder path-to-tree

Or, in this specific example (the default of `--folder` is `.`):

    obr run -o fetchCase

Within `LidDrivenCavity3D/workspace` should now have appeared a multitude of directories (=jobs).
Not all cases are afflicted by every obr operation. For instance, only the directory named `78e2de3e6205144311d04282001fe21f` should have a further subdirectory named `case`.

Inside `78e2de3e6205144311d04282001fe21f/signac_job_document.json`, the operation is summarized.

## Contributing

To contribute to this project, we suggest creating an issue. From then on, we can discuss further development.