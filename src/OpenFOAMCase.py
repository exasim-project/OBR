#!/usr/bin/env python3

from pathlib import Path
import setFunctions as sf
import pyparsing as pp

from subprocess import check_output
from core import logged_execute, logged_func
from functools import wraps


def modifies_file(fns):
    """check if this job modifies a file, thus it needs to unlink
    and copy the file if it is a symlink
    """

    def unlink(fn):
        if Path(fn).is_symlink():
            src = fn.resolve()
            check_output(["rm", fn])
            check_output(["cp", "-r", src, fn])

    if isinstance(fns, list):
        for fn in fns:
            unlink(fn)
    else:
        unlink(fns)


def writes_file(fns):
    """check if this job modifies a file, thus it needs to unlink
    and copy the file if it is a symlink
    """

    def unlink(fn):
        if Path(fn).is_symlink():
            src = fn.resolve()
            check_output(["rm", fn])

    if isinstance(fns, list):
        for fn in fns:
            unlink(fn)
    else:
        unlink(fns)


def decorator_modifies_file(fns):
    def wrapper(f):
        @wraps(f)
        def wrapped(self, *args):
            for fn in fns:
                modifies_file(getattr(self, fn))
            f(self, *args)

        return wrapped

    return wrapper


def decorator_writes_files(fns):
    def wrapper(f):
        @wraps(f)
        def wrapped(self, *args):
            for fn in fns:
                writes_file(getattr(self, fn))
            f(self, *args)

        return wrapped

    return wrapper


class BlockMesh:
    @property
    def blockMeshDict(self):
        # TODO also check in constant folder
        return self.system_folder / "blockMeshDict"

    @property
    def polyMesh(self):
        return [
            self.constant_folder / "polyMesh" / "points",
            self.constant_folder / "polyMesh" / "boundary",
            self.constant_folder / "polyMesh" / "faces",
            self.constant_folder / "polyMesh" / "owner",
            self.constant_folder / "polyMesh" / "neighbour",
        ]

    @decorator_writes_files(["polyMesh"])
    def refineMesh(self, args):
        """ """
        if args.get("adapt_timestep", True):
            deltaT = self.deltaT
            self.setControlDict({"deltaT": deltaT / 2})

    @decorator_modifies_file(["blockMeshDict"])
    def modifyBlockMesh(self, args):
        for block in args["modifyBlock"]:
            orig_block, target_block = block.split("->")
            sf.set_cells(
                self.blockMeshDict,
                orig_block,
                target_block,
            )

        self._exec_operation(["refineMesh", "-overwrite"])

    @decorator_writes_files(["polyMesh"])
    def blockMesh(self, args={}):
        if args.get("modifyBlock"):
            self.modifyBlockMesh(args)
        self._exec_operation("blockMesh")


class ConfigFile:
    """Abstraction of OpenFOAMs config files which contain key value pairs or key block pairs"""

    # TODO move to separate file for the grammar
    @property
    def dimensionSet(self):
        """Parse OF dimension set eg  [0 2 -1 0 0 0 0]"""
        return (
            pp.Suppress("[")
            + pp.delimitedList(pp.pyparsing_common.number * 7, delim=pp.White())
            + pp.Suppress("]")
        ).setParseAction(lambda toks: "[" + " ".join([str(i) for i in toks]) + "]")

    @property
    def keyValuePair(self):
        """list of key value pairs parsed in to a dict"""

        return pp.Dict(
            pp.delimitedList(
                pp.Group(
                    pp.Word(pp.alphanums) + pp.Word(pp.alphanums) + pp.Suppress(";")
                ),
                delim=";",
            )
        )

    @property
    def comment(self):
        pass

    @property
    def footer(self):
        """the footer of a OpenFOAM file"""
        return "//" + "*" * 73 + "//"

    @property
    def separator(self):
        return "// " + "* " * 26 + "//"

    @property
    def include(self):
        """matches #include \"foo/bar.baz\" """
        return pp.Group(
            pp.Keyword("#include") + pp.Word(pp.alphanums + '_-."/')
        ).set_results_name("include")

    @property
    def function_objects_list(self):
        """search for the functions keyword followed by a list of includes"""
        return pp.Dict(
            pp.Group(
                pp.Literal("functions")
                + pp.Literal("{")
                + pp.delimited_list(
                    pp.OneOrMore(self.include),
                    delim="\n",
                )
                + pp.Literal("}")
            )
        ).set_results_name("functions")

    @property
    def of_list(self):
        """matches (a b c)"""
        return (
            pp.Literal("(")
            + pp.delimitedList(pp.OneOrMore(pp.Word(pp.alphanums)), delim=" ")
            + pp.Literal(")")
        ).set_results_name("list")

    @property
    def key_value_pair(self):
        """matches a b; or a (a b c);"""
        return pp.Group(
            pp.Word(pp.alphanums)
            + (pp.Word(pp.alphanums + '"') ^ self.of_list)
            + pp.Suppress(";")
        ).set_results_name("key_value_pair")

    @property
    def of_dict(self):
        """should match b {bar baz;}"""
        return pp.Group(
            pp.Word(pp.alphanums)
            + pp.nested_expr(
                opener="{",
                closer="}",
                content=pp.delimitedList(self.key_value_pair, delim=";"),
            )
        ).set_results_name("of_dict")

    def config_parser(self):
        return (
            self.include
            ^ self.function_objects_list
            ^ self.key_value_pair
            ^ self.of_dict
        )

    def parse_to_dict(self, text):
        """parse an OpenFOAM file to an Ordered dict"""

        return

    def read(self, fn):
        """parse an OF file into a dictionary"""
        with open(fn, "r") as fh:
            return fh.readlines()

    def _dump(self, fn, dictionary):
        """writes a parsed OF file back into a file"""
        pass

    def set_key_value_pairs(self, path, dictionary):
        """check if a given key exists and replaces it with the key value pair

        this can be used to modify the value in the file
        """
        fn = path
        with open(fn, "r") as f:
            lines = f.readlines()
        with open(fn, "w") as f:
            found_keys = []
            for line in lines[0:-1]:
                in_line = False
                for key, value in dictionary.items():
                    entry = line.strip().startswith(key)
                    if entry:
                        in_line = True
                        f.write("{}\t{};\n".format(key, value))
                        found_keys.append(key)
                if not in_line:
                    f.write(line)
            # write remaining keys
            for key, value in dictionary.items():
                if key not in found_keys:
                    f.write("{}\t{};\n".format(key, value))
            f.write(lines[-1])

    def setKeyValuePair(self, args):
        """ """
        logged_func(
            self.set_key_value_pairs,
            self.job.doc,
            path=Path(self.job.path) / "case" / args["file"],
            dictionary={args["key"]: args["value"]},
        )


