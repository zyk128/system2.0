"""数据合并、清洗、派生健康星级、防泄漏划分，并保存到 data/processed/。

数据来源：
1. 中餐八大菜系（figshare，CC BY 4.0）—— 中文菜名
2. 快餐（fastfood.csv）—— 英文菜名 + 人工中文译名
3. 川菜/粤菜数据集（figshare 28457018，CC BY 4.0）—— 英文菜名 + 人工中文译名
4. 单位版中餐（figshare 29977027，CC BY 4.0，教师已批准）—— 英文菜名 + 钠/饱和脂肪 + 环境足迹

星级：主星级 = 欧盟 Nutri-Score（官方公式，绝对标准）；相对星级保留为参考列。
Nutri-Score 由热量/糖/饱和脂肪/钠扣分、纤维/蛋白加分派生（美式快餐含糖项，
中式无糖列用去糖简化版；无饱和脂肪的来源用单位版数据拟合中位比例估算）。
防泄漏：特征只用菜名 + 来源 + 胆固醇（都不在 Nutri-Score 公式里），
排除 calories/sat_fat/sodium/fiber/protein/sugar（标签列）与 total_fat/total_carb（泄漏列）。

一条命令：
    python data_process.py
"""
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

import translations
import translations_unit as translate_unit
from translations_sc import SC_CN

RAW = os.path.join("data", "raw")
OUT = os.path.join("data", "processed")

NUM_COLS = ["calories", "fat", "protein", "carbohydrate", "fiber"]

# Nutri-Score 官方阈值（通用食品版，单位 kJ / g / mg）
ENERGY_B = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]
SUGAR_B = [4.5, 9, 13.5, 18, 22.5, 27, 31, 36, 40, 45]
SATFAT_B = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
SODIUM_B = [90, 180, 270, 360, 450, 540, 630, 720, 810, 900]
FIBER_B = [0.9, 1.9, 2.8, 3.7, 4.7]
PROTEIN_B = [1.6, 3.2, 4.8, 6.4, 8.0]
GRADE_TO_STAR = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}

BRAND_CN = {
    "Mcdonalds": "麦当劳", "Burger King": "汉堡王", "Subway": "赛百味",
    "Dairy Queen": "DQ", "Taco Bell": "塔可钟", "Chick Fil-A": "Chick-fil-A",
    "Sonic": "Sonic", "Arbys": "Arby's",
}

CUISINE_CN = {
    "Chuan Cuisine": "川菜", "Lu Cuisine": "鲁菜", "Yue Cuisine": "粤菜",
    "Su Cuisine": "苏菜", "Min Cuisine": "闽菜", "Zhe Cuisine": "浙菜",
    "Hui Cuisine": "徽菜", "Xiang Cuisine": "湘菜",
}

# 川粤数据集两个文件的菜系名
SC_CUISINE = {"Sichuan cuisines.xlsx": "川菜", "Cantonese cuisines.xlsx": "粤菜"}


