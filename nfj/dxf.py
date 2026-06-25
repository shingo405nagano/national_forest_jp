import os
from typing import Any, Optional

import geopandas as gpd
import pydantic
import shapely
from ezdxf.enums import InsertUnits, TextEntityAlignment
from ezdxf.layouts.layout import Modelspace
from PIL import Image, ImageDraw, ImageFont

from .config import ProtectedForestCoding
from .fields import AddressFields

global windows_font_path
windows_font_path = os.path.join(
    os.path.dirname(__file__), "..", "others", "msgothic.ttc"
)


def split_sub_address_name(sub_address_name: str) -> dict[str, Optional[str]]:
    """
    小班名の文字列を分解し、ひらがな＆カタカナの部分と数字の部分に分ける関数
    Args:
        sub_address_name (str):
            小班名の文字列
    Returns:
        dict[str, Optional[str]]:
            ひらがな＆カタカナの部分と数字の部分を格納した辞書を返す
    ## Samples:
        - "わ" -> {"kana": "わ", "number": None}
        - "わ1" -> {"kana": "わ", "number": "1"}
    """
    # ひらがな＆カタカナの部分を抽出
    kana_part = "".join([c for c in sub_address_name if c.isalpha()])
    # 数字の部分を抽出
    number_part = "".join([c for c in sub_address_name if c.isdigit()])
    return {"kana": kana_part, "number": number_part if number_part else None}


def compute_visual_offset(label, font_path, font_point_size, target_height):
    """
    指定したフォントで描画したときの文字列の視覚的中心を計算し、DXF座標系に変換する関数
    Args:
        label (str): 描画する文字列
        font_path (str): フォントファイルのパス
        font_point_size (float): フォントサイズ（ポイント）
        target_height (float): DXF座標系での目標高さ
    Returns:
        (offset_x, offset_y): DXF座標系での視覚的中心
    """
    # 高倍率レンダリング
    scale = 6
    font = ImageFont.truetype(font_path, int(font_point_size * scale))

    # キャンバスとベースライン
    canvas_w, canvas_h = 4000, 4000
    baseline_x = 1000
    baseline_y = 2000

    img = Image.new("L", (canvas_w, canvas_h), 0)
    draw = ImageDraw.Draw(img)

    # ascent を使ってベースラインに合わせて描画
    ascent, descent = font.getmetrics()
    draw_y = baseline_y - ascent
    draw.text((baseline_x, draw_y), label, font=font, fill=255)

    bbox = img.getbbox()
    if bbox is None:
        return 0.0, 0.0
    x0, y0, x1, y1 = bbox
    center_x_px = (x0 + x1) / 2.0
    center_y_px = (y0 + y1) / 2.0

    # ベースライン原点に対する相対座標（Pillow の Y は下向き）
    rel_x_px = center_x_px - baseline_x
    rel_y_px = baseline_y - center_y_px

    # rendered height を ascent に基づいてスケール（より安定）
    # ascent はフォントサイズ * scale に近い値なのでこれを使う
    rendered_ascent_px = ascent  # already scaled by 'scale'
    if rendered_ascent_px == 0:
        return 0.0, 0.0
    scale_to_dxf = target_height / rendered_ascent_px

    offset_x_dxf = rel_x_px * scale_to_dxf
    offset_y_dxf = rel_y_px * scale_to_dxf

    # 左サイドベアリング補正（経験的）
    left_bearing_px = x0 - baseline_x
    left_bearing_dxf = left_bearing_px * scale_to_dxf
    # 右寄りに見えるなら左へ少し追加でずらす（符号は見た目で調整）
    # 係数は環境依存なので小さめにしておく
    offset_x_dxf += left_bearing_dxf * 0.7

    return offset_x_dxf, offset_y_dxf


