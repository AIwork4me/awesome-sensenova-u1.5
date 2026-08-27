import json
from make_gen_jsonl import bucket_for, stable_seed


def test_bucket_portrait_priority():
    assert bucket_for("vertical movie poster for a film") == (1664, 2496)
    assert bucket_for("wide landscape banner design") == (2496, 1664)
    assert bucket_for("a cat on mars") == (2048, 2048)


def test_seed_stable_and_range():
    a = stable_seed(511, 1, 0)
    assert a == stable_seed(511, 1, 0) and a != stable_seed(511, 1, 1)
    assert 0 <= a < 2**31 - 1
