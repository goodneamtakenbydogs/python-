import logging
from unittest.mock import create_autospec

import pytest
from sample_report import core
from sample_report.source import read_label


@pytest.mark.smoke
def test_label_title(monkeypatch, caplog):
    reader = create_autospec(read_label, return_value={"label": "demo"})
    monkeypatch.setattr(core, "read_label", reader)
    with caplog.at_level(logging.INFO, logger=core.__name__):
        assert core.label_title("C-demo") == "DEMO"
    reader.assert_called_once_with("C-demo")
    records = [record for record in caplog.records if record.name == core.__name__]
    assert len(records) == 1
    assert records[0].case_id == "C-demo"
    assert records[0].getMessage() == "label formatted"


def test_reader_timeout_propagates(monkeypatch):
    reader = create_autospec(read_label, side_effect=TimeoutError("sample timeout"))
    monkeypatch.setattr(core, "read_label", reader)
    with pytest.raises(TimeoutError, match="sample timeout"):
        core.label_title("C-timeout")
    reader.assert_called_once_with("C-timeout")


@pytest.mark.extra
def test_extra_title_rule():
    assert core.render_report([], title="Extra") == "Extra\n"
