"""国有林データ向けのコード変換設定とユーティリティ。

YAML 形式の設定ファイルを読み込み、国有林データで使用する
各種コード値のエンコード・デコード機能を提供します。
"""

import functools
import os
from typing import Optional

import yaml

from .logging_config import get_logger

logger = get_logger(__name__)

conf_dir = os.path.join(os.path.dirname(__file__), ".confs")

_fields_yaml = os.path.join(conf_dir, "fields.yaml")
global ADDRESS_FIELDS
global FOREST_ROAD_FIELDS
with open(_fields_yaml, "r", encoding="utf-8") as f:
    fields = yaml.safe_load(f)
    ADDRESS_FIELDS = fields["address"]
    FOREST_ROAD_FIELDS = fields["forest_road"]

global URLS
with open(os.path.join(conf_dir, "urls.yaml"), "r", encoding="utf-8") as f:
    URLS = yaml.safe_load(f)

global NF_CODING
with open(os.path.join(conf_dir, "nf_coding.yaml"), "r", encoding="utf-8") as f:
    NF_CODING = yaml.safe_load(f)


def encode(code: str, dictionary: dict) -> int:
    """ラベル文字列を数値コードに変換します。

    Args:
        code: 変換対象のラベル。
        dictionary: ラベル文字列から数値コードへの対応表。

    Returns:
        変換後の数値コード。

    Warns:
        UserWarning: ``code`` が見つからない場合に警告し、
            代替値として ``0`` を返します。
    """
    if code not in dictionary:
        logger.warning(f"コード '{code}' は辞書に存在しません。代替値 0 を返します。")
        return 0
    return dictionary[code]


def decode(code: int, dictionary: dict) -> str:
    """数値コードをラベル文字列に変換します。

    Args:
        code: 変換対象の数値コード。
        dictionary: ラベル文字列から数値コードへの対応表。

    Returns:
        変換後のラベル文字列。

    Warns:
        UserWarning: ``code`` が見つからない場合に警告し、
            代替値として ``"-"`` を返します。
    """
    for key, value in dictionary.items():
        if value == code:
            return key
    logger.warning(f"コード '{code}' は辞書に存在しません。代替値 '-' を返します。")
    return "-"


class Coding(object):
    """``NF_CODING`` で定義された項目用の基本変換クラス。

    項目ごとの辞書を保持し、繰り返し変換を高速化するため
    キャッシュ付きの encode/decode メソッドを提供します。
    """

    def __init__(self, field: str):
        """指定した項目に対応する変換器を初期化します。

        Args:
            field: ``NF_CODING["coding"]`` 配下の項目名。

        Raises:
            ValueError: 指定した項目が定義されていない場合。
        """
        if field not in NF_CODING["coding"]:
            raise ValueError(f"Field '{field}' not found in NF_CODING.")
        self.dictionary = NF_CODING["coding"][field]

    @functools.lru_cache(maxsize=20)
    def encode(self, code: str) -> int:
        """項目専用の辞書を使ってラベルを数値コードに変換します。

        Args:
            code: 変換対象のラベル文字列。

        Returns:
            変換後の数値コード。
        """
        return encode(code, self.dictionary)

    @functools.lru_cache(maxsize=20)
    def decode(self, code: int) -> str:
        """項目専用の辞書を使って数値コードをラベルに変換します。

        Args:
            code: 変換対象の数値コード。

        Returns:
            変換後のラベル文字列。
        """
        return decode(code, self.dictionary)


class PrefectureCoding(Coding):
    """都道府県コードの変換クラス。"""

    def __init__(self):
        """都道府県コード変換クラスを初期化します。"""
        super().__init__("prefecture")


class CityCoding(Coding):
    """市町村コードの変換クラス。"""

    def __init__(self):
        """市町村コード変換クラスを初期化します。"""
        super().__init__("city")


class PlanAreaCoding(Coding):
    """森林計画区コードの変換クラス。"""

    def __init__(self):
        """森林計画区コード変換クラスを初期化します。"""
        super().__init__("plan_area")