def draw_labels(
    msp,
    x: float,
    y: float,
    main_label: str,
    label_size: float,
    main_addrs_number_scale: float = 0.5,
    sub_labels: Optional[list[str]] = None,
    sub_label_scale: float = 0.5,
    radius_scale: float = 0.8,
    jp_font_style_name: str = "JP",
) -> None:
    """
    DXFに小班名とその下に円囲みで保安林の短縮コードを描画する関数
    この関数では、日本語の場合中心を測る為に、Pillowを使って視覚的中心を計算し、DXF座標系に変
    換して文字を配置する必要がある為、文字を'Ms Gothic'フォントで描画することを前提としています。
    Args:
        msp: ezdxfのModelspaceオブジェクト
        x (float): 描画する位置のX座標
        y (float): 描画する位置のY座標
        main_label (str): 小班名の文字列
        sub_labels (list[str]): 保安林の短縮コードのリスト
        label_size (float): 小班名の文字サイズ
        main_addrs_number_scale (float): 小班枝番の文字サイズのスケール（小班名に対する比率）
        sub_label_scale (float): 保安林の短縮コードの文字サイズのスケール（小班名に対する比率）
        radius_scale (float): 円の半径のスケール（保安林の短縮コードの文字サイズに対する比率）
    Returns:
        None
    """

    def text_width(h):
        return h * 0.6

    parts = split_sub_address_name(main_label)
    kana = parts["kana"] or ""
    number = parts["number"]  # None or str

    cursor_x = x
    cursor_y = y
    label_spacing = label_size * 0.75  # 少し文字の間隔を空ける
    main_addrs_number_size = label_size * main_addrs_number_scale
    sub_label_size = label_size * sub_label_scale
    radius = sub_label_size * radius_scale

    # --- main_label: 小班主番部分 ---
    if kana:
        t = msp.add_text(
            kana,
            dxfattribs={
                "height": label_size,
                "style": jp_font_style_name,
                "layer": "小班主番レイヤー",
            },
        )
        t.set_placement((cursor_x, cursor_y), align=TextEntityAlignment.LEFT)
        cursor_x += text_width(label_size) * len(kana)

    number_start_x = cursor_x + label_spacing
    # --- main_label: 小班枝番部分 ---
    if number is not None:
        t = msp.add_text(
            number,
            dxfattribs={
                "height": main_addrs_number_size,
                "style": jp_font_style_name,
                "layer": "小班枝番レイヤー",
            },
        )
        t.set_placement(
            (number_start_x, cursor_y), align=TextEntityAlignment.BOTTOM_LEFT
        )
        cursor_x += text_width(main_addrs_number_size) * len(number)

    if sub_labels is None:
        #
        return

    # --- sub_labels: 保安林短縮コードを左から順に並べる ---
    sub_x = x + label_spacing
    sub_y = y - label_spacing

    for s in sub_labels:
        t = msp.add_text(
            s,
            dxfattribs={
                "height": sub_label_size,
                "style": jp_font_style_name,
                "layer": "保安林文字レイヤー",
            },
        )
        # 円の中心は TEXT の配置点そのもの

        msp.add_circle((sub_x, sub_y), radius, dxfattribs={"layer": "保安林円レイヤー"})

        # offsetを計算して、文字を円の中心に配置する
        offset_x, offset_y = compute_visual_offset(
            s, windows_font_path, sub_label_size, sub_label_size
        )
        t.set_placement(
            (sub_x - offset_x, sub_y - offset_y),
            align=TextEntityAlignment.MIDDLE_CENTER,
        )

        # 次の文字へ（直径＋間隔）
        sub_x += radius + label_spacing


