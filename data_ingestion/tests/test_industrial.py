"""
Tests for industrial facility normalizer.
Unit tests — no database required.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.datasets import FACILITY_TYPES
from industrial.normalizer import _map_facility_type


@pytest.mark.parametrize("raw,expected", [
    ("REFINERY",      "REFINERY"),
    ("refinery",      "REFINERY"),
    ("oil refinery",  "REFINERY"),
    ("power plant",   "POWER_PLANT"),
    ("POWER_PLANT",   "POWER_PLANT"),
    ("Steel Plant",   "STEEL_PLANT"),
    ("lng terminal",  "LNG_TERMINAL"),
    ("coal mine",     "MINING"),
    ("cement works",  "CEMENT"),
    ("chemical plant","CHEMICAL"),
    ("unknown xyz",   "OTHER"),
    ("",              "OTHER"),
    (None,            "OTHER"),
])
def test_map_facility_type(raw, expected):
    result = _map_facility_type(raw)
    assert result == expected, f"_map_facility_type({raw!r}) = {result!r}, expected {expected!r}"


def test_all_mapped_types_are_valid_enum_values():
    """Every mapped type must be a valid ENUM value."""
    test_inputs = [
        "refinery", "power plant", "steel mill", "lng",
        "mine", "cement", "chemical", "petrochem", "unknown"
    ]
    for inp in test_inputs:
        result = _map_facility_type(inp)
        assert result in FACILITY_TYPES, f"{result!r} is not a valid FACILITY_TYPES value"
