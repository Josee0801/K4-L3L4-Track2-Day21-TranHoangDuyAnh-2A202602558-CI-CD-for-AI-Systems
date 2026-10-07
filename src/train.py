import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
import json
import joblib
import os
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score

# Nguong chat luong cua lab nay la f1_score, KHONG phai accuracy.
# Ly do: bo du lieu Adult co ty le lop 75/25. Mot mo hinh doan bua
# "thu nhap thap" cho moi mau da dat accuracy 0.75 ma khong hoc duoc gi.
F1_THRESHOLD = 0.65


def train(
    params: dict,
    data_path: str = "data/train_batch1.csv",
    eval_path: str = "data/holdout.csv",
) -> float:
    """
    Huan luyen mo hinh va ghi nhan ket qua vao MLflow.

    Tham so:
        params     : dict chua cac sieu tham so cho GradientBoostingClassifier.
        data_path  : duong dan den file du lieu huan luyen.
        eval_path  : duong dan den file du lieu danh gia (holdout).

    Tra ve:
        f1 (float): diem F1 cua lop duong (thu nhap > 50K) tren tap holdout.
    """

    df_train = pd.read_csv(data_path)
    df_eval = pd.read_csv(eval_path)
    if "target" not in df_train.columns or "target" not in df_eval.columns:
        raise ValueError("Both training and evaluation data must contain a 'target' column.")

    X_train = df_train.drop(columns=["target"])
    y_train = df_train["target"]
    X_eval = df_eval.drop(columns=["target"])
    y_eval = df_eval["target"]

    with mlflow.start_run():
        mlflow.log_params(params)

        model = GradientBoostingClassifier(**params, random_state=42)
        model.fit(X_train, y_train)

        predictions = model.predict(X_eval)
        f1 = float(f1_score(y_eval, predictions))
        accuracy = float(accuracy_score(y_eval, predictions))

        mlflow.log_metric("f1_score", f1)
        mlflow.log_metric("accuracy", accuracy)
        mlflow.sklearn.log_model(model, "model")

        print(f"F1: {f1:.4f} | Accuracy: {accuracy:.4f}")

        os.makedirs("outputs", exist_ok=True)
        with open("outputs/report.json", "w", encoding="utf-8") as report_file:
            json.dump({"f1_score": f1, "accuracy": accuracy}, report_file)

        os.makedirs("models", exist_ok=True)
        joblib.dump(model, "models/model.joblib")

    return f1


if __name__ == "__main__":
    with open("params.yaml") as f:
        params = yaml.safe_load(f)
    train(params)
