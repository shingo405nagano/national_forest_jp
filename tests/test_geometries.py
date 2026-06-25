"""
Tests for geometry transformation functions.
"""

import pytest

from geomesh.data import XY
from geomesh.geometries import dms_to_degree_lonlat, transform_xy


class TestTransformXY:
    """Tests for transform_xy function."""

    def test_identity_transform(self, tokyo_coords):
        """同じCRSへの変換(変化なし)"""
        result = transform_xy(
            tokyo_coords.x, tokyo_coords.y, in_crs="EPSG:4326", out_crs="EPSG:4326"
        )

        assert isinstance(result, XY)
        assert result.x == pytest.approx(tokyo_coords.x, abs=0.0001)
        assert result.y == pytest.approx(tokyo_coords.y, abs=0.0001)

    def test_wgs84_to_webmercator(self, tokyo_coords):
        """WGS84からWeb Mercatorへの変換"""
        result = transform_xy(
            tokyo_coords.x, tokyo_coords.y, in_crs="EPSG:4326", out_crs="EPSG:3857"
        )

        assert isinstance(result, XY)
        # Web Mercatorの値は大きい
        assert abs(result.x) > 1000
        assert abs(result.y) > 1000

    def test_webmercator_to_wgs84(self):
        """Web MercatorからWGS84への変換"""
        # 東京のWeb Mercator座標(概算)
        x_mercator = 15549356.0
        y_mercator = 4256388.0

        result = transform_xy(
            x_mercator, y_mercator, in_crs="EPSG:3857", out_crs="EPSG:4326"
        )

        assert isinstance(result, XY)
        # 東京付近の経度緯度
        assert 139 < result.x < 140
        assert 35 < result.y < 36

    def test_roundtrip_transform(self, tokyo_coords):
        """往復変換で元に戻る"""
        # WGS84 -> Web Mercator
        mercator = transform_xy(
            tokyo_coords.x, tokyo_coords.y, in_crs="EPSG:4326", out_crs="EPSG:3857"
        )

        # Web Mercator -> WGS84
        wgs84 = transform_xy(
            mercator.x, mercator.y, in_crs="EPSG:3857", out_crs="EPSG:4326"
        )

        assert wgs84.x == pytest.approx(tokyo_coords.x, abs=0.0001)
        assert wgs84.y == pytest.approx(tokyo_coords.y, abs=0.0001)


class TestDMSToDegree:
    """Tests for dms_to_degree_lonlat function."""

    def test_simple_conversion(self):
        """度分秒から度への変換"""
        # 139度44分28.15秒E, 35度39分29.16秒N（東京駅）
        lon_dms = 1400516.2781
        lat_dms = 360613.5892

        result = dms_to_degree_lonlat(lon_dms, lat_dms)

        assert isinstance(result, XY)
        # 結果は度単位
        assert result.x > 140 and result.x < 141
        assert result.y > 36 and result.y < 37
