from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ml_governance import GovernanceError, deterministic_group_split, load_governed_dataset, train_baseline


def test_original_synthetic_dataset_is_governed_and_hashable():
    dataset = load_governed_dataset("wysh.synthetic.diabetes.review.v1")
    assert dataset.asset_sha256
    assert dataset.registry_hash
    assert len(dataset.rows) == 20
    assert all(row["patient_id"].startswith("synthetic-") for row in dataset.rows)


def test_split_is_deterministic_and_has_no_group_leakage():
    dataset = load_governed_dataset("wysh.synthetic.diabetes.review.v1")
    first = deterministic_group_split(dataset)
    second = deterministic_group_split(dataset)
    assert {name: [row["patient_id"] for row in rows] for name, rows in first.items()} == {name: [row["patient_id"] for row in rows] for name, rows in second.items()}
    assert {name: len(rows) for name, rows in first.items()} == {"train": 12, "validation": 4, "test": 4}
    assert {row["patient_id"] for row in first["train"]}.isdisjoint({row["patient_id"] for row in first["validation"]})


def test_baseline_is_reproducible_and_not_clinically_authorized():
    dataset = load_governed_dataset("wysh.synthetic.diabetes.review.v1")
    first = train_baseline(dataset)
    second = train_baseline(dataset)
    assert first["provenance_hash"] == second["provenance_hash"]
    assert first["metrics"] == second["metrics"]
    assert first["synthetic_only"] is True
    assert first["clinical_use_authorized"] is False
    assert first["group_leakage_check"] == "PASS"


def test_registry_rejects_unregistered_dataset():
    with pytest.raises(GovernanceError):
        load_governed_dataset("not-registered")
