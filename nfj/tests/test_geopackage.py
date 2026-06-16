import sqlite3

import geopandas as gpd
import pytest
import shapely

from ..geopackage import GeoPackage


def _make_gdf():
    return gpd.GeoDataFrame(
        {"name": ["a"], "geometry": [shapely.Point(0, 0)]},
        geometry="geometry",
        crs="EPSG:4326",
    )


def test_save_copies_temp_file_to_output(tmp_path):
    gpkg = GeoPackage()
    try:
        with open(gpkg.temp_file_path, "wb") as f:
            f.write(b"gpkg-data")

        output_path = tmp_path / "nested" / "output.gpkg"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        gpkg.save(str(output_path))

        assert output_path.exists()
        assert output_path.read_bytes() == b"gpkg-data"
    finally:
        gpkg.delete_temp_file()


def test_save_rejects_non_string_path():
    gpkg = GeoPackage()
    try:
        with pytest.raises(ValueError):
            gpkg.save(123)  # type: ignore[arg-type]
    finally:
        gpkg.delete_temp_file()


def test_delete_temp_file_removes_file():
    gpkg = GeoPackage()

    assert gpkg.temp_file_path
    assert gpkg.temp_file_path.endswith(".gpkg")
    assert gpkg.temp_file_path is not None

    gpkg.delete_temp_file()

    # 2回目の削除も安全に呼べることを確認
    gpkg.delete_temp_file()


def test_add_alias_creates_schema_tables_and_upserts_rows():
    gpkg = GeoPackage()
    try:
        gpkg.add_alias("layer_a", {"field1": "別名1", "field2": "別名2"})

        conn = sqlite3.connect(gpkg.temp_file_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT extension_name FROM gpkg_extensions WHERE extension_name='gpkg_schema'"
            )
            assert cur.fetchone() == ("gpkg_schema",)

            cur.execute(
                "SELECT table_name, column_name, name FROM gpkg_data_columns ORDER BY column_name"
            )
            assert cur.fetchall() == [
                ("layer_a", "field1", "別名1"),
                ("layer_a", "field2", "別名2"),
            ]
        finally:
            conn.close()

        # 同じキーに対して再実行すると UPDATE されることを確認
        gpkg.add_alias("layer_a", {"field1": "更新後"})
        conn = sqlite3.connect(gpkg.temp_file_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM gpkg_data_columns WHERE table_name=? AND column_name=?",
                ("layer_a", "field1"),
            )
            assert cur.fetchone() == ("更新後",)
        finally:
            conn.close()
    finally:
        gpkg.delete_temp_file()


def test_to_geopackage_calls_to_file_and_add_alias(monkeypatch):
    gdf = _make_gdf()
    gpkg = GeoPackage(field_and_alias={"name": "名称"})
    calls = {"to_file": 0, "add_alias": 0}

    def fake_to_file(self, path, driver=None, layer=None):
        calls["to_file"] += 1
        assert path == gpkg.temp_file_path
        assert driver == "GPKG"
        assert layer == "layer_a"

    def fake_add_alias(table_name, field_and_alias):
        calls["add_alias"] += 1
        assert table_name == "layer_a"
        assert field_and_alias == {"name": "名称"}

    monkeypatch.setattr(gpd.GeoDataFrame, "to_file", fake_to_file)
    monkeypatch.setattr(gpkg, "add_alias", fake_add_alias)

    try:
        gpkg.to_geopackage(gdf, layer="layer_a", alias=True)
        assert calls == {"to_file": 1, "add_alias": 1}

        gpkg.to_geopackage(gdf, layer="layer_a", alias=False)
        assert calls == {"to_file": 2, "add_alias": 1}
    finally:
        gpkg.delete_temp_file()
