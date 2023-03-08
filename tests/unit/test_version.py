import re

from pysmx.version import get_version_number


# Make sure version matches PEP440
def test_version_string():
    # Regex found here:
    # https://www.python.org/dev/peps/pep-0440/#appendix-b-parsing-version-strings-with-regular-expressions
    regex = (
        r"^([1-9][0-9]*!)"
        r"?(0|[1-9][0-9]*)"
        r"(\.(0|[1-9][0-9]*))*((a|b|rc)(0|[1-9][0-9]*))"
        r"?(\.post(0|[1-9][0-9]*))"
        r"?(\.dev(0|[1-9][0-9]*))?$"
    )

    assert re.search(regex, get_version_number())
