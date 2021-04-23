#!/usr/bin/env python3

from pathlib import Path
import OBR.setFunctions as sf
from OBR.OpenFOAMCase import OpenFOAMCase
import os
from subprocess import check_output


class DefaultPrepareEnviroment:
    def __init__(self):
        pass

    def set_up(self):
        pass

    def clean_up(self):
        pass


class PrepareOMPMaxThreads(DefaultPrepareEnviroment):
    """ Sets the enviroment variable for OMP """

    def __init__(self):
        self.processes = 1

    def set_up(self):
        print(" use ", self.processes, " threads")
        os.environ["OMP_NUM_THREADS"] = str(self.processes)

    def clean_up(self):
        pass


class CachePrepare(DefaultPrepareEnviroment):
    """ copies cases from a base """

    def __init__(self, path):
        """ prepare a cache folder for the target folder in path """
        self.path = path
        self.alternative_cache_path_ = None

    @property
    def cache_path(self):
        """ append cache to the current path name """
        path = self.path
        if self.alternative_cache_path_:
            path = self.alternative_cache_path_

        base_path = Path(path.parent).parent
        variant_name = path.parent.name
        case_name = self.path.name
        print("EnviromentSetters:53", case_name, variant_name, base_path)
        return base_path / (variant_name + "-cache") / case_name


class CellsPrepare(CachePrepare):
    """ sets the number of cells or copies from a base to avoid remeshing """

    def __init__(self, path):
        super().__init__(path=path)
        self.cells = Path(path.parent).name

    def set_up_cache(self):
        print("setup cache", self.path)
        cache_case = OpenFOAMCase(self.cache_path)
        deltaT = 0.1 * 16 / float(self.cells)
        new_cells = "{} {} {}".format(self.cells, self.cells, self.cells)
        sf.set_cells(cache_case.blockMeshDict, "16 16 16", new_cells)
        sf.set_mesh_boundary_type_to_wall(cache_case.blockMeshDict)
        sf.set_p_init_value(cache_case.init_p)
        sf.set_U_init_value(cache_case.init_U)
        sf.add_libOGL_so(cache_case.controlDict)
        sf.set_end_time(cache_case.controlDict, 10 * deltaT)
        sf.set_deltaT(cache_case.controlDict, deltaT)
        sf.set_writeInterval(cache_case.controlDict)
        sf.clear_solver_settings(cache_case.fvSolution)
        print("Meshing", cache_case.path)
        check_output(["blockMesh"], cwd=cache_case.path)

    def set_up(self):
        target_path = self.path.parent
        sf.ensure_path(self.cache_path.parent)
        if not os.path.exists(self.cache_path):
            print("cache does not exist")
            check_output(["cp", "-r", self.root, self.cache_path])
            self.set_up_cache()

        # check if cache_path exists otherwise copy
        print("copying from", self.cache_path, " to ", target_path)
        sf.ensure_path(target_path)
        check_output(["cp", "-r", self.cache_path, target_path])

    def clean_up(self):
        pass
