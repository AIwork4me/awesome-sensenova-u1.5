"""Shared resolver for the per-round judge provenance manifest.

build_judge_tasks.py writes manifest.json into the judge-visible queue dir
(historical default) or into runs/judge-private/round-N/ (--isolated,
provenance-separated runs). Every consumer — collect, resample tooling,
tests — resolves the location through this module so the private-first rule
lives in exactly one place.
"""
import json
from pathlib import Path


def private_manifest_path(root: Path, round_id: int) -> Path:
    return Path(root) / f"runs/judge-private/round-{round_id}/manifest.json"


def public_manifest_path(root: Path, round_id: int) -> Path:
    return Path(root) / f"runs/judge-queue/round-{round_id}/manifest.json"


def manifest_path(root: Path, round_id: int) -> Path:
    """Prefer the provenance-separated private manifest; fall back to the
    in-queue manifest written by historical default assemblies."""
    priv = private_manifest_path(root, round_id)
    return priv if priv.exists() else public_manifest_path(root, round_id)


def load_manifest(root: Path, round_id: int) -> list:
    return json.loads(manifest_path(root, round_id).read_text(encoding="utf-8"))
