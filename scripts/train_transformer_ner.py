import argparse
import csv
import inspect
import json
import random
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_field_training_data import OUTPUT_PATH, build_dataset


DEFAULT_BASE_MODEL = "monologg/koelectra-small-v3-discriminator"
DEFAULT_OUTPUT_DIR = ROOT / "models" / "transformer_ner"
DEFAULT_METRICS_PATH = ROOT / "models" / "transformer_ner_metrics.json"
RANDOM_SEED = 42


def load_rows(path: Path = OUTPUT_PATH) -> list[dict]:
    if not path.exists():
        build_dataset(path)
    with path.open(encoding="utf-8", newline="") as source:
        return [
            row
            for row in csv.DictReader(source)
            if row["label"] != "other" and row.get("value")
        ]


def build_label_list(rows: list[dict]) -> list[str]:
    del rows
    return ["O", "B-VALUE", "I-VALUE"]


def value_span(row: dict) -> tuple[int, int]:
    start = row["text"].find(row["value"])
    if start >= 0:
        return start, start + len(row["value"])

    compact_text, text_positions = _compact_with_positions(row["text"])
    compact_value = "".join(row["value"].split())
    compact_start = compact_text.find(compact_value)
    if compact_start < 0:
        raise ValueError(
            f"학습 값이 문장에 없습니다: {row['label']} / {row['value']}"
        )
    compact_end = compact_start + len(compact_value)
    return text_positions[compact_start], text_positions[compact_end - 1] + 1


def _compact_with_positions(text: str) -> tuple[str, list[int]]:
    characters = []
    positions = []
    for index, character in enumerate(text):
        if character.isspace():
            continue
        characters.append(character)
        positions.append(index)
    return "".join(characters), positions


def align_row_labels(
    row: dict,
    offsets: list[tuple[int, int]],
    label_to_id: dict[str, int],
) -> list[int]:
    start, end = value_span(row)
    labels = []
    entity_started = False
    for token_start, token_end in offsets:
        if token_start == token_end:
            labels.append(-100)
            continue
        overlaps = token_end > start and token_start < end
        if not overlaps:
            labels.append(label_to_id["O"])
            continue
        prefix = "I" if entity_started else "B"
        labels.append(label_to_id[f"{prefix}-VALUE"])
        entity_started = True
    if not entity_started:
        raise ValueError(f"토큰화 후 값 범위를 찾지 못했습니다: {row['text']}")
    return labels


class TokenDataset:
    def __init__(self, rows, tokenizer, label_to_id, max_length):
        self.items = []
        for row in rows:
            encoded = tokenizer(
                row["text"],
                truncation=True,
                max_length=max_length,
                return_offsets_mapping=True,
            )
            offsets = encoded.pop("offset_mapping")
            encoded["labels"] = align_row_labels(row, offsets, label_to_id)
            self.items.append(encoded)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


