from data_loader import load_all_data
from features import create_features
from train import train_models
from evaluate import evaluate_model
from sklearn.model_selection import train_test_split
import joblib
import os

DATA_DIR = "../data"
TARGET = "consommation"

df = load_all_data(DATA_DIR)

df = create_features(df)

X = df.drop(columns=[TARGET])
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)


models = train_models(X_train, y_train)

best_name, best_model, best_r2 = None, None, -999
for name, model in models.items():
    metrics = evaluate_model(model, X_test, y_test)
    print(f"Modèle : {name}")
    for k, v in metrics.items():
        print(f"{k} : {v:.4f}")

    if metrics["R2"] > best_r2:
        best_r2 = metrics["R2"]
        best_name, best_model = name, model

os.makedirs("../models", exist_ok=True)
joblib.dump(best_model, "../models/model.joblib")

print(f"Modèle retenu : {best_name} (R2={best_r2:.4f})")
