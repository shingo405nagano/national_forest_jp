"""
日本のメッシュコードに関するクラスと関数の定義
"""

import math
from decimal import Decimal
from typing import NamedTuple

import geopandas as gpd
import numpy as np
import shapely
import yaml

from .data import Bounds
from .formatter import type_checker_float, valid_names
from .geometries import dms_to_degree_lonlat, str_dms_to_degree

global DIGITS
DIGITS = 10
global SCALE
SCALE = 10**DIGITS


class _Cds(NamedTuple):
    lon: int
    lat: int
    lon_sec: int
    lat_sec: int
    lon_std: int
    lat_std: int


class MeshCodeJP(object):
    @type_checker_float(arg_index=1, kward="lon")
    @type_checker_float(arg_index=2, kward="lat")
    def __init__(self, lon: float, lat: float, is_dms: bool = False):
        if is_dms:
            # 経緯度がDMS形式の場合、度分秒を度に変換
            xy = dms_to_degree_lonlat(lon, lat)
            lon = xy.x  # type: ignore
            lat = xy.y  # type: ignore

        mesh = self._mesh_code(lon, lat)
        self.first_mesh_code: str = mesh["first_mesh_code"]
        self.secandary_mesh_code: str = mesh["secandary_mesh_code"]
        self.standard_mesh_code: str = mesh["standard_mesh_code"]
        self.half_mesh_code: str = mesh["half_mesh_code"]
        self.quarter_mesh_code: str = mesh["quarter_mesh_code"]
        self._cds = self._coordinates()

    def _mesh_code(self, lon: float, lat: float) -> dict[str, str]:
        """
        ## Description:
            この計算に使用されている1文字の変数名は[地域メッシュ統計の特質・沿革 p12]
            (https://www.stat.go.jp/data/mesh/pdf/gaiyo1.pdf)を参考にしています。
        ## Args:
            lon (float):
                経度（10進法）
            lat (float):
                緯度（10進法）
        ## Returns:
            dict[str, str]:
                メッシュコードの各部分を含む辞書
                - first_mesh_code: 第1次メッシュコード
                - secandary_mesh_code: 第2次メッシュコード
                - standard_mesh_code: 基準地域メッシュコード
                - half_mesh_code: 2分の1地域メッシュコード
                - quarter_mesh_code: 4分の1地域メッシュコード
        """
        # latitude
        p, a = divmod(lat * 60, 40)
        q, b = divmod(a, 5)
        r, c = divmod(b * 60, 30)
        s, d = divmod(c, 15)
        t, e = divmod(b, 7.5)
        first_lat_code = str(int(p))
        secandary_lat_code = str(int(q))
        standard_lat_code = str(int(r))
        # longitude
        f, i = math.modf(lon)
        u = int(i - 100)
        v, g = divmod(f * 60, 7.5)
        w, h = divmod(g * 60, 45)
        x, j = divmod(h, 22.5)
        y, j = divmod(j, 11.25)
        first_lon_code = str(int(u))
        secandary_lon_code = str(int(v))
        standard_lon_code = str(int(w))
        m = str(int((s * 2) + (x + 1)))
        lat_in_half = int(d / 7.5)
        n = str(int((lat_in_half * 2) + (y + 1)))
        first_mesh_code = first_lat_code + first_lon_code
        secandary_mesh_code = first_mesh_code + secandary_lat_code + secandary_lon_code
        standard_mesh_code = secandary_mesh_code + standard_lat_code + standard_lon_code
        half_mesh_code = standard_mesh_code + m
        quarter_mesh_code = half_mesh_code + n
        return {
            "first_mesh_code": first_mesh_code,
            "secandary_mesh_code": secandary_mesh_code,
            "standard_mesh_code": standard_mesh_code,
            "half_mesh_code": half_mesh_code,
            "quarter_mesh_code": quarter_mesh_code,
        }

    def _coordinates(self) -> _Cds:
        first_lon = int(self.first_mesh_code[2:4]) + 100
        first_lat = int(self.first_mesh_code[0:2])
        secandary_lon = int(self.secandary_mesh_code[5:6])
        secandary_lat = int(self.secandary_mesh_code[4:5])
        standard_lon = int(self.standard_mesh_code[7:8])
        standard_lat = int(self.standard_mesh_code[6:7])
        return _Cds(
            lon=first_lon,
            lat=first_lat,
            lon_sec=secandary_lon,
            lat_sec=secandary_lat,
            lon_std=standard_lon,
            lat_std=standard_lat,
        )

    def get_mesh_code(self, mesh_name: str) -> str:
        """
        ## Summary:
            指定されたメッシュ名に対応するメッシュコードを取得する関数
        Args:
            mesh_name (str):
                取得したいメッシュの名前。'1st', '2nd', 'standard', 'half', 'quarter'のいずれか。
        Returns:
            str:
                指定されたメッシュ名に対応するメッシュコード
        """
        if mesh_name == "1st":
            return self.first_mesh_code
        elif mesh_name == "2nd":
            return self.secandary_mesh_code
        elif mesh_name == "standard":
            return self.standard_mesh_code
        elif mesh_name == "half":
            return self.half_mesh_code
        elif mesh_name == "quarter":
            return self.quarter_mesh_code
        else:
            raise ValueError(
                f"mesh_name must be one of ['1st', '2nd', 'standard', 'half', 'quarter'], got: {mesh_name}"
            )

    def first_mesh(self) -> Bounds:
        """
        ## Summary:
            第1次メッシュの境界を取得する関数
        Returns:
            Bounds:
                第1次メッシュの境界
        """
        lat = int(self.first_mesh_code[0:2])
        lon = int(self.first_mesh_code[2:4]) + 100
        # 整数演算による高精度計算（10**10倍で整数化）
        SCALE = 10**10

        # 第1次メッシュのサイズを高精度整数化
        # 経度方向: 1度 = SCALE
        first_lon_size_int = SCALE
        # 緯度方向: 40/60度 = 2/3度 = SCALE * 2 // 3
        first_lat_size_int = SCALE * 2 // 3

        # 整数演算で境界を計算
        x_min_int = lon * first_lon_size_int
        x_max_int = (lon + 1) * first_lon_size_int
        y_min_int = lat * first_lat_size_int
        y_max_int = (lat + 1) * first_lat_size_int

        # 整数から小数に変換
        x_min_final = x_min_int / SCALE
        x_max_final = x_max_int / SCALE
        y_min_final = y_min_int / SCALE
        y_max_final = y_max_int / SCALE

        return Bounds(x_min_final, y_min_final, x_max_final, y_max_final)

    def secandary_mesh(self) -> Bounds:
        """
        ## Summary:
            第2次メッシュの境界を取得する関数
        Returns:
            Bounds:
                第2次メッシュの境界
        """
        # 整数演算による高精度計算（10**10倍で整数化）
        lon_scaled = self._cds.lon * SCALE
        lat_base_scaled = int((self._cds.lat * 40 / 60) * SCALE)
        lon_int = int(lon_scaled)
        lat_int = int(lat_base_scaled)

        # 第2次メッシュのサイズを高精度整数化
        # 経度方向: 0.125度 = SCALE / 8
        sec_lon_size_int = SCALE // 8
        # 緯度方向: 5/60度 = 1/12度 = SCALE / 12
        sec_lat_size_int = SCALE // 12

        # 整数演算で境界を計算
        x_min_int = lon_int + (self._cds.lon_sec * sec_lon_size_int)
        x_max_int = lon_int + ((self._cds.lon_sec + 1) * sec_lon_size_int)
        y_min_int = lat_int + (self._cds.lat_sec * sec_lat_size_int)
        y_max_int = lat_int + ((self._cds.lat_sec + 1) * sec_lat_size_int)

        # 整数から小数に変換
        x_min = x_min_int / SCALE
        x_max = x_max_int / SCALE
        y_min = y_min_int / SCALE
        y_max = y_max_int / SCALE

        return Bounds(x_min, y_min, x_max, y_max)

    def standard_mesh(self) -> Bounds:
        """
        ## Summary:
            基準地域メッシュの境界を取得する関数
        Returns:
            Bounds:
                基準地域メッシュの境界
        """
        cds = self._cds
        # 整数演算による高精度計算（10**10倍で整数化、roundではなくint変換）
        # 第2次メッシュ内の位置を計算
        sec_x_min = cds.lon + (cds.lon_sec * 7.5 / 60)
        sec_y_min = (cds.lat * 40 / 60) + (cds.lat_sec * 5 / 60)

        sec_x_min_scaled = sec_x_min * SCALE
        sec_y_min_scaled = sec_y_min * SCALE
        sec_x_min_int = int(sec_x_min_scaled)
        sec_y_min_int = int(sec_y_min_scaled)

        # 基準地域メッシュのサイズを高精度整数化
        # 経度方向: 0.75分 = 0.0125度 = 1250000000000000 (SCALE単位)
        std_lon_size_int = SCALE // 80  # 0.0125 = 1/80
        # 緯度方向: 0.5分 = 0.00833333...度 = 8333333333333333.33... (SCALE単位)
        # 正確には 1/120度なので SCALE // 120
        std_lat_size_int = SCALE // 120  # 0.5/60 = 1/120

        # 整数演算で境界を計算
        x_min_int = sec_x_min_int + (cds.lon_std * std_lon_size_int)
        x_max_int = sec_x_min_int + (cds.lon_std + 1) * std_lon_size_int
        y_min_int = sec_y_min_int + (cds.lat_std * std_lat_size_int)
        y_max_int = sec_y_min_int + (cds.lat_std + 1) * std_lat_size_int

        # 整数から小数に変換
        x_min_final = x_min_int / SCALE
        x_max_final = x_max_int / SCALE
        y_min_final = y_min_int / SCALE
        y_max_final = y_max_int / SCALE

        return Bounds(x_min_final, y_min_final, x_max_final, y_max_final)

    def half_mesh(self) -> Bounds:
        """
        ## Summary:
            2分の1地域メッシュの境界を取得する関数
        Returns:
            Bounds:
                2分の1地域メッシュの境界
        """
        half_code = int(self.half_mesh_code[8:9])

        # 基準地域メッシュの境界を計算
        standard_bounds = self.standard_mesh()
        std_x_min = Decimal(f"{standard_bounds.x_min}")
        std_y_min = Decimal(f"{standard_bounds.y_min}")

        # 2分の1メッシュのコード解析（1-4の値）
        # 1: 南西, 2: 南東, 3: 北西, 4: 北東
        if half_code == 1:  # 南西
            x_offset, y_offset = 0, 0
        elif half_code == 2:  # 南東
            x_offset, y_offset = 1, 0
        elif half_code == 3:  # 北西
            x_offset, y_offset = 0, 1
        elif half_code == 4:  # 北東
            x_offset, y_offset = 1, 1
        else:
            raise ValueError(f"Invalid half mesh code: {half_code}")

        # 整数演算による高精度計算（10**10倍で整数化）
        SCALE = 10**10

        # Decimal境界を整数化（roundを使わない）
        std_x_min_scaled = std_x_min * SCALE
        std_y_min_scaled = std_y_min * SCALE
        std_x_min_int = int(std_x_min_scaled)
        std_y_min_int = int(std_y_min_scaled)

        # 2分の1メッシュのサイズを高精度整数化
        # 経度方向: 0.00625度 = SCALE / 160
        half_lon_size_int = SCALE // 160
        # 緯度方向: 0.25/60度 = 1/240度 = SCALE / 240
        half_lat_size_int = SCALE // 240

        # 整数演算で境界を計算
        x_min_int = std_x_min_int + (x_offset * half_lon_size_int)
        x_max_int = std_x_min_int + ((x_offset + 1) * half_lon_size_int)
        y_min_int = std_y_min_int + (y_offset * half_lat_size_int)
        y_max_int = std_y_min_int + ((y_offset + 1) * half_lat_size_int)

        # 整数から小数に変換
        x_min_final = x_min_int / SCALE
        x_max_final = x_max_int / SCALE
        y_min_final = y_min_int / SCALE
        y_max_final = y_max_int / SCALE

        return Bounds(x_min_final, y_min_final, x_max_final, y_max_final)

    def quarter_mesh(self) -> Bounds:
        """
        ## Summary:
            4分の1地域メッシュの境界を取得する関数
        Returns:
            Bounds:
                4分の1地域メッシュの境界
        """
        half_code = int(self.quarter_mesh_code[8:9])
        quarter_code = int(self.quarter_mesh_code[9:10])

        # 基準地域メッシュの境界を計算
        standard_bounds = self.standard_mesh()
        std_x_min = Decimal(f"{standard_bounds.x_min}")
        std_y_min = Decimal(f"{standard_bounds.y_min}")

        # 2分の1メッシュの境界を計算
        # 1: 南西, 2: 南東, 3: 北西, 4: 北東
        if half_code == 1:  # 南西
            half_x_offset, half_y_offset = 0, 0
        elif half_code == 2:  # 南東
            half_x_offset, half_y_offset = 1, 0
        elif half_code == 3:  # 北西
            half_x_offset, half_y_offset = 0, 1
        elif half_code == 4:  # 北東
            half_x_offset, half_y_offset = 1, 1
        else:
            raise ValueError(f"Invalid half mesh code: {half_code}")

        half_x_min = std_x_min + (half_x_offset * Decimal("0.375") / 60)
        half_y_min = std_y_min + (half_y_offset * Decimal("0.25") / 60)

        # 4分の1メッシュのコード解析（1-4の値）
        # 1: 南西, 2: 南東, 3: 北西, 4: 北東
        if quarter_code == 1:  # 南西
            quarter_x_offset, quarter_y_offset = 0, 0
        elif quarter_code == 2:  # 南東
            quarter_x_offset, quarter_y_offset = 1, 0
        elif quarter_code == 3:  # 北西
            quarter_x_offset, quarter_y_offset = 0, 1
        elif quarter_code == 4:  # 北東
            quarter_x_offset, quarter_y_offset = 1, 1
        else:
            raise ValueError(f"Invalid quarter mesh code: {quarter_code}")

        # 整数演算による高精度計算（10**10倍で整数化）
        SCALE = 10**10

        # Decimal境界を整数化（roundを使わない）
        half_x_min_scaled = half_x_min * SCALE
        half_y_min_scaled = half_y_min * SCALE
        half_x_min_int = int(half_x_min_scaled)
        half_y_min_int = int(half_y_min_scaled)

        # 4分の1メッシュのサイズを高精度整数化
        # 経度方向: 0.003125度 = 1/320度 = SCALE / 320
        quarter_lon_size_int = SCALE // 320
        # 緯度方向: 0.125/60度 = 1/480度 = SCALE / 480
        quarter_lat_size_int = SCALE // 480

        # 整数演算で境界を計算
        x_min_int = half_x_min_int + (quarter_x_offset * quarter_lon_size_int)
        x_max_int = half_x_min_int + ((quarter_x_offset + 1) * quarter_lon_size_int)
        y_min_int = half_y_min_int + (quarter_y_offset * quarter_lat_size_int)
        y_max_int = half_y_min_int + ((quarter_y_offset + 1) * quarter_lat_size_int)

        # 整数から小数に変換
        x_min_final = x_min_int / SCALE
        x_max_final = x_max_int / SCALE
        y_min_final = y_min_int / SCALE
        y_max_final = y_max_int / SCALE

        return Bounds(x_min_final, y_min_final, x_max_final, y_max_final)

    def __str__(self) -> str:
        data = {
            "first_mesh_code": self.first_mesh_code,
            "secandary_mesh_code": self.secandary_mesh_code,
            "standard_mesh_code": self.standard_mesh_code,
            "half_mesh_code": self.half_mesh_code,
            "quarter_mesh_code": self.quarter_mesh_code,
        }
        return yaml.dump(data, allow_unicode=True, sort_keys=False)


