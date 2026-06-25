"""
Tests for global mesh (tile) functions (glmesh module).
"""

import geopandas as gpd

from geomesh.glmesh import TileDesign, TileDesigner


class TestTileDesign:
    """Tests for TileDesign class."""

    def test_initialization(self):
        """TileDesignクラスの初期化"""
        from geomesh.data import Bounds

        bounds = Bounds(x_min=0, y_min=0, x_max=1, y_max=1)
        tile = TileDesign(
            zoom_level=8, x_idx=233, y_idx=101, bounds=bounds, width=256, height=256
        )
        assert tile.x_idx == 233
        assert tile.y_idx == 101
        assert tile.zoom_level == 8

    def test_zoom_zero_tile(self):
        """ズームレベル0のタイル(世界全体)"""
        from geomesh.data import Bounds

        bounds = Bounds(x_min=0, y_min=0, x_max=1, y_max=1)
        tile = TileDesign(
            zoom_level=0, x_idx=0, y_idx=0, bounds=bounds, width=256, height=256
        )
        assert tile.x_idx == 0
        assert tile.y_idx == 0
        assert tile.zoom_level == 0

    def test_bounds_calculation(self):
        """タイルの境界が正しく設定される"""
        from geomesh.data import Bounds

        bounds = Bounds(x_min=100.0, y_min=200.0, x_max=300.0, y_max=400.0)
        tile = TileDesign(
            zoom_level=8, x_idx=233, y_idx=101, bounds=bounds, width=256, height=256
        )

        assert tile.bounds.x_min == 100.0
        assert tile.bounds.x_max == 300.0
        assert tile.bounds.y_min == 200.0
        assert tile.bounds.y_max == 400.0

    def test_zxy_property(self):
        """zxyプロパティの動作確認"""
        from geomesh.data import Bounds

        bounds = Bounds(x_min=0, y_min=0, x_max=1, y_max=1)
        tile = TileDesign(
            zoom_level=8, x_idx=233, y_idx=101, bounds=bounds, width=256, height=256
        )
        zxy = tile.zxy

        assert isinstance(zxy, dict)
        assert zxy["z"] == 8
        assert zxy["x"] == 233
        assert zxy["y"] == 101


class TestTileDesigner:
    """Tests for TileDesigner class."""

    def test_initialization(self):
        """TileDesignerクラスの初期化"""
        designer = TileDesigner()
        assert designer is not None
        assert designer.width == 256
        assert designer.height == 256

    def test_create_tiles_small_area(self):
        """小さなエリアでタイル生成"""
        designer = TileDesigner()
        gdf = designer.tiles(
            x_min=139.7,
            y_min=35.6,
            x_max=139.8,
            y_max=35.7,
            zoom_level=10,
            geodataframe=True,
        )

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) > 0
        assert "geometry" in gdf.columns

    def test_from_lonlat(self):
        """経緯度からタイル生成"""
        designer = TileDesigner()
        tile = designer.from_lonlat(lon=139.7, lat=35.6, zoom_level=10)

        assert isinstance(tile, TileDesign)
        assert tile.zoom_level == 10
        assert tile.x_idx >= 0
        assert tile.y_idx >= 0
