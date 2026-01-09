import numpy as np
from sklearn.metrics import r2_score, mean_squared_error

def mape(y_true, y_pred):
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    eps = 1e-9
    return np.mean(np.abs((y_true - y_pred) / (y_true + eps))) * 100


def evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)

    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)

    return {
        "R2": r2_score(y_test, y_pred),
        "RMSE": rmse,
        "MAPE": mape(y_test, y_pred),
    }
