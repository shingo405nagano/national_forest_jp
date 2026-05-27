import io
import json
import os
import tempfile
import zipfile

import pandas as pd
import pytest
import requests
import yaml

from ..fetch import Fetcher, GsShapeFile
from ..fields import AddressFields


def test_normalize_plan_area_name_removes_digits_and_spaces():
    assert GsShapeFile._normalize_plan_area_name("  第12計画区  ") == "第計画区"
    assert GsShapeFile._normalize_plan_area_name("計画区３") == "計画区"


def test_check_url_returns_true_when_head_succeeds(monkeypatch):
    fetcher = Fetcher.__new__(Fetcher)
    fetcher.urls = {"北海道": "https://example.com/hokkaido"}

    class Response:
        def raise_for_status(self):
            return None

    monkeypatch.setattr("requests.head", lambda url: Response())

    assert fetcher.check_url("北海道") is True


def test_check_url_returns_false_for_similar_names_and_request_errors(
    monkeypatch, caplog
):
    fetcher = Fetcher.__new__(Fetcher)
    fetcher.urls = {
        "東京": "https://example.com/tokyo",
        "東北": "https://example.com/tohoku",
    }

    caplog.set_level("WARNING")

    assert fetcher.check_url("東") is False
    assert "類似する都道府県名" in caplog.text

    def raise_request_exception(url):
        raise requests.RequestException("boom")

    monkeypatch.setattr("requests.head", raise_request_exception)

    assert fetcher.check_url("東京") is False
    assert "アクセスできませんでした" in caplog.text


def test_check_url_returns_false_without_similar_names(caplog):
    fetcher = Fetcher.__new__(Fetcher)
    fetcher.urls = {"北海道": "https://example.com/hokkaido"}

    caplog.set_level("WARNING")

    assert fetcher.check_url("大阪") is False
    assert "類似する都道府県名" not in caplog.text


def test_safe_extract_zip_requires_initialized_state():
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.zip_file = None
    shape_file.temp_dir_path = None

    with pytest.raises(
        ValueError, match="ZIPファイルまたは一時ディレクトリが未初期化です。"
    ):
        shape_file._safe_extract_zip()


def test_safe_extract_zip_rejects_path_traversal(tmp_path):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.temp_dir_path = str(tmp_path)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as zf:
        zf.writestr("../escape.txt", "boom")
    buffer.seek(0)

    shape_file.zip_file = zipfile.ZipFile(buffer)

    try:
        with pytest.raises(ValueError, match="ZIPに不正なパスが含まれています。"):
            shape_file._safe_extract_zip()
    finally:
        shape_file.zip_file.close()


def test_download_and_extract_reads_zip_and_sets_paths(monkeypatch):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.url = "https://example.com/archive.zip"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as zf:
        zf.writestr("第1計画区/小班区画.shp", "dummy")
    zip_bytes = buffer.getvalue()

    class Response:
        content = zip_bytes

        def raise_for_status(self):
            return None

    monkeypatch.setattr("requests.get", lambda url, timeout: Response())

    assert shape_file.download_and_extract() is True
    assert shape_file.file_names == ["第1計画区/小班区画.shp"]
    assert shape_file.extract_root_path.endswith("第1計画区")
    assert shape_file.plan_area2keikaku == {}

    shape_file.cleanup()


def test_download_and_extract_wraps_request_errors(monkeypatch):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.url = "https://example.com/archive.zip"

    def raise_request_exception(url, timeout):
        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr("requests.get", raise_request_exception)

    with pytest.raises(
        ValueError,
        match="URL 'https://example.com/archive.zip' からデータをダウンロードできませんでした。",
    ):
        shape_file.download_and_extract()


def test_extract_root_path_handles_empty_and_nested_entries(tmp_path):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.temp_dir_path = str(tmp_path)

    shape_file.file_names = []
    assert shape_file._extract_root_path() == str(tmp_path)

    shape_file.file_names = ["A/one.shp", "B/two.shp", "A/other.dbf"]
    assert shape_file._extract_root_path() == os.path.join(str(tmp_path), "A")


def test_get_plan_area_names_filters_files_and_normalizes_names(tmp_path):
    root = tmp_path / "extract"
    root.mkdir()
    (root / "第1計画区").mkdir()
    (root / "第2計画区  ").mkdir()
    (root / "ignore.txt").write_text("x", encoding="utf-8")

    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.extract_root_path = str(root)

    assert shape_file.get_plan_area_names() == ["第計画区", "第計画区"]


def test_get_plan_area_names_skips_non_matching_directory(tmp_path):
    root = tmp_path / "extract"
    root.mkdir()
    (root / "readme.txt").write_text("x", encoding="utf-8")
    (root / "第1計画区").mkdir()

    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.extract_root_path = str(root)

    assert shape_file.get_plan_area_names() == ["第計画区"]


def test_get_plan_area_names_returns_empty_when_root_is_missing():
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.extract_root_path = None

    assert shape_file.get_plan_area_names() == []


def test_select_file_path_finds_matching_shapefile(tmp_path):
    root = tmp_path / "extract"
    plan_area_dir = root / "第1計画区"
    nested_dir = plan_area_dir / "nested"
    nested_dir.mkdir(parents=True)
    target_file = nested_dir / "小班区画.shp"
    target_file.write_text("dummy", encoding="utf-8")

    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.extract_root_path = str(root)
    shape_file.file_name = "小班区画.shp"
    shape_file.endswith = ".shp"
    shape_file.plan_area_names = ["第計画区"]

    assert shape_file.select_file_path("第計画区") == str(target_file)