class BaseDxf(pydantic.BaseModel):
    """DXFファイルに変換する際のオプションを定義するクラスです。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "小班区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "sub_address_name"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 10。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "小班区画ラベルレイヤー"。
    """

    gdf: Optional[gpd.GeoDataFrame] = None
    geometry_column: str = "geometry"
    geometry_layer: str = "小班区画レイヤー"
    label_column: Optional[str] = "sub_address_name"
    label_size: int = 23
    label_layer: str = "小班区画ラベルレイヤー"
    model_config = pydantic.ConfigDict(
        validate_default=True,
        arbitrary_types_allowed=True,
    )

    @staticmethod
    def dxf_versions() -> list[str]:
        """サポートされているDXFのバージョンを返します。"""
        return ["R12", "R2000", "R2004", "R2007", "R2010", "R2013", "R2018"]

    @staticmethod
    def dxf_units() -> list[InsertUnits]:
        """サポートされているDXFの単位を返します。"""
        return [
            InsertUnits.Unitless,
            InsertUnits.Millimeters,
            InsertUnits.Centimeters,
            InsertUnits.Meters,
            InsertUnits.Kilometers,
        ]

    def geometry_dxf_attributes(self) -> dict[str, Any]:
        return {
            "layer": self.geometry_layer,
        }

    def label_dxf_attributes(self) -> dict[str, Any]:
        return {
            "height": self.label_size,
            "layer": self.label_layer,
        }

    def _add_geometry(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        label: Optional[str] = None,
    ) -> None:
        # 外周の座標を取得し、座標をDXFのLWPolylineとして追加
        exterior_coords = list(geom.exterior.coords)
        modelspace.add_lwpolyline(
            exterior_coords,
            close=True,
            dxfattribs=self.geometry_dxf_attributes(),
        )
        if label is not None:
            # ラベルがある場合、Polygonと交差する点を取得してテキストを追加
            centroid = shapely.point_on_surface(geom)
            modelspace.add_text(
                label, dxfattribs=self.label_dxf_attributes()
            ).set_placement((centroid.x, centroid.y))
        # Polygonに内周がある場合、内周の座標もDXFのLWPolylineとして追加
        if geom.interiors:
            for interior in geom.interiors:
                interior_coords = list(interior.coords)
                modelspace.add_lwpolyline(
                    interior_coords,
                    close=True,
                    dxfattribs=self.geometry_dxf_attributes(),
                )

    def add_geometries(
        self,
        modelspace: Modelspace,
    ) -> None:
        if self.gdf is None:
            raise ValueError("gdf must be provided to add geometries.")

        # ジオメトリとラベルの取り出し
        geoms = self.gdf[self.geometry_column].to_list()
        if self.label_column is not None:
            if self.label_column in self.gdf.columns:
                labels = self.gdf[self.label_column].to_list()
            else:
                raise ValueError(
                    f"Label column '{self.label_column}' does not exist in the GeoDataFrame."
                )
        else:
            labels = None

        for i, geom in enumerate(geoms):
            if geom.geom_type == "Polygon":
                # 外周の座標を取得し、座標をDXFのLWPolylineとして追加
                self._add_geometry(
                    modelspace, geom, labels[i] if labels is not None else None
                )

            elif geom.geom_type == "MultiPolygon":
                for poly in geom.geoms:
                    self._add_geometry(
                        modelspace, poly, labels[i] if labels is not None else None
                    )


