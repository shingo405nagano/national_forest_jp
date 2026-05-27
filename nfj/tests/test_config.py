import logging

import pytest

from ..config import (
    Coding,
    ConservationCoding,
    PrefectureCoding,
    ProtectedForestCoding,
    TreeNameCoding,
    TreeSpeciesCoding,
    decode,
    encode,
)
from ..logging_config import get_logger, setup_logging


def test_get_logger_returns_named_logger():
    logger = get_logger("nfj.tests.sample")

    assert logger is logging.getLogger("nfj.tests.sample")


def test_setup_logging_calls_basicConfig(monkeypatch):
    captured = {}

    def fake_basicConfig(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basicConfig)

    setup_logging(logging.DEBUG)

    assert captured == {
        "level": logging.DEBUG,
        "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
    }


def test_encode_decode_and_missing_values():
    dictionary = {"北海道": 1, "青森": 2}

    assert encode("北海道", dictionary) == 1
    assert encode("不存在", dictionary) == 0
    assert decode(2, dictionary) == "青森"
    assert decode(9, dictionary) == "-"


def test_coding_helpers_cover_representative_mappings():
    prefecture = PrefectureCoding()
    tree_name = TreeNameCoding()
    tree_species = TreeSpeciesCoding()
    protected_forest = ProtectedForestCoding()
    conservation = ConservationCoding()

    assert prefecture.encode("北海道") == 1
    assert prefecture.decode(1) == "北海道"
    assert tree_name.tree_species("スギ") == "N"
    assert tree_name.tree_species("未登録") == "-"
    assert tree_species.encode("N") == 1
    assert tree_species.decode(1) == "N"
    assert protected_forest.mark("水涵保") == "水"
    assert protected_forest.mark("未登録") is None
    assert conservation.decode_original(2010) == "森林生態系保護地域保存地区"
    assert conservation.decode_original(9999) == "-"


def test_coding_rejects_unknown_field():
    with pytest.raises(ValueError):
        Coding("not_defined")