class AuthorityCoding(Coding):
    """森林管理局コードの変換クラス。"""

    def __init__(self):
        """森林管理局コード変換クラスを初期化します。"""
        super().__init__("authority")


class OfficeCoding(Coding):
    """森林管理署コードの変換クラス。"""

    def __init__(self):
        """森林管理署コード変換クラスを初期化します。"""
        super().__init__("office")


class BranchOfficeCoding(Coding):
    """担当区コードの変換クラス。"""

    def __init__(self):
        """担当区コード変換クラスを初期化します。"""
        super().__init__("branch_office")


class LocalityCoding(Coding):
    """国有林コードの変換クラス。"""

    def __init__(self):
        """国有林コード変換クラスを初期化します。"""
        super().__init__("locality")


class SubAddressNameCoding(Coding):
    """小班名称コードの変換クラス。"""

    def __init__(self):
        """小班名称コード変換クラスを初期化します。"""
        super().__init__("sub_address_name")


class TreeNameCoding(Coding):
    """樹種名コードの変換と樹種区分参照を行うクラス。"""

    def __init__(self):
        """樹種名コード変換クラスを初期化します。"""
        super().__init__("tree_name")

    def tree_species(self, code: str) -> str:
        """樹種名コードから樹種区分を取得します。

        Args:
            code: 樹種名ラベル。

        Returns:
            ``"N"`` や ``"L"`` などの樹種区分コード。
            見つからない場合は ``"-"`` を返します。
        """
        return NF_CODING["tree_species"].get(code, "-")


class TreeSpeciesCoding(Coding):
    """樹種区分コードの変換クラス。"""

    def __init__(self):
        """樹種区分コード変換クラスを初期化します。"""
        super().__init__("tree_species")


class ForestTypeDetailCoding(Coding):
    """林種の細分コードの変換クラス。"""

    def __init__(self):
        """林種の細分コード変換クラスを初期化します。"""
        super().__init__("forest_type_detail")


class ForestFeatureTypeCoding(Coding):
    """機能類型コードの変換クラス。"""

    def __init__(self):
        """機能類型コード変換クラスを初期化します。"""
        super().__init__("forest_feature_type")


class ProtectedForestCoding(Coding):
    """保安林コードの変換と記号参照を行うクラス。"""

    def __init__(self):
        """保安林コード変換クラスを初期化します。"""
        super().__init__("protected_forest")

    def mark(self, code: str) -> Optional[str]:
        """保安林コードに対応する簡易記号を取得します。

        Args:
            code: 保安林ラベル。

        Returns:
            対応する記号文字列。見つからない場合は ``None``。
        """
        return NF_CODING["mark"].get(code, None)


class ConservationCoding(Coding):
    """保護林コードの変換クラス。"""

    def __init__(self):
        """保護林コード変換クラスを初期化します。"""
        super().__init__("conservation")

    def decode_original(self, code: int) -> str:
        """G空間センターオリジナルのデータは数値コードが4桁の為、それを文字列に変換するためのメソッドです。

        Args:
            code: 変換対象の数値コード。

        Returns:
            変換後のラベル文字列。見つからない場合は ``"-"`` を返します。
        """
        org_codes = {
            2010: "森林生態系保護地域保存地区",
            2020: "森林生態系保護地域保全利用地区",
            2021: "生物群集保護林保存地区",
            2022: "生物群集保護林保全利用地区",
            2023: "希少個体群保護林",
            2030: "森林生物遺伝資源保存林",
            2040: "林木遺伝資源保存林",
            2050: "植物群落保護林",
            2060: "特定動物生息地保護林",
            2070: "特定地理等保護林",
            2080: "郷土の森",
        }
        return org_codes.get(code, "-")


class GreenCorridorCoding(Coding):
    """緑の回廊コードの変換クラス。"""

    def __init__(self):
        """緑の回廊コード変換クラスを初期化します。"""
        super().__init__("green_corridor")
