"""
HEATWATCH Data Ingestion — Dataset Constants
=============================================
Controlled vocabulary, source names, and column mappings
for all six ingested datasets.

These constants must stay in sync with the existing database
schema defined in database/migrations/.
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════════
# hotspots.source — allowed values (CHECK constraint in DB)
# ═══════════════════════════════════════════════════════════════
HOTSPOT_SOURCES = frozenset({
    "MODIS_TERRA", "MODIS_AQUA",
    "VIIRS_NOAA20", "VIIRS_NPP",
    "LANDSAT_8", "LANDSAT_9",
    "SENTINEL_2", "SENTINEL_3",
    "GOES_16", "GOES_18",
    "HIMAWARI_9", "OTHER",
})

# ═══════════════════════════════════════════════════════════════
# FIRMS satellite → hotspots.source mapping
# Keys are common FIRMS CSV values; values are DB-allowed sources.
# ═══════════════════════════════════════════════════════════════
FIRMS_SATELLITE_MAP: dict[str, str] = {
    # MODIS variants
    "Terra":        "MODIS_TERRA",
    "TERRA":        "MODIS_TERRA",
    "terra":        "MODIS_TERRA",
    "Aqua":         "MODIS_AQUA",
    "AQUA":         "MODIS_AQUA",
    "aqua":         "MODIS_AQUA",
    # VIIRS variants
    "NOAA-20":      "VIIRS_NOAA20",
    "NOAA20":       "VIIRS_NOAA20",
    "N20":          "VIIRS_NOAA20",
    "J1":           "VIIRS_NOAA20",
    "Suomi NPP":    "VIIRS_NPP",
    "NPP":          "VIIRS_NPP",
    "SNPP":         "VIIRS_NPP",
    # Landsat
    "Landsat-8":    "LANDSAT_8",
    "Landsat8":     "LANDSAT_8",
    "Landsat-9":    "LANDSAT_9",
    "Landsat9":     "LANDSAT_9",
    # Sentinel
    "Sentinel-2":   "SENTINEL_2",
    "Sentinel-3":   "SENTINEL_3",
    # GOES
    "GOES-16":      "GOES_16",
    "GOES16":       "GOES_16",
    "GOES-18":      "GOES_18",
    "GOES18":       "GOES_18",
    # Himawari
    "Himawari-9":   "HIMAWARI_9",
    "Himawari9":    "HIMAWARI_9",
}

# ═══════════════════════════════════════════════════════════════
# FIRMS instrument normalization
# ═══════════════════════════════════════════════════════════════
FIRMS_INSTRUMENT_MAP: dict[str, str] = {
    "MODIS":  "MODIS",
    "VIIRS":  "VIIRS",
    "OLI":    "OLI",
    "SLSTR":  "SLSTR",
    "ABI":    "ABI",
    "AHI":    "AHI",
}

# ═══════════════════════════════════════════════════════════════
# FIRMS CSV column aliases → normalized column names
# Different FIRMS products use slightly different headers.
# ═══════════════════════════════════════════════════════════════
FIRMS_COLUMN_ALIASES: dict[str, str] = {
    # Coordinates
    "latitude":   "latitude",
    "lat":        "latitude",
    "longitude":  "longitude",
    "lon":        "longitude",
    "long":       "longitude",
    # Acquisition
    "acq_date":   "acq_date",
    "acq_time":   "acq_time",
    # Sensor
    "satellite":  "satellite",
    "instrument": "instrument",
    # Brightness temperature
    "brightness":  "brightness",
    "bright_ti4":  "brightness",
    "bright_t21":  "brightness",
    "bright_ti5":  "brightness_2",
    "bright_t31":  "brightness_2",
    # FRP
    "frp":        "frp",
    # Confidence
    "confidence": "confidence",
    # Day/night
    "daynight":   "daynight",
    "day_night":  "daynight",
    # Scan / track
    "scan":       "scan",
    "track":      "track",
    # Version
    "version":    "version",
}

# Required columns that MUST be present in any FIRMS file
FIRMS_REQUIRED_COLUMNS = frozenset({"latitude", "longitude", "acq_date", "acq_time"})

# ═══════════════════════════════════════════════════════════════
# industrial_facilities.facility_type ENUM values
# ═══════════════════════════════════════════════════════════════
FACILITY_TYPES = frozenset({
    "REFINERY", "POWER_PLANT", "STEEL_PLANT",
    "PETROCHEMICAL", "LNG_TERMINAL", "MINING",
    "CEMENT", "CHEMICAL", "OTHER",
})

# Keyword-based auto-classification for industrial facilities
# Maps lowercase substrings to facility_type ENUM values.
FACILITY_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["refinery", "oil refinery", "petroleum refinery"],          "REFINERY"),
    (["power plant", "power station", "thermal power", "coal plant",
      "gas plant", "nuclear plant", "hydro plant"],               "POWER_PLANT"),
    (["steel", "iron", "blast furnace", "sinter"],                "STEEL_PLANT"),
    (["petrochemical", "chemical complex", "naphtha"],            "PETROCHEMICAL"),
    (["lng", "liquefied natural gas", "lng terminal",
      "lng plant", "regasification"],                             "LNG_TERMINAL"),
    (["mine", "mining", "coal mine", "quarry", "open pit"],       "MINING"),
    (["cement", "clinker", "lime kiln"],                          "CEMENT"),
    (["chemical", "fertilizer", "ammonia", "chlorine",
      "acid plant", "caustic soda"],                              "CHEMICAL"),
]

# ═══════════════════════════════════════════════════════════════
# OSM tags → industrial_facilities vs osm_context routing
# ═══════════════════════════════════════════════════════════════
# Tags that indicate a feature is an industrial facility candidate
OSM_INDUSTRIAL_TAGS: dict[str, list[str]] = {
    "landuse":  ["industrial"],
    "man_made": ["petroleum_well", "oil_refinery", "works",
                 "chimney", "storage_tank", "gasometer",
                 "silo", "wastewater_plant"],
    "industrial": ["oil", "gas", "refinery", "steel", "mining",
                   "chemical", "power", "petrochemical", "cement",
                   "coal", "fertilizer", "aluminium"],
    "power":    ["plant"],
    "building": ["industrial"],
}

# ═══════════════════════════════════════════════════════════════
# Land-cover ESA WorldCover class codes → field names
# Reference: ESA WorldCover 10m 2021 v200
# ═══════════════════════════════════════════════════════════════
ESA_WORLDCOVER_CLASSES: dict[int, dict] = {
    10:  {"name": "Tree cover",          "score_field": "tree_cover_score"},
    20:  {"name": "Shrubland",           "score_field": "shrubland_score"},
    30:  {"name": "Grassland",           "score_field": "grassland_score"},
    40:  {"name": "Cropland",            "score_field": "cropland_score"},
    50:  {"name": "Built-up",            "score_field": "built_up_score"},
    60:  {"name": "Bare/sparse veg.",    "score_field": "bare_land_score"},
    70:  {"name": "Snow/ice",            "score_field": None},
    80:  {"name": "Permanent water",     "score_field": "water_score"},
    90:  {"name": "Herbaceous wetland",  "score_field": "grassland_score"},
    95:  {"name": "Mangroves",           "score_field": "tree_cover_score"},
    100: {"name": "Moss/lichen",         "score_field": "bare_land_score"},
}

# Dominant class name lookup (for land_cover_class TEXT field)
ESA_WORLDCOVER_CLASS_NAMES: dict[int, str] = {
    k: v["name"] for k, v in ESA_WORLDCOVER_CLASSES.items()
}

# Dataset / source identifiers
DATASET_SOURCE_FIRMS       = "NASA_FIRMS"
DATASET_SOURCE_FIRMS_HIST  = "NASA_FIRMS_HISTORICAL"
DATASET_SOURCE_OSM         = "OSM"
DATASET_SOURCE_LANDCOVER   = "ESA_WorldCover_2021"
DATASET_SOURCE_INDUSTRIAL  = "INDUSTRIAL_DB"
DATASET_SOURCE_SATELLITE   = "SENTINEL2"
