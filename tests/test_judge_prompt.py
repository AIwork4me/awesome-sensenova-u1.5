from pathlib import Path


def test_judge_prompt_contains_schema_keys_and_ban():
    t = (Path(__file__).resolve().parents[1] / "scripts" / "judge-prompt.md").read_text(encoding="utf-8")
    for key in ("real_world_fidelity", "text_miss_count", "不允许猜测或推断", "GARBLED"):
        assert key in t
