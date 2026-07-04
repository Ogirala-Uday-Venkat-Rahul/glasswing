import pytest

from agent.tools.convert import convert


def test_length_miles_to_km():
    assert convert(10, "mi", "km") == "16.0934 km"


def test_length_is_symmetric():
    # 1 inch is exactly 2.54 cm.
    assert convert(1, "in", "cm") == "2.54 cm"


def test_mass_pounds_to_kg():
    assert convert(10, "lb", "kg") == "4.5359 kg"


def test_temperature_boiling_point():
    assert convert(100, "C", "F") == "212 f"


def test_temperature_accepts_degree_symbol_and_case():
    assert convert(32, "°F", "c") == "0 c"


def test_rejects_cross_dimension():
    # Length to mass is meaningless and must be refused.
    with pytest.raises(ValueError):
        convert(5, "km", "kg")


def test_rejects_unknown_unit():
    with pytest.raises(ValueError):
        convert(5, "smoots", "m")


def test_rejects_below_absolute_zero():
    # -300 C is colder than absolute zero and must be refused, not converted.
    with pytest.raises(ValueError):
        convert(-300, "C", "F")


def test_allows_absolute_zero_exactly():
    # 0 K is exactly absolute zero and is a valid temperature.
    assert convert(0, "K", "C") == "-273.15 c"
