"""FINAL · 候选模型：健康星级分类（主任务）+ 热量回归（辅助），中美两个独立模型。

美式(完整 Nutri-Score)与中式(去糖简化 Nutri-Score)标签尺度不同、不可横向比较，
因此各自独立建模：
- 美式：特征 = 菜名 + 餐厅 + 反式脂肪 + 胆固醇；
- 中式：特征 = 菜名 + 菜系 + 胆固醇 + 灰分/维生素/矿物质/单多不饱和脂肪酸。

主任务：分类 —— 从特征预测健康星级 1-5（Nutri-Score A~E）。
辅助：回归 —— 从同样特征估 calories。

标签由 Nutri-Score 官方公式派生（见 data_process.py），特征里不含公式输入列，
也不含会间接泄露它们的 total_fat / total_carb / cal_fat。

用法：python train_model.py
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split

from data_process import US_FEATURES, CN_FEATURES, CN_NUM_FEATURES

PROC = Path("data/processed")
MODELS = Path("models")

# 每个来源：特征里数值列（文本=item 走 TF-IDF，类别=cuisine 走 one-hot）
NUM = {"us": ["trans_fat", "cholesterol"], "cn": CN_NUM_FEATURES}


def severe_rate(y_true, y_pred) -> float:
    """把不健康(<=2星)判成健康(>=4星) 或 反之，所占比例。"""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    under = (y_true <= 2) & (y_pred >= 4)
    over = (y_true >= 4) & (y_pred <= 2)
    return float((under | over).mean())


def build_pipeline(num_cols: list[str]) -> Pipeline:
    pre = ColumnTransformer([
        ("txt", TfidfVectorizer(stop_words="english", sublinear_tf=True), "item"),
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["cuisine"]),
        ("num", "passthrough", num_cols),
    ])
    return pre


def train_source(name: str, num_cols: list[str]) -> None:
    tr = pd.read_csv(PROC / f"{name}_train.csv")
    te = pd.read_csv(PROC / f"{name}_test.csv")
    feats = US_FEATURES if name == "us" else CN_FEATURES
    y_tr, y_te = tr["health_star"], te["health_star"]
    c_tr, c_te = tr["calories"], te["calories"]
    X_tr, X_te = tr[feats], te[feats]

    pre = build_pipeline(num_cols)

    clf = Pipeline([("pre", pre),
                    ("clf", RandomForestClassifier(n_estimators=300, random_state=42))])
    clf.fit(X_tr, y_tr)
    pred = clf.predict(X_te)
    acc = accuracy_score(y_te, pred)
    sev = severe_rate(y_te, pred)
    majority = int(y_tr.value_counts().idxmax())
    base = accuracy_score(y_te, [majority] * len(y_te))

    reg = Pipeline([("pre", pre),
                    ("reg", RandomForestRegressor(n_estimators=300, random_state=42))])
    reg.fit(X_tr, c_tr)
    c_pred = reg.predict(X_te)
    mae = mean_absolute_error(c_te, c_pred)
    base_mae = mean_absolute_error(c_te, [c_tr.mean()] * len(c_te))

    MODELS.mkdir(exist_ok=True)
    joblib.dump(clf, MODELS / f"{name}_star_model.pkl", compress=("lzma", 9))
    joblib.dump(reg, MODELS / f"{name}_cal_model.pkl", compress=("lzma", 9))

    label = "美式(完整 Nutri-Score)" if name == "us" else "中式(简化 Nutri-Score)"
    print(f"=== {label} ===")
    print(f"  候选  测试准确率: {acc:.4f}  ({int(acc * len(y_te))}/{len(y_te)})")
    print(f"  基线(多数类={majority}星): {base:.4f}")
    print(f"  严重误判率(≤2↔≥4): {sev:.4f}")
    print(f"  热量 MAE: {mae:.1f} 大卡 (基线 {base_mae:.1f})")
    names = pre.get_feature_names_out()
    imps = clf.named_steps["clf"].feature_importances_
    order = np.argsort(imps)[::-1]
    top = [f"{names[i]}:{imps[i]:.3f}" for i in order[:8]]
    print(f"  最重要特征: " + "  ".join(top))
    print()


def main() -> int:
    train_source("us", NUM["us"])
    train_source("cn", NUM["cn"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
