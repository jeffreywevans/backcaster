import pandas as pd

from marcelball.normalize import numeric_columns, safe_divide


def test_numeric_columns_includes_only_numeric_dtypes() -> None:
    df = pd.DataFrame(
        {
            "int_col": [1, 2, 3],
            "float_col": [1.5, 2.5, 3.5],
            "bool_col": [True, False, True],
            "str_col": ["a", "b", "c"],
            "obj_col": [1, "2", 3],
        }
    )

    assert numeric_columns(df) == ["int_col", "float_col", "bool_col"]


def test_numeric_columns_respects_exclude_set() -> None:
    df = pd.DataFrame(
        {
            "pa": [500, 600],
            "ab": [450, 550],
            "name": ["A", "B"],
        }
    )

    assert numeric_columns(df, exclude={"ab"}) == ["pa"]


def test_safe_divide_nonzero_denominator() -> None:
    assert safe_divide(9.0, 4.0) == 2.25


def test_safe_divide_zero_denominator_returns_zero() -> None:
    assert safe_divide(9.0, 0.0) == 0.0
