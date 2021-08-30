# OBR - OpenFOAM Benchmark Runner

This repository is used to easily create benchmark cases to evaluate the
performance of the OpenFOAM Ginkgo Layer.

## Usage

The benchmark runnner is split into several layers:
1. case generation
2. case decomposition
3. case run

### 1. Creating a tree

To create a tree of case variation run


    python obr_create_tree.py \
         --parameters lidDrivenCavity3DFull.json \
         --folder lidDrivenCavity3DFull

### 2. Running a tree