class SubAddrsDxf(BaseDxf):
    """小班区画のDXFファイルに変換する際のオプションを定義するクラスです。
    小班区画のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        version(str, optional):
            DXFのバージョン。デフォルトは "R2013"。他には "R12", "R2000", "R2004",
            "R2007", "R2010", "R2018" が使用可能です。
        unit(InsertUnits, optional):
            DXFの単位。デフォルトは InsertUnits.Meters。InsertUnits.Unitless,
            InsertUnits.Millimeters, InsertUnits.Centimeters, InsertUnits.Kilometers
            も使用可能です。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "小班区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "sub_address_name"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 10。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "小班区画ラベルレイヤー"。
        protection_forest_mark(bool, optional):
            保安林の短縮コードを円囲みで描画するかどうか。デフォルトは True。
        protection_mark_layer(str, optional):
            保安林の短縮コードを描画するレイヤー名。デフォルトは "保安林コードレイヤー"。
        protection_mark_circle_layer(str, optional):
            保安林の短縮コードを円囲みで描画するレイヤー名。デフォルトは "保安林コード円レイヤー"。
        protection_mark_offset_x_factor(float, optional):
            保安林の短縮コードを円囲みで描画する際の、円の中心と文字の左下のX方向のオフセット係数。デフォルトは 0.6。
        protection_mark_offset_y_factor(float, optional):
            保安林の短縮コードを円囲みで描画する際の、円の中心と文字の左下のY方向のオフセット係数。デフォルトは 0.4。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import SubAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        sub_addrs_dxf = SubAddrsDxf(gdf=gdf, protection_forest_mark=True)
        sub_addrs_dxf.add_geometries(modelspace)
        doc.saveas("sub_addrs.dxf")
        ```
    """

    protection_forest_mark: bool = True
    protection_mark_offset_x_factor: float = 0.5
    protection_mark_offset_y_factor: float = 0.4

    def _add_geometry(
        self,
        modelspace: Modelspace,
        geom: shapely.geometry.Polygon,
        label: Optional[str] = None,
        marks: Optional[list[str]] = None,
    ) -> None:
        exterior_coords = list(geom.exterior.coords)
        modelspace.add_lwpolyline(
            exterior_coords,
            close=True,
            dxfattribs=self.geometry_dxf_attributes(),
        )

        if geom.interiors:
            for interior in geom.interiors:
                interior_coords = list(interior.coords)
                modelspace.add_lwpolyline(
                    interior_coords,
                    close=True,
                    dxfattribs=self.geometry_dxf_attributes(),
                )

        if label is not None:
            # ラベルがある場合、Polygonと交差する点を取得してテキストを追加
            centroid = shapely.point_on_surface(geom)
            draw_labels(
                modelspace,
                centroid.x,
                centroid.y,
                main_label=label,
                sub_labels=marks,
                label_size=self.label_size,
            )

    def protection_marks(self) -> Optional[dict[int, Optional[list[str]]]]:
        """
        小班区画に保安林が含まれている場合、保安林の種別に応じた短縮コードをリスト化して返します。
        保安林が含まれていない場合は None を返します。
        """
        pf_coding = ProtectedForestCoding()

        if self.protection_forest_mark:
            if not isinstance(self.gdf, gpd.GeoDataFrame):
                # GeoDataFrameでない場合はエラーを返す
                raise ValueError(
                    "gdf must be a GeoDataFrame to calculate protection marks."
                )

            # 保安林の要素が含まれているカラムを取得
            addrs_fields = AddressFields()
            pf_cols = [
                field.en
                for field in addrs_fields.fields.values()
                if "protection_forest" in field.en
            ]
            # 保安林の種別に応じた短縮コードをリスト化して返す
            marks = {}
            for idx, row in self.gdf.iterrows():
                pfs = [pf for pf in row[pf_cols].tolist() if "-" != pf]
                if len(pfs) == 0:
                    marks[idx] = None
                else:
                    codes = []
                    for pf in pfs:
                        code = pf_coding.mark(pf)
                        if code is not None:
                            codes.append(code)
                    marks[idx] = codes if len(codes) > 0 else None
            return marks
        else:
            return None

    def add_geometries(
        self,
        modelspace: Modelspace,
    ) -> None:
        # ジオメトリとラベルの取り出し
        if self.gdf is None:
            raise ValueError("gdf must be provided to add geometries.")

        if self.label_column is not None:
            if self.label_column not in self.gdf.columns:
                raise ValueError(
                    f"Label column '{self.label_column}' does not exist in the GeoDataFrame."
                )

        marks_by_index = (
            self.protection_marks() if self.protection_forest_mark else None
        )

        for idx, row in self.gdf.iterrows():
            geom = row[self.geometry_column]
            label = row[self.label_column] if self.label_column is not None else None
            marks = marks_by_index.get(idx) if marks_by_index is not None else None

            if geom.geom_type == "Polygon":
                self._add_geometry(modelspace, geom, label, marks)

            elif geom.geom_type == "MultiPolygon":
                for poly in geom.geoms:
                    self._add_geometry(modelspace, poly, label, marks)


