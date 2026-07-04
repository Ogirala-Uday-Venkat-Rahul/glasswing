import pytest

from agent.tools.calculator import calculator


def test_basic_arithmetic():
    assert calculator("2 + 2") == "4"


def test_precedence_and_parens():
    assert calculator("37 * (12 + 5)") == "629"


def test_power_and_unary():
    assert calculator("-2 ** 3") == "-8"


def test_rejects_names():
    # A bare name is not arithmetic and must be refused.
    with pytest.raises(ValueError):
        calculator("__import__('os')")


def test_rejects_function_calls():
    with pytest.raises(ValueError):
        calculator("pow(2, 3)")


def test_rejects_huge_exponent_without_hanging():
    # "9**9**9" would build a ~370-million-digit integer and hang the process.
    # The exponent is checked before the power runs, so this returns fast.
    with pytest.raises(ValueError):
        calculator("9**9**9")


def test_allows_reasonable_exponent():
    assert calculator("2 ** 10") == "1024"


def test_rejects_booleans():
    # bool is an int subclass; make sure it is not accepted as a number.
    with pytest.raises(ValueError):
        calculator("True + 1")
