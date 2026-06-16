import io
import os
import tempfile
import zipfile

import geopandas as gpd
import pytest
import shapely

from ..fetch import GsShapeFile
from ..fields import AddressFields
from ..geospatial import GsicAddressShape, convert_wareki_to_seireki
from ..keyhole import Kmz


class _DummyDateTime:
    @classmethod
    def now(cls):
        return type("_Now", (), {"year": 2026})()


def _make_shape_file():
    shape_file = GsicAddressShape.__new__(GsicAddressShape)
    shape_file.fields = AddressFields()
    return shape_file


def _make_raw_address_gdf():
    address_fields = AddressFields()
    row = {}
    for field_info in address_fields.fields.values():
        if field_info.org == "県市町村":
            row[field_info.org] = ["　ＡＢＣ　"]
        elif field_info.org == "局名称":
            row[field_info.org] = ["北海道森林管理局"]
        elif field_info.org == "計画区":
            row[field_info.org] = ["計画区"]
        elif field_info.org == "署名称":
            row[field_info.org] = ["札幌森林管理署"]
        elif field_info.org == "担当区":
            row[field_info.org] = ["　ＤＥＦ　"]
        elif field_info.org == "国有林名":
            row[field_info.org] = ["　ＧＨＩ　"]
        elif field_info.org == "林小班名称":
            row[field_info.org] = ["_林班_　ＡＢＣ"]
        elif field_info.org == "林班主番":
            row[field_info.org] = [1]
        elif field_info.org == "林班枝番":
            row[field_info.org] = [2]
        elif field_info.org == "小班名":
            row[field_info.org] = ["小班"]
        elif field_info.org == "材積":
            row[field_info.org] = [1.5]
        elif field_info.org == "面積":
            row[field_info.org] = [2.5]
        elif field_info.org == "樹種１":
            row[field_info.org] = ["-"]
        elif field_info.org == "樹立林齢１":
            row[field_info.org] = [1]
        elif field_info.org == "樹種２":
            row[field_info.org] = ["-"]
        elif field_info.org == "樹立林齢２":
            row[field_info.org] = [2]
        elif field_info.org == "樹種３":
            row[field_info.org] = ["-"]
        elif field_info.org == "樹立林齢３":
            row[field_info.org] = [3]
        elif field_info.org == "林種の細分":
            row[field_info.org] = ["単"]
        elif field_info.org == "機能類型":
            row[field_info.org] = ["水源涵養"]
        elif field_info.org == "保安林１":
            row[field_info.org] = ["-"]
        elif field_info.org == "保安林２":
            row[field_info.org] = ["-"]
        elif field_info.org == "保安林３":
            row[field_info.org] = ["-"]
        elif field_info.org == "保安林４":
            row[field_info.org] = ["-"]
        elif field_info.org == "保護林":
            row[field_info.org] = [2010]
        elif field_info.org == "緑の回廊":
            row[field_info.org] = [1]
        elif field_info.org == "樹立年度":
            row[field_info.org] = ["令和元年度樹立"]
        elif field_info.org == "geometry":
            row[field_info.org] = [shapely.Point(0, 0)]
        else:
            row[field_info.org] = [field_info.default]
    return gpd.GeoDataFrame(row, geometry="geometry")


def test_convert_wareki_to_seireki_handles_string_eras():
    assert convert_wareki_to_seireki("令和元年度樹立") == 2019
    assert convert_wareki_to_seireki("平成5年度樹立") == 1993


def test_convert_wareki_to_seireki_passthrough_for_non_string():
    assert convert_wareki_to_seireki(2024) == 2024


def test_convert_wareki_to_seireki_rejects_unknown_format():
    with pytest.raises(ValueError):
        convert_wareki_to_seireki("昭和5年度樹立")


def test_replace_address_strips_marker_and_normalizes():
    shape_file = _make_shape_file()

    assert shape_file._GsicAddressShape__replace_address("_林班_　ＡＢＣ") == "ABC"


def test_fix_tree_age_uses_current_year(monkeypatch):
    shape_file = _make_shape_file()
    monkeypatch.setattr("nfj.geospatial.datetime.datetime", _DummyDateTime)

    assert shape_file._GsicAddressShape__fix_tree_age(2020, 5) == 12


def test_decode_conservation_handles_numeric_and_non_numeric():
    shape_file = _make_shape_file()

    assert (
        shape_file._GsicAddressShape__decode_conservation(2010)
        == "森林生態系保護地域保存地区"
    )
    assert shape_file._GsicAddressShape__decode_conservation("x") == "x"


def test_decode_green_corridor_handles_numeric_and_non_numeric():
    shape_file = _make_shape_file()

    assert shape_file._GsicAddressShape__decode_green_corridor(1) == "知床半島"
    assert shape_file._GsicAddressShape__decode_green_corridor("x") == "x"


