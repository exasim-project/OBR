import re
import os
import urllib.request
from pathlib import Path
import sys

from .logger_setup import logger

def find_first(d, key_in):
    """ recursively scan dictionary dictionary for k """
    res = {}
    if d.get(key_in):
        return {key_in:d[key_in]}
    for k, v in d.items():
        if isinstance(v, dict):
            res = find_first(v, key_in)
            if res:
                return res
    return res


def read_yaml(kwargs: dict) -> str:
    if kwargs.get("url"):
        with urllib.request.urlopen(kwargs["url"]) as f:
            config_str = f.read().decode("utf-8")
    else:
        config_file = kwargs["config"]
        yaml_location = (Path(os.getcwd()) / config_file).parents[0]

        # load base yaml file
        with open(config_file, "r") as config_handle:
            config_str = config_handle.read()

        # search for includes
        config_str = add_includes(yaml_location, config_str)

    return parse_special_variables(
        parse_special_variables(
            config_str, dict(os.environ), "env", kwargs.get("env", False)
        ),
        {"location": str(yaml_location)},
        "yaml",
        kwargs.get("env", False),
    )


def add_includes(yaml_location: Path, config_str: str) -> str:
    """Replace {{include.filename}} by the content of that file"""
    includes = re.findall(r"([ \t]*)\${{include.([_/\w.]*)}}", config_str)
    for ws, fn in includes:
        # if fn startswith a single dot here it is left from the re.findall
        # and means include.. thus we add the dot again
        orig_fn = fn
        if fn.startswith("."):
            fn = "../" + fn[1:]
        with open(yaml_location / fn, "r") as include_handle:
            include_str = ws + ws.join(include_handle.readlines())
        orig_search = ws + "${{include." + orig_fn + "}}"
        config_str = config_str.replace(orig_search, include_str)
    return config_str


def parse_special_variables(in_str: str, args: dict, domain: str, verbose: bool) -> str:
    """Replaces ${{ domain.value }} expressions with environmental variable values"""
    occurrences = re.findall(r"\${{" + domain + r"\.(\w+)}}", in_str)
    for inst in occurrences:
        if not args.get(inst, ""):
            logger.warning(f"warning {inst} not defined")
        print(f"setting {domain}.{inst} to {args.get(inst)}")
        in_str = in_str.replace(
            "${{" + domain + "." + inst + "}}", args.get(inst, f"'{inst}'")
        )
    return in_str


def parse_queries(in_str: str, args: dict) -> str:
    """Replaces ${{ get.value }} expressions with values from yaml"""
    occurrences = re.findall(r"\${{get" + r"\.(\w+)}}", in_str)
    for inst in occurrences:
        value = find_first(args, inst)
        in_str = in_str.replace(
            "${{get." + inst + "}}", str(value.get(inst, f"'{inst}'"))
        )
    return in_str


def eval_generator_expressions(in_str: str) -> str:
    """Tries evaluate ${{ }} expressions"""
    expr = re.findall(r"\${{([\'\"\= 0.-9()*+A-Za-z_>!]*)}}", in_str)
    for inst in expr:
        if inst.startswith("get"):
            continue
        try:
            in_str = in_str.replace("${{" + inst + "}}", str(eval(inst)))
        except Exception as e:
            logger.error(in_str + inst)
            logger.error(e)

            sys.exit(1)
    return in_str
