from enum import Enum


class OutputGeoJsonType(Enum):
    STRING = 0
    BYTES = 1
    DICT = 2
    PATH = 3


class OutputGeoPackageType(Enum):
    GPKG = 0
    PATH = 1
