"""
Tests for square mesh functions.
"""

import geopandas as gpd

from geomesh.square import SquareMesh


class TestSquareMesh:
    """Tests for SquareMesh class."""

    def test_initialization(self):
        """SquareMeshクラスの初期化"""
        square = SquareMesh(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)
        assert square is not None
        assert square.bounds.x_min == 139.0
        assert square.bounds.y_min == 35.0

    def test_create_square_mesh(self):
        """正方形メッシュの生成"""
        square = SquareMesh(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)
        gdf = square.generate_squares_from_length(horizontal=0.01, vertical=0.01)

        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) > 0
        assert "geometry" in gdf.columns

    def test_small_size_more_squares(self):
        """小さいサイズのほうが多くの正方形が生成される"""
        large = SquareMesh(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)
        small = SquareMesh(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)

        gdf_large = large.generate_squares_from_length(horizontal=0.1)
        gdf_small = small.generate_squares_from_length(horizontal=0.01)

        assert len(gdf_small) > len(gdf_large)

    def test_square_geometry_type(self):
        """生成されたジオメトリがPolygonか"""
        square = SquareMesh(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)
        gdf = square.generate_squares_from_length(horizontal=0.01)

        # すべてのジオメトリがPolygon
        assert all(geom.geom_type == "Polygon" for geom in gdf.geometry)

    def test_has_id_column(self):
        """生成されたGeoDataFrameにidカラムがある"""
        square = SquareMesh(x_min=139.0, y_min=35.0, x_max=140.0, y_max=36.0)
        gdf = square.generate_squares_from_length(horizontal=0.01)

        assert "id" in gdf.columns
        assert "xy" in gdf.columns