def generate_jpmesh(
    x_min: float,  #
    y_min: float,
    x_max: float,
    y_max: float,
    mesh_name: str,
) -> gpd.GeoDataFrame:
    """
    ## Summary:
        指定された範囲内で、指定の地域メッシュを生成する関数。
    Args:
        x_min (float):
            範囲の最小経度（10進法）
        y_min (float):
            範囲の最小緯度（10進法）
        x_max (float):
            範囲の最大経度（10進法）
        y_max (float):
            範囲の最大緯度（10進法）
        mesh_name (str):
            生成するメッシュの名前。'1st', '2nd', 'standard', 'half', 'quarter'のいずれか。
    Returns:
        gpd.GeoDataFrame:
            生成された地域メッシュのGeoDataFrame
    """
    # 範囲の検証
    if x_min >= x_max or y_min >= y_max:
        raise ValueError("Invalid range: min values must be less than max values")
    # メッシュのステップ値を取得
    steps = _get_step(mesh_name)
    step_lon = int(steps["lon"] * SCALE)
    step_lat = int(steps["lat"] * SCALE)
    # 範囲をメッシュの刻みに合わせて調整、そして整数にスケール変換
    _bounds = _resize_mesh(x_min, y_min, x_max, y_max, mesh_name)
    bounds = Bounds(*[int(v * SCALE) for v in _bounds])
    # Numpyでmeshgridを作成
    x_sequential = np.arange(
        start=bounds.x_min, stop=bounds.x_max + step_lon, step=step_lon
    ).round(DIGITS)
    y_sequential = np.arange(
        start=bounds.y_min, stop=bounds.y_max + step_lat, step=step_lat
    )[::-1].round(DIGITS)
    mesh_code_lst = []
    geoms = []
    for x_min, x_max in zip(x_sequential[:-1], x_sequential[1:]):
        for y_min, y_max in zip(y_sequential[:-1], y_sequential[1:]):
            # Scaleを戻して境界を作成
            mesh_bounds = Bounds(*[v / SCALE for v in [x_min, y_min, x_max, y_max]])
            geom = shapely.box(*mesh_bounds)
            # MeshCodeJPオブジェクトを作成してメッシュコードを取得
            cnt_x = (mesh_bounds.x_max + mesh_bounds.x_min) / 2
            cnt_y = (mesh_bounds.y_max + mesh_bounds.y_min) / 2
            mesh_obj = MeshCodeJP(cnt_x, cnt_y)
            mesh_code = mesh_obj.get_mesh_code(mesh_name)
            mesh_code_lst.append(mesh_code)
            geoms.append(geom)

    # GeoDataFrameを作成
    gdf = gpd.GeoDataFrame(
        data={"mesh_code": mesh_code_lst}, geometry=geoms, crs="EPSG:4326"
    )
    return gdf


