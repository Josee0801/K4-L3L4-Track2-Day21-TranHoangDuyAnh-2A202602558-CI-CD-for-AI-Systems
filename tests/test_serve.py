from pathlib import Path

import pytest
from fastapi import HTTPException, Request

from src import serve


class StubModel:
    def predict(self, features):
        assert list(features.columns) == serve.FEATURE_NAMES
        return [1]


class StubS3Client:
    def __init__(self):
        self.downloaded_to = None
        self.bucket = None
        self.key = None

    def download_file(self, bucket, key, filename):
        self.bucket = bucket
        self.key = key
        self.downloaded_to = filename
        Path(filename).write_bytes(b"model")


def _request():
    return Request({"type": "http", "headers": [], "app": serve.app})


def test_download_model_fetches_configured_artifact(tmp_path, monkeypatch):
    model_path = tmp_path / "models" / "model.joblib"
    client = StubS3Client()
    loaded_model = StubModel()
    monkeypatch.setattr(serve, "ARTIFACT_BUCKET", "income-bucket")
    monkeypatch.setattr(serve, "MODEL_PATH", str(model_path))
    monkeypatch.setattr(serve.boto3, "client", lambda _: client)
    monkeypatch.setattr(serve.joblib, "load", lambda _: loaded_model)

    assert serve.download_model() is loaded_model
    assert client.bucket == "income-bucket"
    assert client.key == "artifacts/current/model.joblib"
    assert client.downloaded_to == str(model_path)


def test_healthz_returns_ok():
    assert serve.healthz() == {"status": "ok"}


def test_score_returns_prediction_and_label(monkeypatch):
    monkeypatch.setattr(serve.app.state, "model", StubModel(), raising=False)

    response = serve.score(
        serve.ScoreRequest(features=[28, 2, 14, 2, 11, 0, 1, 0, 0, 45]),
        _request(),
    )

    assert response == {"prediction": 1, "label": "thu_nhap_cao"}


def test_score_rejects_wrong_number_of_features():
    with pytest.raises(HTTPException) as exc_info:
        serve.score(serve.ScoreRequest(features=[28, 2]), _request())

    assert exc_info.value.status_code == 400
