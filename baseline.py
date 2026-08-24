"""多数类基线：总是预测训练集里最常见的 health_star，在测试集上评估。

与候选模型使用同一份 train/test 划分（同条件比较）。
"""
import json
import os

import pandas as pd
from sklearn.metrics import accuracy_score

OUT = os.path.join("data", "processed")


def severe_misjudge_rate(y_true, y_pred):
    """严重误判率：真实<=2 被判>=4，或 真实>=4 被判<=2 的比例。"""
    n = len(y_true)
    if n == 0:
        return 0.0
    bad = sum(1 for t, p in zip(y_true, y_pred) if (t <= 2 and p >= 4) or (t >= 4 and p <= 2))
    return bad / n


def main():
    train = pd.read_csv(os.path.join(OUT, "train.csv"))
    test = pd.read_csv(os.path.join(OUT, "test.csv"))

    majority = int(train["nutri_star"].mode()[0])
    y_true = test["nutri_star"].tolist()
    y_pred = [majority] * len(y_true)

    acc = accuracy_score(y_true, y_pred)
    severe = severe_misjudge_rate(y_true, y_pred)
    print(f"基线(多数类={majority})  准确率: {acc:.3f}  严重误判率: {severe:.3f}")

    with open("metrics_baseline.json", "w", encoding="utf-8") as f:
        json.dump({"baseline": "majority class", "majority": majority,
                   "accuracy": acc, "severe_misjudge_rate": severe},
                  f, ensure_ascii=False, indent=2)
    print("已保存 metrics_baseline.json")


if __name__ == "__main__":
    main()