def test_validate_geometry_calls_make_valid(monkeypatch):
    shape_file = _make_shape_file()
    geometry = shapely.Point(0, 0)
    captured = {}

    def fake_make_valid(value, method=None, keep_collapsed=None):
        captured["value"] = value
        captured["method"] = method
        captured["keep_collapsed"] = keep_collapsed
        return "validated"

    monkeypatch.setattr("nfj.geospatial.shapely.make_valid", fake_make_valid)

    assert shape_file.validate_geometry(geometry) == "validated"
    assert captured == {
        "value": geometry,
        "method": "structure",
        "keep_collapsed": True,
    }


def test_make_query_string_supports_list_str_and_int():
    shape_file = _make_shape_file()

    assert shape_file._GsicAddressShape__make_query_string(
        "city", ["北海道", "青森"]
    ) == ("city == '北海道' or city == '青森'")
    assert (
        shape_file._GsicAddressShape__make_query_string("city", "北海道")
        == "city == '北海道'"
    )
    assert (
        shape_file._GsicAddressShape__make_query_string("main_address", 12)
        == "main_address == 12"
    )


def test_check_geodataframe_accepts_expected_columns():
    shape_file = _make_shape_file()
    cols = shape_file.fields.use_default_en_fields()
    gdf = gpd.GeoDataFrame(
        {
            column: [shapely.Point(0, 0)] if column == "geometry" else ["-"]
            for column in cols
        },
        geometry="geometry",
    )

    shape_file._GsicAddressShape__check_geodataframe(gdf)


def test_check_geodataframe_rejects_invalid_columns():
    shape_file = _make_shape_file()
    gdf = gpd.GeoDataFrame(
        {"city": ["北斗市"], "geometry": [shapely.Point(0, 0)]}, geometry="geometry"
    )

    with pytest.raises(AssertionError):
        shape_file._GsicAddressShape__check_geodataframe(gdf)


def test_cast_geodataframe_converts_and_fills_values(monkeypatch):
    shape_file = _make_shape_file()

    class DummyFieldInfo:
        def __init__(self, dtype, default):
            self.dtype = dtype
            self.default = default

        def cast(self, value):
            if value in (None, "nan", "NaN"):
                return self.default
            return value

    class DummyFields:
        def rename_dict_org_to_en(self):
            return {"市町村": "city", "値": "value", "geometry": "geometry"}

        def use_default_en_fields(self):
            return ["city", "value", "geometry"]

        def field_info(self, col):
            if col == "city":
                return DummyFieldInfo(str, "-")
            return DummyFieldInfo(int, 0)

    shape_file.fields = DummyFields()

    gdf = gpd.GeoDataFrame(
        {"市町村": ["nan"], "値": [None], "geometry": [shapely.Point(0, 0)]},
        geometry="geometry",
    )

    result = shape_file._GsicAddressShape__cast_geodataframe(gdf)

    assert list(result.columns) == ["city", "value", "geometry"]
    assert result.loc[0, "city"] == "-"
    assert result.loc[0, "value"] == 0


def test_gsic_address_shape_initialization_passes_address_category(monkeypatch):
    captured = {}

    def fake_init(self, prefecture, year=2025, category="address", endswith=".shp"):
        captured["prefecture"] = prefecture
        captured["year"] = year
        captured["category"] = category
        captured["endswith"] = endswith
        self.fields = AddressFields()
        self.file_name = "小班区画.shp"
        self.extract_root_path = None
        self.plan_area_names = []

    monkeypatch.setattr(GsShapeFile, "__init__", fake_init)

    GsicAddressShape("北海道", year=2024, endswith=".geojson")

    assert captured == {
        "prefecture": "北海道",
        "year": 2024,
        "category": "address",
        "endswith": ".geojson",
    }


def test_geodataframe_transforms_address_data_end_to_end(monkeypatch):
    shape_file = _make_shape_file()
    raw_gdf = _make_raw_address_gdf()
    monkeypatch.setattr("nfj.geospatial.datetime.datetime", _DummyDateTime)
    monkeypatch.setattr(shape_file, "_read_file", lambda plan_area: raw_gdf.copy())

    result = shape_file.geodataframe("計画区")

    assert list(result.columns) == shape_file.fields.use_default_en_fields()
    assert result.loc[0, "city"] == "ABC"
    assert result.loc[0, "authority"] == "北海道"
    assert result.loc[0, "branch_office"] == "DEF"
    assert result.loc[0, "locality"] == "GHI"
    assert result.loc[0, "address"] == "ABC"
    assert result.loc[0, "tree_age_1"] == 9
    assert result.loc[0, "tree_age_2"] == 10
    assert result.loc[0, "tree_age_3"] == 11
    assert result.loc[0, "conservation"] == "森林生態系保護地域保存地区"
    assert result.loc[0, "green_corridor"] == "知床半島"
    assert result.loc[0, "updated_year"] == 2026


