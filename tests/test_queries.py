from obr.core.queries import (
    input_to_query,
    execute_query,
    input_to_queries,
    query_flat_jobs,
    query_to_dataframe,
    filter_jobs,
    Query,
)
from obr.signac_wrapper.operations import OpenFOAMProject
from obr.create_tree import create_tree
import pytest
import os
import pandas as pd


def test_input_to_query():
    input_wo_value = "{key:'preconditioner'}"
    # ", {key:'TimeStep’}}”
    query = input_to_query(input_wo_value)

    assert query.key == "preconditioner"
    assert query.value == None
    assert query.predicate == "eq"

    input_w_value = "{key:'preconditioner', value:'IC'}"
    query = input_to_query(input_w_value)
    assert query.value == "IC"
    # ", {key:'TimeStep’}}”

    input_w_value_w_predicate = "{key:'preconditioner', value:'IC', predicate:'neq'}"
    query = input_to_query(input_w_value_w_predicate)
    assert query.predicate == "neq"


def test_input_to_queries():
    input_w_value = "{key:'preconditioner', value:'IC'}, {key:'solver'}"
    queries = input_to_queries(input_w_value)
    assert len(queries) == 2

    for query in queries:
        assert query.key != None


def test_execute_query():
    input_w_value = "{key:'preconditioner', value:'IC'}"
    query = input_to_query(input_w_value)
    executed_query = execute_query(query, key="preconditioner", value="IC")
    assert executed_query.state == {"preconditioner": "IC"}

    input_w_value = "{key:'preconditioner'}"
    query = input_to_query(input_w_value)
    executed_query = execute_query(query, key="preconditioner", value="IC")
    assert executed_query.state == {"preconditioner": "IC"}

    input_w_value = "{key:'preconditioner', value:'IC', predicate:'neq'}"
    query = input_to_query(input_w_value)
    executed_query = execute_query(query, key="preconditioner", value="IC")
    assert executed_query.state == {}


@pytest.fixture
def mock_job_dict():
    return {
        12345: {"preconditioner": "IC"},
        23456: {"obr": {"preconditioner": "IC"}},
        34567: {
            "obr": {
                "postProcessing": {
                    "machine_name": {
                        "time": [1, 2, 3],
                        "logFiles": ["foo", "bar", "baz"],
                    }
                }
            }
        },
    }


def test_flatten_jobs(mock_job_dict):
    input_w_value = "{key:'preconditioner'}"
    queries = input_to_queries(input_w_value)

    executed_query = query_flat_jobs(mock_job_dict, queries, False, True, True)

    assert executed_query[0].id == 12345
    assert executed_query[0].result == [{"preconditioner": "IC"}]
    assert executed_query[0].sub_keys == [[]]

    assert executed_query[1].id == 23456
    assert executed_query[1].result == [{"preconditioner": "IC"}]
    assert executed_query[1].sub_keys == [["obr"]]

    input_w_value = "{key:'preconditioner', value:'IC'}"
    queries = input_to_queries(input_w_value)

    executed_query = query_flat_jobs(mock_job_dict, queries, False, True, True)
    assert executed_query[0].id == 12345


def test_nested_results_with_lists(mock_job_dict):
    input_w_value = "{key:'time'}"
    queries = input_to_queries(input_w_value)

    executed_query = execute_query(queries[0], 34567, mock_job_dict[34567], True, [])
    assert executed_query.state == {"time": 3}
    assert executed_query.sub_keys == [34567, "obr", "postProcessing", "machine_name"]


@pytest.fixture()
def get_project(tmpdir):
    config = {
        "case": {
            "type": "GitRepo",
            "solver": "pisoFoam",
            "url": "https://develop.openfoam.com/committees/hpc.git",
            "folder": "Lid_driven_cavity-3d/S",
            "commit": "f9594d16aa6993bb3690ec47b2ca624b37ea40cd",
            "cache_folder": "None/S",
            "post_build": [
                {"shell": "cp system/fvSolution.fixedNORM system/fvSolution"},
                {"controlDict": {"writeFormat": "binary", "libs": ["libOGL.so"]}},
                {
                    "fvSolution": {
                        "set": "solvers/p",
                        "clear": True,
                        "tolerance": "1e-04",
                        "relTol": 0,
                        "maxIter": 3000,
                    }
                },
            ],
        },
    }
    os.chdir(tmpdir)

    project = OpenFOAMProject.init_project(root=tmpdir)
    create_tree(project, config, {"folder": tmpdir}, skip_foam_src_check=True)
    project.run(names=["fetchCase"])
    return project


def test_filters(get_project: OpenFOAMProject):
    filters = ["maxIter!=0"]
    jobs = get_project.filter_jobs(filters)
    assert len(jobs) > 0


def test_predicates(get_project):
    p = get_project
    queries_str = "{key: 'maxIter', value: '2900', predicate:'geq'}"
    jobs = filter_jobs(p, queries_str)
    assert jobs[0].sp.get("post_build")[2].get("fvSolution").get("maxIter") == 3000
    queries_str = "{key: 'maxIter', value: '2900', predicate:'gt'}"
    jobs = filter_jobs(p, queries_str)
    assert jobs[0].sp.get("post_build")[2].get("fvSolution").get("maxIter") == 3000
    queries_str = "{key: 'maxIter', value: '2900', predicate:'neq'}"
    jobs = filter_jobs(p, queries_str)
    assert jobs[0].sp.get("post_build")[2].get("fvSolution").get("maxIter") == 3000
    queries_str = "{key: 'maxIter', value: '3100', predicate:'lt'}"
    jobs = filter_jobs(p, queries_str)
    assert jobs[0].sp.get("post_build")[2].get("fvSolution").get("maxIter") == 3000
    queries_str = "{key: 'maxIter', value: '3100', predicate:'leq'}"
    jobs = filter_jobs(p, queries_str)
    assert jobs[0].sp.get("post_build")[2].get("fvSolution").get("maxIter") == 3000
