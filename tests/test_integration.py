import pytest
from subprocess import check_output

@pytest.fixture
def emmit_test_config():
    return """case:
    type: OpenFOAMTutorialCase
    solver: icoFoam
    domain: incompressible
    case: cavity/cavity
    post_build:
      - controlDict:
           writeFormat: binary
           libs: ["libOGL.so"]
      - fvSolution:
            set: solvers/p
            clear: True
            tolerance: 1e-04
            relTol: 0
            maxIter: 5000
      - blockMesh
      - decomposePar:
            method: simple
            numberOfSubdomains: 2
            coeffs: [2,1,1]
variation:
  - operation: fvSolution
    schema: "linear_solver/{solver}{preconditioner}{executor}"
    values:
      - set: solvers/p
        preconditioner: none
        solver: GKOCG
        forceHostBuffer: 1
        verbose: 1
        executor: ${{env.GINKGO_EXECUTOR}}
      - set: solvers/p
        solver: PCG
        preconditioner: none
        executor: CPU
"""


@pytest.mark.integtest
def test_cavity(tmp_path, emmit_test_config):
    with open(tmp_path/"cavity.yaml", "a") as fh:
        fh.write(emmit_test_config)

    check_output(["obr", "init", "--config",  "cavity.yaml"], cwd=tmp_path)
    check_output(["obr", "run", "-o", "fetchCase"])
    check_output(["obr", "run", "-o", "generate"])
    #
    workspace_dir = tmp_path / "workspace"
    assert workspace_dir.exists() == True




