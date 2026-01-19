import numpy as np
from sklearn.metrics import r2_score, mean_squared_error


def mape(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    eps = 1e-9
    return np.mean(np.abs((y_true - y_pred) / (y_true + eps))) * 100


def evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)

    return {
        "R2": r2_score(y_test, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_test, y_pred)),
        "MAPE (%)": mape(y_test, y_pred),
    }
