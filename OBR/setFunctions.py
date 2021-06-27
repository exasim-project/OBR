#!/usr/bin/env python3
from subprocess import check_output


def sed(fn, in_reg_exp, out_reg_exp, inline=True):
    """ wrapper around sed """
    ret = check_output(["sed", "-i", "s/" + in_reg_exp + "/" + out_reg_exp + "/g", fn])


def clean_block_from_file(fn, block_starts, block_end, replace):
    """ cleans everything from block_start to block_end and replace it """
    with open(fn, "r") as f:
        lines = f.readlines()
    with open(fn, "w") as f:
        skip = False
        for line in lines:
            is_start = [block_start in line for block_start in block_starts]
            if any(is_start):
                skip = True
            if skip == True and block_end in line:
                skip = False
                f.write(replace)
            if not skip:
                f.write(line)


def set_cells(blockMeshDict, old_cells, new_cells):
    """ """
    sed(blockMeshDict, old_cells, new_cells)


def set_mesh_boundary_type_to_wall(blockMeshDict):
    """ """
    sed(blockMeshDict, "type[  ]*cyclic", "type wall")


def set_p_init_value(p):
    """ """
    sed(p, "type[  ]*cyclic;", "type zeroGradient;")


def set_U_init_value(U):
    """ """
    sed(U, "type[  ]*cyclic;", "type fixedValue;value uniform (0 0 0);")


def add_libOGL_so(controlDict):
    with open(controlDict, "a") as ctrlDict_handle:
        ctrlDict_handle.write('libs ("libOGL.so");')


def set_end_time(controlDict, endTime):
    sed(controlDict, "endTime[ ]*[0-9.]+;", "endTime {};".format(endTime))

def read_block(blockMeshDict):
    import re

    ret = check_output(["grep", "hex", blockMeshDict]).decode("utf-8")
    num_cells = re.findall("[(][0-9 ]*[)]", ret)[1]
    return list(map(int, re.findall("[0-9]+", num_cells)))


def read_deltaT(controlDict):
    ret = (
        check_output(["grep", "deltaT", controlDict])
        .split()[-1]
        .decode("utf-8")
        .replace(";", "")
    )
    return float(ret)


def set_deltaT(controlDict, deltaT):
    sed(controlDict, "deltaT[ ]*[0-9.]*", "deltaT {}".format(deltaT))


def set_writeInterval(controlDict, writeInterval):
    sed(controlDict, "writeInterval[ ]*[0-9.]*", "writeInterval " + str(writeInterval))


def clear_solver_settings(fvSolution, field):
    clean_block_from_file(
        fvSolution,
        ["   {}\n".format(field), '"' + field + '.*"'],
        "  }\n",
        field + "{}\n",
    )


def ensure_path(path):
    print("creating", path)
    check_output(["mkdir", "-p", path])
