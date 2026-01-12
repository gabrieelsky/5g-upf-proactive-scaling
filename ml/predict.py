import json
import numpy as np
import joblib
import tensorflow as tf

ART_DIR = "artifacts"
MODEL_PATH = f"{ART_DIR}/lstm_model.keras"
SCALER_PATH = f"{ART_DIR}/scaler.pkl"
META_PATH = f"{ART_DIR}/meta.json"

_CACHED_COMPONENTS = None

def load_all():
    model = tf.keras.models.load_model(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return model, scaler, meta

def get_cached_components():
    global _CACHED_COMPONENTS
    if _CACHED_COMPONENTS is None:
        _CACHED_COMPONENTS = load_all()
    return _CACHED_COMPONENTS

def predict_next_throughput(last_values_mbps):
    model, scaler, meta = get_cached_components()
    lookback = int(meta["lookback"])

    arr = np.array(last_values_mbps, dtype=float).reshape(-1, 1)
    if arr.shape[0] != lookback:
        raise ValueError(f"Need exactly {lookback} values, got {arr.shape[0]}")

    arr_scaled = scaler.transform(arr)
    X = arr_scaled.reshape((1, lookback, 1))
    yhat_scaled = model.predict(X, verbose=0).reshape(-1, 1)
    yhat = scaler.inverse_transform(yhat_scaled)[0, 0]
    return float(yhat)

if __name__ == "__main__":
    model, scaler, meta = load_all()
    lookback = int(meta["lookback"])
    dummy = [10.0] * lookback
    print("Predicted Mbps:", predict_next_throughput(dummy))
