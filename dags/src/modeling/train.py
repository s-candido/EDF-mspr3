from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import LinearRegression
import xgboost as xgb

from utils.timer import timer
from utils.prophet_wrapper import ProphetWrapper


@timer("Entraînement du modèle")
def train_models(X, y):
    models = {
        "LinearRegression": LinearRegression(),
        "RandomForest": RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1),
        "KNN": KNeighborsRegressor(n_neighbors=7),
        "XGBoost": xgb.XGBRegressor(random_state=42, verbosity=0),
        "Prophet": ProphetWrapper(),
    }

    trained = {}
    for name, model in models.items():
        model.fit(X, y)
        trained[name] = model
    return trained
