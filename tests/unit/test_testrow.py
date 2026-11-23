"""TestRow.from_data_row keeps the sheet's order for the fields the sheet tests loop over."""
import pytest

from src.babel_validation.core.testrow import TestRow

pytestmark = pytest.mark.unit


def test_biolink_classes_keep_sheet_order_and_repeats():
    # test_label stops at the first class that misses, so a set here made its outcome depend on
    # the hash seed (#193). Enough entries that a set would almost never keep this order.
    classes = [f"biolink:Class{i}" for i in range(20, 0, -1)] + ["biolink:Class5"]
    row = TestRow.from_data_row({"Biolink Classes": "|".join(classes)})
    assert row.BiolinkClasses == classes


def test_empty_biolink_classes_cell_is_one_empty_entry():
    # An empty cell is what makes test_label query without a Biolink class.
    assert TestRow.from_data_row({}).BiolinkClasses == [""]