def _get_step(mesh_name: str) -> dict[str, float]:
    """
    ## Summary:
        メッシュの種類に応じた経度・緯度のステップ値を取得するヘルパー関数
    Args:
        mesh_name (str):
            メッシュの種類。'1st', '2nd', 'standard', 'half', 'quarter'のいずれか。
    Returns:
        dict[str, float]:
            - lon: 経度方向のステップ値
            - lat: 緯度方向のステップ値
    """
    steps = {
        "1st": {
            "lon": str_dms_to_degree(1, 0, 0),  # 1度
            "lat": str_dms_to_degree(0, 40, 0),  # 40分
        },
        "2nd": {
            "lon": str_dms_to_degree(0, 7, 30),  # 7.5分
            "lat": str_dms_to_degree(0, 5, 0),  # 5分
        },
        "standard": {
            "lon": str_dms_to_degree(0, 0, 45),  # 45秒
            "lat": str_dms_to_degree(0, 0, 30),  # 30秒
        },
        "half": {
            "lon": str_dms_to_degree(0, 0, 22.5),  # 22.5秒
            "lat": str_dms_to_degree(0, 0, 15),  # 15秒
        },
        "quarter": {
            "lon": str_dms_to_degree(0, 0, 11.25),  # 11.25秒
            "lat": str_dms_to_degree(0, 0, 7.5),  # 7.5秒
        },
    }
    if mesh_name not in steps:
        raise ValueError(
            f"mesh_name must be one of {list(steps.keys())}, got: {mesh_name}"
        )
    return steps[mesh_name]


