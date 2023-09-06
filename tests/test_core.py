from obr.core.core import get_mesh_stats
from pathlib import Path
import pytest


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