def _load_sc():
    """读川菜/粤菜数据集（figshare 28457018），统一列名。

    - food_name 保留英文原名（真实数据原样）
    - food_name_cn 用人工中文译名（展示用，不影响营养数据）
    - source 按具体菜系：川菜文件 -> "川菜"，粤菜文件 -> "粤菜"
      （与八大菜系 "中餐" 区分来源，网页上每个菜都标对其菜系）
    """
    frames = []
    for fname, cuisine in SC_CUISINE.items():
        f = os.path.join(RAW, fname)
        if not os.path.exists(f):
            continue
        sc = pd.read_excel(f, sheet_name="Sheet1")
        sc = sc.rename(columns={
            "Energy (kcal)": "calories", "Fat (g)": "fat", "Protein (g)": "protein",
            "Carbohydrate (g)": "carbohydrate", "Dietary fiber (g)": "fiber",
        })
        keep = pd.DataFrame({
            "food_name": sc["Dish name"].astype(str).str.strip(),
            "ingredients": "",
            "calories": sc["calories"],
            "fat": sc["fat"],
            "protein": sc["protein"],
            "carbohydrate": sc["carbohydrate"],
            "fiber": sc["fiber"],
            "sodium_mg": pd.to_numeric(sc.get("Sodium (mg)"), errors="coerce"),
            "sat_fat_g": np.nan,
            "sugar_g": np.nan,
            "cholesterol": pd.to_numeric(sc.get("Cholesterol (mg)"), errors="coerce"),
            "servings": pd.to_numeric(sc.get("Serving"), errors="coerce"),
            "weight_g": np.nan,
            "source": cuisine,  # "川菜" / "粤菜"
            "category": cuisine,
            "food_name_cn": sc["Dish name"].astype(str).str.strip().map(SC_CN).fillna(""),
        })
        frames.append(keep)
    if not frames:
        return pd.DataFrame(columns=["food_name", "ingredients", "calories", "fat", "protein",
                                     "carbohydrate", "fiber", "sodium_mg", "sat_fat_g",
                                     "sugar_g", "cholesterol", "servings", "weight_g",
                                     "source", "category", "food_name_cn"])
    return pd.concat(frames, ignore_index=True)


# 单位版中餐（figshare 29977027）：菜系英文名 -> 中文
UNITS_CUISINE = {
    "Anhui cuisine": "徽菜", "Fujian cuisine": "闽菜", "Jiangsu cuisine": "苏菜",
    "Hunan cuisine": "湘菜", "Zhejiang cuisine": "浙菜", "Shandong cuisine": "鲁菜",
    "Sichuan cuisine": "川菜", "Cantonese cuisine": "粤菜",
}

# 新增可选字段：钠 / 饱和脂肪 / 糖 / 胆固醇 / 环境足迹（其他来源为 NaN）
UNITS_EXTRA_COLS = ["sodium_mg", "sat_fat_g", "sugar_g", "cholesterol",
                    "carbon_g", "water_l", "land_m2"]


def _load_units():
    """读 figshare 29977027 单位版营养 + 环境足迹数据（来源④，教师已批准）。

    - 英文菜名保留真实原样；food_name_cn = 中餐 320 道准确译名优先，其余机译
    - 营养表只覆盖 6 个菜系（徽/闽/苏/湘/浙/鲁），川/粤在 28457018 中
    - 两份表按 (Cuisine type, Dish_name) 内连接，再按菜名去重
    - source 标为 "中餐单位版"，与中文版中餐/川粤/快餐区分
    """
    nut_path = os.path.join(RAW, "Nutritional_content-unit.xlsx")
    env_path = os.path.join(RAW, "Environmental_footprint-unit.xlsx")
    if not (os.path.exists(nut_path) and os.path.exists(env_path)):
        return pd.DataFrame()
    nut = pd.read_excel(nut_path, sheet_name="Nutritional results")
    env = pd.read_excel(env_path, sheet_name="Environmental footprint")
    key = ["Cuisine type", "Dish_name"]
    m = nut.merge(env, on=key, how="inner")
    m = m.drop_duplicates(subset="Dish_name").reset_index(drop=True)
    # 中文名：中餐 320 道的准确英->中优先，其余用 translations_unit 机译
    cn_path = os.path.join(RAW, "Carbon footprint and nutrition estimation of Chinese cuisines.xlsx")
    en2cn: dict = {}
    if os.path.exists(cn_path):
        cn_df = pd.read_excel(cn_path, sheet_name="Recipe")
        en2cn = dict(zip(cn_df["Recipe English name"].astype(str).str.strip().str.lower(),
                         cn_df["Recipe Chinese name"].astype(str).str.strip()))
    dish_names = m["Dish_name"].astype(str).str.strip()
    cn_col = dish_names.map(lambda n: en2cn.get(n.lower()) or translate_unit.translate(n))
    out = pd.DataFrame({
        "food_name": m["Dish_name"].astype(str).str.strip(),
        "ingredients": "",
        "calories": pd.to_numeric(m.get("Energy (kcal)"), errors="coerce"),
        "fat": pd.to_numeric(m.get("Fat (g)"), errors="coerce"),
        "protein": pd.to_numeric(m.get("Protein (g)"), errors="coerce"),
        "carbohydrate": pd.to_numeric(m.get("Carbohydrates (g)"), errors="coerce"),
        "fiber": pd.to_numeric(m.get("Dietary fiber (g)"), errors="coerce"),
        "sodium_mg": pd.to_numeric(m.get("Sodium (mg)"), errors="coerce"),
        "sat_fat_g": pd.to_numeric(m.get("Saturated Fatty Acids (g)"), errors="coerce"),
        "sugar_g": np.nan,
        "cholesterol": pd.to_numeric(m.get("Cholesterol (mg)"), errors="coerce"),
        "carbon_g": pd.to_numeric(m.get("Carbon footprint (g)"), errors="coerce"),
        "water_l": pd.to_numeric(m.get("Water footprint (L)"), errors="coerce"),
        "land_m2": pd.to_numeric(m.get("Land footprint (m2)"), errors="coerce"),
        "servings": pd.to_numeric(m.get("Serving"), errors="coerce"),
        "weight_g": pd.to_numeric(m.get("Weight (g)"), errors="coerce"),
        "source": "中餐单位版",
        "category": m["Cuisine type"].map(UNITS_CUISINE).fillna(m["Cuisine type"]),
        "food_name_cn": cn_col,
    })
    return out