def train_and_save(
    base_model: str = DEFAULT_BASE_MODEL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    epochs: float = 3.0,
    batch_size: int = 16,
    learning_rate: float = 3e-5,
    max_length: int = 128,
) -> dict:
    try:
        import torch
        from transformers import (
            AutoModelForTokenClassification,
            AutoTokenizer,
            DataCollatorForTokenClassification,
            Trainer,
            TrainingArguments,
        )
    except ImportError as error:
        raise RuntimeError(
            "`requirements-optional-ml.txt`의 패키지를 먼저 설치하세요."
        ) from error

    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    torch.manual_seed(RANDOM_SEED)
    rows = load_rows()
    train_rows, test_rows = train_test_split(
        rows,
        test_size=0.2,
        random_state=RANDOM_SEED,
        stratify=[row["label"] for row in rows],
    )
    labels = build_label_list(rows)
    label_to_id = {label: index for index, label in enumerate(labels)}
    id_to_label = {index: label for label, index in label_to_id.items()}
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    if not tokenizer.is_fast:
        raise ValueError("오프셋 정렬을 위해 fast tokenizer가 필요합니다.")
    train_dataset = TokenDataset(train_rows, tokenizer, label_to_id, max_length)
    test_dataset = TokenDataset(test_rows, tokenizer, label_to_id, max_length)
    model = AutoModelForTokenClassification.from_pretrained(
        base_model,
        num_labels=len(labels),
        id2label=id_to_label,
        label2id=label_to_id,
    )
    output_dir = output_dir.resolve()
    checkpoint_dir = output_dir.with_name(f"{output_dir.name}-checkpoints")
    if checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)

    def compute_metrics(evaluation):
        logits, expected = evaluation
        predicted = np.argmax(logits, axis=-1)
        flat_expected = []
        flat_predicted = []
        for expected_row, predicted_row in zip(expected, predicted):
            for expected_id, predicted_id in zip(expected_row, predicted_row):
                if expected_id == -100:
                    continue
                flat_expected.append(labels[int(expected_id)])
                flat_predicted.append(labels[int(predicted_id)])
        return {
            "macro_f1": f1_score(
                flat_expected,
                flat_predicted,
                average="macro",
                zero_division=0,
            ),
            "accuracy": sum(
                expected == predicted
                for expected, predicted in zip(flat_expected, flat_predicted)
            )
            / len(flat_expected),
        }

    argument_values = {
        "output_dir": str(checkpoint_dir),
        "learning_rate": learning_rate,
        "per_device_train_batch_size": batch_size,
        "per_device_eval_batch_size": batch_size,
        "num_train_epochs": epochs,
        "weight_decay": 0.01,
        "save_strategy": "epoch",
        "logging_strategy": "epoch",
        "load_best_model_at_end": True,
        "metric_for_best_model": "macro_f1",
        "greater_is_better": True,
        "seed": RANDOM_SEED,
        "report_to": [],
        "save_total_limit": 1,
    }
    argument_names = inspect.signature(TrainingArguments.__init__).parameters
    evaluation_key = (
        "eval_strategy" if "eval_strategy" in argument_names else "evaluation_strategy"
    )
    argument_values[evaluation_key] = "epoch"
    training_arguments = TrainingArguments(**argument_values)
    trainer_values = {
        "model": model,
        "args": training_arguments,
        "train_dataset": train_dataset,
        "eval_dataset": test_dataset,
        "data_collator": DataCollatorForTokenClassification(tokenizer=tokenizer),
        "compute_metrics": compute_metrics,
    }
    trainer_names = inspect.signature(Trainer.__init__).parameters
    trainer_values[
        "processing_class" if "processing_class" in trainer_names else "tokenizer"
    ] = tokenizer
    trainer = Trainer(**trainer_values)
    trainer.train()
    prediction = trainer.predict(test_dataset)
    evaluation = compute_metrics((prediction.predictions, prediction.label_ids))
    flat_expected, flat_predicted = _flatten_predictions(
        prediction.predictions,
        prediction.label_ids,
        labels,
    )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    training_arguments_path = output_dir / "training_args.bin"
    if training_arguments_path.exists():
        training_arguments_path.unlink()
    shutil.rmtree(checkpoint_dir, ignore_errors=True)
    metrics = {
        "model_type": "Transformer token classification BIO NER",
        "task": "contract field value span extraction",
        "base_model": base_model,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "dataset_size": len(rows),
        "train_size": len(train_rows),
        "test_size": len(test_rows),
        "label_count": len(labels),
        "field_count": len({row["label"] for row in rows}),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "max_length": max_length,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "holdout_macro_f1": round(evaluation["macro_f1"], 4),
        "holdout_accuracy": round(evaluation["accuracy"], 4),
        "classification_report": classification_report(
            flat_expected,
            flat_predicted,
            output_dict=True,
            zero_division=0,
        ),
        "class_distribution": dict(Counter(flat_expected)),
        "limitations": [
            "합성 문장으로 학습되어 실제 계약서와 OCR 오류에 대한 외부 평가가 필요하다.",
            "필드 문장 분류 모델이 선택한 문장 안에서 값 범위를 추출한다.",
            "자동 추출 결과는 법률 판단이 아니라 사용자 검토를 위한 보조 정보다.",
        ],
    }
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if output_dir == DEFAULT_OUTPUT_DIR.resolve():
        from scripts.build_model_manifest import build_manifest

        build_manifest()
    return metrics


def _flatten_predictions(logits, expected, labels):
    predicted = np.argmax(logits, axis=-1)
    flat_expected = []
    flat_predicted = []
    for expected_row, predicted_row in zip(expected, predicted):
        for expected_id, predicted_id in zip(expected_row, predicted_row):
            if expected_id == -100:
                continue
            flat_expected.append(labels[int(expected_id)])
            flat_predicted.append(labels[int(predicted_id)])
    return flat_expected, flat_predicted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--max-length", type=int, default=128)
    arguments = parser.parse_args()
    metrics = train_and_save(
        base_model=arguments.base_model,
        output_dir=arguments.output_dir,
        metrics_path=arguments.metrics,
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        learning_rate=arguments.learning_rate,
        max_length=arguments.max_length,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