@valid_names(
    arg_index=4,
    kward="mesh_name",
    valid_names=["1st", "2nd", "standard", "half", "quarter", "eighth"],
)
def _resize_mesh(
    x_min: float, y_min: float, x_max: float, y_max: float, mesh_name: str
):
    """
    ## Summary:
        地域メッシュの刻みに応じて範囲を調整するヘルパー関数
        例えば、基準地域メッシュの場合、経度方向に7.5分、緯度方向に5分の倍数に調整します。
    Args:
        x_min (float):
            範囲の最小経度（10進法）
        y_min (float):
            範囲の最小緯度（10進法）
        x_max (float):
            範囲の最大経度（10進法）
        y_max (float):
            範囲の最大緯度（10進法）
        mesh_name (str):
            メッシュの種類。'1st', '2nd', 'standard', 'half', 'quarter'のいずれか。
    Returns:
        Bounds:
            調整された範囲の境界
    """
    steps = _get_step(mesh_name)
    step_lon = steps["lon"]
    step_lat = steps["lat"]
    x_min_resized = x_min - (x_min % step_lon)
    y_min_resized = y_min - (y_min % step_lat)
    x_max_resized = (
        x_max + (step_lon - (x_max % step_lon)) if (x_max % step_lon) != 0 else x_max
    )
    y_max_resized = (
        y_max + (step_lat - (y_max % step_lat)) if (y_max % step_lat) != 0 else y_max
    )
    return Bounds(x_min_resized, y_min_resized, x_max_resized, y_max_resized)


