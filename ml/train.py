import os
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import joblib
import tensorflow as tf

np.random.seed(42)
tf.random.set_seed(42)

DATA_PATH = "ml/dataset.csv"
ART_DIR = "ml/artifacts"
MODEL_PATH = os.path.join(ART_DIR, "lstm_model.keras")
SCALER_PATH = os.path.join(ART_DIR, "scaler.pkl")
META_PATH = os.path.join(ART_DIR, "meta.json")

LOOKBACK = 20        
HORIZON = 1          
EPOCHS = 30
BATCH_SIZE = 32

def make_windows(series: np.ndarray, lookback: int, horizon: int):
    X, y = [], []
    n = len(series)
    for i in range(n - lookback - horizon + 1):
        X.append(series[i:i+lookback])
        y.append(series[i+lookback+horizon-1])
    X = np.array(X)
    y = np.array(y)
    X = X.reshape((X.shape[0], X.shape[1], 1))
    y = y.reshape((-1, 1))
    return X, y

def main():
    os.makedirs(ART_DIR, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    df = df.sort_values("timestamp").reset_index(drop=True)

    y_raw = df["throughput_mbps"].astype(float).values.reshape(-1, 1)

    split = int(0.9 * len(y_raw))
    train_raw = y_raw[:split]
    test_raw = y_raw[split:]

    scaler = MinMaxScaler()
    train_scaled = scaler.fit_transform(train_raw)
    test_scaled = scaler.transform(test_raw)

    context = train_scaled[-LOOKBACK+1:] if LOOKBACK > 1 else np.empty((0,1))
    test_for_windows = np.vstack([context, test_scaled])

    X_train, y_train = make_windows(train_scaled, LOOKBACK, HORIZON)
    X_test, y_test = make_windows(test_for_windows, LOOKBACK, HORIZON)

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(LOOKBACK, 1)),
        tf.keras.layers.LSTM(64),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(1)
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
        metrics=[tf.keras.metrics.MeanAbsoluteError(name="mae")]
    )

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=5, restore_best_weights=True
        )
    ]

    history = model.fit(
        X_train, y_train,
        validation_split=0.1,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1
    )

    test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)

    model.save(MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    meta = {
        "lookback": LOOKBACK,
        "horizon": HORIZON,
        "train_split_index": split,
        "columns": list(df.columns),
        "target": "throughput_mbps",
        "test_loss_mse_scaled": float(test_loss),
        "test_mae_scaled": float(test_mae),
        "threshold_mbps": 15.0
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("\n=== TRAINING DONE ===")
    print(f"Saved model to: {MODEL_PATH}")
    print(f"Saved scaler to: {SCALER_PATH}")
    print(f"Saved meta to:   {META_PATH}")
    print(f"Test MAE (scaled): {test_mae:.6f}")

if __name__ == "__main__":
    main()
