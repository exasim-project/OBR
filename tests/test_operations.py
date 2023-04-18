from obr.signac_wrapper.operations import _link_path

from subprocess import check_output
from pathlib import Path


def test_link_path(tmpdir):
    check_output(["mkdir", "src"], cwd=tmpdir)
    check_output(["touch", "src/file1"], cwd=tmpdir)
    check_output(["mkdir", "src/fold1"], cwd=tmpdir)
    check_output(["touch", "src/fold1/file2"], cwd=tmpdir)

    _link_path(tmpdir / "src", tmpdir / "dst", copy_instead_link=False)

    dst = Path(tmpdir) / "dst"

    assert dst.exists() == True

    dst_file = dst / "file1"

    assert dst_file.exists() == True
    assert dst_file.is_symlink() == True

    dst_fold = dst / "fold1"
    assert dst_fold.exists() == True
