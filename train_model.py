"""候选模型：TF-IDF(菜名字符n-gram) + OneHot(中/西) + 数值特征 -> 梯度提升分类。

与基线同条件（同一份 train/test）比较，输出指标与特征重要性。
在新数据（823 道）上梯度提升优于随机森林（0.527 vs 0.503），故选梯度提升。
"""
import json
import os

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

OUT = os.path.join("data", "processed")


def severe_misjudge_rate(y_true, y_pred):
    n = len(y_true)
    if n == 0:
        return 0.0
    bad = sum(1 for t, p in zip(y_true, y_pred) if (t <= 2 and p >= 4) or (t >= 4 and p <= 2))
    return bad / n


def main():
    train = pd.read_csv(os.path.join(OUT, "train.csv"))
    test = pd.read_csv(os.path.join(OUT, "test.csv"))

    X_train = train.drop(columns=["nutri_star"])
    y_train = train["nutri_star"]
    X_test = test.drop(columns=["nutri_star"])
    y_test = test["nutri_star"]

    # 防泄漏：特征只含菜名/来源/胆固醇（都不在 Nutri-Score 公式里）
    pre = ColumnTransformer([
        ("text", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), max_features=2000), "text"),
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["source"]),
        ("num", "passthrough", ["cholesterol"]),
    ])

    model = Pipeline([
        ("pre", pre),
        ("clf", GradientBoostingClassifier(n_estimators=200, random_state=42)),
    ])
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    acc = accuracy_score(y_test, y_pred)
    severe = severe_misjudge_rate(y_test, y_pred)
    print(f"候选(梯度提升)  准确率: {acc:.3f}  严重误判率: {severe:.3f}")

    try:
        base = json.load(open("metrics_baseline.json", encoding="utf-8"))
        print(f"基线(多数类)    准确率: {base['accuracy']:.3f}  严重误判率: {base['severe_misjudge_rate']:.3f}")
        print(f"对比：候选准确率 - 基线准确率 = {acc - base['accuracy']:+.3f}")
    except Exception:
        print("未找到基线结果，请先运行 python baseline.py")

    feats = model.named_steps["pre"].get_feature_names_out()
    imp = model.named_steps["clf"].feature_importances_
    top = sorted(zip(feats, imp), key=lambda x: -x[1])[:10]
    print("Top 10 特征重要性:")
    for name, v in top:
        print(f"  {name}: {v:.4f}")

    joblib.dump(model, "model.pkl")
    with open("metrics_candidate.json", "w", encoding="utf-8") as f:
        json.dump({"candidate": "GradientBoostingClassifier", "accuracy": acc,
                   "severe_misjudge_rate": severe}, f, ensure_ascii=False, indent=2)
    print("已保存 model.pkl 和 metrics_candidate.json")


if __name__ == "__main__":
    main()
