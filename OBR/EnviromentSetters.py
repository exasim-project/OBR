#!/usr/bin/env python3


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

    def set_up(self, _):
        print(" use ", self.processes, " threads")
        os.environ["OMP_NUM_THREADS"] = str(self.processes)

    def clean_up(self):
        pass


class CachePrepare(DefaultPrepareEnviroment):
    """ copies cases from a base """

    def __init__(self, path):
        """ prepare a cache folder for the target folder in path """
        self.path = path

    def cache_path(self):
        """ append cache to the current path name """

        base_path = self.path.parent
        name = self.path.name
        return base_path / (name + "-cache")


class CellsPrepare(CachePrepare):
    """ sets the number of cells or copies from a base to avoid remeshing """

    def __init__(self, path):
        super().__init__(path=path)
        self.cells = path.name

    def set_up_cache(self, path):
        print("setup cache", path)
        cache_case = OpenFOAMCase()
        cache_case.set_parent_path(Path(path))
        cache_case.path_ = path
        deltaT = 0.1 * 16 / self.cells
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
        test_path = self.path
        cache_path = test_path / self.cache_path(str(self.cells), self.case_name)
        target_path = test_path / self.local_path
        sf.ensure_path(cache_path.parent)
        if not os.path.exists(cache_path):
            print("cache does not exist")
            check_output(["cp", "-r", self.root, cache_path])
            self.set_up_cache(cache_path)

        # check if cache_path exists otherwise copy
        print("copying from", cache_path, " to ", target_path)
        sf.ensure_path(target_path.parent)
        check_output(["cp", "-r", cache_path, target_path.parent])

    def clean_up(self):
        pass
