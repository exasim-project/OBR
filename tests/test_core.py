import obr
import os
import pytest

from obr.core.core import (
    get_mesh_stats,
    TemporaryFolder,
    link_folder_to_copy,
    DelinkFolder,
)
from pathlib import Path
from subprocess import check_output


@pytest.fixture
def create_ansa_owner(tmpdir):
    fn = "owner"
    owner_content = """/*--------------------------------------------------------------------------------------------*\
|                                                                                              |
|    ANSA_VERSION: 22.1.0                                                                      |
|                                                                                              |
|    file created by  A N S A  Wed Mar  9 13:20:26 2022                                        |
|                                                                                              |
|    Output from: /home/mockett/Projects_TechActive/AutoCFD-3/Case01/GridConversion/c1g1.ccm   |
|                                                                                              |
\\*--------------------------------------------------------------------------------------------*/



FoamFile
{
        version 2.0;
        format binary;
        class labelList;

        note "nCells:6307136 nActiveFaces:19135515 nActivePoints:6517376";

        location "";
        object owner;
}
/*---------------------------------------------------------------------------*/
"""
    with open(Path(tmpdir) / fn, "a") as fh:
        fh.write(owner_content)


@pytest.fixture
def create_of_default_owner(tmpdir):
    fn = "owner"
    owner_content = """/*--------------------------------------------------------------------------------------------*\
/*--------------------------------*- C++ -*----------------------------------*\
| =========                 |                                                 |
| \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\    /   O peration     | Version:  2306                                  |
|   \\  /    A nd           | Website:  www.openfoam.com                      |
|    \\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      binary;
    arch        "LSB;label=32;scalar=64";
    note        "nPoints:26057759  nCells:25228544  nFaces:76530828  nInternalFaces:75633500";
    class       labelList;
    location    "constant/polyMesh";
    object      owner;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""
    with open(Path(tmpdir) / fn, "a") as fh:
        fh.write(owner_content)


def test_ansa_owner(tmpdir, create_ansa_owner):
    mesh_stats = get_mesh_stats(f"{tmpdir}/owner")
    assert mesh_stats["nCells"] == 6307136
    assert mesh_stats["nFaces"] == 19135515


def test_default_owner(tmpdir, create_of_default_owner):
    mesh_stats = get_mesh_stats(f"{tmpdir}/owner")
    assert mesh_stats["nCells"] == 25228544
    assert mesh_stats["nFaces"] == 76530828


def test_obr_has_a_version():
    assert obr.__version__ != ""
    assert obr.__version__ != "0.0.0"


def test_TemporaryFolder(tmpdir):
    def create_tmp_dir(test_dir, test_target):
        test_file = test_dir / "test_file"
        with open(test_file, "w") as fh:
            fh.write("foo")
        tmp_folder = TemporaryFolder(test_dir, test_target)
        # test that test_target was created
        assert test_target.exists()
        # test that test_target also contains the test file
        assert (test_target / "test_file").exists()

    tmpdir = Path(tmpdir)
    test_dir = tmpdir / "test"
    test_dir.mkdir()
    test_target_dir = tmpdir / "test_target"
    create_tmp_dir(test_dir, test_target_dir)

    # outside the scope of create_tmp_dir test_target_dir should
    # be already deleted
    assert not test_target_dir.exists()


def test_link_folder_to_copy(tmpdir):
    def create_unlink_dir(source_dir):
        bck_dir = link_folder_to_copy(source_dir)

        # the backup dir was created
        assert bck_dir.exists()
        # the backup contains the test_file
        assert (bck_dir / "test_file").exists()
        # the test_file is still a symlink
        assert (bck_dir / "test_file").is_symlink()

        # the new source path has been created
        assert source_dir.exists()
        # the new source contains a  test file
        assert (source_dir / "test_file").exists()
        # the new test_file is not a symlink
        assert not (source_dir / "test_file").is_symlink()

    tmpdir = Path(tmpdir)
    test_dir = tmpdir / "test"
    test_dir.mkdir()

    check_output(["ln", "-s", "/bin/bash", test_dir / "test_file"], cwd=tmpdir)
    create_unlink_dir(test_dir)


def test_DelinkFolder(tmpdir):
    def create_unlink_dir(source_dir):
        bck_dir = DelinkFolder(source_dir)

        assert source_dir.exists()
        assert (source_dir / "../test.bck").exists()

    tmpdir = Path(tmpdir)
    test_dir = tmpdir / "test"
    test_dir.mkdir()

    check_output(["ln", "-s", "/bin/bash", test_dir / "test_file"], cwd=tmpdir)
    create_unlink_dir(test_dir)

    # outside the create_unlink_dir the bck folder should not exist anymore
    assert not (tmpdir / "test.bck").exists()
