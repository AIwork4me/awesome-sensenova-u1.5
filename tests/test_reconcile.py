import json
from reconcile_generation import parse_tags


def test_parse_tags_maps_files(tmp_path):
    (tmp_path / "0001_case511-r1-s111_1664x2496.png").write_bytes(b"x")
    m = parse_tags(tmp_path)
    assert m == {"case511-r1-s111": "0001_case511-r1-s111_1664x2496.png"}
