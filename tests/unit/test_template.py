from pysmx.template import function_test


def test_function_test():
    data = 2
    expected = 4
    assert function_test(data) == expected
