import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import joblib
import pandas as pd
import boto3
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel


FEATURE_NAMES = [
    "age", "workclass", "education_num", "marital_status", "occupation",
    "relationship", "sex", "capital_gain", "capital_loss", "hours_per_week",
]
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET")
MODEL_KEY = "artifacts/current/model.joblib"
MODEL_PATH = os.path.expanduser("~/models/model.joblib")


def download_model():
    """Tải model hiện hành từ S3 về máy chủ bằng IAM role credentials."""
    if not ARTIFACT_BUCKET:
        raise RuntimeError("ARTIFACT_BUCKET must be set before starting the API.")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    client = boto3.client("s3")
    client.download_file(ARTIFACT_BUCKET, MODEL_KEY, MODEL_PATH)
    print("Model da duoc tai xuong tu Amazon S3.")
    return joblib.load(MODEL_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.model = download_model()
    yield


app = FastAPI(lifespan=lifespan)


class ScoreRequest(BaseModel):
    features: list[float]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/score")
def score(req: ScoreRequest, request: Request) -> dict[str, int | str]:
    """
    Endpoint suy luan chinh.

    Dau vao : JSON {"features": [f1, f2, ..., f10]}
    Dau ra  : JSON {"prediction": <0|1>, "label": <"thu_nhap_thap"|"thu_nhap_cao">}

    Thu tu 10 dac trung (khop voi thu tu trong FEATURE_NAMES cua test):
        age, workclass, education_num, marital_status, occupation,
        relationship, sex, capital_gain, capital_loss, hours_per_week
    """
    if len(req.features) != len(FEATURE_NAMES):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(FEATURE_NAMES)} features (adult income)",
        )

    model = request.app.state.model
    features = pd.DataFrame([req.features], columns=FEATURE_NAMES)
    prediction = int(model.predict(features)[0])
    label = "thu_nhap_cao" if prediction == 1 else "thu_nhap_thap"
    return {"prediction": prediction, "label": label}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
