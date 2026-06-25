"""
pytest configuration and shared fixtures.
"""

import pytest

from geomesh.data import XY, Bounds


@pytest.fixture
def tokyo_coords():
    """東京の座標（経度、緯度）"""
    return XY(x=139.6917, y=35.6895)


@pytest.fixture
def osaka_coords():
    """大阪の座標（経度、緯度）"""
    return XY(x=135.5022, y=34.6937)


@pytest.fixture
def known_mesh_codes():
    """
    既知のメッシュコードと座標のペア
    公式ドキュメントや実際のデータから取得
    """
    return {
        "tokyo_standard": {
            "coords": (139.7417, 35.6581),  # 東京駅付近
            "codes": {
                "first": "5339",
                "secondary": "533945",
                "standard": "53394611",
            },
        },
        "osaka_standard": {
            "coords": (135.5000, 34.6833),  # 大阪市付近
            "codes": {
                "first": "5235",
                "secondary": "523546",
                "standard": "52354611",
            },
        },
    }


@pytest.fixture
def test_bounds():
    """テスト用の境界"""
    return Bounds(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)


@pytest.fixture
def small_bounds():
    """小さな範囲の境界（テスト高速化用）"""
    return Bounds(x_min=139.7, y_min=35.6, x_max=139.8, y_max=35.7)
