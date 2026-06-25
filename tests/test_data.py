"""
Tests for data classes (XY, XYZ, Bounds).
"""

from geomesh.data import XY, XYZ, Bounds


class TestXY:
    """Tests for XY class."""

    def test_initialization(self):
        """XYクラスの初期化テスト"""
        xy = XY(x=139.0, y=35.0)
        assert xy.x == 139.0
        assert xy.y == 35.0

    def test_with_integers(self):
        """整数での初期化"""
        xy = XY(x=139, y=35)
        assert xy.x == 139
        assert xy.y == 35

    def test_negative_coordinates(self):
        """負の座標での初期化"""
        xy = XY(x=-139.0, y=-35.0)
        assert xy.x == -139.0
        assert xy.y == -35.0

    def test_zero_coordinates(self):
        """ゼロ座標での初期化"""
        xy = XY(x=0.0, y=0.0)
        assert xy.x == 0.0
        assert xy.y == 0.0


class TestXYZ:
    """Tests for XYZ class."""

    def test_initialization(self):
        """XYZクラスの初期化テスト"""
        xyz = XYZ(x=139.0, y=35.0, z=10)
        assert xyz.x == 139.0
        assert xyz.y == 35.0
        assert xyz.z == 10

    def test_tile_coordinates(self):
        """タイル座標でのテスト"""
        xyz = XYZ(x=233, y=101, z=8)
        assert xyz.x == 233
        assert xyz.y == 101
        assert xyz.z == 8

    def test_zero_zoom(self):
        """ズームレベル0でのテスト"""
        xyz = XYZ(x=0, y=0, z=0)
        assert xyz.z == 0


class TestBounds:
    """Tests for Bounds class."""

    def test_initialization(self):
        """Boundsクラスの初期化テスト"""
        bounds = Bounds(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)
        assert bounds.x_min == 139.0
        assert bounds.y_min == 35.0
        assert bounds.x_max == 140.0
        assert bounds.y_max == 36.0

    def test_valid_bounds(self):
        """正しい境界の範囲"""
        bounds = Bounds(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0)
        assert bounds.x_min < bounds.x_max
        assert bounds.y_min < bounds.y_max

    def test_world_bounds(self):
        """世界全体の境界"""
        bounds = Bounds(x_min=-180.0, y_min=-90.0, x_max=180.0, y_max=90.0)
        assert bounds.x_min == -180.0
        assert bounds.y_min == -90.0
        assert bounds.x_max == 180.0
        assert bounds.y_max == 90.0

    def test_single_point(self):
        """1点の境界（同じ座標）"""
        bounds = Bounds(x_min=139.0, y_min=35.0, x_max=139.0, y_max=35.0)
        assert bounds.x_min == bounds.x_max
        assert bounds.y_min == bounds.y_max