def test_select_file_path_rejects_missing_root():
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.extract_root_path = None

    with pytest.raises(ValueError, match="データ展開先ディレクトリが存在しません。"):
        shape_file.select_file_path("第計画区")


def test_select_file_path_rejects_missing_file(tmp_path):
    root = tmp_path / "extract"
    (root / "第1計画区").mkdir(parents=True)

    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.extract_root_path = str(root)
    shape_file.file_name = "小班区画.shp"
    shape_file.endswith = ".shp"
    shape_file.plan_area_names = ["第計画区"]

    with pytest.raises(
        ValueError, match="指定された条件に対応するファイルが見つかりませんでした。"
    ):
        shape_file.select_file_path("第計画区")


def test_read_file_returns_dataframe(monkeypatch):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.select_file_path = lambda plan_area: "/tmp/sample.shp"

    expected = pd.DataFrame({"x": [1]})
    monkeypatch.setattr("nfj.fetch.pyogrio.read_dataframe", lambda path: expected)

    assert shape_file._read_file("第計画区") is expected


def test_read_file_wraps_pyogrio_errors(monkeypatch):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.select_file_path = lambda plan_area: "/tmp/sample.shp"

    def raise_error(path):
        raise Exception("boom")

    monkeypatch.setattr("nfj.fetch.pyogrio.read_dataframe", raise_error)

    with pytest.raises(
        ValueError, match="ファイル '/tmp/sample.shp' の読み込みに失敗しました。"
    ):
        shape_file._read_file("第計画区")


def test_cleanup_resets_resources():
    shape_file = GsShapeFile.__new__(GsShapeFile)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w") as zf:
        zf.writestr("sample.txt", "data")
    zip_buffer.seek(0)
    shape_file.zip_file = zipfile.ZipFile(zip_buffer)
    shape_file.temp_dir_obj = tempfile.TemporaryDirectory()
    shape_file.temp_dir_path = shape_file.temp_dir_obj.name
    shape_file.extract_root_path = shape_file.temp_dir_path
    shape_file.file_names = ["sample.txt"]

    shape_file.cleanup()

    assert shape_file.zip_file is None
    assert shape_file.temp_dir_obj is None
    assert shape_file.temp_dir_path is None
    assert shape_file.extract_root_path is None
    assert shape_file.file_names == []


def test_summary_builds_nested_structure_and_serializes(monkeypatch):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    shape_file.fields = AddressFields()
    shape_file.plan_area_names = ["第1計画区", "第2計画区"]
    shape_file._summary_files = {
        "第1計画区": "/tmp/plan1.shp",
        "第2計画区": "/tmp/plan2.shp",
    }
    shape_file.select_file_path = lambda plan_area: shape_file._summary_files[plan_area]

    cols = shape_file.fields
    plan_area_org = cols.field_info("plan_area").org
    office_org = cols.field_info("office").org
    branch_org = cols.field_info("branch_office").org
    locality_org = cols.field_info("locality").org
    main_address_org = cols.field_info("main_address").org

    df_map = {
        "/tmp/plan1.shp": pd.DataFrame(
            [
                {
                    plan_area_org: "第1計画区",
                    office_org: "札幌森林管理署",
                    branch_org: "担当区A",
                    locality_org: "　国有林１　",
                    main_address_org: 1,
                },
                {
                    plan_area_org: "第1計画区",
                    office_org: "札幌森林管理署",
                    branch_org: "担当区A",
                    locality_org: "　国有林１　",
                    main_address_org: 2,
                },
            ]
        ),
        "/tmp/plan2.shp": pd.DataFrame(
            [
                {
                    plan_area_org: "第2計画区",
                    office_org: "旭川森林管理署",
                    branch_org: "担当区B",
                    locality_org: "国有林２",
                    main_address_org: 3,
                }
            ]
        ),
    }

    monkeypatch.setattr(
        "nfj.fetch.pyogrio.read_dataframe", lambda path, **kwargs: df_map[path].copy()
    )

    result = shape_file.summary()
    assert result == {
        "第1計画区": {"札幌森林管理署": {"担当区A": {"国有林1": [1, 2]}}},
        "第2計画区": {"旭川森林管理署": {"担当区B": {"国有林2": [3]}}},
    }

    yaml_result = shape_file.summary(yaml=True)
    json_result = shape_file.summary(json=True)

    assert yaml.safe_load(yaml_result) == result
    assert json.loads(json_result) == result


def test_gsshapefile_init_handles_road_and_invalid_category(monkeypatch, caplog):
    monkeypatch.setattr(Fetcher, "check_url", lambda self, prefecture: True)
    monkeypatch.setattr(GsShapeFile, "download_and_extract", lambda self: None)
    monkeypatch.setattr(GsShapeFile, "get_plan_area_names", lambda self: [])

    caplog.set_level("WARNING")
    road = GsShapeFile("北海道", year=2025, category="FOREST_ROAD", endswith=".geojson")

    assert road.file_name == "林道.geojson"
    assert "道路データのフィールドは未定義です。" in caplog.text

    with pytest.raises(
        ValueError,
        match="カテゴリ 'invalid' は 'address' または 'road' のいずれかでなければなりません。",
    ):
        GsShapeFile("北海道", year=2025, category="invalid")


def test_fetcher_rejects_unknown_year():
    with pytest.raises(ValueError, match="指定された年 1999 の URL が存在しません。"):
        Fetcher(year=1999)


def test_gsshapefile_context_manager_calls_cleanup(monkeypatch):
    shape_file = GsShapeFile.__new__(GsShapeFile)
    called = {}

    monkeypatch.setattr(
        shape_file, "cleanup", lambda: called.setdefault("cleanup", True)
    )

    with shape_file as returned:
        assert returned is shape_file

    assert called == {"cleanup": True}