def test_encode_decode_and_field_alias_use_real_fields():
    shape_file = _make_shape_file()
    cols = shape_file.fields.use_default_en_fields()
    gdf = gpd.GeoDataFrame(
        {
            column: ["-" if column != "geometry" else shapely.Point(0, 0)]
            for column in cols
        },
        geometry="geometry",
    )

    encoded = shape_file.encode(gdf)
    decoded = shape_file.decode(encoded)

    assert encoded.loc[0, "city"] == 0
    assert encoded.loc[0, "authority"] == 0
    assert decoded.loc[0, "city"] == "-"
    assert decoded.loc[0, "authority"] == "-"
    assert shape_file.field_and_alias()["city"] == "市区町村"


def test_query_filters_matching_rows():
    shape_file = _make_shape_file()
    cols = shape_file.fields.use_default_en_fields()
    gdf = gpd.GeoDataFrame(
        {
            **{column: ["-"] for column in cols if column != "geometry"},
            "city": ["ABC"],
            "office": ["札幌森林管理署"],
            "geometry": [shapely.Point(0, 0)],
        },
        geometry="geometry",
    )

    result = shape_file.query(gdf, city="ABC", office="札幌森林管理署")

    assert len(result) == 1
    assert result.loc[0, "city"] == "ABC"


def test_kmz_save_creates_parent_dir_and_copies_file(tmp_path):
    source_path = tmp_path / "source.kmz"
    source_path.write_bytes(b"kmz-data")

    kmz = Kmz.__new__(Kmz)
    kmz.kmz_path = str(source_path)

    output_path = tmp_path / "nested" / "out.kmz"
    kmz.save(str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes() == b"kmz-data"


def test_kmz_save_from_tempfile_makes_output_readable_by_others(tmp_path):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".kmz") as tmp_file:
        tmp_file.write(b"kmz-data")
        temp_kmz_path = tmp_file.name

    try:
        kmz = Kmz.__new__(Kmz)
        kmz.kmz_path = temp_kmz_path

        output_path = tmp_path / "saved_from_temp.kmz"
        kmz.save(str(output_path))

        assert output_path.exists()
        assert output_path.read_bytes() == b"kmz-data"

        mode = output_path.stat().st_mode & 0o777
        assert mode & 0o444 == 0o444
    finally:
        if os.path.exists(temp_kmz_path):
            os.remove(temp_kmz_path)


def test_to_kmz_returns_bytesio_when_requested(monkeypatch):
    shape_file = _make_shape_file()
    gdf = gpd.GeoDataFrame(
        {"geometry": [shapely.Point(0, 0)]}, geometry="geometry", crs="EPSG:4326"
    )

    monkeypatch.setattr(
        shape_file,
        "_GsicAddressShape__check_geodataframe",
        lambda _: None,
    )
    monkeypatch.setattr("nfj.geospatial.SubAddressKmlKwargs", lambda gdf: object())
    monkeypatch.setattr(shape_file, "to_kml_doc", lambda kwargs: object())

    created_paths = []

    class FakeKmz:
        def __init__(self, name, document_list):
            self.name = name
            self.document_list = document_list
            with tempfile.NamedTemporaryFile(delete=False, suffix=".kmz") as tmp_file:
                with zipfile.ZipFile(tmp_file, mode="w") as zf:
                    zf.writestr("doc.kml", "<kml/>")
                self.kmz_path = tmp_file.name
            created_paths.append(self.kmz_path)

    monkeypatch.setattr("nfj.geospatial.Kmz", FakeKmz)

    memory_file = shape_file.to_kmz(
        gdf,
        main_address=False,
        locality=False,
        branch_office=False,
        office=False,
        return_memory_file=True,
    )

    try:
        assert isinstance(memory_file, io.BytesIO)
        assert memory_file.tell() == 0

        with zipfile.ZipFile(memory_file) as zf:
            assert "doc.kml" in zf.namelist()
    finally:
        for path in created_paths:
            if os.path.exists(path):
                os.remove(path)


def test_to_kmz_returns_kmz_object_by_default(monkeypatch):
    shape_file = _make_shape_file()
    gdf = gpd.GeoDataFrame(
        {"geometry": [shapely.Point(0, 0)]}, geometry="geometry", crs="EPSG:4326"
    )

    monkeypatch.setattr(
        shape_file,
        "_GsicAddressShape__check_geodataframe",
        lambda _: None,
    )
    monkeypatch.setattr("nfj.geospatial.SubAddressKmlKwargs", lambda gdf: object())
    monkeypatch.setattr(shape_file, "to_kml_doc", lambda kwargs: object())

    class FakeKmz:
        def __init__(self, name, document_list):
            self.name = name
            self.document_list = document_list
            self.kmz_path = "dummy.kmz"

    monkeypatch.setattr("nfj.geospatial.Kmz", FakeKmz)

    result = shape_file.to_kmz(
        gdf,
        main_address=False,
        locality=False,
        branch_office=False,
        office=False,
        return_memory_file=False,
    )

    assert isinstance(result, FakeKmz)
    assert result.name == "国有林区画データ"
