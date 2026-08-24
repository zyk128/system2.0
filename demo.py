"""FINAL · 控制台演示：输入菜名 → 健康星级(Nutri-Score) + 热量。

流程：
1. 按菜名在真实菜里查找（先精确、再包含子串，忽略大小写）；
2. 命中：判断这道菜属于美式还是中式，路由到对应的独立模型 → 预测星级；
   同时展示「真实星级(Nutri-Score)」和「真实热量」做对照（现场能看出对错，含失败案例）；
3. 未命中：明确说明「不在覆盖范围」，不硬猜——这就是使用边界。

两套标准各自独立：美式用完整 Nutri-Score(含糖)，中式用去糖简化版，不横向比较。
用法：python demo.py
"""
from __future__ import annotations

import joblib
import pandas as pd

from data_process import STAR_TO_GRADE, US_FEATURES, CN_FEATURES
from dish_translate import build_zh_lookup, build_en_lookup, build_us_lookup, has_chinese

labeled = pd.read_csv("data/processed/food_labeled.csv")
MODELS = {
    "us": (joblib.load("models/us_star_model.pkl"), joblib.load("models/us_cal_model.pkl"),
           US_FEATURES),
    "china": (joblib.load("models/cn_star_model.pkl"), joblib.load("models/cn_cal_model.pkl"),
              CN_FEATURES),
}

STD = {"us": "美式(完整 Nutri-Score, 含糖)", "china": "中式(简化 Nutri-Score, 去糖)"}
EN_NAMES = set(labeled["item"].dropna().str.strip().str.lower())
CHINESE_NAMES = set(labeled.loc[labeled["source"] == "china", "item"].dropna().str.strip().str.lower())
ZH2EN = build_zh_lookup(EN_NAMES)
EN2ZH = build_en_lookup(CHINESE_NAMES)
EN2ZH.update(build_us_lookup())  # 合并美式菜中文对照（覆盖 100% 美式）


def remind(star: int) -> str:
    grade = STAR_TO_GRADE[star]
    if star <= 2:
        return f"[提醒] Nutri-Score {grade}：高热量/高饱和脂肪/高糖/高钠，建议尽量少吃"
    if star == 3:
        return f"[中等] Nutri-Score {grade}：偶尔吃可以，注意搭配"
    return f"[健康] Nutri-Score {grade}：相对清淡，日常可常吃（仍以营养表为准）"


def lookup(name: str) -> pd.DataFrame:
    zh = name.strip()
    if has_chinese(zh) and zh in ZH2EN:
        name = ZH2EN[zh]
    lower = name.lower()
    m = labeled[labeled["item"].str.strip().str.lower() == lower]
    if m.empty:
        m = labeled[labeled["item"].str.strip().str.lower().str.contains(lower, na=False)]
    return m


def main() -> int:
    print("=== 外卖健康评估（Nutri-Score 官方标准）===")
    print("覆盖美式快餐 + 中国菜（两套标准、两个独立模型）")
    print("输入菜名（如 big mac / Mapo Tofu / salad / Beer-Braised Duck），输入 q 退出")
    print("（注：中国菜数据集的菜名是英文，如 Mapo Tofu=麻婆豆腐、Fried Rice=炒饭）")
    while True:
        name = input("\n菜名> ").strip()
        if name.lower() in {"q", "quit", "退出"}:
            break
        if not name:
            continue
        m = lookup(name)
        if m.empty:
            note = "（中文菜名不在词典时，可换英文名试试，如 Mapo Tofu）" if has_chinese(name) else ""
            print(f"「{name}」不在收录的 4805 道菜里，无法仅凭菜名判断健康星级"
                  f"——星级由营养标签按 Nutri-Score 计算，菜名本身信号不足{note}")
            continue
        row = m.iloc[0]
        src = str(row["source"])
        star_model, cal_model, feats = MODELS[src]
        X = row[feats].to_frame().T
        pred_star = int(star_model.predict(X)[0])
        pred_cal = float(cal_model.predict(X)[0])
        true_star = int(row["health_star"])
        true_grade = str(row["nutri_grade"])
        true_cal = float(row["calories"])
        zh = EN2ZH.get(str(row["item"]).strip().lower(), "")
        title = f"{zh}（{row['item']}）" if zh else str(row["item"])
        print(f"菜品: {title}  ({row['cuisine']})")
        print(f"标准: {STD.get(src, src)}")
        servings = int(round(float(row.get("servings", 1))))
        portion = ("约 250 克/个" if src == "us"
                   else f"约 250 克/人份（整盘 ÷ {servings} 份"
                        + (f"；吃整盘 ≈ {250 * servings} 克" if servings > 1 else "") + "）")
        print(f"分量标准(克): {portion}（数据无真实克重，统一参照值）")
        print(f"占每日参考热量: 约 {pred_cal/2000*100:.0f}%（按 2000 大卡/日）")
        print(f"预测健康星级: {pred_star}/5 ({STAR_TO_GRADE[pred_star]})   "
              f"真实: {true_star}/5 ({true_grade})")
        print(f"估计热量: {pred_cal:.0f} 大卡   真实热量: {true_cal:.0f} 大卡")
        print(remind(pred_star))
        if len(m) > 1:
            print(f"(还有 {len(m) - 1} 个同名/相似菜品，取第一个)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
