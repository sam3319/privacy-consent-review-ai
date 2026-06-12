import importlib.util

import pytest

from src import optional_models
from src.ml_classifier import predict_field_value_span
from scripts.train_transformer_ner import (
    align_row_labels,
    build_label_list,
    value_span,
)


def test_transformer_label_list_uses_generic_value_bio_labels():
    labels = build_label_list(
        [
            {"label": "housing.deposit"},
            {"label": "employment.wage"},
        ]
    )

    assert labels == ["O", "B-VALUE", "I-VALUE"]


def test_transformer_label_alignment_uses_character_offsets():
    row = {
        "text": "보증금은 1억 5,000만원으로 정한다.",
        "label": "housing.deposit",
        "value": "1억 5,000만원",
    }
    labels = ["O", "B-VALUE", "I-VALUE"]
    label_to_id = {label: index for index, label in enumerate(labels)}

    aligned = align_row_labels(
        row,
        [(0, 4), (5, 7), (8, 16), (16, 18), (18, 22), (0, 0)],
        label_to_id,
    )

    assert aligned == [0, 1, 2, 0, 0, -100]


def test_value_span_preserves_original_offsets_with_repeated_spaces():
    row = {
        "text": "급여  구성:  월  기본급  3,000,000원",
        "label": "employment.wage",
        "value": "월 기본급 3,000,000원",
    }

    start, end = value_span(row)

    assert row["text"][start:end] == "월  기본급  3,000,000원"


def test_transformer_prediction_prefers_matching_field(monkeypatch):
    def classifier(_text):
        return [
            {
                "entity_group": "EMPLOYMENT_WAGE",
                "score": 0.99,
                "start": 0,
                "end": 4,
            },
            {
                "entity_group": "HOUSING_DEPOSIT",
                "score": 0.91,
                "start": 5,
                "end": 15,
            },
        ]

    monkeypatch.setattr(optional_models, "load_transformer_ner", lambda: classifier)
    result = optional_models.predict_transformer_span(
        "보증금은 1억 5,000만원이다.",
        "housing.deposit",
    )

    assert result["value"] == "1억 5,000만원"
    assert result["span_method"] == "transformer_ner"
    assert result["span_probability"] == 91.0


def test_transformer_prediction_respects_minimum_score(monkeypatch):
    monkeypatch.setattr(
        optional_models,
        "load_transformer_ner",
        lambda: lambda _text: [
            {
                "entity": "B-HOUSING_DEPOSIT",
                "score": 0.2,
                "start": 5,
                "end": 15,
            }
        ],
    )

    assert (
        optional_models.predict_transformer_span(
            "보증금은 1억 5,000만원이다.",
            "housing.deposit",
        )
        is None
    )


@pytest.mark.skipif(
    importlib.util.find_spec("transformers") is None,
    reason="transformers is not installed",
)
def test_local_transformer_model_is_used_for_span_extraction():
    optional_models.load_transformer_ner.cache_clear()

    result = predict_field_value_span(
        "임차보증금은 1억 5,000만원으로 정한다.",
        "housing.deposit",
    )

    assert result["span_method"] == "transformer_ner"
    assert result["value"] == "1억 5,000만원"
