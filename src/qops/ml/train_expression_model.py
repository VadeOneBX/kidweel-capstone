"""CLI: offline logistic regression on expression-style training CSV (research only)."""

from __future__ import annotations

import argparse

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression

from qops.ml.features import features_to_frame
from qops.ml.targets import build_expression_target


def main() -> None:
    """Train a logistic regression model from ``--training-csv`` and persist with joblib."""
    parser = argparse.ArgumentParser(description="Train offline LogisticRegression on feature columns.")
    parser.add_argument("--training-csv", required=True, help="CSV with features and outcome columns.")
    parser.add_argument("--output-model", required=True, help="Path to write joblib model artifact.")
    args = parser.parse_args()

    df = pd.read_csv(args.training_csv)
    X = features_to_frame(df.to_dict(orient="records"))
    y = build_expression_target(df)

    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    joblib.dump(model, args.output_model)

    print(f"rows={len(df)}")
    print(f"model={args.output_model}")


if __name__ == "__main__":
    main()
