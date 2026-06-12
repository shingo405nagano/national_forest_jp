from typing import Any, Optional, cast
from uuid import uuid4

import fastkml
import geopandas as gpd
import pydantic
import pygeoif
import shapely
from fastkml.enums import AltitudeMode
from matplotlib.colors import to_rgba
from pygeoif.types import GeoCollectionInterface, GeoInterface

from .fields import AddressFields
from .logging_config import get_logger

logger = get_logger(__name__)


def hex_to_abgr(hex_str: str, alpha: float = 1.0):
    """16進カラーコードをABGR形式に変換して返す。

    ABGR形式はKML、マップアプリケーションで汎用される
    アルファベッド色カラーコード。

    Args:
        hex_str: 16進カラーコード。
        alpha: アルファ値（0.0～1.0）。デフォルトは1.0。

    Returns:
        ABGR形式の8文字の16進文字列。
    """

    def func(v):
        return f"{int(v * 255):x}".zfill(2)

    r, g, b, a = [func(v) for v in to_rgba(hex_str, alpha)]
    return "".join([a, b, g, r])


class KmlKwargs(pydantic.BaseModel):
    """KML作成の引数を管理するクラス。

    とりあえず小班区画のKMLを作成する場合は、このクラスのインスタンス変数を利用する。

    Attributes:
        gdf(gpd.GeoDataFrame):
            KMLに変換するGeoDataFrame。ジオメトリ列はWGS84（EPSG:4326）である必要があります。
        name_column(str):
            Featureの名前に使用するカラム名。指定されたカラムがgdfに存在しない場合は、インデ
            ックスを名前として使用します。
        folder_name(str):
            KMLのFolder要素の名前。指定しない場合は、"国有林データ"になります。
        geometry_column(str):
            ジオメトリ列の名前。デフォルトは"geometry"。
        alias(bool):
            属性名をエイリアスに変換するかどうか。デフォルトはTrueで、AddressFieldsクラスのfield_infoのja属性をエイリアスとして使用します。Falseの場合は、属性名をそのまま使用します。
        line_color(str):
            ラインの色を16進カラーコードで指定します。デフォルトは"#00c03a"（緑色）。
        line_width(int):
            ラインの幅を指定します。デフォルトは2。
        line_alpha(float):
            ラインのアルファ値を0.0～1.0の範囲で指定します。デフォルトは1.0で、完全に不透明です。
        poly_fill_color(str):
            ポリゴンの塗りつぶしの色を16進カラーコードで指定します。デフォルトは"#00c03a"（緑色）。
        poly_fill_alpha(float):
            ポリゴンの塗りつぶしのアルファ値を0.0～1.0の範囲で指定します。デフォルトは0.5で、半透明です。
        poly_outline(bool):
            ポリゴンの輪郭線の有無を指定します。デフォルトはTrueで、輪郭線を表示します。
        poly_fill(bool):
            ポリゴンの塗りつぶしの有無を指定します。デフォルトはFalseで、塗りつぶしなしです。
        label(bool):
            ラベルの有無を指定します。デフォルトはTrueで、ラベルを表示します。
        label_color(str):
            ラベルの色を16進カラーコードで指定します。デフォルトは"#ffffff"（白色）。
        label_alpha(float):
            ラベルのアルファ値を0.0～1.0の範囲で指定します。デフォルトは1.0で、完全に不透明です。
        label_scale(float):
            ラベルのスケールを指定します。デフォルトは0.5で、ラベルを表示する。
        altitude_mode(AltitudeMode):
            ジオメトリの高度モードを指定します。
             - clamp_to_ground: ジオメトリを地表に沿って配置します。ジオメトリの高度は無視されます。
             - relative_to_ground: ジオメトリの高度を地表からの相対高度として解釈します。
             - absolute: ジオメトリの高度を地球中心からの絶対高度として解釈します。
             - clamp_to_sea_floor: ジオメトリを海底に沿って配置します。ジオメトリの高度は無視されます。
             - relative_to_sea_floor: ジオメトリの高度を海底からの相対高度として解釈します。`
        extrude(bool):
            ジオメトリの押し出しの有無を指定します。デフォルトはTrueで、ジオメトリが地表から垂直に押し出されます。
    """

    gdf: gpd.GeoDataFrame
    name_column: str = "sub_address_name"
    folder_name: str = "小班区画"
    geometry_column: str = "geometry"
    alias: bool = True
    line_color: str = "#887f7a"
    line_width: int = 2
    line_alpha: float = 1.0
    poly_fill_color: str = "#887f7a"
    poly_fill_alpha: float = 0.0
    poly_outline: bool = True
    poly_fill: bool = False
    label: bool = True
    label_color: str = "#ffffff"
    label_alpha: float = 1.0
    label_scale: float = 0.5
    altitude_mode: AltitudeMode = AltitudeMode.clamp_to_ground
    extrude: bool = True
    model_config = pydantic.ConfigDict(
        validate_default=True,
        arbitrary_types_allowed=True,
    )

    @pydantic.field_validator("gdf", mode="before")
    def validate_gdf(cls, v):
        if not isinstance(v, gpd.GeoDataFrame):
            raise ValueError("`gdf`はGeoDataFrameでなければなりません。")
        if v.crs is None:
            raise ValueError("`gdf`のCRSが定義されていません。")
        elif v.crs.to_epsg() != 4326:
            logger.warning(
                "`gdf`のCRSがEPSG:4326ではありません。ジオメトリ列をEPSG:4326に変換します。"
            )
            v = v.to_crs(epsg=4326)
        return v

    @pydantic.field_validator("name_column", mode="before")
    def validate_name_column(cls, v, info):
        gdf = info.data.get("gdf")
        if not isinstance(v, str):
            raise ValueError("`name_column`は文字列でなければなりません。")
        if gdf is not None and v not in gdf.columns:
            raise ValueError(f"`name_column`の値 '{v}' は`gdf`のカラムに存在しません。")
        return v

    @pydantic.field_validator("geometry_column", mode="before")
    def validate_geometry_column(cls, v, info):
        gdf = info.data.get("gdf")
        if not isinstance(v, str):
            raise ValueError("`geometry_column`は文字列でなければなりません。")
        if gdf is not None and v not in gdf.columns:
            raise ValueError(
                f"`geometry_column`の値 '{v}' は`gdf`のカラムに存在しません。"
            )
        return v

    @pydantic.field_validator(
        "line_color", "poly_fill_color", "label_color", mode="before"
    )
    def validate_hex_color(cls, v):
        if not isinstance(v, str):
            raise ValueError("カラーコードは文字列でなければなりません。")
        try:
            to_rgba(v)
        except ValueError:
            raise ValueError(f"'{v}'は有効な16進カラーコードではありません。")
        return v

    @pydantic.field_validator("altitude_mode", mode="before")
    def validate_altitude_mode(cls, v):
        if isinstance(v, str):
            try:
                v = AltitudeMode[v]
            except KeyError:
                raise ValueError(
                    f"'{v}'は有効なAltitudeModeの値ではありません。"
                    "有効な値は'clamp_to_ground'、'relative_to_ground'、'absolute'"
                    "'clamp_to_sea_floor'、'relative_to_sea_floor'のいずれかです。"
                )
        elif isinstance(v, int):
            try:
                v = AltitudeMode(v)
            except ValueError:
                raise ValueError(
                    f"'{v}'は有効なAltitudeModeの値ではありません。"
                    "有効な値は0（clamp_to_ground）、1（relative_to_ground）、2（absolute）、"
                    "3（clamp_to_sea_floor）、4（relative_to_sea_floor）のいずれかです。"
                )
        if not isinstance(v, AltitudeMode):
            raise ValueError("`altitude_mode`はAltitudeModeの値でなければなりません。")
        return v


