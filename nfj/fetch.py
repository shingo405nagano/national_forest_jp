"""国有林野データのダウンロードと Shapefile 選択機能を提供するモジュール。

このモジュールは、設定ファイルで定義された URL から国有林野データ（ZIP）を
取得し、安全に展開したうえで対象の Shapefile パスを特定するための機能を提供します。
"""

import io
import json
import os
import re
import tempfile
import zipfile
from enum import StrEnum
from typing import Any, Literal, Optional

import geopandas as gpd
import pandas as pd
import pyogrio
import requests
import yaml

from .config import URLS
from .fields import AddressFields, _AddrsColumns
from .logging_config import get_logger
from .utils import zen_to_han

logger = get_logger(__name__)


class GsFile(StrEnum):
    """国有林野データセット内の主要ファイル種別を表す列挙型。

    Attributes:
        ADDRESS: 小班区画データを表すファイル名プレフィックス。
        FOREST_ROAD: 林道データを表すファイル名プレフィックス。
    """

    ADDRESS = "小班区画"
    FOREST_ROAD = "林道"


class Fetcher(object):
    """国有林野のデータを取得するためのクラス。

    ``URLS`` で定義された URL を使用して、指定された年のデータを取得します。
    """

    def __init__(self, year: int = 2025):
        """Fetcher クラスのインスタンスを初期化します。

        Args:
            year: データを取得する対象の年。デフォルトは 2025 年。

        Raises:
            ValueError: 指定された年に対応する URL 設定が存在しない場合。
        """
        if year not in URLS:
            raise ValueError(f"指定された年 {year} の URL が存在しません。")
        self.urls = URLS[year]

    def check_url(self, prefecture: str) -> bool:
        """指定された都道府県の URL が存在するかを確認します。

        Args:
            prefecture: 確認する都道府県の名前。

        Returns:
            指定された都道府県の URL が存在する場合は True、そうでない場合は False。

        Warns:
            UserWarning: 都道府県名が設定に存在しない場合、または URL へのアクセスに
                失敗した場合に警告します。
        """
        if prefecture not in self.urls:
            pattern = re.compile(prefecture)
            results = [pref for pref in self.urls.keys() if pattern.search(pref)]
            if results:
                logger.warning(
                    f"都道府県 '{prefecture}' の URL が見つかりませんでした。"
                    f"類似する都道府県名: {', '.join(results)}"
                )
            else:
                logger.warning(
                    f"都道府県 '{prefecture}' の URL が見つかりませんでした。"
                )
            return False
        url = self.urls[prefecture]
        try:
            response = requests.head(url)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning(f"URL '{url}' にアクセスできませんでした: {e}")
            return False


