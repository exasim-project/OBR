from obr.signac_wrapper.operations import OpenFOAMProject
import os


def test_filtering():
    dir = "/home/pedda/Documents/work/micro_benchmarks/WindsorBody"
    os.chdir(dir)

    project = OpenFOAMProject.init_project(root=dir)
    # project.get_jobs()

    f = {"labels": "ready"}
    project.filter_jobs(filters=f)
