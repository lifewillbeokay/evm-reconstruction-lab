import json
from pathlib import Path
import pytest
from evm_lab.verification import check_sources, inside
from evm_lab.selectors import selector

CASE=Path(__file__).resolve().parents[1]/'cases/wintermute-curve-balancer'


def test_submitted_sources_are_preserved():
    check_sources(CASE)


def test_all_42_signatures_and_17_mined_names():
    rows=json.loads((CASE/'selector-map.json').read_text())
    assert len(rows)==42
    assert len({x['selector'] for x in rows})==42
    assert sum(x['mined_name'] for x in rows)==17
    assert sum(x['trade_entrypoint'] for x in rows)==11
    for row in rows: assert selector(row['signature'])==row['selector']


def test_case_paths_cannot_escape(tmp_path):
    with pytest.raises(ValueError): inside(tmp_path,'../outside')
