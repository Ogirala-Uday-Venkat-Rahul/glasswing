"""Convert a value between units of length, mass, or temperature.

Models are unreliable at exact conversions -- they'll approximate miles to km or
fumble Fahrenheit to Celsius. This does it deterministically instead. Pure
Python, no network.

Length and mass are simple ratios, so we express every unit as a multiple of one
base unit (metres, grams) and divide. Temperature is not a ratio -- 0 degrees is
not "no temperature" -- so it needs real formulas, handled separately.
"""

# unit alias -> (dimension, how many base units it equals). Base units: metre
# for length, gram for mass. Aliases are lower-cased before lookup.
_LINEAR = {
    # length (base: metre)
    "m": ("length", 1.0), "meter": ("length", 1.0), "meters": ("length", 1.0),
    "metre": ("length", 1.0), "metres": ("length", 1.0),
    "km": ("length", 1000.0), "kilometer": ("length", 1000.0),
    "kilometers": ("length", 1000.0), "kilometre": ("length", 1000.0),
    "kilometres": ("length", 1000.0),
    "cm": ("length", 0.01), "centimeter": ("length", 0.01),
    "centimeters": ("length", 0.01),
    "mm": ("length", 0.001), "millimeter": ("length", 0.001),
    "millimeters": ("length", 0.001),
    "mi": ("length", 1609.344), "mile": ("length", 1609.344),
    "miles": ("length", 1609.344),
    "yd": ("length", 0.9144), "yard": ("length", 0.9144),
    "yards": ("length", 0.9144),
    "ft": ("length", 0.3048), "foot": ("length", 0.3048),
    "feet": ("length", 0.3048),
    "in": ("length", 0.0254), "inch": ("length", 0.0254),
    "inches": ("length", 0.0254),
    # mass (base: gram)
    "g": ("mass", 1.0), "gram": ("mass", 1.0), "grams": ("mass", 1.0),
    "kg": ("mass", 1000.0), "kilogram": ("mass", 1000.0),
    "kilograms": ("mass", 1000.0),
    "mg": ("mass", 0.001), "milligram": ("mass", 0.001),
    "milligrams": ("mass", 0.001),
    "lb": ("mass", 453.59237), "lbs": ("mass", 453.59237),
    "pound": ("mass", 453.59237), "pounds": ("mass", 453.59237),
    "oz": ("mass", 28.349523125), "ounce": ("mass", 28.349523125),
    "ounces": ("mass", 28.349523125),
}

# temperature aliases -> canonical symbol
_TEMP = {
    "c": "c", "celsius": "c", "centigrade": "c",
    "f": "f", "fahrenheit": "f",
    "k": "k", "kelvin": "k",
}


def _clean(unit: str) -> str:
    return unit.strip().lower().lstrip("°")


def _to_celsius(value: float, unit: str) -> float:
    if unit == "c":
        return value
    if unit == "f":
        return (value - 32) * 5 / 9
    return value - 273.15  # kelvin


def _from_celsius(value: float, unit: str) -> float:
    if unit == "c":
        return value
    if unit == "f":
        return value * 9 / 5 + 32
    return value + 273.15  # kelvin


def _fmt(x: float) -> str:
    # Trim to something readable and drop a pointless trailing ".0".
    r = round(x, 4)
    return str(int(r)) if r == int(r) else str(r)


def convert(value: float, from_unit: str, to_unit: str) -> str:
    src, dst = _clean(from_unit), _clean(to_unit)

    if src in _TEMP and dst in _TEMP:
        celsius = _to_celsius(float(value), _TEMP[src])
        # Nothing can be colder than absolute zero (-273.15 C). Rather than hand
        # back a physically impossible number, reject it so the model can tell
        # the user the input was wrong.
        if celsius < -273.15 - 1e-9:
            raise ValueError("temperature is below absolute zero")
        return f"{_fmt(_from_celsius(celsius, _TEMP[dst]))} {_TEMP[dst]}"

    if src in _LINEAR and dst in _LINEAR:
        src_dim, src_factor = _LINEAR[src]
        dst_dim, dst_factor = _LINEAR[dst]
        if src_dim != dst_dim:
            raise ValueError(f"cannot convert {src_dim} ({src}) to {dst_dim} ({dst})")
        return f"{_fmt(float(value) * src_factor / dst_factor)} {dst}"

    raise ValueError(f"unknown or mismatched units: {from_unit!r} to {to_unit!r}")


SCHEMA = {
    "type": "function",
    "function": {
        "name": "convert",
        "description": (
            "Convert a value between units of length (m, km, cm, mm, mi, yd, ft, "
            "in), mass (g, kg, mg, lb, oz), or temperature (C, F, K). Use this for "
            "any unit conversion instead of computing it yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": "The amount to convert, e.g. 10",
                },
                "from_unit": {
                    "type": "string",
                    "description": "The unit to convert from, e.g. 'mi' or 'F'",
                },
                "to_unit": {
                    "type": "string",
                    "description": "The unit to convert to, e.g. 'km' or 'C'",
                },
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    },
}
