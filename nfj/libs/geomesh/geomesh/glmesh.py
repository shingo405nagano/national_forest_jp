"""
タイルメッシュの生成と操作に関するクラスと関数の定義
"""

import math
from dataclasses import dataclass

import geopandas as gpd
import pyproj
import shapely
import yaml

from .data import XY, Bounds
from .formatter import (
    type_checker_crs,
    type_checker_float,
    type_checker_integer,
    type_checker_zoom_level,
)
from .geometries import transform_xy

# 座標の小数点以下の桁数
global decimal_places
DECIMAL_PLACES = 4
# 座標の丸め処理に使用する値
global FLOOR_NUM
FLOOR_NUM = 10**DECIMAL_PLACES


@type_checker_integer(arg_index=0, kward="value")
def floor(value: float) -> float:
    """
    ## Summary:
        指定した小数点以下の桁数で値を切り捨てる関数。
    Args:
        value (float):
            切り捨てる値
    Returns:
        float:
            切り捨てられた値
    """
    return math.floor(value * FLOOR_NUM) / FLOOR_NUM  # type: ignore


# Webメルカトルの座標範囲
tile_scope = Bounds(
    x_min=-20037508.342789244,
    y_min=-20037508.342789244,
    x_max=20037508.342789244,
    y_max=20037508.342789244,
)


@dataclass
class TileDesign:
    """
    ## Summary:
        タイルメッシュの設計を表すデータクラス
    Args:
        zoom_level (int):
            ズームレベル
        x_idx (int):
            タイルのxインデックス
        y_idx (int):
            タイルのyインデックス
        bounds (Bounds):
            タイルのバウンディングボックス
        width (int):
            タイルの幅（ピクセル単位）
        height (int):
            タイルの高さ（ピクセル単位）
        crs (pyproj.CRS):
            タイルの座標参照系。デフォルトはEPSG:3857（Webメルカトル）
    """

    zoom_level: int
    x_idx: int
    y_idx: int
    bounds: Bounds
    width: int
    height: int
    crs: pyproj.CRS = pyproj.CRS.from_epsg(3857)

    @property
    def x_resolution(self) -> float:
        """
        ## Summary:
            タイルのx方向の解像度を計算する関数。
        Returns:
            float:
                タイルのx方向の解像度（メートル/ピクセル）
        """
        resol = (self.bounds.x_max - self.bounds.x_min) / self.width
        return floor(resol)

    @property
    def y_resolution(self) -> float:
        """
        ## Summary:
            タイルのy方向の解像度を計算する関数。
        Returns:
            float:
                タイルのy方向の解像度（メートル/ピクセル）
        """
        resol = (self.bounds.y_max - self.bounds.y_min) / self.height
        return floor(resol)

    @property
    def zxy(self) -> dict[str, int]:
        return {"z": self.zoom_level, "x": self.x_idx, "y": self.y_idx}

    def __str__(self) -> str:
        data = {
            "type": str(type(self)),
            "crs": {
                "name": self.crs.name,
                "epsg": self.crs.to_epsg(),
                "unit": self.crs.axis_info[1].unit_name,
            },
            "XYZ": {
                "x_idx": self.x_idx,
                "y_idx": self.y_idx,
                "zoom_level": self.zoom_level,
            },
            "bounds": {
                "x_min": self.bounds.x_min,
                "y_min": self.bounds.y_min,
                "x_max": self.bounds.x_max,
                "y_max": self.bounds.y_max,
            },
            "resolution": {
                "x_resolution [m/px]": self.x_resolution,
                "y_resolution [m/px]": self.y_resolution,
            },
        }
        return yaml.dump(data, sort_keys=False)