def load_and_merge():
    """读中餐（八大菜系）、快餐、川粤三份数据，统一列名后合并为一张表。

    去重规则：川粤数据的中文译名若与八大菜系现有中文菜名完全相同（如
    麻婆豆腐/宫保鸡丁/回锅肉等），跳过该行——同一道菜只保留一份真实数据。
    """
    cn = pd.read_excel(os.path.join(RAW, "Carbon footprint and nutrition estimation of Chinese cuisines.xlsx"),
                       sheet_name="Recipe")
    ff = pd.read_csv(os.path.join(RAW, "fastfood.csv"))

    cn_keep = pd.DataFrame({
        "food_name": cn["Recipe Chinese name"].astype(str).str.strip(),
        "ingredients": cn["Cooking methods"].fillna("").astype(str),
        "calories": cn["Energy (kacl)"],
        "fat": cn["Fat (g)"],
        "protein": cn["Protein (g)"],
        "carbohydrate": cn["Carbohydrates (g)"],
        "fiber": cn["Dietary Fiber (g)"],
        "sodium_mg": pd.to_numeric(cn.get("Sodium (mg)"), errors="coerce"),
        "sat_fat_g": np.nan,
        "sugar_g": np.nan,
        "cholesterol": pd.to_numeric(cn.get("Cholesterol (mg)"), errors="coerce"),
        "servings": 1,
        "weight_g": np.nan,
        "source": "中餐",
        "category": cn["Cuisine"].map(CUISINE_CN).fillna(cn["Cuisine"]),
    })

    ff_keep = ff[["restaurant", "item", "calories", "total_fat", "protein", "total_carb", "fiber",
                  "sodium", "sat_fat", "sugar", "cholesterol"]].copy()
    ff_keep = ff_keep.rename(columns={"item": "food_name", "total_fat": "fat", "total_carb": "carbohydrate",
                                      "sodium": "sodium_mg", "sat_fat": "sat_fat_g",
                                      "sugar": "sugar_g", "cholesterol": "cholesterol"})
    ff_keep["ingredients"] = ""
    ff_keep["source"] = "快餐"
    ff_keep["category"] = ff_keep["restaurant"].map(BRAND_CN).fillna(ff_keep["restaurant"])
    ff_keep["servings"] = 1
    ff_keep["weight_g"] = np.nan

    parts = [cn_keep, ff_keep]
    # 省事入口：用户用 add_dish.py 新增的菜存在 user_added.csv，若存在则一并合并
    ua_path = os.path.join(RAW, "user_added.csv")
    if os.path.exists(ua_path):
        ua = pd.read_csv(ua_path)
        ua = ua[["food_name", "ingredients", "calories", "fat", "protein",
                 "carbohydrate", "fiber", "source", "category"]].copy()
        ua["ingredients"] = ua["ingredients"].fillna("")
        for c in ["sodium_mg", "sat_fat_g", "sugar_g", "cholesterol", "weight_g"]:
            ua[c] = np.nan
        ua["servings"] = 1
        parts.append(ua)

    # 川粤数据集
    sc_keep = _load_sc()
    if not sc_keep.empty:
        # 去重：跳过中文译名与八大菜系现有中文菜名完全相同的行
        existing_cn = set(cn_keep["food_name"].astype(str).str.strip())
        mask = ~sc_keep["food_name_cn"].isin(existing_cn)
        dropped = int((~mask).sum())
        if dropped:
            print(f"川粤数据集跳过 {dropped} 道与八大菜系同名的菜（去重）")
        sc_keep = sc_keep[mask].reset_index(drop=True)
        parts.append(sc_keep)

    df = pd.concat(parts, ignore_index=True)
    # 单位版中餐（figshare 29977027，来源④，教师已批准）
    units = _load_units()
    if not units.empty:
        existing = set(df["food_name"].astype(str).str.lower())
        mask = ~units["food_name"].str.lower().isin(existing)
        dropped_units = int((~mask).sum())
        if dropped_units:
            print(f"单位版数据跳过 {dropped_units} 道与现有菜名相同的菜（去重）")
        df = pd.concat([df, units[mask].reset_index(drop=True)], ignore_index=True)
    # 展示层中文名：中餐已是中文；川菜/粤菜用人工对照译名；快餐用机译译名
    # （仅供参考，不影响营养数据）；单位版中餐无人工译名，留空只显示英文
    def _cn(r):
        if r["source"] == "中餐":
            return r["food_name"]
        if r["source"] in ("川菜", "粤菜"):
            return SC_CN.get(r["food_name"], r["food_name"])
        if r["source"] == "中餐单位版":
            return r["food_name_cn"]
        return translations.translate(r["food_name"])

    df["food_name_cn"] = df.apply(_cn, axis=1)
    return df


