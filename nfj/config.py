"""国有林データ向けのコード変換設定とユーティリティ。

YAML 形式の設定ファイルを読み込み、国有林データで使用する
各種コード値のエンコード・デコード機能を提供します。
"""

import functools
import os
import warnings
from typing import Optional

import yaml

conf_dir = os.path.join(os.path.dirname(__file__), ".confs")

_fields_yaml = os.path.join(conf_dir, "fields.yaml")
global ADDRESS_FIELDS
global FOREST_ROAD_FIELDS
with open(_fields_yaml, "r", encoding="utf-8") as f:
    fields = yaml.safe_load(f)
    ADDRESS_FIELDS = fields["address"]
    FOREST_ROAD_FIELDS = fields["forest_road"]

global URLS_2025
with open(os.path.join(conf_dir, "urls.yaml"), "r", encoding="utf-8") as f:
    urls = yaml.safe_load(f)
    URLS_2025 = urls[2025]

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
        warnings.warn(f"コード '{code}' は辞書に存在しません。代替値 0 を返します。")
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
    warnings.warn(f"コード '{code}' は辞書に存在しません。代替値 '-' を返します。")
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

    def autority_coding(self) -> "AuthorityCoding":
        """森林管理局コードの変換器を取得します。

        Returns:
            AuthorityCoding インスタンス。
        """
        return AuthorityCoding()

    def office_coding(self) -> "OfficeCoding":
        """森林管理署コードの変換器を取得します。

        Returns:
            OfficeCoding インスタンス。
        """
        return OfficeCoding()

    def branch_office_coding(self) -> "BranchOfficeCoding":
        """担当区コードの変換器を取得します。

        Returns:
            BranchOfficeCoding インスタンス。
        """
        return BranchOfficeCoding()

    def locality_coding(self) -> "LocalityCoding":
        """国有林コードの変換器を取得します。

        Returns:
            LocalityCoding インスタンス。
        """
        return LocalityCoding()

    def sub_address_name_coding(self) -> "SubAddressNameCoding":
        """小班名称コードの変換器を取得します。

        Returns:
            SubAddressNameCoding インスタンス。
        """
        return SubAddressNameCoding()

    def tree_name_coding(self) -> "TreeNameCoding":
        """樹種名コードの変換器を取得します。

        Returns:
            TreeNameCoding インスタンス。
        """
        return TreeNameCoding()

    def tree_species_coding(self) -> "TreeSpeciesCoding":
        """樹種区分コードの変換器を取得します。

        Returns:
            TreeSpeciesCoding インスタンス。
        """
        return TreeSpeciesCoding()

    def forest_type_detail_coding(self) -> "ForestTypeDetailCoding":
        """林種の細分コードの変換器を取得します。

        Returns:
            ForestTypeDetailCoding インスタンス。
        """
        return ForestTypeDetailCoding()

    def forest_feature_type_coding(self) -> "ForestFeatureTypeCoding":
        """機能類型コードの変換器を取得します。

        Returns:
            ForestFeatureTypeCoding インスタンス。
        """
        return ForestFeatureTypeCoding()

    def protected_forest_coding(self) -> "ProtectedForestCoding":
        """保安林コードの変換器を取得します。

        Returns:
            ProtectedForestCoding インスタンス。
        """
        return ProtectedForestCoding()


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