class MeshCodeTo(object):
    def _check_mesh_code(self, mesh_code: str):
        if not isinstance(mesh_code, str):
            raise TypeError("mesh_code must be a string")
        if len(mesh_code) == 4:
            self.mesh_type = "1st"
        elif len(mesh_code) == 6:
            self.mesh_type = "2nd"
        elif len(mesh_code) == 8:
            self.mesh_type = "standard"
        elif len(mesh_code) == 9:
            self.mesh_type = "half"
        elif len(mesh_code) == 10:
            self.mesh_type = "quarter"
        else:
            raise ValueError("Invalid mesh code length")

    def to_bounds(self, mesh_code: str) -> Bounds:
        """
        ## Summary:
            メッシュコードから境界を取得する関数。メッシュコードの種類に応じて適切な境界を返します。
        Args:
            mesh_code (str):
                メッシュコード
        Returns:
            Bounds:
                メッシュコードに対応する境界
        """
        self._check_mesh_code(mesh_code)

        # メッシュコードから座標を逆算する
        if self.mesh_type == "1st":
            # 第1次メッシュコード（4桁）
            lat_code = int(mesh_code[0:2])
            lon_code = int(mesh_code[2:4]) + 100

            # 境界計算
            SCALE = 10**10
            first_lon_size_int = SCALE
            first_lat_size_int = SCALE * 2 // 3

            x_min_int = lon_code * first_lon_size_int
            x_max_int = (lon_code + 1) * first_lon_size_int
            y_min_int = lat_code * first_lat_size_int
            y_max_int = (lat_code + 1) * first_lat_size_int

            x_min = x_min_int / SCALE
            x_max = x_max_int / SCALE
            y_min = y_min_int / SCALE
            y_max = y_max_int / SCALE

        elif self.mesh_type == "2nd":
            # 第2次メッシュコード（6桁）
            first_lat = int(mesh_code[0:2])
            first_lon = int(mesh_code[2:4]) + 100
            sec_lat = int(mesh_code[4:5])
            sec_lon = int(mesh_code[5:6])

            # 境界計算
            SCALE = 10**10
            lon_scaled = first_lon * SCALE
            lat_base_scaled = int((first_lat * 40 / 60) * SCALE)

            sec_lon_size_int = SCALE // 8
            sec_lat_size_int = SCALE // 12

            x_min_int = lon_scaled + (sec_lon * sec_lon_size_int)
            x_max_int = lon_scaled + ((sec_lon + 1) * sec_lon_size_int)
            y_min_int = lat_base_scaled + (sec_lat * sec_lat_size_int)
            y_max_int = lat_base_scaled + ((sec_lat + 1) * sec_lat_size_int)

            x_min = x_min_int / SCALE
            x_max = x_max_int / SCALE
            y_min = y_min_int / SCALE
            y_max = y_max_int / SCALE

        elif self.mesh_type == "standard":
            # 基準地域メッシュコード（8桁）
            first_lat = int(mesh_code[0:2])
            first_lon = int(mesh_code[2:4]) + 100
            sec_lat = int(mesh_code[4:5])
            sec_lon = int(mesh_code[5:6])
            std_lat = int(mesh_code[6:7])
            std_lon = int(mesh_code[7:8])

            # 境界計算
            SCALE = 10**10
            sec_x_min = first_lon + (sec_lon * 7.5 / 60)
            sec_y_min = (first_lat * 40 / 60) + (sec_lat * 5 / 60)

            sec_x_min_int = int(sec_x_min * SCALE)
            sec_y_min_int = int(sec_y_min * SCALE)

            std_lon_size_int = SCALE // 80
            std_lat_size_int = SCALE // 120

            x_min_int = sec_x_min_int + (std_lon * std_lon_size_int)
            x_max_int = sec_x_min_int + ((std_lon + 1) * std_lon_size_int)
            y_min_int = sec_y_min_int + (std_lat * std_lat_size_int)
            y_max_int = sec_y_min_int + ((std_lat + 1) * std_lat_size_int)

            x_min = x_min_int / SCALE
            x_max = x_max_int / SCALE
            y_min = y_min_int / SCALE
            y_max = y_max_int / SCALE

        elif self.mesh_type == "half":
            # 2分の1地域メッシュコード（9桁）
            std_mesh_code = mesh_code[:8]
            half_code = int(mesh_code[8:9])

            # 基準地域メッシュの境界を計算
            temp_mesh_to = MeshCodeTo()
            std_bounds = temp_mesh_to.to_bounds(std_mesh_code)

            # 2分の1メッシュの位置計算
            if half_code == 1:  # 南西
                x_offset, y_offset = 0, 0
            elif half_code == 2:  # 南東
                x_offset, y_offset = 1, 0
            elif half_code == 3:  # 北西
                x_offset, y_offset = 0, 1
            elif half_code == 4:  # 北東
                x_offset, y_offset = 1, 1
            else:
                raise ValueError(f"Invalid half mesh code: {half_code}")

            # 境界計算
            SCALE = 10**10
            std_x_min = Decimal(f"{std_bounds.x_min}")
            std_y_min = Decimal(f"{std_bounds.y_min}")

            std_x_min_int = int(std_x_min * SCALE)
            std_y_min_int = int(std_y_min * SCALE)

            half_lon_size_int = SCALE // 160
            half_lat_size_int = SCALE // 240

            x_min_int = std_x_min_int + (x_offset * half_lon_size_int)
            x_max_int = std_x_min_int + ((x_offset + 1) * half_lon_size_int)
            y_min_int = std_y_min_int + (y_offset * half_lat_size_int)
            y_max_int = std_y_min_int + ((y_offset + 1) * half_lat_size_int)

            x_min = x_min_int / SCALE
            x_max = x_max_int / SCALE
            y_min = y_min_int / SCALE
            y_max = y_max_int / SCALE

        elif self.mesh_type == "quarter":
            # 4分の1地域メッシュコード（10桁）
            half_mesh_code = mesh_code[:9]
            quarter_code = int(mesh_code[9:10])

            # 2分の1地域メッシュの境界を計算
            temp_mesh_to = MeshCodeTo()
            half_bounds = temp_mesh_to.to_bounds(half_mesh_code)

            # 4分の1メッシュの位置計算
            if quarter_code == 1:  # 南西
                x_offset, y_offset = 0, 0
            elif quarter_code == 2:  # 南東
                x_offset, y_offset = 1, 0
            elif quarter_code == 3:  # 北西
                x_offset, y_offset = 0, 1
            elif quarter_code == 4:  # 北東
                x_offset, y_offset = 1, 1
            else:
                raise ValueError(f"Invalid quarter mesh code: {quarter_code}")

            # 境界計算
            SCALE = 10**10
            half_x_min = Decimal(f"{half_bounds.x_min}")
            half_y_min = Decimal(f"{half_bounds.y_min}")

            half_x_min_int = int(half_x_min * SCALE)
            half_y_min_int = int(half_y_min * SCALE)

            quarter_lon_size_int = SCALE // 320
            quarter_lat_size_int = SCALE // 480

            x_min_int = half_x_min_int + (x_offset * quarter_lon_size_int)
            x_max_int = half_x_min_int + ((x_offset + 1) * quarter_lon_size_int)
            y_min_int = half_y_min_int + (y_offset * quarter_lat_size_int)
            y_max_int = half_y_min_int + ((y_offset + 1) * quarter_lat_size_int)

            x_min = x_min_int / SCALE
            x_max = x_max_int / SCALE
            y_min = y_min_int / SCALE
            y_max = y_max_int / SCALE

        else:
            raise ValueError(f"Unsupported mesh type: {self.mesh_type}")

        return Bounds(x_min, y_min, x_max, y_max)


def mesh_code_to_bounds(mesh_code: str) -> Bounds:
    """
    ## Summary:
        メッシュコードから境界を取得する関数。メッシュコードの種類に応じて適切な境界を返します。
    Args:
        mesh_code (str):
            メッシュコード
    Returns:
        Bounds:
            メッシュコードに対応する境界
    """
    mesh_to = MeshCodeTo()
    return mesh_to.to_bounds(mesh_code)
