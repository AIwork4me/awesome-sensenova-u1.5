from pathlib import Path


def test_repo_layout():
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "superpowers" / "specs").is_dir()