def clean(df):
    """数值化；丢掉核心字段缺失或数值不合理的整行。

    核心字段仍是 NUM_COLS；新增的可选字段（钠/饱和脂肪/糖/胆固醇/环境足迹）
    也数值化，但不作为丢弃条件（其他来源为 NaN）。
    """
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in UNITS_EXTRA_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ["servings", "weight_g"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=NUM_COLS)
    df = df[(df["calories"] > 0) & (df["fat"] >= 0) & (df["protein"] >= 0)]
    return df.reset_index(drop=True)


# ---------- Nutri-Score（欧盟官方公式，绝对标准；队友版口径，已并入）----------
def _pts(value: float, bounds: list) -> int:
    """按官方阈值表打分：value 超过几个上界就得几分（0~len(bounds)）。"""
    return int(sum(float(value) > b for b in bounds))


def _nutri_score_row(row: pd.Series) -> float:
    """Nutri-Score 得分：热量/饱和脂肪/钠（+糖，仅快餐）扣分，纤维/蛋白加分。

    中式无糖列 → 去糖简化版；官方规则 N>=11 时蛋白加分不计入。
    """
    energy = float(row["calories"]) * 4.184  # kcal -> kJ
    n = (_pts(energy, ENERGY_B) + _pts(row["sat_fat_g"], SATFAT_B)
         + _pts(row["sodium_mg"], SODIUM_B))
    if row["source"] == "快餐" and pd.notna(row.get("sugar_g")):
        n += _pts(row["sugar_g"], SUGAR_B)
    fiber = _pts(row["fiber"], FIBER_B)
    protein = _pts(row["protein"], PROTEIN_B)
    p = fiber + (protein if n < 11 else 0)
    return float(n - p)


