"""
Tests for Japanese mesh code functions (jpmesh module).
"""

import geopandas as gpd
import pytest
import shapely

import geomesh

from .data import TestDataSets

data = TestDataSets()
prefectures = data.pref_points_df["prefecture"].tolist()


"""
********************************************************************************
Summary:
    経緯度から日本の地域メッシュコードとその境界を取得する機能をテスト
Details:
    - 各都道府県庁所在地のポイントデータを使用
    - 生成されるメッシュコードが文字列であり、正しい長さを持つことを確認
    - 各メッシュコードが正しく生成され、ポイントがメッシュ内に含まれることを確認
    - 第1次メッシュコード（4桁）
    - 第2次メッシュコード（6桁）
    - 基準地域メッシュコード（8桁）
    - 2分の1地域メッシュコード（9桁）
    - 4分の1地域メッシュコード（10桁）
    - 度分秒（DMS）形式の経緯度だとしても正しくメッシュコードが生成されることを確認
********************************************************************************
"""


@pytest.mark.parametrize(
    ("pnt", "code"),
    [
        (data.get_pref_point(pref), data.get_pref_mesh_code(pref, "1st"))
        for pref in prefectures
    ],
)
def test_1st_mesh_code_generation(pnt, code):
    """第1次メッシュコードの生成テスト"""
    mesh = geomesh.jpmesh.MeshCodeJP(pnt.x, pnt.y)
    # MeshCodeが正しいことを確認
    assert isinstance(mesh.first_mesh_code, str)
    assert len(mesh.first_mesh_code) == 4
    assert mesh.first_mesh_code == code
    bounds = shapely.box(*mesh.first_mesh())
    # ポイントがメッシュ内に含まれることを確認
    assert bounds.contains(pnt)


@pytest.mark.parametrize(
    ("pnt", "code"),
    [
        (data.get_pref_point(pref), data.get_pref_mesh_code(pref, "2nd"))
        for pref in prefectures
    ],
)
def test_2nd_mesh_code_generation(pnt, code):
    """第2次メッシュコードの生成テスト"""
    mesh = geomesh.jpmesh.MeshCodeJP(pnt.x, pnt.y)
    assert isinstance(mesh.secandary_mesh_code, str)
    assert len(mesh.secandary_mesh_code) == 6
    assert mesh.secandary_mesh_code == code
    bounds = shapely.box(*mesh.secandary_mesh())
    assert bounds.contains(pnt)


@pytest.mark.parametrize(
    ("pnt", "code"),
    [
        (data.get_pref_point(pref), data.get_pref_mesh_code(pref, "standard"))
        for pref in prefectures
    ],
)
def test_standard_mesh_code_generation(pnt, code):
    """基準地域メッシュコードの生成テスト"""
    mesh = geomesh.jpmesh.MeshCodeJP(pnt.x, pnt.y)
    assert isinstance(mesh.standard_mesh_code, str)
    assert len(mesh.standard_mesh_code) == 8
    assert mesh.standard_mesh_code == code
    bounds = shapely.box(*mesh.standard_mesh())
    assert bounds.contains(pnt)


@pytest.mark.parametrize(
    ("pnt", "code"),
    [
        (data.get_pref_point(pref), data.get_pref_mesh_code(pref, "half"))
        for pref in prefectures
    ],
)
def test_half_mesh_code_generation(pnt, code):
    """2分の1地域メッシュコードの生成テスト"""
    mesh = geomesh.jpmesh.MeshCodeJP(pnt.x, pnt.y)
    assert isinstance(mesh.half_mesh_code, str)
    assert len(mesh.half_mesh_code) == 9
    assert mesh.half_mesh_code == code
    bounds = shapely.box(*mesh.half_mesh())
    assert bounds.contains(pnt)


@pytest.mark.parametrize(
    ("pnt", "code"),
    [
        (data.get_pref_point(pref), data.get_pref_mesh_code(pref, "quarter"))
        for pref in prefectures
    ],
)
def test_quarter_mesh_code_generation(pnt, code):
    """4分の1地域メッシュコードの生成テスト"""
    mesh = geomesh.jpmesh.MeshCodeJP(pnt.x, pnt.y)
    assert isinstance(mesh.quarter_mesh_code, str)
    assert len(mesh.quarter_mesh_code) == 10
    assert mesh.quarter_mesh_code == code
    bounds = shapely.box(*mesh.quarter_mesh())
    assert bounds.contains(pnt)


def test_dms_input_quarter_mesh_code():
    """度分秒（DMS）形式の経緯度から4分の1地域メッシュコードを取得するテスト"""
    lon_dms, lat_dms = 1400516.27815, 360613.58925
    lon, lat = 140.08785504166664, 36.103774791666666
    dms_mesh = geomesh.jpmesh.MeshCodeJP(lon_dms, lat_dms, is_dms=True)
    standard_mesh = geomesh.jpmesh.MeshCodeJP(lon, lat)
    assert dms_mesh.quarter_mesh_code == standard_mesh.quarter_mesh_code


