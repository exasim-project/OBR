from obr.core.caseOrigins import CaseOnDisk, OpenFOAMTutorialCase, GitRepo
import os
import pytest


@pytest.mark.skipif(
    not os.environ.get("FOAM_TUTORIALS"), reason="Cannot determine $FOAM_TUTORIALS path"
)
def test_OpenFOAMTutorialCase(tmp_path):
    ofcase = OpenFOAMTutorialCase(
        domain="incompressible", application="icoFoam", case="cavity/cavity"
    )
    ofcase.init(tmp_path)

    assert (tmp_path / "case").exists()
    assert (tmp_path / "case/constant").exists()
    assert (tmp_path / "case/system").exists()
    assert (tmp_path / "case/system/controlDict").exists()


@pytest.mark.skipif(
    not os.environ.get("FOAM_TUTORIALS"), reason="Cannot determine $FOAM_TUTORIALS path"
)
def test_OpenFOAMTutorialCase_raises_if_nonexistent(tmp_path):
    ofcase = OpenFOAMTutorialCase(
        domain="compressible", application="icoFoam", case="cavity/cavity"
    )
    ofcase.init(tmp_path)

    assert (tmp_path / "case").exists()
    assert (tmp_path / "case/constant").exists()
    assert (tmp_path / "case/system").exists()
    assert (tmp_path / "case/system/controlDict").exists()
