from obr.core.caseOrigins import CaseOnDisk, OpenFOAMTutorialCase, GitRepo


def test_OpenFOAMTutorialCase(tmp_path):
    ofcase = OpenFOAMTutorialCase(
        domain="incompressible", solver="icoFoam", case="cavity/cavity"
    )
    ofcase.init(tmp_path)

    assert (tmp_path / "case").exists()
    assert (tmp_path / "case/constant").exists()
    assert (tmp_path / "case/system").exists()
    assert (tmp_path / "case/system/controlDict").exists()


def test_OpenFOAMTutorialCase_raises_if_nonexistent(tmp_path):
    ofcase = OpenFOAMTutorialCase(
        domain="compressible", solver="icoFoam", case="cavity/cavity"
    )
    ofcase.init(tmp_path)

    assert (tmp_path / "case").exists()
    assert (tmp_path / "case/constant").exists()
    assert (tmp_path / "case/system").exists()
    assert (tmp_path / "case/system/controlDict").exists()