"""
********************************************************************************
Summary:
    地域メッシュコードから経緯度への変換テスト
Details:
    - 桁数の異なる各種メッシュコードを使用
    - メッシュコードが「1st」「2nd」「standard」「half」「quarter」の順に小さくなる事を確認
    - 生成されたBoundsの重心点から再度メッシュコードを生成し、元のメッシュコードと一致することを確認
    - 第1次メッシュコード（4桁）
    - 第2次メッシュコード（6桁）
    - 基準地域メッシュコード（8桁）
    - 2分の1地域メッシュコード（9桁）
    - 4分の1地域メッシュコード（10桁）
********************************************************************************
"""


@pytest.mark.parametrize(("pref"), prefectures)
def test_mesh_code_to_bounds_conversion(pref):
    code_1st = data.get_pref_mesh_code(pref, "1st")
    mesh1st = shapely.box(*geomesh.jpmesh.mesh_code_to_bounds(code_1st))
    code_2nd = data.get_pref_mesh_code(pref, "2nd")
    mesh2nd = shapely.box(*geomesh.jpmesh.mesh_code_to_bounds(code_2nd))
    code_standard = data.get_pref_mesh_code(pref, "standard")
    mesh_standard = shapely.box(*geomesh.jpmesh.mesh_code_to_bounds(code_standard))
    code_half = data.get_pref_mesh_code(pref, "half")
    mesh_half = shapely.box(*geomesh.jpmesh.mesh_code_to_bounds(code_half))
    code_quarter = data.get_pref_mesh_code(pref, "quarter")
    mesh_quarter = shapely.box(*geomesh.jpmesh.mesh_code_to_bounds(code_quarter))
    # 生成されたBoundsの重心点から再度メッシュコードを生成し、元のメッシュコードと一致することを確認
    mesh1st_pnt = mesh1st.centroid
    re_mesh1st = geomesh.jpmesh.MeshCodeJP(mesh1st_pnt.x, mesh1st_pnt.y)
    assert re_mesh1st.first_mesh_code == code_1st
    mesh2nd_pnt = mesh2nd.centroid
    re_mesh2nd = geomesh.jpmesh.MeshCodeJP(mesh2nd_pnt.x, mesh2nd_pnt.y)
    assert re_mesh2nd.secandary_mesh_code == code_2nd
    mesh_standard_pnt = mesh_standard.centroid
    re_mesh_standard = geomesh.jpmesh.MeshCodeJP(
        mesh_standard_pnt.x, mesh_standard_pnt.y
    )
    assert re_mesh_standard.standard_mesh_code == code_standard
    mesh_half_pnt = mesh_half.centroid
    re_mesh_half = geomesh.jpmesh.MeshCodeJP(mesh_half_pnt.x, mesh_half_pnt.y)
    assert re_mesh_half.half_mesh_code == code_half
    mesh_quarter_pnt = mesh_quarter.centroid
    re_mesh_quarter = geomesh.jpmesh.MeshCodeJP(mesh_quarter_pnt.x, mesh_quarter_pnt.y)
    assert re_mesh_quarter.quarter_mesh_code == code_quarter


"""
********************************************************************************
Summary:
    指定した範囲をカバーする日本の地域メッシュコードを取得する機能をテスト
Details:
    - 指定した範囲をカバーしている事を確認
    - 戻り値がGeoDataFrameである事を確認
    - GeoDataFrameには、メッシュコードとジオメトリが含まれている事を確認
    - メッシュコードがユニークである事を確認
    - touchesメソッドにより、各メッシュが他のメッシュと接している事を確認（3, 5, 8方向のいずれか）
********************************************************************************
"""


@pytest.mark.parametrize(
    ("mesh_name"),
    [
        "1st",
        "2nd",
    ],
)
def test_generate_jpmesh(mesh_name):
    x_min = 140.650815029
    y_min = 41.134576484
    x_max = 141.312398899
    y_max = 41.503717109
    gdf = geomesh.jpmesh.generate_jpmesh(
        x_min, y_min, x_max, y_max, mesh_name=mesh_name
    )
    # 戻り値がGeoDataFrameである事を確認
    assert isinstance(gdf, gpd.GeoDataFrame)
    # GeoDataFrameには、メッシュコードとジオメトリが含まれている事を確認
    assert "mesh_code" in gdf.columns
    assert "geometry" in gdf.columns
    # メッシュコードがユニークである事を確認
    assert len(gdf) == len(gdf["mesh_code"].unique())
    # 指定した範囲をカバーしている事を確認
    trg_scope = shapely.box(x_min, y_min, x_max, y_max)
    cover_scope = shapely.box(*shapely.union_all(gdf.geometry).bounds)
    assert cover_scope.contains(trg_scope)
    for mesh_box in gdf.geometry:
        rows = gdf[gdf.geometry.touches(mesh_box)].shape[0]
        assert rows in [3, 5, 8]  # 3, 5, 8方向のいずれか
