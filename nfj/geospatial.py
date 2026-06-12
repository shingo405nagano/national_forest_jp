import datetime
import io
import json
import re
from typing import Any, Optional

import fastkml
import geopandas as gpd
import shapely

from .config import (  # noqa: F401
    AuthorityCoding,
    BranchOfficeCoding,
    CityCoding,
    ConservationCoding,
    ForestFeatureTypeCoding,
    ForestTypeDetailCoding,
    GreenCorridorCoding,
    LocalityCoding,
    OfficeCoding,
    PlanAreaCoding,
    ProtectedForestCoding,
    TreeNameCoding,
)
from .enums import OutputGeoJsonType
from .fetch import GsShapeFile
from .fields import (
    BranchOfficeFields,
    FieldInfo,
    LocalityFields,
    MainAddressFields,
    OfficeFields,
    ProtectedForestFields,
    _AddrsColumns,
)
from .geopackage import GeoPackage
from .keyhole import (  # noqa: F401
    BranchOfficeKmlKwargs,
    KeyholeMarkupLanguage,
    KmlKwargs,
    LocalityKmlKwargs,
    MainAddressKmlKwargs,
    OfficeKmlKwargs,
    SubAddressKmlKwargs,
)
from .utils import txt_normalizer


def convert_wareki_to_seireki(wareki: str) -> int:
    """和暦を西暦に変換する関数。

    Args:
        wareki: 和暦の文字列（例: "令和５年度樹立"）。

    Returns:
        西暦の整数（例: 2023）。
    """
    if not isinstance(wareki, str):
        return wareki
    wareki = txt_normalizer(wareki.strip()).replace("年度樹立", "").replace("元", "1")

    era_mapping = {
        "平成": 1989,
        "令和": 2019,
    }
    for era, start_year in era_mapping.items():
        if wareki.startswith(era):
            wy = int(re.findall(r"\d+", wareki)[0])
            return start_year + wy - 1
    raise ValueError(f"不明な和暦形式: {wareki}")


