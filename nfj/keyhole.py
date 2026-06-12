from typing import Any, Optional, cast
from uuid import uuid4

import fastkml
import geopandas as gpd
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
