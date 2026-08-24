"""数据集外菜名的粗估模型：只用「菜名 + 中/西」预测星级。

原理：TF-IDF(菜名字符 n-gram) + OneHot(source) -> 随机森林。
与主流程同一划分参数（stratify, random_state=42），在真实测试集上评估并如实保存。
用途：demo.py 对查不到的菜给出「模型粗估星（非数据实测）」。
"""
import json
import os

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

PROC = os.path.join("data", "processed")


def severe_misjudge_rate(y_true, y_pred):
    n = len(y_true)
    if n == 0:
        return 0.0
    bad = sum(1 for t, p in zip(y_true, y_pred) if (t <= 2 and p >= 4) or (t >= 4 and p <= 2))
    return bad / n


def main():
    df = pd.read_csv(os.path.join(PROC, "merged.csv"))
    y = df["nutri_star"]
    # 与 data_process.py 相同的划分参数 -> 同一份训练/测试（同条件）
    X = df[["food_name", "source"]]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print("train:", len(X_train), "test:", len(X_test))

    pre = ColumnTransformer([
        ("text", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), max_features=2000), "food_name"),
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["source"]),
    ])
    model = Pipeline([("pre", pre), ("clf", RandomForestClassifier(n_estimators=200, random_state=42))])
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    acc = accuracy_score(y_test, pred)
    sev = severe_misjudge_rate(y_test, pred)
    print(f"粗估模型(只用菜名+中/西)  准确率: {acc:.3f}  严重误判率: {sev:.3f}")
    try:
        cand = json.load(open("metrics_candidate.json", encoding="utf-8"))
        base = json.load(open("metrics_baseline.json", encoding="utf-8"))
        print(f"对比：完整候选(含数值特征) {cand['accuracy']:.3f} / 基线(多数类) {base['accuracy']:.3f}")
    except Exception:
        print("对比：请先运行 baseline.py 与 train_model.py")

    joblib.dump(model, "rough_model.pkl")
    with open("metrics_rough.json", "w", encoding="utf-8") as f:
        json.dump({"candidate": "rough name+source model", "accuracy": acc,
                   "severe_misjudge_rate": sev}, f, ensure_ascii=False, indent=2)
    print("已保存 rough_model.pkl 和 metrics_rough.json")


if __name__ == "__main__":
    main()