class GsicAddressShape(GsShapeFile):
    """国有林の小班区画データを扱うクラス。

    GsShapeFile クラスを継承し、国有林の小班区画に特化した機能を提供します。
    """

    def __init__(
        self,  #
        prefecture: str,
        year: int = 2025,
        endswith: str = ".shp",
    ):
        """GsicAddressShape クラスのインスタンスを初期化します。

        Args:
            prefecture: 取得対象の都道府県名。
            year: 取得対象年。
            endswith: 対象ファイルの拡張子。

        Raises:
            ValueError: URL が見つからない場合。
        """
        super().__init__(
            prefecture=prefecture,
            year=year,
            category="address",
            endswith=endswith,
        )

    def geodataframe(self, plan_area: str, **kwargs: Any) -> gpd.GeoDataFrame:
        """指定した森林計画区の小班区画データを GeoDataFrame として返します。

        ここでは、内部で以下の処理が行われます。
            1. EsriShapefile を GeoDataFrame として読み込む。
            2. GeoDataFrame のカラムを英名に変換し、必要なカラムのみを残す。
            3. 各カラムのデータ型を '.confs/fields.yaml' に定義されたものに基づいて適切に変換する。
            4. Nan 値を適切なデフォルト値に置換する。
            5. 国有林名に全角数字が含まれるため、全角を半角に変換する。
            6. 林小班名に余計な文字が含まれる為、削除してしまう。
            7. 樹立年度を和暦から西暦に変換する。
            8. 樹齢を修正する。
            9. 保護林の区分コードを正式な名称に変換する。
            10. 緑の回廊の区分コードを正式な名称に変換する。
            11. 重複する林小班が存在する場合は、1つにまとめる。
            12. Geometry のバリデーションを行い、無効なジオメトリを修正する。

        Args:
            plan_area: 森林計画区の名称。

        Returns:
            指定した森林計画区の小班区画データを含む GeoDataFrame。
        """
        addrs_cols = _AddrsColumns()
        # EsriShapefile を GeoDataFrame として読み込む
        gdf = self._read_file(plan_area=plan_area)
        # 樹立年度を西暦に変換する
        gdf["樹立年度"] = gdf["樹立年度"].apply(convert_wareki_to_seireki)
        # 更新年を記録
        gdf[addrs_cols.updated_year] = datetime.datetime.now().year
        gdf = self.__cast_geodataframe(gdf)
        org_columns = gdf.columns
        # 森林管理局名に”森林管理局”が含まれている場合は削除する
        gdf[addrs_cols.authority] = (
            gdf[addrs_cols.authority].str.replace("森林管理局", "").str.strip()
        )
        # 正規化が必要なカラムの値を正規化する（「市町村名」「担当区」「国有林名」）
        for col in [addrs_cols.city, addrs_cols.branch_office, addrs_cols.locality]:
            gdf[col] = gdf[col].apply(txt_normalizer)

        # 林小班名に余計な文字が含まれる為、削除してしまう
        gdf[addrs_cols.address] = gdf[addrs_cols.address].apply(self.__replace_address)
        # 重複する林小班が存在する場合は、1つにまとめる
        gdf = gdf.dissolve(
            by=[addrs_cols.office, addrs_cols.address], as_index=False, aggfunc="first"
        )
        # 樹齢を修正する
        for col in [
            addrs_cols.tree_age_1,
            addrs_cols.tree_age_2,
            addrs_cols.tree_age_3,
        ]:
            gdf[col] = gdf.apply(
                lambda row: self.__fix_tree_age(
                    row[addrs_cols.establishment_year], row[col]
                ),
                axis=1,
            )

        # 保護林の区分コードを正式な名称に変換する
        gdf[addrs_cols.conservation] = gdf[addrs_cols.conservation].apply(
            self.__decode_conservation
        )
        # 緑の回廊の区分コードを正式
        gdf[addrs_cols.green_corridor] = gdf[addrs_cols.green_corridor].apply(
            self.__decode_green_corridor
        )
        # Geometry のバリデーションを行い、無効なジオメトリを修正する
        gdf["geometry"] = gdf["geometry"].apply(self.validate_geometry)  # type: ignore
        return gdf[org_columns]  # 元の列順に戻す

    def __cast_geodataframe(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame の属性を適切なデータ型に変換します。

        ここで処理されるデータ型は、'.confs/fields.yaml' に定義されたものに基づいています。

        Args:
            gdf: データ型を変換する GeoDataFrame。

        Returns:
            データ型が変換された GeoDataFrame。
        """
        # 属性名をオリジナルの日本語から英語に変換し、必要な属性のみを残す
        gdf.rename(columns=self.fields.rename_dict_org_to_en(), inplace=True)
        gdf = gdf[self.fields.use_default_en_fields()].copy()
        for col in gdf.columns:
            if col == "geometry":
                # geometry列は変換しない
                continue
            field_info: FieldInfo = self.fields.field_info(col)  # type: ignore
            gdf[col] = gdf[col].apply(lambda x: field_info.cast(x))
            gdf[col] = gdf[col].fillna(field_info.default)
            if field_info.dtype == str:  # type: ignore
                gdf[col] = gdf[col].replace(
                    {"nan": field_info.default, "NaN": field_info.default}
                )
        return gdf

    def __replace_address(self, text: str) -> str:
        """林小班名に余計な文字が含まれる為、削除してしまう。

        Args:
            text: 変換対象の文字列。

        Returns:
            余計な文字が削除された文字列。
        """
        return txt_normalizer(text.replace("_林班_", "").strip())

    def __fix_tree_age(self, ad: int, age: int) -> int:
        """樹齢の値を修正するための関数。

        Args:
            ad: 樹立年度の西暦年。
            age: 樹齢の値

        Returns:
            修正された樹齢の値、林齢は計算結果に1を加算した値を返す。
        """
        now_year = datetime.datetime.now().year
        diff_year = now_year - ad
        return age + diff_year + 1

    def __decode_conservation(self, code: int) -> str:
        """保護林の区分コードを正式な名称に変換する関数。

        Args:
            code: 保護区分コード。

        Returns:
            保護区分のラベル。
        """
        try:
            code = int(code)
        except Exception:
            return str(code)
        else:
            coding = ConservationCoding()
            return coding.decode_original(code)

    def __decode_green_corridor(self, code: int) -> str:
        """緑の回廊の区分コードを正式な名称に変換する関数。

        Args:
            code: 緑の回廊区分コード。

        Returns:
            緑の回廊区分のラベル。
        """
        try:
            code = int(code)
        except Exception:
            return str(code)
        else:
            coding = GreenCorridorCoding()
            return coding.decode(code)

    def validate_geometry(
        self, geometry: shapely.geometry.base.BaseGeometry
    ) -> shapely.geometry.base.BaseGeometry:
        """ジオメトリのバリデーションを行い、無効なジオメトリを修正します。

        ここでは、GeometryCollectionを避ける為に、'method="structure"' を指定しています。
        Args:
            geometry: バリデーションするジオメトリ。

        Returns:
            バリデーションされたジオメトリ。
        """
        geometry = shapely.make_valid(geometry, method="structure", keep_collapsed=True)
        return geometry

    def query(self, gdf: gpd.GeoDataFrame, **kwargs: Any) -> gpd.GeoDataFrame:
        """GeoDataFrame に対してクエリを実行するための関数。

        GeoDataFrameは``geodataframe()`` メソッドで生成され、未加工の状態で渡されることを
        想定しています。クエリの条件は、キーワード引数として指定されます。

        Args:
            gdf: クエリを実行する対象の GeoDataFrame。
            **kwargs: クエリの条件を指定するキーワード引数。

        Returns:
            クエリの条件に一致する行を含む GeoDataFrame。

        ## Kwargs:
            - plan_area: 森林計画区の名称でフィルタリングします
            - office: 森林管理署の名称でフィルタリングします
            - branch_office: 担当区の名称でフィルタリングします
            - locality: 国有林の所在地でフィルタリングします
            - main_address: 林班主番でフィルタリングします
            - city: 市町村名でフィルタリングします
        """
        self.__check_geodataframe(gdf)
        q = []
        if "plan_area" in kwargs:
            q.append(self.__make_query_string("plan_area", kwargs["plan_area"]))
        if "office" in kwargs:
            q.append(self.__make_query_string("office", kwargs["office"]))
        if "branch_office" in kwargs:
            q.append(self.__make_query_string("branch_office", kwargs["branch_office"]))
        if "locality" in kwargs:
            q.append(self.__make_query_string("locality", kwargs["locality"]))
        if "main_address" in kwargs:
            q.append(self.__make_query_string("main_address", kwargs["main_address"]))
        if "city" in kwargs:
            q.append(self.__make_query_string("city", kwargs["city"]))
        query_string = " and ".join(q)
        return gdf.query(query_string)

    def __make_query_string(self, column: str, value: str | int | list[Any]) -> str:
        """DataFrameのクエリ文字列を生成するための関数。SQLとは異なります。

        Args:
            column: クエリ対象のカラム名。
            value: クエリ条件の値。文字列、整数、またはそれらのリストで指定できます。

        Returns:
            クエリ文字列。
        """
        if isinstance(value, list):
            q = " or ".join([self.__make_query_string(column, v) for v in value])
            return q
        elif isinstance(value, str):
            return f"{column} == {repr(value)}"
        elif isinstance(value, int):
            return f"{column} == {value}"

    def __check_geodataframe(self, gdf: gpd.GeoDataFrame) -> None:
        """GeoDataFrame の内容をチェックするための関数。

        Args:
            gpd.GeoDataFrame: チェック対象の GeoDataFrame。

        Returns:
            なし。エラーがある場合は例外を発生させる。
        """
        assert set(gdf.columns) == set(self.fields.use_default_en_fields())
        assert gdf["geometry"].dtype.name == "geometry"

    def encode(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame の属性をコード化します。

        ここで処理されるコード化は、'.confs/nf_coding.yaml' に定義されたものに基づいています。
        GeoDataFrameは``geodataframe()`` メソッドで生成され、未加工の状態で渡されることを
        想定しています。

        Args:
            gdf: コード化する GeoDataFrame。

        Returns:
            コード化された GeoDataFrame。
        """

        def _encode(gdf, col, coding, dtype):
            gdf[col] = gdf[col].apply(coding.encode).astype(dtype)
            return gdf

        self.__check_geodataframe(gdf)
        gdf = gdf.copy()
        cols = _AddrsColumns()
        city_coding = CityCoding()
        gdf = _encode(gdf, cols.city, city_coding, "int")
        authority_coding = AuthorityCoding()
        gdf = _encode(gdf, cols.authority, authority_coding, "int")
        plan_area_coding = PlanAreaCoding()
        gdf = _encode(gdf, cols.plan_area, plan_area_coding, "int")
        office_coding = OfficeCoding()
        gdf = _encode(gdf, cols.office, office_coding, "int")
        branch_office_coding = BranchOfficeCoding()
        gdf = _encode(gdf, cols.branch_office, branch_office_coding, "int")
        locality_coding = LocalityCoding()
        gdf = _encode(gdf, cols.locality, locality_coding, "int")
        tree_name_coding = TreeNameCoding()
        gdf = _encode(gdf, cols.tree_name_1, tree_name_coding, "int")
        gdf = _encode(gdf, cols.tree_name_2, tree_name_coding, "int")
        gdf = _encode(gdf, cols.tree_name_3, tree_name_coding, "int")
        ftd_coding = ForestTypeDetailCoding()
        gdf = _encode(gdf, cols.forest_type_detail, ftd_coding, "int")
        fft_coding = ForestFeatureTypeCoding()
        gdf = _encode(gdf, cols.forest_feature_type, fft_coding, "int")
        protected_coding = ProtectedForestCoding()
        gdf = _encode(gdf, cols.protection_forest_1, protected_coding, "int")
        gdf = _encode(gdf, cols.protection_forest_2, protected_coding, "int")
        gdf = _encode(gdf, cols.protection_forest_3, protected_coding, "int")
        gdf = _encode(gdf, cols.protection_forest_4, protected_coding, "int")
        conservation_coding = ConservationCoding()
        gdf = _encode(gdf, cols.conservation, conservation_coding, "int")
        green_corridor_coding = GreenCorridorCoding()
        gdf = _encode(gdf, cols.green_corridor, green_corridor_coding, "int")
        return gdf

    def decode(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame の属性をコード化します。
        ここで処理されるコード化は、'.confs/nf_coding.yaml' に定義されたものに基づいています。
        GeoDataFrameは``geodataframe()`` メソッドで生成され、未加工の状態で渡されることを
        想定しています。

        Args:
            gdf: デコードする GeoDataFrame。

        Returns:
            デコードされた GeoDataFrame。
        """

        def _decode(gdf, col, coding, dtype):
            gdf[col] = gdf[col].apply(coding.decode).astype(dtype)
            return gdf

        self.__check_geodataframe(gdf)
        gdf = gdf.copy()
        cols = _AddrsColumns()
        city_coding = CityCoding()
        gdf = _decode(gdf, cols.city, city_coding, "str")
        authority_coding = AuthorityCoding()
        gdf = _decode(gdf, cols.authority, authority_coding, "str")
        plan_area_coding = PlanAreaCoding()
        gdf = _decode(gdf, cols.plan_area, plan_area_coding, "str")
        office_coding = OfficeCoding()
        gdf = _decode(gdf, cols.office, office_coding, "str")
        branch_office_coding = BranchOfficeCoding()
        gdf = _decode(gdf, cols.branch_office, branch_office_coding, "str")
        locality_coding = LocalityCoding()
        gdf = _decode(gdf, cols.locality, locality_coding, "str")
        tree_name_coding = TreeNameCoding()
        gdf = _decode(gdf, cols.tree_name_1, tree_name_coding, "str")
        gdf = _decode(gdf, cols.tree_name_2, tree_name_coding, "str")
        gdf = _decode(gdf, cols.tree_name_3, tree_name_coding, "str")
        ftd_coding = ForestTypeDetailCoding()
        gdf = _decode(gdf, cols.forest_type_detail, ftd_coding, "str")
        fft_coding = ForestFeatureTypeCoding()
        gdf = _decode(gdf, cols.forest_feature_type, fft_coding, "str")
        protected_coding = ProtectedForestCoding()
        gdf = _decode(gdf, cols.protection_forest_1, protected_coding, "str")
        gdf = _decode(gdf, cols.protection_forest_2, protected_coding, "str")
        gdf = _decode(gdf, cols.protection_forest_3, protected_coding, "str")
        gdf = _decode(gdf, cols.protection_forest_4, protected_coding, "str")
        conservation_coding = ConservationCoding()
        gdf = _decode(gdf, cols.conservation, conservation_coding, "str")
        green_corridor_coding = GreenCorridorCoding()
        gdf = _decode(gdf, cols.green_corridor, green_corridor_coding, "str")
        return gdf

    def field_and_alias(self) -> dict[str, str]:
        """
        GeoDataFrame の属性名とそのエイリアスの辞書を返します。
        ここでのエイリアスは、'.confs/fields.yaml' に定義されたものに基づいています。
        Returns:
            属性名とエイリアスの辞書。
        """
        return {
            field_info.en: field_info.ja for field_info in self.fields.fields.values()
        }

    def dissolve_by_office(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame を森林管理署ごとにディゾルブします。
        Args:
            gdf(gpd.GeoDataFrame):
                このクラスで生成された GeoDataFrame を想定しています。それ以外の GeoDataFrame
                を渡した場合、エラーが発生します。
        Returns:
            森林管理署ごとにディゾルブされた GeoDataFrame。
        """
        office_fields = OfficeFields()
        self.__check_geodataframe(gdf)
        dissolved = gdf.dissolve(by=office_fields.dissolve_fields(), as_index=False)
        return dissolved[office_fields.fields()]

    def dissolve_by_branch_office(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame を担当区ごとにディゾルブします。
        Args:
            gdf(gpd.GeoDataFrame):
                このクラスで生成された GeoDataFrame を想定しています。それ以外の GeoDataFrame
                を渡した場合、エラーが発生します。
        Returns:
            担当区ごとにディゾルブされた GeoDataFrame。
        """
        branch_office_fields = BranchOfficeFields()
        self.__check_geodataframe(gdf)
        dissolved = gdf.dissolve(
            by=branch_office_fields.dissolve_fields(), as_index=False
        )
        return dissolved[branch_office_fields.fields()]

    def dissolve_by_locality(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame を国有林の所在地ごとにディゾルブします。
        Args:
            gdf(gpd.GeoDataFrame):
                このクラスで生成された GeoDataFrame を想定しています。それ以外の GeoDataFrame
                を渡した場合、エラーが発生します。
        Returns:
            国有林の所在地ごとにディゾルブされた GeoDataFrame。
        """
        locality_fields = LocalityFields()
        self.__check_geodataframe(gdf)
        dissolved = gdf.dissolve(by=locality_fields.dissolve_fields(), as_index=False)
        return dissolved[locality_fields.fields()]

    def dissolve_by_main_address(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """GeoDataFrame を林班ごとにディゾルブします。
        Args:
            gdf(gpd.GeoDataFrame):
                このクラスで生成された GeoDataFrame を想定しています。それ以外の GeoDataFrame
                を渡した場合、エラーが発生します。
        Returns:
            林班ごとにディゾルブされた GeoDataFrame。
        """
        main_address_fields = MainAddressFields()
        self.__check_geodataframe(gdf)
        dissolved = gdf.dissolve(
            by=main_address_fields.dissolve_fields(), as_index=False
        )
        return dissolved[main_address_fields.fields()]

    def dissolve_by_protection_forests(
        self, gdf: gpd.GeoDataFrame
    ) -> dict[str, gpd.GeoDataFrame]:
        """GeoDataFrame を保護林の区分ごとにディゾルブします。
        Args:
            gdf(gpd.GeoDataFrame):
                このクラスで生成された GeoDataFrame を想定しています。それ以外の GeoDataFrame
                を渡した場合、エラーが発生します。
        Returns:
            dict[str, gpd.GeoDataFrame]:
                保安林の区分ごとにディゾルブされた GeoDataFrame の辞書。
        """

        def get_unique_protection_forests(gdf: gpd.GeoDataFrame) -> list[str]:
            """GeoDataFrameからユニークな保安林の種類を取得します。"""
            addrs = _AddrsColumns()
            ary = gdf[addrs.protection_forests].to_numpy().flatten()
            unique_values = [v for v in set(ary.tolist()) if v != "-"]
            return unique_values

        def get_protection_forest_rows(
            gdf: gpd.GeoDataFrame, protection_forest: str
        ) -> gpd.GeoDataFrame:
            """GeoDataFrameから指定された保安林の種類に該当する行を取得します。"""
            addrs = _AddrsColumns()
            pf_rows = gdf[
                (gdf[addrs.protection_forest_1] == protection_forest)
                | (gdf[addrs.protection_forest_2] == protection_forest)
                | (gdf[addrs.protection_forest_3] == protection_forest)
                | (gdf[addrs.protection_forest_4] == protection_forest)
            ]
            return pf_rows

        pf_fields = ProtectedForestFields()
        self.__check_geodataframe(gdf)
        data = {}
        for pf in get_unique_protection_forests(gdf):
            pf_rows = get_protection_forest_rows(gdf, pf)
            pf_rows["protected_forest_type"] = pf
            dissolved = pf_rows.dissolve(by=pf_fields.dissolve_fields(), as_index=False)
            data[pf] = dissolved[pf_fields.fields()]

        return data

    def to_geojson(
        self,
        gdf: gpd.GeoDataFrame,
        alias: bool = False,
        output_dtype: OutputGeoJsonType | str | int = OutputGeoJsonType.STRING,
        **kwargs: Any,
    ) -> str | bytes | dict[str, Any]:
        """
        GeoDataFrameをGeoJSON形式の文字列に変換します。
        フィールド名のエイリアスを適用したい場合は、``alias`` を ``True`` に設定し、
        クラスの初期化時に渡した ``field_and_alias`` を使用してカラム名を変更します。
        出力形式を指定する場合は、``output_dtype`` に適切な値を設定してください。ディゾルブ
        後のGeoDataFrameでも同様に処理されます。

        GeoJSONは通常、EPSG:4326（WGS 84）を使用するため、CRSが異なる場合は変換します。

        Args:
            gdf(gpd.GeoDataFrame):
                GeoJSON形式に変換する対象のGeoDataFrame。
            alias(bool, optional):
                フィールド名のエイリアスを適用するかどうか。デフォルトは ``False`` です。
            output_dtype(OutputGeoJsonType, optional):
                出力形式を指定します。デフォルトは ``OutputGeoJsonType.STRING`` です。
                 - 0 | OutputGeoJsonType.STRING | 'string': 文字列で出力します。
                 - 1 | OutputGeoJsonType.BYTES | 'bytes': バイト列で出力します。
                 - 2 | OutputGeoJsonType.DICT | 'dict': 辞書形式で出力します。
                 - 3 | OutputGeoJsonType.PATH | 'path': ファイルパスに出力します。
            path(str, optional):
                GeoJSONファイルの出力先パス。``OutputGeoJsonType.PATH`` を指定した場合
                に使用されます。

        Returns:
            GeoJSON形式の文字列、バイト列、辞書、またはファイルパス。

        Example:
            ```python
            shp = GsicAddressShape(prefecture="滋賀県")
            gdf = shp.geodataframe(plan_area="湖南森林計画区")
            geojson_string = shp.to_geojson(gdf, alias=True, output_dtype="string")
            with open("output.geojson", "w", encoding="utf-8") as f:
                f.write(geojson_string)
            ```
        """
        if gdf.crs is None:
            raise ValueError("GeoDataFrameのCRSが設定されていません。")
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        if alias:
            gdf = gdf.rename(columns=self.field_and_alias())

        if isinstance(output_dtype, int):
            output_dtype = OutputGeoJsonType(output_dtype)
        elif isinstance(output_dtype, str):
            output_dtype = OutputGeoJsonType[output_dtype.upper()]

        if output_dtype == OutputGeoJsonType.STRING:
            return json.dumps(gdf.to_geo_dict(), ensure_ascii=False)
        elif output_dtype == OutputGeoJsonType.BYTES:
            with io.BytesIO() as buffer:
                gdf.to_file(buffer, driver="GeoJSON")
                return buffer.getvalue()
        elif output_dtype == OutputGeoJsonType.DICT:
            return gdf.to_geo_dict()
        elif output_dtype == OutputGeoJsonType.PATH and "path" in kwargs:
            path = kwargs["path"]
            if not isinstance(path, str):
                raise ValueError("pathは文字列で指定してください。")
            gdf.to_file(path, driver="GeoJSON")
            return path
        else:
            raise ValueError(f"Unsupported output_dtype: {output_dtype}")

    def to_geopackage(
        self,
        gdf: gpd.GeoDataFrame,
        layer: str,
        alias: bool = False,
        gpkg: Optional[GeoPackage] = None,
        **kwargs: Any,
    ) -> GeoPackage:
        """
        GeoDataFrameをGeoPackage形式に変換します。
        フィールド名のエイリアスを適用したい場合は、``alias`` を ``True`` に設定し、クラス
        の初期化時に渡した ``field_and_alias`` を使用してカラム名を変更します。
        出力形式を指定する場合は、``output_dtype`` に適切な値を設定してください。

        Args:
            gdf(gpd.GeoDataFrame):
                GeoPackage形式に変換する対象のGeoDataFrame。
            layer(str):
                GeoPackage内のレイヤー名を指定します。
            alias(bool, optional):
                フィールド名のエイリアスを適用するかどうか。デフォルトは ``False`` です。
                ``True``の場合は、Layerとして保存した後に、指定されたエイリアスを追加し、
                FieldとAliasの対応関係を保持します。
            gpkg(GeoPackage, optional):
                GeoPackageオブジェクトを指定します。指定された場合、出力形式に関わらずこのオブジェクトに書き込まれます。
                指定されない場合は、出力形式に応じて内部でGeoPackageオブジェクトが作成されます。
        ## Kwargs:
            - office(bool): 森林管理署の名称でディゾルブするかどうかを指定します。デフォルトは ``False`` です。
            - branch_office(bool): 担当区の名称でディゾルブするかどうかを指定します。デフォルトは ``False`` です。
            - locality(bool): 国有林の所在地でディゾルブするかどうかを指定します。デフォルトは ``False`` です。
            - main_address(bool): 林班主番でディゾルブするかどうかを指定します。デフォルトは ``False`` です。
            - protection_forests(bool): 保安林の区分でディゾルブするかどうかを指定します。デフォルトは ``False`` です。
             ディゾルブする場合は、指定されたカラムでディゾルブされたGeoDataFrameがGeoPackageに書き込まれます。
             このオプションを指定する場合は、引数の`gdf`が小班区画レベルのGeoDataFrameである必要があります。

        Returns:
            GeoPackageオブジェクト、バイト列、またはファイルパス。
        """
        # CRSの確認
        if gdf.crs is None:
            raise ValueError("GeoDataFrameのCRSが設定されていません。")
        # `gpkg`が指定されている場合はそれを使用し、そうでない場合は出力形式に応じて内部で
        # GeoPackageオブジェクトを作成する
        if gpkg is not None:
            if not isinstance(gpkg, GeoPackage):
                raise ValueError("gpkgはGeoPackageオブジェクトで指定してください。")
            gpkg.to_geopackage(gdf, layer=layer, alias=alias)
        else:
            # GeoPackageオブジェクトに書き込む
            gpkg = GeoPackage(self.field_and_alias())
            gpkg.to_geopackage(gdf, layer=layer, alias=alias)
        # `gdf`が小班区画レベルのGeoDataFrameかを確認
        if set(gdf.columns) == set(self.fields.use_default_en_fields()):
            sub_address_level = True
        else:
            sub_address_level = False
        # ディゾルブのオプションに応じて、指定されたカラムでディゾルブされたGeoDataFrameをGeoPackageに書き込む
        if kwargs.get("office", False):
            if not sub_address_level:
                raise ValueError(
                    "ディゾルブする場合は、引数の`gdf`が小班区画レベルのGeoDataFrameである必要があります。"
                )
            dissolved = self.dissolve_by_office(gdf)
            self.to_geopackage(dissolved, layer="office", alias=alias, gpkg=gpkg)
        if kwargs.get("branch_office", False):
            if not sub_address_level:
                raise ValueError(
                    "ディゾルブする場合は、引数の`gdf`が小班区画レベルのGeoDataFrameである必要があります。"
                )
            dissolved = self.dissolve_by_branch_office(gdf)
            self.to_geopackage(dissolved, layer="branch_office", alias=alias, gpkg=gpkg)
        if kwargs.get("locality", False):
            if not sub_address_level:
                raise ValueError(
                    "ディゾルブする場合は、引数の`gdf`が小班区画レベルのGeoDataFrameである必要があります。"
                )
            dissolved = self.dissolve_by_locality(gdf)
            self.to_geopackage(dissolved, layer="locality", alias=alias, gpkg=gpkg)
        if kwargs.get("main_address", False):
            if not sub_address_level:
                raise ValueError(
                    "ディゾルブする場合は、引数の`gdf`が小班区画レベルのGeoDataFrameである必要があります。"
                )
            dissolved = self.dissolve_by_main_address(gdf)
            self.to_geopackage(dissolved, layer="main_address", alias=alias, gpkg=gpkg)
        if kwargs.get("protection_forests", False):
            if not sub_address_level:
                raise ValueError(
                    "ディゾルブする場合は、引数の`gdf`が小班区画レベルのGeoDataFrameである必要があります。"
                )
            dissolved_dict = self.dissolve_by_protection_forests(gdf)
            for pf, dissolved in dissolved_dict.items():
                layer_name = f"protection_forest_{pf}"
                self.to_geopackage(dissolved, layer=layer_name, alias=alias, gpkg=gpkg)

        return gpkg

    def to_kml_doc(self, kwargs: KmlKwargs) -> fastkml.Document:
        """KmlKwargsの設定に基づいて、GeoDataFrameをKMLのDocument要素に変換します。

        `label=True` の場合は、ポリゴンフォルダとラベルフォルダを親フォルダにまとめて返します。
        `label=False` の場合は、ポリゴンフォルダのみを返します。

        Args:
            kwargs (KmlKwargs):
                KML作成の設定を保持するオブジェクト。

        Returns:
            fastkml.Document: 変換されたDocument要素。

        Example:
            ```python
            from nfj.geospatial imort GsicAddressShape
            from nfj.keyhole imoprt SubAddressKmlKwargs

            shp = GsicAddressShape(prefecture="滋賀県")
            gdf = shp.geodataframe(plan_area="湖南森林計画区")
            kml_kwargs = SubAddressKmlKwargs(gdf=gdf)
            kml_doc = shp.to_kml_doc(kml_kwargs)
            with open("output.kml", "w", encoding="utf-8") as f:
                f.write(kml_doc.to_string(prettyprint=True))
            ```
        """
        if not isinstance(kwargs, KmlKwargs):
            raise ValueError("kwargsはKmlKwargsのインスタンスで指定してください。")

        # `kwargs.gdf`がこのクラスで生成されたGeoDataFrameかを確認するために、列名とgeometry列の型をチェックします。
        default_fields = self.fields.use_default_en_fields() + ["geometry"]
        for col in kwargs.gdf.columns:
            if col not in default_fields:
                raise ValueError(
                    f"kwargs.gdfの列名がこのクラスで生成されたGeoDataFrameの列名と一致しません。列名: {col}"
                )

        keyhole = KeyholeMarkupLanguage()

        line_style = keyhole.create_line_style(
            hex_color=kwargs.line_color,
            alpha=kwargs.line_alpha,
            width=kwargs.line_width,
        )
        poly_style = keyhole.create_poly_style(
            hex_color=kwargs.poly_fill_color,
            alpha=kwargs.poly_fill_alpha,
            fill=kwargs.poly_fill,
            outline=kwargs.poly_outline,
        )
        poly_folder = keyhole.geodataframe_to_poly_folder(
            gdf=kwargs.gdf,
            geometry_column=kwargs.geometry_column,
            alias=kwargs.alias,
            line_style=line_style,
            poly_style=poly_style,
            folder_name=kwargs.folder_name,
            geometry_altitude_mode=kwargs.altitude_mode,
            geometry_extrude=kwargs.extrude,
            name_column=kwargs.name_column,
        )

        if not kwargs.label:
            doc = fastkml.Document(name=kwargs.folder_name)
            doc.append(poly_folder)
            return doc

        label_style = keyhole.create_label_style(
            hex_color=kwargs.label_color,
            alpha=kwargs.label_alpha,
            scale=kwargs.label_scale,
        )
        label_folder = keyhole.geodataframe_to_label_folder(
            gdf=kwargs.gdf,
            geometry_column=kwargs.geometry_column,
            label_style=label_style,
            folder_name=f"{kwargs.folder_name}ラベル",
            name_column=kwargs.name_column,
        )

        doc = fastkml.Document(name=kwargs.folder_name)
        doc.append(poly_folder)
        doc.append(label_folder)
        return doc