def _nutri_grade(score: float) -> str:
    if score <= -1:
        return "A"
    if score <= 2:
        return "B"
    if score <= 10:
        return "C"
    if score <= 18:
        return "D"
    return "E"


def add_nutri_star(df):
    """给全表算 Nutri-Score 星级（主星级），保留相对星级 health_star 作参考。

    无饱和脂肪的来源（中餐 320 / 川粤）用有真实 sat_fat 的单位版数据拟合的
    中位比例估算（sat_fat ≈ fat × 比例），近似值已在 README 标注。
    """
    base = df[(df["sat_fat_g"].notna()) & (df["fat"] > 0.5)]
    ratio = float((base["sat_fat_g"] / base["fat"]).median()) if len(base) else 0.132
    df["sat_fat_g"] = df["sat_fat_g"].fillna(df["fat"] * ratio)
    df["nutri_score"] = df.apply(_nutri_score_row, axis=1)
    df["nutri_grade"] = df["nutri_score"].apply(_nutri_grade)
    df["nutri_star"] = df["nutri_grade"].map(GRADE_TO_STAR).astype(int)
    return df


def make_star(df):
    """健康星级：脂肪、热量各自升序分 5 档（数值越小越健康 -> 星越高），平均后取 1~5。

    同时保存两个子分数 fat_level / cal_level（5=最健康），供演示时解释「星级怎么来的」。
    """
    def _score(series):
        # rank 升序分 5 档：第 1 档数值最小（最健康），健康分=5；第 5 档健康分=1
        return pd.qcut(series.rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)

    df["fat_level"] = _score(df["fat"])
    df["cal_level"] = _score(df["calories"])
    df["health_star"] = ((df["fat_level"] + df["cal_level"]) / 2.0).round().astype(int)
    df["health_star"] = df["health_star"].clip(1, 5)
    return df


def split_and_save(df):
    """防泄漏划分：目标 nutri_star(Nutri-Score 主星级)，特征只用不在公式里的列。

    特征 = text(菜名+配料) + source + cholesterol；排除标签列（calories/sat_fat/
    sodium/fiber/protein/sugar）与泄漏列（total_fat/total_carb）。
    """
    os.makedirs(OUT, exist_ok=True)
    df.to_csv(os.path.join(OUT, "merged.csv"), index=False, encoding="utf-8")

    # text = 菜名 + 配料（快餐无配料，只有菜名）
    df["text"] = (df["food_name"] + " " + df["ingredients"].fillna("")).str.strip()
    df["cholesterol"] = df["cholesterol"].fillna(0)
    feature_cols = ["text", "source", "cholesterol"]
    X = df[feature_cols]
    y = df["nutri_star"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    pd.concat([X_train, y_train.rename("nutri_star")], axis=1).to_csv(
        os.path.join(OUT, "train.csv"), index=False, encoding="utf-8")
    pd.concat([X_test, y_test.rename("nutri_star")], axis=1).to_csv(
        os.path.join(OUT, "test.csv"), index=False, encoding="utf-8")
    return feature_cols


def main():
    df = load_and_merge()
    print("合并后行数:", len(df), " 中餐:", (df["source"] == "中餐").sum(), " 快餐:", (df["source"] == "快餐").sum())
    df = clean(df)
    print("清洗后行数:", len(df))
    df = make_star(df)          # 相对星级（参考列 health_star）
    df = add_nutri_star(df)     # 主星级 Nutri-Score（nutri_star + nutri_grade）
    print("Nutri-Score 分布:\n", df["nutri_grade"].value_counts().reindex(list("ABCDE")).fillna(0).astype(int).to_string())
    print("相对星级分布:\n", df["health_star"].value_counts().sort_index().to_string())
    feature_cols = split_and_save(df)
    print("特征列(防泄漏，不含 Nutri-Score 公式列):", feature_cols)
    print("已保存到 data/processed/merged.csv, train.csv, test.csv")


if __name__ == "__main__":
    main()
