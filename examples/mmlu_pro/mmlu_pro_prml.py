"""Inspect AI task for a small MMLU-Pro PRML example.

Run a development sample with:

    inspect eval examples/mmlu_pro/mmlu_pro_prml.py --limit 10 --sample-shuffle 42
"""

from __future__ import annotations

from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, hf_dataset
from inspect_ai.scorer import choice
from inspect_ai.solver import multiple_choice

DATASET_PATH = "TIGER-Lab/MMLU-Pro"
DATASET_REVISION = "527feea0afed1de15a8c115abf7be4c912123315"


def record_to_sample(record: dict[str, Any]) -> Sample:
    """Convert one MMLU-Pro Hugging Face record into an Inspect sample."""
    return Sample(
        input=record["question"],
        choices=record["options"],
        target=record["answer"],
        id=record["question_id"],
        metadata={
            "subject": record["category"].lower(),
        },
    )


@task
def mmlu_pro_prml(shuffle: bool = False) -> Task:
    """Return a lightweight MMLU-Pro task suitable for PRML examples."""
    dataset = hf_dataset(
        path=DATASET_PATH,
        split="test",
        sample_fields=record_to_sample,
        revision=DATASET_REVISION,
        shuffle=shuffle,
    )

    return Task(
        dataset=dataset,
        solver=[multiple_choice()],
        scorer=choice(),
    )