class MainAddrsDxf(BaseDxf):
    """林班区画のDXFファイルに変換する際のオプションを定義するクラスです。
    林班区画のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。
    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "林班区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "main_address"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 50。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "林班区画ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import MainAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        main_addrs_dxf = MainAddrsDxf(gdf=gdf)
        main_addrs_dxf.add_geometries(modelspace)
        doc.saveas("main_addrs.dxf")
        ```
    """

    geometry_layer: str = "林班区画レイヤー"
    label_column: Optional[str] = "main_address"
    label_size: int = 40
    label_layer: str = "林班区画ラベルレイヤー"


class LocalityDxf(BaseDxf):
    """国有林区画のDXFファイルに変換する際のオプションを定義するクラスです。
    国有林区画のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "国有林区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "locality"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 70。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "国有林名ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import LocalityAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        locality_dxf = LocalityDxf(gdf=gdf)
        locality_dxf.add_geometries(modelspace)
        doc.saveas("locality.dxf")
        ```
    """

    geometry_layer: str = "国有林区画レイヤー"
    label_column: Optional[str] = "locality"
    label_size: int = 50
    label_layer: str = "国有林名ラベルレイヤー"


class BranchOfficeDxf(BaseDxf):
    """森林事務所（担当区）のDXFファイルに変換する際のオプションを定義するクラスです。
    森林事務所（担当区）のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "森林事務所区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "branch_office"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 100。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "森林事務所区画ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import BranchOfficeAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        branch_office_dxf = BranchOfficeDxf(gdf=gdf)
        branch_office_dxf.add_geometries(modelspace)
        doc.saveas("branch_office.dxf")
        ```
    """

    geometry_layer: str = "森林事務所レイヤー"
    label_column: Optional[str] = "branch_office"
    label_size: int = 70
    label_layer: str = "森林事務所区画ラベルレイヤー"


class OfficeDxf(BaseDxf):
    """森林管理署のDXFファイルに変換する際のオプションを定義するクラスです。
    森林管理署のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "森林管理署区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "office"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 120。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "森林管理署区画ラベルレイヤー"。

    Example:
        ```python
        import ezdxf
        from nfj.dxf import OfficeAddrsDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        office_dxf = OfficeDxf(gdf=gdf)
        office_dxf.add_geometries(modelspace)
        doc.saveas("office.dxf")
        ```
    """

    geometry_layer: str = "森林管理署レイヤー"
    label_column: Optional[str] = "office"
    label_size: int = 90
    label_layer: str = "森林管理署区画ラベルレイヤー"


class ProtectionForestDxf(BaseDxf):
    """保安林のDXFファイルに変換する際のオプションを定義するクラスです。
    保安林のDXFファイルは、ジオデータフレームのジオメトリをDXFのLWPolylineとして追加し、
    ラベルがある場合は、Polygonと交差する点にテキストを追加します。

    Attributes:
        gdf(gpd.GeoDataFrame):
            ジオデータフレーム。
        geometry_column(str, optional):
            ジオデータフレームのジオメトリを含むカラム名。デフォルトは "geometry"。
        geometry_layer(str, optional):
            DXFのジオメトリを追加するレイヤー名。デフォルトは "保安林区画レイヤー"。
        label_column(str, optional):
            ジオデータフレームのラベルを含むカラム名。デフォルトは "protection_forests"。
            ラベルが不要な場合は None に設定できます。
        label_size(int, optional):
            DXFのラベルのサイズ。デフォルトは 10。
        label_layer(str, optional):
            DXFのラベルを追加するレイヤー名。デフォルトは "保安林区画ラベルレイヤー"。
    Example:
        ```python
        import ezdxf
        from nfj.dxf import ProtectionForestDxf

        gdf = ...  # ジオデータフレームを取得
        doc = ezdxf.new(dxfversion="R2013", units=InsertUnits.Meters)
        modelspace = doc.modelspace()
        protection_forest_dxf = ProtectionForestDxf(gdf=gdf)
        protection_forest_dxf.add_geometries(modelspace)
        doc.saveas("protection_forest.dxf")
        ```
    """

    geometry_layer: str = "保安林区画レイヤー"
    label_column: Optional[str] = "protected_forest_type"
    label_size: int = 20
    label_layer: str = "保安林区画ラベルレイヤー"
