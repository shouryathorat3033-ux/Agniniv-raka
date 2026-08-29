"""
Tests for OSM classifier (normalizer).
Unit tests — no database or real OSM files required.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from osm.normalizer import _is_industrial, _classify_facility_type


@pytest.mark.parametrize("tags,expected_industrial", [
    ({"landuse": "industrial"},                True),
    ({"man_made": "oil_refinery"},             True),
    ({"industrial": "oil"},                    True),
    ({"power": "plant"},                       True),
    ({"building": "industrial"},               True),
    ({"man_made": "works"},                    True),
    ({"amenity": "restaurant"},                False),
    ({"landuse": "residential"},               False),
    ({},                                       False),
])
def test_is_industrial_classification(tags, expected_industrial):
    result = _is_industrial(tags)
    assert result == expected_industrial, f"_is_industrial({tags}) = {result}, expected {expected_industrial}"


@pytest.mark.parametrize("tags,name,expected_type", [
    ({"industrial": "oil"},    "Oil Refinery",    "REFINERY"),
    ({"industrial": "steel"},  "Steel Works",     "STEEL_PLANT"),
    ({"power": "plant"},       "Power Station",   "POWER_PLANT"),
    ({"industrial": "mining"}, "Coal Mine",       "MINING"),
    ({"industrial": "cement"}, "Cement Factory",  "CEMENT"),
    ({},                       "Unknown Site",    "OTHER"),
])
def test_classify_facility_type(tags, name, expected_type):
    result = _classify_facility_type(tags, name)
    assert result == expected_type, f"_classify_facility_type({tags}, {name!r}) = {result!r}, expected {expected_type!r}"
