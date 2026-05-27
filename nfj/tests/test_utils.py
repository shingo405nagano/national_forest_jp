import pytest

from ..utils import txt_normalizer


@pytest.mark.parametrize(
    "input_txt, expected",
    [
        ("ＡＢＣ１２３", "ABC123"),
        ("ａｂｃ", "abc"),
        ("−１２３", "-123"),
        ("－１２３", "-123"),
        ("―１２３", "-123"),
        ("　ＡＢＣ　１２３　", "ABC123"),
        ("A B", "AB"),
        ("A　B", "AB"),
        ("漢字ケ漢字", "漢字ヶ漢字"),
        ("ケ", "ケ"),
    ],
)
def test_txt_normalizer(input_txt, expected):
    assert txt_normalizer(input_txt) == expected