class SubAddressKmlKwargs(KmlKwargs):
    pass


class MainAddressKmlKwargs(KmlKwargs):
    name_column: str = "main_address"
    folder_name: str = "林班区画"
    line_color: str = "#65318e"
    line_width: int = 4
    label_color: str = "#884898"
    label_scale: float = 1.0


class LocalityKmlKwargs(KmlKwargs):
    name_column: str = "locality"
    folder_name: str = "国有林区画"
    line_color: str = "#4d5aaf"
    line_width: int = 4
    label_color: str = "#4d5aaf"
    label_scale: float = 1.5


class BranchOfficeKmlKwargs(KmlKwargs):
    name_column: str = "branch_office"
    folder_name: str = "担当区"
    line_color: str = "#0f2350"
    line_width: int = 4
    label_color: str = "#0f2350"
    label_scale: float = 2.0


class OfficeKmlKwargs(KmlKwargs):
    name_column: str = "office"
    folder_name: str = "森林管理署"
    line_color: str = "#008899"
    line_width: int = 4
    label_color: str = "#008899"
    label_scale: float = 2.5


class KeyholeMarkupLanguage(object):
    """
    Keyhole Markup Language (KML) 形式のデータを扱うクラス。
     - KMLは、地理空間データを格納するためのXMLベースのフォーマットで、Google EarthやGoogle
        MapsなどのGISソフトウェアで広く使用されています。
     - ここに渡すGeoDataFrameは、GsicAddressShapeクラスのgeodataframeメソッドで取得した
        ものを想定しています。それ以外のGeoDataFrameを渡すと、意図しない動作をする可能性があ
       ります。

    Example:
        ```
        import fastkml

        from nfj.geospatial import GsicAddressShape
        from nfj.keyhole import KeyholeMarkupLanguage

        # 例として、長崎県の林班区画データをKMLに変換するコード
        pref = "長崎県"
        plan_area = "長崎北部森林計画区"
        shp = GsicAddressShape(prefecture=pref)
        # 小班区画の作成
        sub_addrs_gdf = shp.geodataframe(plan_area=plan_area)
        # 林班区画の作成
        main_addrs_gdf = shp.dissolve_by_main_address(sub_addrs_gdf)
        # KMLドキュメントの作成
        kml = fastkml.KML()
        doc = fastkml.Document()
        kml.append(doc)

        # KeyholeMarkupLanguageクラスのインスタンスを作成
        # fastkml.KMLクラスと名前が被らないように、冗長ですがKeyholeMarkupLanguageクラスを命名しています。
        keyhole = KeyholeMarkupLanguage()

        # 林班区画のFolder要素を作成してドキュメントに追加
        maddrs_folder = keyhole.geodataframe_to_poly_folder(
            gdf=main_addrs_gdf,
            geometry_column="geometry",
            alias=True,
            folder_name=f"{plan_area}の林班区画",
            name_column="main_address",
        )
        doc.append(maddrs_folder)

        # 林班区画のラベルのFolder要素を作成してドキュメントに追加
        maddrs_label_folder = keyhole.geodataframe_to_label_folder(
            gdf=main_addrs_gdf,
            geometry_column="geometry",
            folder_name=f"{plan_area}の林班区画ラベル",
            name_column="main_address",
        )
        doc.append(maddrs_label_folder)

        # 小班区画のFolder要素を作成してドキュメントに追加
        ls = keyhole.create_line_style("#ff0000", alpha=1.0, width=2.0)
        ps = keyhole.create_poly_style("#ff0000", alpha=0.3, fill=True, outline=True)
        sub_addrs_folder = keyhole.geodataframe_to_poly_folder(
            gdf=sub_addrs_gdf,
            geometry_column="geometry",
            alias=True,
            line_style=ls,
            poly_style=ps,
            folder_name=f"{plan_area}の小班区画",
            name_column="sub_address_name",
        )
        doc.append(sub_addrs_folder)

        # 小班区画ラベルのFolder要素を作成してドキュメントに追加
        sub_label_style = keyhole.create_label_style(
            hex_color="#ffffff", alpha=1.0, scale=0.5
        )
        sub_label_folder = keyhole.geodataframe_to_label_folder(
            gdf=sub_addrs_gdf,
            geometry_column="geometry",
            label_style=sub_label_style,
            folder_name=f"{plan_area}の小班区画ラベル",
            name_column="sub_address_name",
        )
        doc.append(sub_label_folder)

        # KMLドキュメントをファイルに保存
        with open("output.kml", "w", encoding="utf-8") as f:
            f.write(kml.to_string(prettyprint=True))
        ```
    """

    def create_label_style(
        self,
        hex_color: str = "#FFFFFF",
        alpha: float = 1.0,
        scale: float = 1.0,
    ) -> fastkml.LabelStyle:
        """LabelStyle要素を作成して返す。

        Args:
            hex_color: 16進カラーコード
            alpha: アルファ値（0.0～1.0）
            scale: ラベルのスケール。デフォルトは1.0で、ラベルを表示する。
        Returns:
            LabelStyle要素を掲載したKMLスタイル要素。
        """
        abgr = hex_to_abgr(hex_color, alpha)
        label_style = fastkml.LabelStyle(color=abgr, scale=scale)
        return label_style

    def create_icon_style(
        self,
        hex_color: str = "#FFFFFF",
        alpha: float = 1.0,
        scale: float = 0.0,
        icon_href: str = "http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png",
    ) -> fastkml.IconStyle:
        """IconStyle要素を作成して返す。

        Args:
            hex_color: 16進カラーコード
            alpha: アルファ値（0.0～1.0）
            scale: アイコンのスケール。デフォルトは0.0で、アイコンを表示しない。
            icon_href: アイコンのURL。デフォルトはデフォルトのアイコンを使用する。
        Returns:
            IconStyle要素を掲載したKMLスタイル要素。
        """
        abgr = hex_to_abgr(hex_color, alpha)
        icon_style = fastkml.IconStyle(
            color=abgr,
            scale=scale,
            icon_href=icon_href,
        )
        return icon_style

    def create_line_style(
        self,
        hex_color: str,
        alpha: float = 1.0,
        width: float = 1.0,
    ) -> fastkml.LineStyle:
        """LineStringのスタイルを作成して返す。

        作成した'Style'要素はKMLドキュメントに追加する事で参照できます。参照したい
        'Placemark'要素の'styleUrl'プロパティに'#style_id'を設定してください。

        Args:
            hex_color: 16進カラーコード
            alpha: アルファ値（0.0～1.0）
            width: ラインの幅

        Returns:
            LineStyle要素を掲載したKMLスタイル要素。
        """
        abgr = hex_to_abgr(hex_color, alpha)
        line_style = fastkml.LineStyle(
            color=abgr,
            width=width,
        )
        return line_style

    def create_poly_style(
        self,
        hex_color: str,
        alpha: float = 0.5,
        fill: bool = False,
        outline: bool = True,
    ) -> fastkml.PolyStyle:
        """Polygonのスタイルを作成して返す。

        作成した'Style'要素はKMLドキュメントに追加する事で参照できます。参照したい
        'Placemark'要素の'styleUrl'プロパティに'#style_id'を設定してください。

        Args:
            hex_color: 16進カラーコード
            alpha: アルファ値（0.0～1.0）
            fill: ポリゴンの塗りつぶしの有無
            outline: ポリゴンの輪郭線の有無

        Returns:
            PolyStyle要素を掲載したKMLスタイル要素。
        """
        abgr = hex_to_abgr(hex_color, alpha)
        poly_style = fastkml.PolyStyle(
            color=abgr,
            outline=outline,
            fill=fill,
        )
        return poly_style

    def create_style(
        self,
        style_id: str,
        line_style: fastkml.LineStyle,
        poly_style: fastkml.PolyStyle,
    ) -> fastkml.Style:
        """スタイルを作成して返す。
        今回は国有林の小班区画データのみの為、Polygonを想定して、スタイルIDとLineStyle要素、
        PolyStyle要素を引数に取るスタイル作成関数を用意しています。

        Args:
            style_id: スタイルID
            line_style: LineStyle要素
            poly_style: PolyStyle要素

        Returns:
            Style要素を掲載したKMLスタイル要素。
        """
        style = fastkml.Style(
            id=style_id,
            styles=[line_style, poly_style],
        )
        return style

    def create_data_element(
        self, name: str, value: Any, alias: Optional[str] = None
    ) -> fastkml.Data:
        """
        属性情報を含むData要素を作成して返すメソッド。
        Args:
            name (str): 属性名
            value (Any): 属性値
            alias (Optional[str]): 表示名
        Returns:
            fastkml.Data: Data要素
        """
        d = fastkml.Data(
            name=name,
            value=str(value),
            display_name=alias,
        )
        return d

    def create_extended_data_element(
        self, data_elements: list[fastkml.Data]
    ) -> fastkml.ExtendedData:
        """
        複数のData要素を含むExtendedData要素を作成して返すメソッド。
        Args:
            data_elements (list[fastkml.Data]): Data要素のリスト
        Returns:
            fastkml.ExtendedData: ExtendedData要素
        """
        extended_data = fastkml.ExtendedData(elements=data_elements)
        return extended_data

    def geometry_element(
        self,
        geometry: shapely.Polygon | shapely.MultiPolygon,
        altitude_mode: AltitudeMode = AltitudeMode.clamp_to_ground,
        extrude: bool = False,
    ) -> fastkml.Polygon | fastkml.MultiGeometry:
        """shapely.geometry オブジェクトを KML ジオメトリに変換する。

        Args:
            geometry (shapely.geometry.base.BaseGeometry):
                変換するshapelyジオメトリオブジェクト。このジオメトリは
                WGS84（EPSG:4326）である必要があります。'Point','LineString',
                'Polygon'、およびそれらのマルチジオメトリに対応しています。
            altitude_mode (AltitudeMode):
                ジオメトリの高度モード。デフォルトはclamp_to_groundで、地表に沿ってジオメトリを配置します。
            extrude (bool):
                ジオメトリの押し出しの有無。デフォルトはFalseで、押し出しなしです。Trueにす
                ると、ジオメトリが地表から垂直に押し出されます。
        """
        if shapely.get_type_id(geometry) in [-1, 7]:
            raise ValueError(
                "`geometry`のジオメトリタイプがサポートされていません。`Point`、`LineString`、"
                "`Polygon`、およびそれらのマルチジオメトリのみがサポートされています。"
            )
        elif shapely.is_empty(geometry):
            raise ValueError("`geometry`は空のジオメトリであってはなりません。")

        geo_context = cast(
            GeoInterface | GeoCollectionInterface,
            geometry.__geo_interface__,
        )
        geo_elem = fastkml.create_kml_geometry(
            extrude=extrude,
            altitude_mode=altitude_mode,
            geometry=pygeoif.shape(geo_context),
        )
        return geo_elem  # type: ignore

    def create_placemark(
        self,
        id_: str,
        name: str,
        geometry_elem: fastkml.Polygon | fastkml.MultiGeometry,
        extended_data: fastkml.ExtendedData,
        style_url: Optional[str] = None,
    ) -> fastkml.Placemark:
        """Placemark要素を作成して返す。

        Args:
            id_ (str):
                PlacemarkのID
            name (str):
                Placemarkの名前
            geometry_elem (fastkml.Polygon | fastkml.MultiGeometry):
                Placemarkのジオメトリ要素
            extended_data (fastkml.ExtendedData):
                Placemarkの拡張データ要素
            style_url (Optional[str]):
                PlacemarkのスタイルURL（例: '#style_id'）

        Returns:
            fastkml.Placemark: 作成されたPlacemark要素
        """
        placemark = fastkml.Placemark(
            id=id_,
            name=name,
            kml_geometry=geometry_elem,
            extended_data=extended_data,
        )
        if isinstance(style_url, str):
            placemark.style_url = fastkml.StyleUrl(url=f"#{style_url}")
        return placemark

    def _check_crs(self, gdf: gpd.GeoDataFrame):
        """GeoDataFrameのCRSがEPSG:4326であることを確認する。そうでない場合は、EPSG:4326に変換する。

        Args:
            gdf (gpd.GeoDataFrame): CRSを確認するGeoDataFrame

        Returns:
            gpd.GeoDataFrame: CRSがEPSG:4326のGeoDataFrame
        """
        if gdf.crs is None:
            raise ValueError("'gdf'(GeoDataFrame)のCRSが定義されていません。")
        elif gdf.crs.to_epsg() != 4326:
            logger.warning(
                "'gdf'(GeoDataFrame)のCRSがEPSG:4326ではありません。"
                "ジオメトリ列をEPSG:4326に変換します。"
            )
            gdf = gdf.to_crs(epsg=4326)
        return gdf

    def geodataframe_to_poly_folder(
        self,
        gdf: gpd.GeoDataFrame,
        geometry_column: str = "geometry",
        alias: bool = True,
        line_style: Optional[fastkml.LineStyle] = None,
        poly_style: Optional[fastkml.PolyStyle] = None,
        folder_name: Optional[str] = None,
        geometry_altitude_mode: AltitudeMode = AltitudeMode.clamp_to_ground,
        geometry_extrude: bool = False,
        name_column: Optional[str] = None,
    ) -> fastkml.Folder:
        """GeoDataFrameをKMLのFolder要素に変換する。

        Args:
            gdf (gpd.GeoDataFrame): 変換するGeoDataFrame。ジオメトリ列はWGS84（EPSG:4326）である必要があります。
            geometry_column (str): ジオメトリ列の名前。デフォルトは'geometry'。
            alias (bool): 属性名をエイリアスに変換するかどうか。デフォルトはTrue。
            line_style (Optional[fastkml.LineStyle]): LineStyle要素。デフォルトはNone。
            poly_style (Optional[fastkml.PolyStyle]): PolyStyle要素。デフォルトはNone。
            folder_name (Optional[str]): Folderの名前。デフォルトはNone。
            geometry_altitude_mode (AltitudeMode): ジオメトリの高度モード。デフォルトはclamp_to_ground。
            geometry_extrude (bool): ジオメトリの押し出しの有無。デフォルトはFalse。
        Returns:
            fastkml.Folder: 変換されたFolder要素
        """
        gdf = self._check_crs(gdf)

        folder = fastkml.Folder(name=folder_name if folder_name else "国有林データ")
        # スタイルの作成と追加
        if not isinstance(line_style, fastkml.LineStyle):
            line_style = self.create_line_style("#00c03a", alpha=1.0, width=2.0)
        if not isinstance(poly_style, fastkml.PolyStyle):
            poly_style = self.create_poly_style(
                "#00c03a", alpha=0.5, fill=False, outline=True
            )
        style = self.create_style(
            str(uuid4()), line_style=line_style, poly_style=poly_style
        )
        folder.styles.append(style)
        # GeoDataFrameの各行をPlacemark要素に変換してFolderに追加
        addrs_fields = AddressFields()
        en_fields = addrs_fields.use_default_en_fields()
        for idx, row in gdf.iterrows():
            geom_elem = self.geometry_element(
                geometry=row[geometry_column],
                altitude_mode=geometry_altitude_mode,
                extrude=geometry_extrude,
            )
            row_data = row.drop(geometry_column)
            data_list = []
            for name, value in row_data.to_dict().items():
                name = str(name)

                if alias:
                    if name in en_fields:
                        display = addrs_fields.field_info(name).ja
                    else:
                        display = name

                data = self.create_data_element(name=name, value=value, alias=display)
                data_list.append(data)

            extended_data = self.create_extended_data_element(data_elements=data_list)
            # name_columnが指定されている場合は、name_columnの値をPlacemarkのnameに設定する
            if name_column and name_column in row:
                name_column_value = str(row[name_column])
            else:
                name_column_value = f"idx_{idx}"

            placemark = self.create_placemark(
                id_=name_column_value,
                name=name_column_value,
                geometry_elem=geom_elem,
                extended_data=extended_data,
                style_url=style.id,
            )
            folder.append(placemark)
        return folder

    def geodataframe_to_label_folder(
        self,
        gdf: gpd.GeoDataFrame,
        geometry_column: str = "geometry",
        label_style: Optional[fastkml.LabelStyle] = None,
        folder_name: Optional[str] = None,
        name_column: Optional[str] = None,
    ) -> fastkml.Folder:
        """GeoDataFrameをKMLのFolder要素に変換する。ジオメトリはポイントのみで、スタイルはラベルのみを想定している。

        Args:
            gdf (gpd.GeoDataFrame): 変換するGeoDataFrame。ジオメトリ列はWGS84（EPSG:4326）である必要があります。
            geometry_column (str): ジオメトリ列の名前。デフォルトは'geometry'。
        Returns:
            fastkml.Folder: 変換されたFolder要素
        """
        # KMLはCRSがWGS84（EPSG:4326）である必要があるため、ジオメトリ列をEPSG:4326に変換する
        gdf = self._check_crs(gdf)
        gdf.geometry = [geom.point_on_surface() for geom in gdf.geometry]

        folder = fastkml.Folder(name=folder_name if folder_name else "国有林データ")
        # スタイルの作成と追加
        if not isinstance(label_style, fastkml.LabelStyle):
            label_style = self.create_label_style()
        icon_style = self.create_icon_style()

        style_url = str(uuid4())
        style = fastkml.Style(
            id=style_url,
            styles=[label_style, icon_style],
        )
        style_url = fastkml.StyleUrl(url=f"#{style_url}")
        folder.styles.append(style)
        # GeoDataFrameの各行をPlacemark要素に変換してFolderに追加
        for idx, row in gdf.iterrows():
            geom_elem = self.geometry_element(geometry=row[geometry_column])
            row_data = row.drop(geometry_column)
            if name_column and name_column in row_data:
                name_column_value = str(row_data[name_column])
            else:
                name_column_value = f"idx_{idx}"

            placemark = fastkml.Placemark(
                id=name_column_value,
                name=name_column_value,
                kml_geometry=geom_elem,
                style_url=style_url,
            )
            folder.append(placemark)
        return folder
