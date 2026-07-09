import pandas as pd
from prophet import Prophet


class ProphetWrapper:
    """Scikit-learn compatible wrapper for Facebook Prophet.

    Makes Prophet usable in the train_models() pipeline alongside
    sklearn models: implements .fit(X, y) and .predict(X).

    Prophet is a pure time-series model — it treats y as a sequential
    series and ignores the feature matrix X.
    """

    def __init__(self):
        self.model: Prophet | None = None
        self._n_train: int = 0

    def fit(self, X, y):
        df = pd.DataFrame(
            {
                "ds": pd.date_range("2020-01-01", periods=len(y), freq="h"),
                "y": y,
            }
        )
        self.model = Prophet()
        self.model.fit(df)
        self._n_train = len(y)
        self.n_features_in_ = X.shape[1] if hasattr(X, "shape") else 0
        return self

    def predict(self, X):
        if self.model is None:
            raise RuntimeError("ProphetWrapper must be fitted before predict")
        future = self.model.make_future_dataframe(
            periods=len(X), freq="h"
        )
        forecast = self.model.predict(future)
        return forecast["yhat"].values[-len(X) :]
