"""Tests for checked-in examples."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_mmlu_pro_verification_example_passes():
    root = Path(__file__).resolve().parents[1]
    script = root / "examples" / "mmlu_pro" / "verify_claim.py"
    spec = importlib.util.spec_from_file_location("mmlu_pro_verify_claim", script)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.verify()
    assert result["hash_match"] is True
    assert result["threshold_satisfied"] is True
    assert result["ok"] is True
