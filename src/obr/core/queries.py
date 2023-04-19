from dataclasses import dataclass, field
from typing import Any
from copy import deepcopy
import re


@dataclass
class query_result:
    id: str = field()
    result: list[dict] = field(default_factory=list[dict])
    sub_keys: list[list[str]] = field(default_factory=list[list[str]])


@dataclass
class Query:
    key: str
    value: Any = None
    state: dict = field(default_factory=dict)
    predicate: str = "eq"
    # If negate is set to true this Query must not match
    # for a list of queries to be succesful
    sub_keys: list = field(default_factory=list)
    negate: bool = False

    def execute(self, key, value):
        predicate_map = {
            "eq": lambda a, b: a == b,
            "neq": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
        }
        self.predicate_op = predicate_map[self.predicate]

        if not (self.value == None):
            if (
                self.predicate_op(self.value, value)
                and self.key == key
                and not self.state
            ):
                self.state = {key: value}
        else:
            # print(key, value)
            if self.predicate_op(self.key, key) and not self.state:
                self.state = {key: value}

    def match(self):
        return self.state


def input_to_query(inp: str) -> Query:
    """converts cli input  str to a Query object"""
    inp = (
        inp.replace("key", '"key"')
        .replace("value", '"value"')
        .replace("predicate", '"predicate"')
    )
    return Query(**eval(inp))


def input_to_queries(inp: str) -> list[Query]:
    """Convert a json string to list of queries"""
    inp_lst = re.findall("{[\w:\"'0-9,. ]*}", inp)
    return [input_to_query(x) for x in inp_lst]


def execute_query(query, key, value, latest_only=True, track_keys=list) -> Query:
    if isinstance(value, list) and latest_only and value:
        value = value[-1]
    # descent one level down, statepoints and job documents might contain
    # subdicts which we want to descent into at the same time we need to track
    signac_attr_dict_str = "JSONAttrDict"
    if isinstance(value, dict) or type(value).__name__ == signac_attr_dict_str:
        track_keys.append(key)
        sub_results = list(
            filter(
                lambda x: x.state,
                [
                    execute_query(
                        deepcopy(query), sub_key, sub_value, latest_only, track_keys
                    )
                    for sub_key, sub_value in value.items()
                ],
            )
        )
        if len(sub_results) > 0:
            return sub_results[0]
    query.execute(key, value)
    # if we have a match store previous keys
    if query.match():
        query.sub_keys = track_keys
    return query


def flatten_jobs(jobs: list) -> dict:
    """convert a list of jobs to a dictionary"""
    docs: dict = {}

    # merge job docs and statepoints
    for job in jobs:
        if not job.doc.get("obr"):
            continue
        docs[job.id] = {}
        for key, value in job.doc.obr.items():
            docs[job.id].update({key: value})
        docs[job.id].update(job.sp())
    return docs


def query_flat_jobs(
    jobs: dict, queries: list[Query], output, latest_only, strict
) -> list[query_result]:
    """
    Parameters:
    jobs -- a job dictionary ordered by job ids
    queries -- list of queries to run
    output -- Whether to print result to screen
    latest_only -- Take only latest value if resulting value is a list
    strict -- needs all queries to be succesfull to return a result
    """
    ret = []
    for job_id, doc in jobs.items():
        # scan through merged operations and statepoint values of a job
        # look for keys and values
        # and append if all queries have been matched
        tmp_qs: list[Query] = []
        all_required = True
        for q in queries:
            res_cache = {}
            for key, value in doc.items():
                q_tmp = deepcopy(q)
                res = execute_query(q_tmp, key, value, latest_only, [])
                if res.state:
                    # a filter query was hit
                    if res.negate:
                        all_required = False
                        break

                    res_cache = res.state
                    tmp_qs.append(res)

            # res.state could be from any key before
            if q.value and not res_cache:
                all_required = False

        # append if all required results are present
        res_tmp = query_result(job_id)
        for q in tmp_qs:
            # requests a value but not a state
            # is currently considered to be failed
            res_tmp.result.append(q.state)
            res_tmp.sub_keys.append(q.sub_keys)

        # in strict mode all queries need to have some result
        if strict:
            all_required = len(res_tmp.result) == len(queries)
            # if not all_required:
            #    raise Exception(res_tmp)

        # merge all results to a single dictionary
        res_tmp_dict = {}
        for d in res_tmp.result:
            res_tmp_dict.update(d)
        res_tmp.result = [res_tmp_dict]

        if all_required:
            ret.append(deepcopy(res_tmp))
    return ret


def query_to_dict(
    jobs: list, queries: list[Query], output=False, latest_only=True, strict=False
) -> list[query_result]:
    """Given a list jobs find all jobs for which a query matches

    Flattens list of jobs to a dictionary with merged statepoints and job document first
    """
    return query_flat_jobs(flatten_jobs(jobs), queries, output, latest_only, strict)


def query_impl(
    jobs: list, queries: list[Query], output=False, latest_only=True
) -> list[str]:
    """Performs a query and returns corresponding job.ids"""
    res = query_to_dict(jobs, queries, output, latest_only)
    if output:
        for r in res:
            print(r)

    query_ids = []
    for id_ in res:
        query_ids.append(id_.id)

    return query_ids