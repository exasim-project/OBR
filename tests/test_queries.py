from obr.core.queries import (
    input_to_query,
    execute_query,
    input_to_queries,
    query_flat_jobs,
    query_to_dataframe,
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


@pytest.fixture
def emit_test_config(tmpdir):
    return {
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


def test_query_to_df(tmpdir, emit_test_config, mock_job_dict):
    os.chdir(tmpdir)

    project = OpenFOAMProject.init_project(root=tmpdir)
    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)
    project.run(names=["fetchCase"])
    base_query = [Query(key="solver", value="pisoFoam")]
    df = query_to_dataframe(project, base_query)

    correct_df = pd.DataFrame(
        [["pisoFoam", "2c436d59c91a9ec68eaa0dcf70181cbf"]],
        columns=["solver", "jobid"],
    )
    assert isinstance(df, pd.DataFrame)
    assert df["solver"][0] == "pisoFoam"
    assert df.equals(correct_df)
