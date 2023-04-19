import re
import os
import urllib.request
from pathlib import Path


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

    return parse_variables(
        parse_variables(config_str, dict(os.environ), "env"),
        {"location": str(yaml_location)},
        "yaml",
    )


def add_includes(yaml_location: Path, config_str: str) -> str:
    """Replace {{include.filename}} by the content of that file"""
    includes = re.findall("([ \t]*)\${{include.([\w.]*)}}", config_str)
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


def parse_variables(in_str: str, args: dict, domain: str) -> str:
    ocurrances = re.findall(r"\${{" + domain + "\.(\w+)}}", in_str)
    for inst in ocurrances:
        if not args.get(inst, ""):
            print(f"warning {inst} not defined")
        in_str = in_str.replace(
            "${{" + domain + "." + inst + "}}", args.get(inst, f"'{inst}'")
        )
    expr = re.findall(r"\${{([\'\"\= 0.-9()*+A-Za-z_>!]*)}}", in_str)
    for inst in expr:
        try:
            in_str = in_str.replace("${{" + inst + "}}", str(eval(inst)))
        except:
            print(in_str, inst)
    return in_str