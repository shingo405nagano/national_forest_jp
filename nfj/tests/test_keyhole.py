import os
import zipfile

import fastkml
import geopandas as gpd
import pytest
import shapely
from fastkml.enums import AltitudeMode

from ..keyhole import KeyholeMarkupLanguage, KmlKwargs, Kmz, hex_to_abgr


def _make_polygon_gdf(crs: str = "EPSG:4326"):
    polygon = shapely.Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
    return gpd.GeoDataFrame(
        {
            "sub_address_name": ["A-1"],
            "main_address": ["1"],
            "locality": ["テスト林"],
            "branch_office": ["第一担当区"],
            "office": ["第一管理署"],
            "geometry": [polygon],
        },
        geometry="geometry",
        crs=crs,
    )


def test_hex_to_abgr_converts_hex_and_alpha():
    assert hex_to_abgr("#112233", alpha=0.5) == "7f332211"


def test_kmlkwargs_requires_crs():
    gdf = _make_polygon_gdf()
    gdf = gdf.set_crs(None, allow_override=True)

    with pytest.raises(ValueError):
        KmlKwargs(gdf=gdf)


def test_kmlkwargs_converts_to_epsg_4326():
    gdf = _make_polygon_gdf(crs="EPSG:3857")

    kwargs = KmlKwargs(gdf=gdf)

    assert kwargs.gdf.crs is not None
    assert kwargs.gdf.crs.to_epsg() == 4326


def test_geometry_element_rejects_empty_geometry():
    keyhole = KeyholeMarkupLanguage()

    with pytest.raises(ValueError):
        keyhole.geometry_element(shapely.Polygon())


def test_geometry_element_builds_kml_geometry():
    keyhole = KeyholeMarkupLanguage()
    geometry = shapely.Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])

    geom_elem = keyhole.geometry_element(
        geometry,
        altitude_mode=AltitudeMode.clamp_to_ground,
        extrude=True,
    )

    # fastkml geometry object が返ることだけ検証
    assert geom_elem is not None


def test_create_placemark_sets_style_url_when_given():
    keyhole = KeyholeMarkupLanguage()
    geom_elem = keyhole.geometry_element(
        shapely.Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
    )
    data = keyhole.create_data_element(name="k", value="v", alias="表示")
    ext = keyhole.create_extended_data_element([data])

    placemark = keyhole.create_placemark(
        id_="id-1",
        name="name-1",
        geometry_elem=geom_elem,
        extended_data=ext,
        style_url="style-1",
    )

    assert placemark.style_url is not None
    assert "style-1" in placemark.style_url.url


def test_check_crs_rejects_none():
    keyhole = KeyholeMarkupLanguage()
    gdf = _make_polygon_gdf()
    gdf = gdf.set_crs(None, allow_override=True)

    with pytest.raises(ValueError):
        keyhole._check_crs(gdf)


def test_geodataframe_to_poly_folder_builds_folder_with_feature():
    keyhole = KeyholeMarkupLanguage()
    gdf = _make_polygon_gdf()

    folder = keyhole.geodataframe_to_poly_folder(
        gdf=gdf,
        geometry_column="geometry",
        alias=True,
        folder_name="テストフォルダ",
        name_column="sub_address_name",
    )

    text = folder.to_string(prettyprint=False)
    assert "テストフォルダ" in text
    assert "A-1" in text


def test_geodataframe_to_poly_folder_accepts_alias_false():
    keyhole = KeyholeMarkupLanguage()
    gdf = _make_polygon_gdf()

    folder = keyhole.geodataframe_to_poly_folder(
        gdf=gdf,
        geometry_column="geometry",
        alias=False,
        folder_name="no-alias",
        name_column="sub_address_name",
    )

    text = folder.to_string(prettyprint=False)
    assert "no-alias" in text
    assert "A-1" in text


def test_geodataframe_to_label_folder_builds_label_feature():
    keyhole = KeyholeMarkupLanguage()
    gdf = _make_polygon_gdf()

    folder = keyhole.geodataframe_to_label_folder(
        gdf=gdf,
        geometry_column="geometry",
        folder_name="ラベル",
        name_column="locality",
    )

    text = folder.to_string(prettyprint=False)
    assert "ラベル" in text
    assert "テスト林" in text


def test_kmz_builds_temp_files_and_zip_contains_required_entries():
    doc = fastkml.Document(name="doc1")
    kmz = Kmz(name="テストKMZ", document_list=[doc])
    try:
        assert os.path.exists(kmz.kml_path)
        assert os.path.exists(kmz.kmz_path)

        with zipfile.ZipFile(kmz.kmz_path) as zf:
            names = zf.namelist()
            assert "doc.kml" in names
            assert "google_earth_screen_overlay.png" in names
    finally:
        kmz.delete_temp_file()


def test_kmz_rejects_non_document_in_list():
    with pytest.raises(ValueError):
        Kmz(name="bad", document_list=[object()])  # type: ignore[list-item]