class TileDesigner(object):
    """
    ## Summary:
        タイルメッシュを設計するためのクラス
    Args:
        width (int):
            タイルの幅（ピクセル単位）。デフォルトは256。
        height (int):
            タイルの高さ（ピクセル単位）。デフォルトは256。
    """

    def __init__(self, width: int = 256, height: int = 256):
        self.width = width
        self.height = height
        self.crs = pyproj.CRS.from_epsg(3857)

    def __post_init__(self):
        if self.width <= 0:
            raise ValueError("widthは正の整数で指定してください。")
        if self.height <= 0:
            raise ValueError("heightは正の整数で指定してください。")

    @type_checker_crs(arg_index=4, kward="in_crs")
    def lonlat_to_tile_idx(
        self,
        lon: float,
        lat: float,
        zoom_level: int,
        in_crs: pyproj.CRS,
    ) -> dict:
        """
        ## Summary:
            経緯度とズームレベルからタイルのインデックスを計算する関数。
        Args:
            lon (float):
            lat (float):
            zoom_level (int):
        Returns:
            dict:
                タイルのxインデックスとyインデックスを含む辞書
        """
        if in_crs.to_epsg() != 4326:
            # 入力座標系が経緯度でない場合、変換を行う
            xy = transform_xy(lon, lat, in_crs, "EPSG:4326")
        else:
            xy = XY(lon, lat)
        n = 2.0**zoom_level
        x_index = int((xy.x + 180.0) / 360.0 * n)  # type: ignore
        _y = math.log(math.tan(math.radians(xy.y)) + 1 / math.cos(math.radians(xy.y)))  # type: ignore
        y_index = int(n * (1 - _y / math.pi) / 2)
        return {"x": x_index, "y": y_index}

    def _tile_idx_to_bounds(self, x: int, y: int, zoom_level: int) -> Bounds:
        """
        ## Summary:
            タイルインデックスとズームレベルからバウンディングボックスを計算する関数。
        Args:
            x (int):
                タイルのxインデックス
            y (int):
                タイルのyインデックス
            zoom_level (int):
                ズームレベル
        Returns:
            Bounds:
                タイルのバウンディングボックス
        """

        n = 2.0**zoom_level
        lon_min = x / n * 360.0 - 180.0
        lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
        lon_max = (x + 1) / n * 360.0 - 180.0
        lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
        # Webメルカトルに変換
        sw = transform_xy(lon_min, lat_min, "EPSG:4326", self.crs)
        sw = XY(x=floor(sw.x), y=floor(sw.y))  # type: ignore
        ne = transform_xy(lon_max, lat_max, "EPSG:4326", self.crs)
        ne = XY(x=floor(ne.x), y=floor(ne.y))  # type: ignore
        return Bounds(x_min=sw.x, y_min=sw.y, x_max=ne.x, y_max=ne.y)  # type: ignore

    @type_checker_float(arg_index=1, kward="lon")
    @type_checker_float(arg_index=2, kward="lat")
    @type_checker_integer(arg_index=3, kward="zoom_level")
    @type_checker_zoom_level(arg_index=3, kward="zoom_level")
    def from_lonlat(
        self,  #
        lon: float,
        lat: float,
        zoom_level: int,
        in_crs: pyproj.CRS = pyproj.CRS.from_epsg(4326),
    ) -> TileDesign:
        """
        ## Summary:
            経緯度とズームレベルからタイルデザインを生成する関数。
        """
        tile_idx = self.lonlat_to_tile_idx(lon, lat, zoom_level, in_crs)
        bounds = self._tile_idx_to_bounds(tile_idx["x"], tile_idx["y"], zoom_level)
        return TileDesign(
            zoom_level=zoom_level,
            x_idx=tile_idx["x"],
            y_idx=tile_idx["y"],
            bounds=bounds,
            width=self.width,
            height=self.height,
        )

    @type_checker_integer(arg_index=1, kward="x")
    @type_checker_integer(arg_index=2, kward="y")
    @type_checker_integer(arg_index=3, kward="zoom_level")
    @type_checker_zoom_level(arg_index=3, kward="zoom_level")
    def from_tile_idx(self, x: int, y: int, zoom_level: int) -> TileDesign:
        """
        ## Summary:
            タイルインデックスとズームレベルからタイルデザインを生成する関数。
        """
        bounds = self._tile_idx_to_bounds(x, y, zoom_level)
        return TileDesign(
            zoom_level=zoom_level,
            x_idx=x,
            y_idx=y,
            bounds=bounds,
            width=self.width,
            height=self.height,
        )

    @type_checker_float(arg_index=1, kward="x_min")
    @type_checker_float(arg_index=2, kward="y_min")
    @type_checker_float(arg_index=3, kward="x_max")
    @type_checker_float(arg_index=4, kward="y_max")
    @type_checker_integer(arg_index=5, kward="zoom_level")
    @type_checker_zoom_level(arg_index=5, kward="zoom_level")
    @type_checker_crs(arg_index=6, kward="in_crs")
    def tiles(
        self,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        zoom_level: int,
        in_crs: pyproj.CRS | int | str = 4326,
        geodataframe: bool = False,
    ) -> list[TileDesign] | gpd.GeoDataFrame:
        """
        ## Summary:
            タイルインデックスの範囲とズームレベルからタイルデザインのリストを生成する関数。
        Args:
            x_min (int):
                x座標の最小値
            y_min (int):
                y座標の最小値
            x_max (int):
                x座標の最大値
            y_max (int):
                y座標の最大値
            zoom_level (int):
                ズームレベル
            in_crs (pyproj.CRS):
                入力座標系。デフォルトはEPSG:4326（経緯度）
            geodataframe (bool):
                タイルデザインのリストをGeoPandasのDataFrameとして返すかどうか。デフォルトはFalse。
        Returns:
            list[TileDesign]:
                タイルデザインのリスト
        """
        # 左下と右上のタイルインデックスを取得
        sw_tile_idx = self.lonlat_to_tile_idx(x_min, y_min, zoom_level, in_crs)  # type: ignore
        ne_tile_idx = self.lonlat_to_tile_idx(x_max, y_max, zoom_level, in_crs)  # type: ignore
        # タイルインデックスの範囲内でタイルデザインを生成
        designs = []
        for x_idx in range(sw_tile_idx["x"], ne_tile_idx["x"] + 1):
            for y_idx in range(ne_tile_idx["y"], sw_tile_idx["y"] + 1):
                design = self.from_tile_idx(x_idx, y_idx, zoom_level)
                designs.append(design)
        if geodataframe:
            return self._tiles_to_dataframe(designs)
        return designs

    def _tiles_to_dataframe(self, designs: list[TileDesign]) -> gpd.GeoDataFrame:
        """
        ## Summary:
            タイルデザインのリストをGeoPandasのDataFrameに変換する関数。
        Args:
            designs (list[TileDesign]):
                タイルデザインのリスト
        """
        data = {
            "zoom_level": [design.zoom_level for design in designs],
            "x_idx": [design.x_idx for design in designs],
            "y_idx": [design.y_idx for design in designs],
            "x_resolution": [design.x_resolution for design in designs],
            "y_resolution": [design.y_resolution for design in designs],
            "zxy": [design.zxy for design in designs],
        }
        polys = [shapely.box(*design.bounds) for design in designs]
        gdf = gpd.GeoDataFrame(data=data, geometry=polys, crs=self.crs)
        return gdf