class GsShapeFile(object):
    """都道府県単位の国有林野データ ZIP を扱うユーティリティクラス。

    インスタンス生成時にデータの取得と展開を実行し、森林計画区の一覧作成や
    対象 Shapefile パスの選択機能を提供します。
    """

    def __init__(
        self,  #
        prefecture: str,
        year: int = 2025,
        category: Literal["address", "road"] = "address",
        endswith: str = ".shp",
    ):
        """GsShapeFile クラスのインスタンスを初期化します。

        Args:
            prefecture: 取得対象の都道府県名。
            year: 取得対象年。
            category: 取得対象カテゴリ。
            endswith: 対象ファイルの拡張子。

        Raises:
            ValueError: URL が見つからない場合、または category の指定が不正な場合。

        Warns:
            UserWarning: 林道カテゴリ選択時に、対応フィールドが未定義であることを警告します。
        """
        # URLの確認
        fetcher = Fetcher(year)
        if not fetcher.check_url(prefecture):
            raise ValueError(f"都道府県 '{prefecture}' の URL を確認できませんでした。")
        self.url = fetcher.urls[prefecture]
        # フィールドの初期化
        if category.upper() == GsFile.ADDRESS.name:
            self.fields: AddressFields = AddressFields()
            self.file_name = GsFile.ADDRESS.value + endswith
        elif category.upper() == GsFile.FOREST_ROAD.name:
            logger.warning("道路データのフィールドは未定義です。")
            self.fields: AddressFields = AddressFields()  # ダミーのフィールドを使用
            self.file_name = GsFile.FOREST_ROAD.value + endswith
        else:
            raise ValueError(
                f"カテゴリ '{category}' は 'address' または 'road' のいずれかで"
                "なければなりません。"
            )
        self.endswith = endswith
        self.zip_file: Optional[zipfile.ZipFile] = None
        self.file_names: list[str] = []
        self.temp_dir_obj: Optional[tempfile.TemporaryDirectory] = None
        self.temp_dir_path: Optional[str] = None
        self.extract_root_path: Optional[str] = None
        self.download_and_extract()
        self.plan_area_names = self.get_plan_area_names()

    def download_and_extract(self) -> bool:
        """指定された都道府県のデータをダウンロードして解凍します。

        ダウンロードした ZIP ファイルは一時ディレクトリに展開され、
        展開後のトップディレクトリは ``extract_root_path`` に設定されます。

        Raises:
            ValueError: ダウンロードに失敗した場合。
        """
        try:
            response = requests.get(self.url, timeout=120)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ValueError(
                f"URL '{self.url}' からデータをダウンロードできませんでした。エラー: {e}"
            )

        zip_buffer = io.BytesIO(response.content)
        self.zip_file = zipfile.ZipFile(zip_buffer)
        self.file_names = self.zip_file.namelist()
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir_path = self.temp_dir_obj.name
        self._safe_extract_zip()
        self.extract_root_path = self._extract_root_path()
        self.plan_area2keikaku = {}
        return True

    def _safe_extract_zip(self) -> None:
        """ZIP 内パスを検証してから安全に展開します。

        展開先ディレクトリ外への書き込みを防ぐため、各エントリの絶対パスを
        検証してから展開を実行します。

        Raises:
            ValueError: ZIP オブジェクトまたは一時ディレクトリが未初期化の場合。
            ValueError: 展開先ディレクトリ外を指す不正なパスが含まれる場合。
        """
        if not self.zip_file or not self.temp_dir_path:
            raise ValueError("ZIPファイルまたは一時ディレクトリが未初期化です。")

        base_dir = os.path.abspath(self.temp_dir_path)
        for member in self.zip_file.infolist():
            member_path = os.path.abspath(os.path.join(base_dir, member.filename))
            if os.path.commonpath([base_dir, member_path]) != base_dir:
                raise ValueError("ZIPに不正なパスが含まれています。")

        self.zip_file.extractall(path=base_dir)

    def _extract_root_path(self) -> str:
        """展開したデータセットのトップディレクトリパスを返します。

        Returns:
            展開後データのルートディレクトリパス。

        Raises:
            ValueError: 一時ディレクトリが未初期化の場合。
        """
        if not self.temp_dir_path:
            raise ValueError("Tempディレクトリが初期化されていません。")

        top_dirs = []
        for name in self.file_names:
            parts = [part for part in name.split("/") if part]
            if parts:
                top_dirs.append(parts[0])

        if not top_dirs:
            return self.temp_dir_path

        top_dir = sorted(set(top_dirs))[0]
        return os.path.join(self.temp_dir_path, top_dir)

    @staticmethod
    def _normalize_plan_area_name(name: str) -> str:
        """森林計画区ディレクトリ名を比較しやすい形式に正規化します。

        ディレクトリ名に含まれる半角・全角の数字を除去し、前後の空白を取り除きます。

        Args:
            name: 正規化対象のディレクトリ名。

        Returns:
            正規化後の森林計画区名。
        """
        result = re.sub(r"[0-9０-９]", "", name)
        return result.strip()

    def get_plan_area_names(self) -> list[str]:
        """展開したディレクトリから森林計画区名を抽出して返します。

        Returns:
            抽出した森林計画区名の一覧。展開先が無効な場合は空リスト。
        """
        if not self.extract_root_path or not os.path.isdir(self.extract_root_path):
            logger.info(
                "`download_and_extract` 実行前の為、森林計画区名を取得できません。空リストを返します。"
            )
            return []

        plan_area_names = []
        for entry in os.listdir(self.extract_root_path):
            full_path = os.path.join(self.extract_root_path, entry)
            if not os.path.isdir(full_path):
                continue

            normalized = self._normalize_plan_area_name(entry)
            if normalized:
                plan_area_names.append(normalized)
        return plan_area_names

    def select_file_path(self, plan_area: str) -> str:
        """指定された森林計画区の対象 Shapefile パスを返します。

        Args:
            plan_area: 対象とする森林計画区名（部分一致可）。

        Returns:
            条件に一致する Shapefile の絶対パス。

        Raises:
            ValueError: データ展開先が存在しない場合。
            ValueError: 条件に一致するファイルが見つからない場合。
        """
        if not self.extract_root_path or not os.path.isdir(self.extract_root_path):
            raise ValueError("データ展開先ディレクトリが存在しません。")

        for entry in os.listdir(self.extract_root_path):
            plan_area_dir = os.path.join(self.extract_root_path, entry)
            if not os.path.isdir(plan_area_dir):
                continue

            normalized = self._normalize_plan_area_name(entry)
            if plan_area not in entry and plan_area not in normalized:
                continue

            for root, _, files in os.walk(plan_area_dir):
                for filename in files:
                    if self.file_name in filename and filename.endswith(self.endswith):
                        return os.path.join(root, filename)

        raise ValueError(
            "指定された条件に対応するファイルが見つかりませんでした。"
            f"条件: plan_area='{plan_area}', file_name='{self.file_name}', "
            f"存在する計画区: {', '.join(self.plan_area_names)}"
        )

    def _read_file(self, plan_area: str) -> gpd.GeoDataFrame:
        """指定された森林計画区の Shapefile を読み込んで GeoDataFrame として返します。

        Args:
            plan_area: 対象とする森林計画区名（部分一致可）。

        Returns:
            読み込んだ Shapefile の GeoDataFrame。

        Raises:
            ValueError: 対象ファイルが見つからない場合。
            ValueError: ファイルの読み込みに失敗した場合。
        """
        file_path = self.select_file_path(plan_area)
        try:
            gdf = pyogrio.read_dataframe(file_path)
            return gdf
        except Exception as e:
            raise ValueError(
                f"ファイル '{file_path}' の読み込みに失敗しました。エラー: {e}"
            )

    def summary(self, **kwargs: Any) -> dict[str, Any]:
        """ダウンロードしたZipファイルに保存されているデータの概要を返します。

        Returns:

            dict[str, Any]:
                データ概要を含む辞書。構造は以下のようになります。
                ```
                ├─ 森林計画区
                │   ├─ 森林管理署
                │   │   ├─ 担当区
                │   │   │   ├─ 国有林
                │   │   │   ...
                │   ... ... ...
                ├─ 森林計画区2
                ...
                ```
        ## Kwargs:
            yaml(bool): データを'YAML'形式の文字列で返すかどうか。デフォルトはFalse。
            json(bool): データを'JSON'形式の文字列で返すかどうか。デフォルトはFalse。
        """
        # ダウンロードしたデータはカラムが日本語であるため注意が必要です。
        cols = _AddrsColumns()
        selects_en = [
            cols.plan_area,
            cols.office,
            cols.branch_office,
            cols.locality,
            cols.main_address,
        ]
        selects_org = []
        for en in selects_en:
            field_info = self.fields.field_info(en)
            selects_org.append(field_info.org)
        dfs = []
        for plan_area in self.plan_area_names:
            file_path = self.select_file_path(plan_area)
            _df = pyogrio.read_dataframe(
                file_path, columns=selects_org, read_geometry=False
            )
            field_info = self.fields.field_info(cols.main_address)
            _df[field_info.org] = _df[field_info.org].apply(field_info.cast)
            _df = _df.groupby(by=selects_org[:-1], as_index=False).agg(
                {field_info.org: "unique"}
            )
            dfs.append(_df)
        # 全ての計画区のデータを結合し、カラムを英語に変換します。
        df = pd.concat(dfs, ignore_index=True)
        rename_dict = self.fields.rename_dict_org_to_en()
        df.rename(columns=rename_dict, inplace=True)
        # 国有林名を全角から半角に変換します。
        df[cols.locality] = df[cols.locality].apply(zen_to_han)
        # 辞書の構造に変換します。
        summary = {}
        for _, row in df.iterrows():
            plan_area, office, branch_office, locality, main_address = row.values
            main_address = main_address.tolist()  # np.ndarray -> list に変換
            (
                summary.setdefault(plan_area, {})
                .setdefault(office, {})
                .setdefault(branch_office, {})
                .setdefault(locality, [])
            )
            if main_address:
                summary[plan_area][office][branch_office][locality] += main_address

        # YAML形式で返す場合
        if kwargs.get("yaml", False):
            return yaml.dump(summary, allow_unicode=True, sort_keys=False, indent=2)
        elif kwargs.get("json", False):
            return json.dumps(summary, ensure_ascii=False, indent=2)
        return summary

    def cleanup(self) -> None:
        """確保したリソースを解放します。

        ZIP ファイルハンドルと一時ディレクトリを解放し、関連する内部状態を初期化します。
        """
        if self.zip_file is not None:
            self.zip_file.close()
            self.zip_file = None

        if self.temp_dir_obj is not None:
            self.temp_dir_obj.cleanup()
            self.temp_dir_obj = None

        self.temp_dir_path = None
        self.extract_root_path = None
        self.file_names = []

    def __enter__(self) -> "GsShapeFile":
        """with 文で利用するために自身を返します。

        Returns:
            現在のインスタンス。
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """with 文終了時にリソースを解放します。

        Args:
            exc_type: 発生した例外クラス。例外がない場合は None。
            exc_value: 発生した例外インスタンス。例外がない場合は None。
            traceback: 例外のトレースバック情報。例外がない場合は None。
        """
        self.cleanup()
