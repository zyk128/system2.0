"""FINAL · 最简单基线：永远预测训练集里出现最多的星级（多数类）。

什么都不学，只记住「最常见的是几星」就猜。中美两个来源分别算。
用来回答：候选方法是否在同一条件下比这个最笨的基线更有用？

用法：python baseline.py
"""
from __future__ import annotations

import pandas as pd
from sklearn.metrics import accuracy_score

for name, label in [("us", "美式(完整 Nutri-Score)"), ("cn", "中式(简化 Nutri-Score)")]:
    y_tr = pd.read_csv(f"data/processed/{name}_train.csv")["health_star"]
    y_te = pd.read_csv(f"data/processed/{name}_test.csv")["health_star"]
    majority = int(y_tr.value_counts().idxmax())
    pred = [majority] * len(y_te)
    acc = accuracy_score(y_te, pred)
    print(f"[{label}] 多数类基线：永远预测 {majority} 星")
    print(f"  测试集准确率: {acc:.4f}  ({int(acc * len(y_te))}/{len(y_te)})")
    print("  训练集星级分布:", y_tr.value_counts().sort_index().to_dict())
