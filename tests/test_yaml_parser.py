import pytest
from pathlib import Path
from subprocess import check_output

from obr.core.parse_yaml import add_includes, parse_variables


@pytest.fixture
def create_include_yaml(tmpdir):
    fn = "test.yaml"

    with open(Path(tmpdir) / fn, "a") as fh:
        for i in range(2):
            fh.write("include_line" + str(i) + "\n")

    # create a subdir
    check_output(["mkdir", "subdir"], cwd=tmpdir)


def test_includes(tmpdir, create_include_yaml):
    test_str = "${{include.test.yaml}}"
    test_str = add_includes(tmpdir, test_str)
    assert "include_line0\ninclude_line1\n" == test_str

    # preceeding ws will be added to all lines as indentation
    test_str = "\t${{include.test.yaml}}"
    test_str = add_includes(tmpdir, test_str)
    assert "\tinclude_line0\n\tinclude_line1\n" == test_str

    # check if relative imports work
    test_str = "${{include..test.yaml}}"
    test_str = add_includes(tmpdir / "subdir", test_str)
    assert "include_line0\ninclude_line1\n" == test_str
