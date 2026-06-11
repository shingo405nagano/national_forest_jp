import os
import shutil
import sqlite3
import tempfile
from typing import Optional

import geopandas as gpd

from .logging_config import get_logger

logger = get_logger(__name__)


class GeoPackage(object):
    """
    GeoPackage形式のデータを扱うクラス。
     - GeoPackageは、地理空間データを格納するためのオープンなフォーマットで、SQLiteデータ
        ベースをベースにしています。
     - ここに渡すGeoDataFrameは、GsicAddressShapeクラスのgeodataframeメソッドで取得した
        ものを想定しています。それ以外のGeoDataFrameを渡すと、意図しない動作をする可能性があ
        ります。
    Args:
        field_and_alias(dict[str, str], optional):
            フィールド名とエイリアスの対応関係を表す辞書。例: {"field1": "エイリアス1", "field2": "エイリアス2"}
            これは、GeoPackageファイルにフィールドエイリアスを追加するために使用されます。
             - GeoPackageファイルの指定されたテーブルにフィールドエイリアスを追加します。
             - これは、gpkg_extensions テーブルに「Schema」拡張を登録し、gpkg_data_columns
                テーブルにエイリアス情報を挿入/更新することで実現されます。
             - これにより、GISソフトウェアがフィールドのエイリアスを認識できるようになります。

    Attributes:
        temp_file_path(str):
            一時的に作成されたGeoPackageファイルのパス。to_geopackageメソッドでGeoDataF
            rameを保存する際に使用されます。
        field_and_alias(dict[str, str], optional):
            フィールド名とエイリアスの対応関係を表す辞書。例: {"field1": "エイリアス1", "field2": "エイリアス2"}
            これは、GeoPackageファイルにフィールドエイリアスを追加するために使用されます。

    Methods:
        to_geopackage(gdf, layer, alias=False):
            GeoDataFrameをGeoPackage形式のファイルに保存し、そのファイルパスを返します。
            フィールド名のエイリアスを適用したい場合は、``alias`` を ``True`` に設定し、ク
            ラスの初期化時に渡した ``field_and_alias`` を使用してカラム名を変更します。
         save(output_path):
            一時的に作成されたGeoPackageファイルを指定されたパスに保存します。
         delete_temp_file():
            一時的に作成されたGeoPackageファイルを削除します。
        add_alias(table_name, field_and_alias):
            GeoPackageファイルの指定されたテーブルにフィールドエイリアスを追加します。
             - これは、gpkg_extensions テーブルに「Schema」拡張を登録し、gpkg_data_columns
                テーブルにエイリアス情報を挿入/更新することで実現されます。
             - これにより、GISソフトウェアがフィールドのエイリアスを認識できるようになります。

    """

    def __init__(self, field_and_alias: Optional[dict[str, str]] = None):
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp_file:
            self.temp_file_path = tmp_file.name

        self.field_and_alias = field_and_alias

    def save(self, output_path: str):
        """
        一時的に作成されたGeoPackageファイルを指定されたパスに保存します。

        Args:
            output_path(str):
                保存先のファイルパス。例: "output.gpkg"
        """
        if isinstance(output_path, str):
            shutil.copy(self.temp_file_path, output_path)
            logger.info(f"GeoPackageファイルが '{output_path}' として保存されました。")
        else:
            raise ValueError("output_pathは文字列で指定してください。")

    def delete_temp_file(self):
        if os.path.exists(self.temp_file_path):
            os.remove(self.temp_file_path)

    def add_alias(self, table_name, field_and_alias: dict[str, str]):
        logger.info(
            f"GeoPackageファイルのテーブル'{table_name}'にエイリアスを追加します。"
        )
        try:
            conn = sqlite3.connect(self.temp_file_path)
            cursor = conn.cursor()
            # 1. gpkg_extensions テーブルの確認と「Schema」拡張の登録
            # まず、gpkg_extensions テーブルが存在するか確認
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='gpkg_extensions';"
            )
            if not cursor.fetchone():
                logger.info("gpkg_extensions テーブルを作成します。")
                cursor.execute("""
                    CREATE TABLE gpkg_extensions (
                        table_name TEXT,
                        column_name TEXT,
                        extension_name TEXT NOT NULL,
                        definition TEXT NOT NULL,
                        scope TEXT NOT NULL,
                        CONSTRAINT ge_tce UNIQUE (table_name, column_name, extension_name)
                    );
                """)
                conn.commit()

            # 「gpkg_schema」拡張が登録されているか確認
            cursor.execute(
                "SELECT * FROM gpkg_extensions WHERE extension_name = 'gpkg_schema';"
            )
            if not cursor.fetchone():
                logger.debug(
                    "gpkg_schema 拡張を gpkg_extensions テーブルに登録します。"
                )
                cursor.execute("""
                    INSERT INTO gpkg_extensions (table_name, column_name, extension_name, definition, scope)
                    VALUES (NULL, NULL, 'gpkg_schema', 'http://www.geopackage.org/spec121/#extension_schema', 'read-write');
                """)
                conn.commit()

            # 2. gpkg_data_columns テーブルの確認と作成
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='gpkg_data_columns';"
            )
            if not cursor.fetchone():
                logger.info("gpkg_data_columns テーブルを作成します。")
                cursor.execute("""
                    CREATE TABLE gpkg_data_columns (
                    table_name TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    name TEXT,
                    title TEXT,
                    description TEXT,
                    mime_type TEXT,
                    constraint_name TEXT,
                    CONSTRAINT pk_gdc PRIMARY KEY (table_name, column_name),
                    CONSTRAINT gdc_tn UNIQUE (table_name, name)
                    );
                """)
                conn.commit()

            # 3. gpkg_data_columns テーブルへのエイリアス情報の挿入/更新
            for field, alias in field_and_alias.items():
                # 既存のレコードがあるか確認
                cursor.execute(
                    "SELECT * FROM gpkg_data_columns WHERE table_name = ? AND column_name = ?;",
                    (table_name, field),
                )
                if cursor.fetchone():
                    # 既存のレコードがあれば更新
                    cursor.execute(
                        """
                        UPDATE gpkg_data_columns
                        SET name = ?, title = ?, description = ?
                        WHERE table_name = ? AND column_name = ?;
                    """,
                        (alias, None, None, table_name, field),
                    )  # title, description はNone（NULL）で設定
                else:
                    # なければ挿入
                    cursor.execute(
                        """
                        INSERT INTO gpkg_data_columns (table_name, column_name, name, title, description)
                        VALUES (?, ?, ?, ?, ?);
                    """,
                        (table_name, field, alias, None, None),
                    )  # title, description はNone（NULL）で設定
                conn.commit()

            logger.info(
                f"テーブル '{table_name}' のフィールドエイリアスが gpkg_data_columns テーブルに追加/更新されました。"
            )

        except sqlite3.Error as e:
            logger.error(f"データベースエラーが発生しました: {e}")
        finally:
            if conn:
                conn.close()

    def to_geopackage(self, gdf: gpd.GeoDataFrame, layer: str, alias: bool = False):
        """
        GeoDataFrameをGeoPackage形式のファイルに保存し、そのファイルパスを返します。
        フィールド名のエイリアスを適用したい場合は、``alias`` を ``True`` に設定し、
        クラスの初期化時に渡した ``field_and_alias`` を使用してカラム名を変更します。

        Args:
            gdf(gpd.GeoDataFrame):
                GeoDataFrameオブジェクト。GsicAddressShapeクラスのgeodataframeメソッドで取得したものを想定しています。
            layer(str):
                保存するレイヤー名。
            alias(bool, optional):
                フィールド名のエイリアスを適用するかどうか。デフォルトは ``False`` です。
                Trueの場合は、Layerとして保存した後に、指定されたエイリアスを追加し、
                FieldとAliasの対応関係を保持します。
        """
        gdf.to_file(self.temp_file_path, driver="GPKG", layer=layer)
        if alias and self.field_and_alias is not None:
            self.add_alias(layer, self.field_and_alias)
