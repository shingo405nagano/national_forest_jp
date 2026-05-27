import pytest

from ..fields import AddressFields, BaseFields, FieldInfo, _AddrsColumns


def test_field_info_validates_and_casts_values():
    field_info = FieldInfo(
        org="県市町村",
        ja="市区町村",
        en="city",
        dtype="string",
        default="-",
    )

    assert field_info.dtype is str
    assert field_info.cast("北斗市") == "北斗市"
    assert field_info.cast(None) == "-"


@pytest.mark.parametrize(
    "dtype, value, expected",
    [
        ("geometry", "raw-geometry", "raw-geometry"),
        ("integer", "123", 123),
        ("float", "1.5", 1.5),
    ],
)
def test_field_info_cast_handles_other_supported_types(dtype, value, expected):
    field_info = FieldInfo(
        org="属性",
        ja="属性",
        en="attr",
        dtype=dtype,
        default="fallback",
    )

    assert field_info.cast(value) == expected


@pytest.mark.parametrize(
    "dtype, value",
    [
        ("integer", "not-a-number"),
        ("float", "not-a-number"),
    ],
)
def test_field_info_cast_returns_default_when_conversion_fails(dtype, value):
    field_info = FieldInfo(
        org="属性",
        ja="属性",
        en="attr",
        dtype=dtype,
        default="fallback",
    )

    assert field_info.cast(value) == "fallback"


@pytest.mark.parametrize(
    "kwargs, message",
    [
        (
            {
                "org": 1,
                "ja": "市区町村",
                "en": "city",
                "dtype": "string",
                "default": "-",
            },
            "org、ja、enは文字列でなければなりません。",
        ),
        (
            {
                "org": "県市町村",
                "ja": "市区町村",
                "en": "city",
                "dtype": 1,
                "default": "-",
            },
            "dtypeは文字列でなければなりません。",
        ),
        (
            {
                "org": "県市町村",
                "ja": "市区町村",
                "en": "city",
                "dtype": "number",
                "default": "-",
            },
            "dtypeはstring、geometry、integer、floatのいずれかでなければなりません。",
        ),
    ],
)
def test_field_info_rejects_invalid_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        FieldInfo(**kwargs)


def test_base_fields_validates_field_mapping():
    field_info = FieldInfo(
        org="県市町村",
        ja="市区町村",
        en="city",
        dtype="string",
        default="-",
    )

    base_fields = BaseFields(fields={"県市町村": field_info})

    assert base_fields.fields["県市町村"] is field_info


@pytest.mark.parametrize(
    "fields, message",
    [
        ([], "fieldsは辞書でなければなりません。"),
        (
            {
                1: FieldInfo(
                    org="県市町村",
                    ja="市区町村",
                    en="city",
                    dtype="string",
                    default="-",
                )
            },
            "fieldsのキーは文字列でなければなりません。",
        ),
        (
            {"県市町村": "not-field-info"},
            "fieldsの値はFieldInfoのインスタンスでなければなりません。",
        ),
    ],
)
def test_base_fields_rejects_invalid_inputs(fields, message):
    with pytest.raises(ValueError, match=message):
        BaseFields(fields=fields)


def test_address_fields_builds_rename_and_lookup_helpers():
    address_fields = AddressFields()

    assert address_fields.rename_dict_org_to_en()["県市町村"] == "city"
    assert address_fields.rename_dict_en_to_ja()["city"] == "市区町村"
    assert address_fields.rename_dict_ja_to_en()["市区町村"] == "city"
    assert address_fields.use_default_en_fields()[0] == "city"
    assert address_fields.field_info("city").org == "県市町村"
    assert address_fields.field_info("city").ja == "市区町村"


def test_address_fields_unknown_field_raises():
    address_fields = AddressFields()

    with pytest.raises(
        ValueError, match="英語の属性名 'unknown' は見つかりませんでした。"
    ):
        address_fields.field_info("unknown")


def test_addrs_columns_exposes_known_field_names_and_fallback_behavior():
    cols = _AddrsColumns()

    assert cols.city == "city"
    assert cols.authority == "authority"
    assert cols.plan_area == "plan_area"
    assert cols.unknown_field == "unknown_field"
