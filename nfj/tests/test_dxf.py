from importlib.resources import files

import ezdxf
import geopandas as gpd
import pytest
import shapely
from ezdxf.enums import InsertUnits

import nfj.dxf as dxf_module

from ..dxf import BaseDxf, SubAddrsDxf
from ..fields import AddressFields


def _build_subaddr_gdf(*, protection_values=None, geometry=None):
    fields = AddressFields()
    cols = fields.use_default_en_fields()

    data = {}
    for col in cols:
        if col == "geometry":
            data[col] = [
                geometry
                if geometry is not None
                else shapely.Polygon([(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)])
            ]
        elif col == "sub_address_name":
            data[col] = ["A-1"]
        elif "protection_forest" in col:
            idx = int(col.split("_")[-1]) - 1
            if protection_values is None:
                data[col] = ["-"]
            else:
                data[col] = [
                    protection_values[idx] if idx < len(protection_values) else "-"
                ]
        elif col in {"main_address", "sub_address"}:
            data[col] = [1]
        else:
            data[col] = ["-"]

    return gpd.GeoDataFrame(data, geometry="geometry", crs="EPSG:6678")


def test_font_resource_exists_inside_package():
    font_path = files("nfj").joinpath("others", "msgothic.ttc")

    assert font_path.is_file()


def test_base_dxf_add_geometries_raises_when_label_column_missing():
    gdf = gpd.GeoDataFrame(
        {"geometry": [shapely.Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])]},
        geometry="geometry",
        crs="EPSG:6678",
    )
    base = BaseDxf(gdf=gdf, label_column="missing_label")
    msp = ezdxf.new(dxfversion="R2010", units=InsertUnits.Meters).modelspace()

    with pytest.raises(ValueError, match="does not exist"):
        base.add_geometries(msp)


def test_base_dxf_add_geometries_handles_multipolygon_without_label():
    multi = shapely.MultiPolygon(
        [
            shapely.Polygon([(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)]),
            shapely.Polygon([(10, 0), (15, 0), (15, 5), (10, 5), (10, 0)]),
        ]
    )
    gdf = gpd.GeoDataFrame({"geometry": [multi]}, geometry="geometry", crs="EPSG:6678")

    base = BaseDxf(gdf=gdf, label_column=None)
    msp = ezdxf.new(dxfversion="R2010", units=InsertUnits.Meters).modelspace()
    base.add_geometries(msp)

    entity_types = [entity.dxftype() for entity in msp]
    assert entity_types.count("LWPOLYLINE") == 2
    assert entity_types.count("TEXT") == 0


def test_subaddrs_protection_marks_maps_known_code_and_missing_values():
    gdf = _build_subaddr_gdf(protection_values=["水涵保", "-", "未知", "-"])
    sub = SubAddrsDxf(gdf=gdf)

    marks = sub.protection_marks()

    assert marks is not None
    assert marks[0] == ["水"]


def test_compute_visual_offset_is_cached_for_repeat_calls(monkeypatch):
    calls = 0

    def fake_uncached(label, font_path, font_point_size, target_height):
        nonlocal calls
        calls += 1
        return (1.0, 2.0)

    monkeypatch.setattr(dxf_module, "_compute_visual_offset_uncached", fake_uncached)
    dxf_module.compute_visual_offset.cache_clear()

    assert dxf_module.compute_visual_offset("A", "dummy.ttf", 12, 20) == (1.0, 2.0)
    assert dxf_module.compute_visual_offset("A", "dummy.ttf", 12, 20) == (1.0, 2.0)
    assert calls == 1


def test_subaddrs_add_geometries_splits_label_into_kana_and_number_parts():
    gdf = _build_subaddr_gdf()
    gdf.at[0, "sub_address_name"] = "A-1"
    sub = SubAddrsDxf(gdf=gdf, label_size=15)

    doc = ezdxf.new(dxfversion="R2010", units=InsertUnits.Meters)
    msp = doc.modelspace()
    sub.add_geometries(msp)

    text_entities = [entity for entity in msp if entity.dxftype() == "TEXT"]

    assert [entity.dxf.text for entity in text_entities] == ["A", "1"]
    assert [entity.dxf.height for entity in text_entities] == [15.0, 7.5]


def test_subaddrs_add_geometries_uses_find_label_position_option(monkeypatch):
    gdf = _build_subaddr_gdf()

    def fake_cluster_center(geom):
        return shapely.Point(10, 10)

    def fail_point_on_surface(_geom):
        raise AssertionError("point_on_surface should not be used")

    monkeypatch.setattr(
        dxf_module, "find_max_adjacent_cluster_center", fake_cluster_center
    )
    monkeypatch.setattr(dxf_module.shapely, "point_on_surface", fail_point_on_surface)

    sub = SubAddrsDxf(gdf=gdf, find_label_position=True)
    doc = ezdxf.new(dxfversion="R2010", units=InsertUnits.Meters)
    msp = doc.modelspace()

    sub.add_geometries(msp)

    text_entities = [entity for entity in msp if entity.dxftype() == "TEXT"]
    assert len(text_entities) == 2
    assert text_entities[0].dxf.insert == (10.0, 10.0)


def test_subaddrs_add_geometries_adds_label_and_protection_mark_entities():
    gdf = _build_subaddr_gdf(protection_values=["水涵保", "土流保", "-", "-"])
    sub = SubAddrsDxf(gdf=gdf, label_size=15)

    doc = ezdxf.new(dxfversion="R2010", units=InsertUnits.Meters)
    msp = doc.modelspace()
    sub.add_geometries(msp)

    entity_types = [entity.dxftype() for entity in msp]

    assert entity_types.count("LWPOLYLINE") == 1
    # 小班名ラベル(kana + number)2つ + 保安林短縮コード2つ
    assert entity_types.count("TEXT") == 4
    assert entity_types.count("CIRCLE") == 2
