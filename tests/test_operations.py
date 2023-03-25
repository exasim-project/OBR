from obr.signac_wrapper.operations import _link_path

from subprocess import check_output
from pathlib import Path


def test_link_path(tmpdir):
    check_output(["mkdir", "foo"], cwd=tmpdir)
    check_output(["touch", "foo/bar"], cwd=tmpdir)

    _link_path(tmpdir / "foo", tmpdir / "bar", copy_instead_link=False)

    dst = Path(tmpdir) / "bar"

    assert dst.exists() == True

    dst_bar = dst / "bar"

    assert dst_bar.exists() == True
    assert dst_bar.is_symlink() == True
