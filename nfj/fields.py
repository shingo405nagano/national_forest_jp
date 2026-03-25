from typing import Any, NamedTuple, Optional

import pydantic

from .config import ADDRESS_FIELDS, FOREST_ROAD_FIELDS  # noqa: F401
from .logging_config import get_logger

logger = get_logger(__name__)


class FieldInfo(pydantic.BaseModel):
    """属性情報を表すクラス

    Attributes:
        org (str): 元の属性名（日本語）
        ja (str): 日本語の属性名
        en (str): 英語の属性名
        dtype (Any): データ型（string、geometry、integer、floatのいずれか）
        default (Any): デフォルト値
    """

    org: str
    ja: str
    en: str
    dtype: Any
    default: Any
    agg: Optional[str] = pydantic.Field(default=None)

    @pydantic.field_validator("org", "ja", "en", mode="before")
    def validate_string(cls, v):
        if not isinstance(v, str):
            raise ValueError("org、ja、enは文字列でなければなりません。")
        return v

    @pydantic.field_validator("dtype", mode="before")
    def validate_dtype(cls, v):
        if not isinstance(v, str):
            raise ValueError("dtypeは文字列でなければなりません。")
        v = v.lower()
        if v == "string":
            return str
        elif v == "geometry":
            return None
        elif v == "integer":
            return int
        elif v == "float":
            return float
        else:
            raise ValueError(
                "dtypeはstring、geometry、integer、floatのいずれかでなければなりません。"
            )

    def cast(self, value: Any) -> Any:
        """値をdtypeに基づいて型変換します。"""
        if value is None:
            return self.default
        if self.dtype is None:
            return value
        try:
            return self.dtype(value)
        except (ValueError, TypeError):
            return self.default


class BaseFields(pydantic.BaseModel):
    """属性管理の基底クラス

    属性管理クラスは、データの属性名やデータ型、デフォルト値などの情報を定義するクラスです。
    """

    fields: dict[str, FieldInfo] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("fields", mode="before")
    def validate_fields(cls, v):
        if not isinstance(v, dict):
            raise ValueError("fieldsは辞書でなければなりません。")
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError("fieldsのキーは文字列でなければなりません。")
            if not isinstance(value, FieldInfo):
                raise ValueError(
                    "fieldsの値はFieldInfoのインスタンスでなければなりません。"
                )
        return v


class AddressFields(BaseFields):
    """G空間センターで公開されている、国有林の林小班区画データの属性管理クラスです。"""

    def __init__(self):
        fields = {}
        for key, data in ADDRESS_FIELDS.items():
            data["org"] = key
            fields[key] = FieldInfo(**data)
        super().__init__(fields=fields)

    def rename_dict_org_to_en(self) -> dict[str, str]:
        """属性名を日本語から英語に変換する辞書を返します。"""
        return {key: field_info.en for key, field_info in self.fields.items()}

    def rename_dict_en_to_ja(self) -> dict[str, str]:
        """属性名を英語から日本語に変換する辞書を返します。"""
        return {field_info.en: field_info.ja for field_info in self.fields.values()}

    def rename_dict_ja_to_en(self) -> dict[str, str]:
        """属性名を日本語から英語に変換する辞書を返します。"""
        return {field_info.ja: field_info.en for field_info in self.fields.values()}

    def use_default_en_fields(self) -> list[str]:
        """英語の属性名のリストを返します。"""
        return [field_info.en for field_info in self.fields.values()]

    def field_info(self, en_field_name: str) -> FieldInfo:
        """英語の属性名からFieldInfoを取得します。

        Args:
            en_field_name: 英語の属性名

        Returns:
            FieldInfoオブジェクト

        Raises:
            ValueError: 指定された英語の属性名が見つからない場合。
        """
        for field_info in self.fields.values():
            if field_info.en == en_field_name:
                return field_info
        raise ValueError(f"英語の属性名 '{en_field_name}' は見つかりませんでした。")


class _AddrsColumns(NamedTuple):
    """小班区画の処理にてよく使用する英名の属性名を定義するクラス。"""

    city: str = ADDRESS_FIELDS.get("県市町村", {}).get("en", "city")
    plan_area: str = ADDRESS_FIELDS.get("計画区", {}).get("en", "plan_area")
    office: str = ADDRESS_FIELDS.get("森林管理署", {}).get("en", "office")
    branch_office: str = ADDRESS_FIELDS.get("担当区", {}).get("en", "branch_office")
    locality: str = ADDRESS_FIELDS.get("国有林名", {}).get("en", "locality")
    main_address: str = ADDRESS_FIELDS.get("林班主番", {}).get("en", "main_address")
    address: str = ADDRESS_FIELDS.get("林小班名称", {}).get("en", "address")
    sub_address: str = ADDRESS_FIELDS.get("小班名", {}).get("en", "sub_address_name")
    establishment_year: str = ADDRESS_FIELDS.get("樹立年度", {}).get(
        "en", "establishment_year"
    )
    tree_age_1: str = ADDRESS_FIELDS.get("樹齢1", {}).get("en", "tree_age_1")
    tree_age_2: str = ADDRESS_FIELDS.get("樹齢2", {}).get("en", "tree_age_2")
    tree_age_3: str = ADDRESS_FIELDS.get("樹齢3", {}).get("en", "tree_age_3")
    conservation: str = ADDRESS_FIELDS.get("保護林", {}).get("en", "conservation")
    green_corridor: str = ADDRESS_FIELDS.get("緑の回廊", {}).get("en", "green_corridor")
