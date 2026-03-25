from typing import Any, Optional

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


class _AddrsColumns(object):
    """小班区画の処理にてよく使用する英名の属性名を定義するクラス。"""

    def __init__(self):
        for _, data in ADDRESS_FIELDS.items():
            setattr(self, data["en"], data["en"])

    def __getattr__(self, name: str) -> str:
        # Pylance向け: ADDRESS_FIELDS由来の動的属性は文字列として扱う
        return name
