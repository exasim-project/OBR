from obr.core.queries import input_to_query, execute_query, input_to_queries
import pytest


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