class ControlDict(ConfigFile):
    @property
    def controlDict(self):
        return self.system_folder / "controlDict"

    @property
    def endTime(self):
        # TODO implement a getKeyValuePair function in ConfigFile
        return sf.get_end_time(self.controlDict)

    @property
    def deltaT(self):
        # TODO implement a getKeyValuePair function in ConfigFile
        return sf.read_deltaT(self.controlDict)

    @decorator_modifies_file(["controlDict"])
    def setControlDict(self, args):
        """modifies the current controlDict by the given dictionary

        if the key exists in the controlDict the values are replaced
        non-existent keys are added
        """
        logged_func(
            self.set_key_value_pairs,
            self.job.doc,
            path=self.controlDict,
            dictionary=args,
        )


class OpenFOAMCase(BlockMesh, ControlDict):
    """A class for simple access to typical OpenFOAM files"""

    def __init__(self, path, job):
        self.path_ = Path(path)
        print("case", self.path_)
        self.job = job

    @property
    def path(self):
        return self.path_

    @property
    def system_folder(self):
        return self.path / "system"

    @property
    def constant_folder(self):
        return self.path / "constant"

    @property
    def zero_folder(self):
        """TODO check for 0.orig folder"""
        return self.path / "0"

    @property
    def init_p(self):
        return self.zero_folder / "p"

    @property
    def init_U(self):
        return self.zero_folder / "U.orig"

    @property
    def decomposeParDict(self):
        return self.system_folder / "decomposeParDict"

    @property
    def fvSolution(self):
        return self.system_folder / "fvSolution"

    def obr_operation_was_sucessful(self, operation):
        """Checks whether an operation was performed without error

        This is performed in two steps,
            1. check if an .obr/operation.log exists
            2. check if .obr/operation.state is success
        """
        # TODO implement
        pass

    @property
    def is_decomposed(self):
        """TODO check if number of processor folder is consitent with decomposeParDict"""
        return self.obr_operation_was_sucessful("decomposePar")

    def _exec_operation(self, operation):
        logged_execute(operation, self.path, self.job.doc)

    def decomposePar(self, args={}):
        if args.get("simple"):
            if not args["simple"].get("numberSubDomains"):
                coeffs = [i for i in args["simple"]["coeffs"]]
                numberSubDomains = coeffs[0] * coeffs[1] * coeffs[2]
            else:
                numberSubDomains = args["simple"]["numberSubDomains"]
                coeffs = args["simple"].get("coeffs", [1, 1, 1])
            logged_func(
                sf.set_number_of_subdomains_simple,
                self.job.doc,
                decomposeParDict=self.decomposeParDict,
                numberSubDomains=numberSubDomains,
                coeffs=coeffs,
            )

        self._exec_operation(["decomposePar", "-force"])

    @decorator_modifies_file(["fvSolution"])
    def setLinearSolver(self, args):
        """ """
        logged_func(
            sf.replace_block,
            self.job.doc,
            path=self.fvSolution,
            field=args["field"],
            new_block=args["block"],
            excludes=["Final"],
        )

    def mapFields(self, args):
        """ """

        # TODO check if mapFields is requested and if it actually needed
        # cmd = [
        #     "mapFields",
        #     "../../../base",
        #     "-consistent",
        #     "-sourceTime",
        #     "latestTime",
        # ]
        pass
