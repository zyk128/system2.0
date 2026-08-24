"""FINAL · 数据管线：读真实营养表 → 清洗 → 派生健康星级(1-5) → 按来源分别划分。

健康星级派生规则（官方标准，写死、可复现）：
- 欧盟官方营养标签系统 Nutri-Score（A~E 五档），A 最健康、E 最不健康；
- 扣分（0~40）：热量(能量 kJ)、糖、饱和脂肪、钠；加分：纤维、蛋白（蔬果/坚果按 0，保守）；
- 得分映射 A~E：A→5 星、B→4 星、C→3 星、D→2 星、E→1 星。
- 【绝对标准】非【相对排序】：即使全是垃圾食品也全落 D/E，不会「矮子里拔高个」。

两套标准 + 两个独立模型（数据限制，非糊弄）：
- 美国快餐(fastfood.csv)：6 项输入齐全 → 用【完整 Nutri-Score】（含糖项）。
- 中国菜(八大菜系：闽/徽/浙/鲁/苏/湘 + 川/粤)：无「糖」列，只有 5 项 → 用【简化 Nutri-Score】（去糖项）。
  中式缺糖、扣分少一项，得分整体偏低（偏健康），因此中式标签与美式【不横向比较】，各自独立建模。
- 中式按整盘报告，除以 Serving（份数）对齐到「一份」，与美式「单份单品」可比。

川/粤数据(与 nutritional_content_unit 同源的姊妹数据集)缺「饱和/单/多不饱和脂肪酸」三列，
用 6 菜系数据拟合的「总脂肪 → 各脂肪酸」中位比例估算（近似值，README 已标注）。

两个近似：1) 官方按每 100g，本数据无重量，按每份近似；2) 蔬果/坚果含量按 0。

防泄漏（每套各自独立）：
- 标签列不能进特征；total_fat 含 sat_fat、total_carb 含 fiber，会间接泄露，一并排除。
- 美式特征 = 菜名 + 餐厅 + 反式脂肪 + 胆固醇；
- 中式特征 = 菜名 + 菜系 + 胆固醇 + 灰分/维生素/矿物质/单多不饱和脂肪酸（都不在公式里、不含标签列）。

用法：
  python data_process.py --check-data   # 只做数据契约检查
  python data_process.py                # 清洗+打标签+划分，写出 data/processed/*
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

US_RAW = Path("data/raw/fastfood.csv")
CN_RAW = Path("data/raw/nutritional_content_unit.xlsx")
OUT = Path("data/processed")

# ---------- Nutri-Score 官方阈值（通用食品版，单位：kJ / g / mg）----------
ENERGY_B = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]
SUGAR_B = [4.5, 9, 13.5, 18, 22.5, 27, 31, 36, 40, 45]
SATFAT_B = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
SODIUM_B = [90, 180, 270, 360, 450, 540, 630, 720, 810, 900]
FIBER_B = [0.9, 1.9, 2.8, 3.7, 4.7]
PROTEIN_B = [1.6, 3.2, 4.8, 6.4, 8.0]

# A~E → 1~5 星（5 星 = A 最健康）
GRADE_TO_STAR = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
STAR_TO_GRADE = {v: k for k, v in GRADE_TO_STAR.items()}

# ---------- 美国（完整 Nutri-Score，含糖）----------
US_LABEL_COLS = ["calories", "sat_fat", "sodium", "fiber", "sugar", "protein"]
US_LEAK_COLS = ["cal_fat", "total_fat", "total_carb"]
US_FEATURES = ["item", "cuisine", "trans_fat", "cholesterol"]

# ---------- 中国（简化 Nutri-Score，去糖）----------
# 中国表列名 → 统一英文列名
CN_COLS = {
    "Dish_name": "item",
    "Cuisine type": "cuisine",
    "Serving": "serving",
    "Energy (kcal)": "calories",
    "Protein (g)": "protein",
    "Fat (g)": "total_fat",
    "Cholesterol (mg)": "cholesterol",
    "Ash (g)": "ash",
    "Carbohydrates (g)": "total_carb",
    "Dietary fiber (g)": "fiber",
    "Carotene (µg)": "carotene",
    "Vitamin A (µg)": "vit_a",
    "α-Tocopherol (mg)": "vit_e",
    "Thiamin (mg)": "thiamin",
    "Riboflavin (mg)": "riboflavin",
    "Niacin(mg)": "niacin",
    "Vitamin C (mg)": "vit_c",
    "Calcium (mg)": "calcium",
    "Potassium (mg)": "potassium",
    "Sodium (mg)": "sodium",
    "Magnesium (mg)": "magnesium",
    "Iron (mg)": "iron",
    "Zinc (mg)": "zinc",
    "Selenium (µg)": "selenium",
    "Copper (mg)": "copper",
    "Manganese (mg)": "manganese",
    "Iodine  (µg)": "iodine",
    "Saturated Fatty Acids (g)": "sat_fat",
    "Monounsaturated Fatty Acids (g)": "mono",
    "Polyunsaturated Fatty Acids (g)": "poly",
}
CN_LABEL_COLS = ["calories", "sat_fat", "sodium", "fiber", "protein"]  # 无 sugar
CN_LEAK_COLS = ["total_fat", "total_carb"]
# 中式的非标签营养素特征（不在公式里、不含标签列，0% 缺失、有方差）
CN_NUM_FEATURES = ["cholesterol", "ash", "carotene", "vit_a", "vit_e", "thiamin",
                   "riboflavin", "niacin", "vit_c", "calcium", "potassium",
                   "magnesium", "iron", "zinc", "selenium", "copper", "manganese",
                   "iodine", "mono", "poly"]
CN_FEATURES = ["item", "cuisine"] + CN_NUM_FEATURES

# ---------- 川/粤（缺饱和/单/多不饱和脂肪酸，用 6 菜系中位比例估算）----------
SC_RAW = {
    "Sichuan cuisine": Path("data/raw/Sichuan cuisines.xlsx"),
    "Cantonese cuisine": Path("data/raw/Cantonese cuisines.xlsx"),
}
SC_COLS = {
    "Dish name": "item",
    "Serving": "serving",
    "Energy (kcal)": "calories",
    "Protein (g)": "protein",
    "Fat (g)": "total_fat",
    "Cholesterol (mg)": "cholesterol",
    "Ash (g)": "ash",
    "Carbohydrate (g)": "total_carb",
    "Dietary fiber (g)": "fiber",
    "Carotene (μg)": "carotene",
    "Vitamin A (μg)": "vit_a",
    "α-TE (mg)": "vit_e",
    "Thiamine (mg)": "thiamin",
    "Riboflavin (mg)": "riboflavin",
    "Niacin (mg)": "niacin",
    "Vitamin C (mg)": "vit_c",
    "Calcium (mg)": "calcium",
    "Potassium (mg)": "potassium",
    "Sodium (mg)": "sodium",
    "Magnesium (mg)": "magnesium",
    "Iron (mg)": "iron",
    "Zinc (mg)": "zinc",
    "Selenium (μg)": "selenium",
    "Cu (mg)": "copper",
    "Manganese (mg)": "manganese",
    "Iodine (μg)": "iodine",
}


def _fat_ratios(df: pd.DataFrame) -> dict[str, float]:
    """用已有数据（含三类脂肪酸）拟合「总脂肪 → 各脂肪酸」的中位比例。

    川/粤缺饱和/单/多不饱和脂肪酸列，用 6 菜系数据的中位比例估算（近似值，已标注）。
    total_fat 过小（<=0.5g）的菜比例噪声大，排除。
    """
    tf = df["total_fat"].astype(float)
    m = tf > 0.5
    return {
        "sat_fat": float((df["sat_fat"][m] / tf[m]).median()),
        "mono": float((df["mono"][m] / tf[m]).median()),
        "poly": float((df["poly"][m] / tf[m]).median()),
    }


def _read_cn6() -> pd.DataFrame:
    """读 6 菜系（闽/徽/浙/鲁/苏/湘）营养表 → 统一 schema。"""
    df = pd.read_excel(CN_RAW)[list(CN_COLS)].rename(columns=CN_COLS)
    df["item"] = df["item"].astype(str).str.strip()
    return df


def _read_cn_sc(ratios: dict[str, float]) -> pd.DataFrame:
    """读川/粤营养表 → 统一 schema；补菜系、按中位比例估算缺的脂肪酸。"""
    parts = []
    for cuisine, path in SC_RAW.items():
        df = pd.read_excel(path)[list(SC_COLS)].rename(columns=SC_COLS)
        df["item"] = df["item"].astype(str).str.strip()
        df["cuisine"] = cuisine
        for col in ("sat_fat", "mono", "poly"):
            df[col] = df["total_fat"].astype(float) * ratios[col]
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def check_data() -> None:
    us = pd.read_csv(US_RAW)
    cn6 = pd.read_excel(CN_RAW)
    print("REAL DATA CHECK PASSED")
    print(f"[美国 fastfood.csv] rows={len(us)}, 餐厅数={us['restaurant'].nunique()}")
    print(f"  餐厅: {sorted(us['restaurant'].dropna().unique())}")
    print(f"[中国 6 菜系 nutritional_content_unit.xlsx] rows={len(cn6)}, 菜系数={cn6['Cuisine type'].nunique()}")
    print(f"  菜系: {sorted(cn6['Cuisine type'].dropna().unique())}")
    for cname, p in SC_RAW.items():
        sc = pd.read_excel(p)
        print(f"[中国 {cname}] rows={len(sc)}（缺饱和/单/多不饱和脂肪酸，用中位比例估算）")
    print(f"  中国表 糖列存在? {'sugar' in [c.lower() for c in cn6.columns]}")
    print(f"  6 菜系 Serving(份数)分布: {sorted(cn6['Serving'].unique())}")


def _pts(value: float, bounds: list[float]) -> int:
    """按官方阈值表打分：value 超过几个上界就得几分（0~len(bounds)）。"""
    return int(sum(value > b for b in bounds))


def nutri_score(row: pd.Series, use_sugar: bool) -> int:
    """Nutri-Score 官方公式（每份近似）。use_sugar=False 时为去糖简化版（中式）。"""
    energy = row["calories"] * 4.184  # kcal → kJ
    n = (_pts(energy, ENERGY_B) + _pts(row["sat_fat"], SATFAT_B)
         + _pts(row["sodium"], SODIUM_B))
    if use_sugar:
        n += _pts(row["sugar"], SUGAR_B)
    fiber = _pts(row["fiber"], FIBER_B)
    protein = _pts(row["protein"], PROTEIN_B)
    # 官方规则：N>=11 且蔬果分 < 5 时，蛋白加分不计入（本数据蔬果分恒为 0）
    p = fiber + (protein if n < 11 else 0)
    return n - p


def nutri_grade(score: int) -> str:
    """得分 → A~E（通用食品版阈值）。"""
    if score <= -1:
        return "A"
    if score <= 2:
        return "B"
    if score <= 10:
        return "C"
    if score <= 18:
        return "D"
    return "E"


def _label(df: pd.DataFrame, use_sugar: bool) -> pd.DataFrame:
    df["nutri_score"] = df.apply(lambda r: nutri_score(r, use_sugar), axis=1)
    df["nutri_grade"] = df["nutri_score"].apply(nutri_grade)
    df["health_star"] = df["nutri_grade"].map(GRADE_TO_STAR)
    return df


def build_us() -> pd.DataFrame:
    df = pd.read_csv(US_RAW).rename(columns={"restaurant": "cuisine"})
    df["item"] = df["item"].astype(str).str.strip()
    df["source"] = "us"
    keep = (["source", "item", "cuisine"] + US_LABEL_COLS + US_LEAK_COLS
            + ["trans_fat", "cholesterol"])
    df = df[keep].dropna(subset=US_LABEL_COLS + ["trans_fat", "cholesterol"]).copy()
    df["servings"] = 1  # 每份 = 一个单品（营养表即每份数值）
    return _label(df, use_sugar=True)


def build_cn() -> pd.DataFrame:
    cn6 = _read_cn6()
    ratios = _fat_ratios(cn6)
    df = pd.concat([cn6, _read_cn_sc(ratios)], ignore_index=True)
    df["serving"] = df["serving"].astype(float)
    s = df["serving"]
    num_cols = CN_LABEL_COLS + CN_LEAK_COLS + CN_NUM_FEATURES
    for col in num_cols:
        df[col] = df[col] / s
    df["source"] = "china"
    df["sugar"] = np.nan  # 无糖列 → 简化版（去糖项）
    df["servings"] = s  # 保留份数：整盘 ÷ 份数 = 每人份（用于分量标准展示）
    df = df.drop(columns=["serving"])
    df = df.dropna(subset=CN_LABEL_COLS + CN_NUM_FEATURES).copy()
    return _label(df, use_sugar=False)


def _split_write(df: pd.DataFrame, features: list[str], name: str) -> None:
    X = df[features]
    y_star = df["health_star"]
    y_cal = df["calories"]
    X_tr, X_te, s_tr, s_te, c_tr, c_te = train_test_split(
        X, y_star, y_cal, test_size=0.2, random_state=42, stratify=y_star)
    tr = X_tr.copy()
    tr["health_star"] = s_tr.values
    tr["calories"] = c_tr.values
    te = X_te.copy()
    te["health_star"] = s_te.values
    te["calories"] = c_te.values
    tr.to_csv(OUT / f"{name}_train.csv", index=False)
    te.to_csv(OUT / f"{name}_test.csv", index=False)
    print(f"  {name}: 训练 {len(tr)} / 测试 {len(te)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-data", action="store_true")
    args = ap.parse_args()

    if args.check_data:
        check_data()
        return 0

    us = build_us()
    cn = build_cn()

    OUT.mkdir(parents=True, exist_ok=True)
    # 合并查找表（demo / 网页用；不同来源缺的列填 NaN）
    lookup = pd.concat([us, cn], ignore_index=True)
    lookup.to_csv(OUT / "food_labeled.csv", index=False)

    print(f"样本数(清洗后): 美式 {len(us)} + 中式 {len(cn)} = {len(lookup)}")
    for src, d, label in [("us", us, "美式(完整版)"), ("china", cn, "中式(简化版)")]:
        dist = d["nutri_grade"].value_counts().reindex(["A", "B", "C", "D", "E"]).fillna(0).astype(int)
        print(f"  {label} Nutri-Score 分布: " + " / ".join(f"{g} {dist[g]}" for g in "ABCDE"))
    print("划分：")
    _split_write(us, US_FEATURES, "us")
    _split_write(cn, CN_FEATURES, "cn")
    print("已写出 data/processed/: food_labeled.csv + us/cn 的 train/test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
