"""FINAL · 网页版前端：外卖健康评估交互界面（Flask）。

启动：python app.py
然后浏览器打开 http://127.0.0.1:5000

流程：
1. 输入菜名（自动补全）→ 后端查表定位这道菜属于美式还是中式；
2. 路由到对应的独立模型（美式完整 Nutri-Score / 中式去糖简化版）→ 预测星级 + 估计热量；
3. 同时展示真实星级/热量做对照，并给出健康提醒；
4. 不在覆盖范围的菜名明确拒绝：星级由营养标签按 Nutri-Score 公式计算，仅凭菜名无法可靠判断，不硬猜。
"""
from __future__ import annotations

import joblib
import pandas as pd
from flask import Flask, jsonify, render_template_string, request

from data_process import STAR_TO_GRADE, US_FEATURES, CN_FEATURES
from dish_translate import build_zh_lookup, build_en_lookup, build_us_lookup, has_chinese

app = Flask(__name__)

labeled = pd.read_csv("data/processed/food_labeled.csv")
MODELS = {
    "us": (joblib.load("models/us_star_model.pkl"), joblib.load("models/us_cal_model.pkl"),
           US_FEATURES),
    "china": (joblib.load("models/cn_star_model.pkl"), joblib.load("models/cn_cal_model.pkl"),
              CN_FEATURES),
}

# 中文别名查找表（只收录数据集中真实存在的菜）
EN_NAMES = set(labeled["item"].dropna().str.strip().str.lower())
CHINESE_NAMES = set(labeled.loc[labeled["source"] == "china", "item"].dropna().str.strip().str.lower())
ZH2EN = build_zh_lookup(EN_NAMES)
EN2ZH = build_en_lookup(CHINESE_NAMES)
EN2ZH.update(build_us_lookup())  # 合并美式菜中文对照（覆盖 100% 美式）


def resolve_name(name: str) -> str:
    """中文菜名（若有别名）→ 英文名；英文输入原样返回。"""
    zh = name.strip()
    if has_chinese(zh) and zh in ZH2EN:
        return ZH2EN[zh]
    return name

STD = {"us": "美式 · 完整 Nutri-Score（含糖）", "china": "中式 · 简化 Nutri-Score（去糖）"}
COLORS = {"A": "#2e9e6b", "B": "#d99a21", "C": "#d9822b", "D": "#d9534f", "E": "#c0392b"}
DAILY_KCAL = 2000  # 成人每日能量参考值（通用近似，非个体处方）
REF_GRAMS = 250    # 标准参考分量（克/份）：数据无克重，用统一标准让不同店可比较

# 活动量 → (中文说明, 活动系数)，把基础代谢(BMR)换算成每日总消耗(TDEE)
ACTIVITY = {
    "sedentary": ("久坐", 1.2), "light": ("轻度", 1.375), "moderate": ("中度", 1.55),
    "active": ("高强度", 1.725), "athlete": ("运动员", 1.9),
}

# 菜系/餐厅 → 中文名
CUISINE_ZH = {
    "Taco Bell": "塔可贝尔", "Subway": "赛百味", "Burger King": "汉堡王",
    "Mcdonalds": "麦当劳", "Arbys": "阿拜斯", "Sonic": "索尼克",
    "Dairy Queen": "冰雪皇后", "Chick Fil-A": "福来鸡",
    "Fujian cuisine": "闽菜", "Anhui cuisine": "徽菜", "Zhejiang cuisine": "浙菜",
    "Shandong cuisine": "鲁菜", "Jiangsu cuisine": "苏菜", "Hunan cuisine": "湘菜",
    "Sichuan cuisine": "川菜", "Cantonese cuisine": "粤菜",
}

# 菜系/餐厅 → 表情符号（主界面分类卡片用，纯视觉装饰）
CUISINE_EMOJI = {
    "Taco Bell": "🌮", "Subway": "🥪", "Burger King": "🍔", "Mcdonalds": "🍟",
    "Arbys": "🥩", "Sonic": "🌭", "Dairy Queen": "🍦", "Chick Fil-A": "🐔",
    "Fujian cuisine": "🥣", "Anhui cuisine": "🥘", "Zhejiang cuisine": "🐟",
    "Shandong cuisine": "🥟", "Jiangsu cuisine": "🦐", "Hunan cuisine": "🌶️",
    "Sichuan cuisine": "🍲", "Cantonese cuisine": "🍵",
}


def daily_energy(gender, age, height, weight, activity) -> int:
    """Mifflin-St Jeor 基础代谢 + 活动系数 = 每日总能量消耗(TDEE)。参数无效则回退 2000。"""
    try:
        age, height, weight = float(age), float(height), float(weight)
    except (TypeError, ValueError):
        return DAILY_KCAL
    if min(age, height, weight) <= 0 or gender not in ("male", "female"):
        return DAILY_KCAL
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender == "male" else -161)
    factor = ACTIVITY.get(activity, ACTIVITY["sedentary"])[1]
    return int(round(bmr * factor))


def portion_note(src: str, servings) -> str:
    """分量标准（克）：注明结果基于多少克。数据本身无克重，用统一标准参考分量 250 克近似。"""
    if src == "us":
        return f"约 {REF_GRAMS} 克/个（数据无真实克重，此为统一参照值）"
    s = int(round(float(servings)))
    note = f"约 {REF_GRAMS} 克/人份（整盘 ÷ {s} 份"
    if s > 1:
        note += f"；吃整盘 ≈ {REF_GRAMS * s} 克"
    note += "；数据无真实克重，此为统一参照值）"
    return note


def remind(star: int) -> str:
    grade = STAR_TO_GRADE[star]
    if star <= 2:
        return f"Nutri-Score {grade}：高热量/高饱和脂肪/高钠，建议尽量少吃"
    if star == 3:
        return f"Nutri-Score {grade}：偶尔吃可以，注意搭配"
    return f"Nutri-Score {grade}：相对清淡，日常可常吃（仍以营养表为准）"


def lookup(name: str) -> pd.DataFrame:
    name = resolve_name(name)
    lower = name.strip().lower()
    m = labeled[labeled["item"].str.strip().str.lower() == lower]
    if m.empty:
        m = labeled[labeled["item"].str.strip().str.lower().str.contains(lower, na=False)]
    return m


def _predict_one(row: pd.Series, tdee: int = DAILY_KCAL) -> dict:
    src = str(row["source"])
    star_model, cal_model, feats = MODELS[src]
    X = row[feats].to_frame().T
    pred_star = int(star_model.predict(X)[0])
    pred_cal = float(cal_model.predict(X)[0])
    true_star = int(row["health_star"])
    return {
        "item": str(row["item"]),
        "zh": EN2ZH.get(str(row["item"]).strip().lower(), ""),
        "cuisine": str(row["cuisine"]),
        "source": src,
        "standard": STD[src],
        "portion": portion_note(src, row.get("servings", 1)),
        "tdee": tdee,
        "personalized": tdee != DAILY_KCAL,
        "daily_pct": round(pred_cal / tdee * 100),
        "pred_star": pred_star,
        "pred_grade": STAR_TO_GRADE[pred_star],
        "pred_color": COLORS[STAR_TO_GRADE[pred_star]],
        "pred_cal": round(pred_cal),
        "true_star": true_star,
        "true_grade": str(row["nutri_grade"]),
        "true_color": COLORS[str(row["nutri_grade"])],
        "true_cal": round(float(row["calories"])),
        "remind": remind(pred_star),
    }


def healthier_alternatives(row: pd.Series) -> list[dict]:
    """同菜系/同餐厅里、比当前菜更健康（星级更高）的同类菜，取最健康 3 道。"""
    src = str(row["source"])
    cuisine = str(row["cuisine"])
    cur_star = int(row["health_star"])
    same = labeled[(labeled["source"] == src) & (labeled["cuisine"] == cuisine)]
    better = same[same["health_star"] > cur_star].copy()
    better = better.drop_duplicates(subset=["item"])
    better = better.sort_values(["health_star", "calories"], ascending=[False, True])
    out = []
    for _, r in better.head(3).iterrows():
        out.append({
            "item": str(r["item"]),
            "zh": EN2ZH.get(str(r["item"]).strip().lower(), ""),
            "grade": str(r["nutri_grade"]),
            "star": int(r["health_star"]),
            "color": COLORS[str(r["nutri_grade"])],
            "cal": round(float(r["calories"])),
        })
    return out


# 「未收录」时引导用户点击的示例菜（保证存在于数据集内）
SAMPLE_ITEMS = [
    "Mapo Tofu", "Kung Pao Chicken", "Yangzhou Fried Rice with Eggs",
    "Sweet and Sour Pork", "Big Mac", "Grilled Chicken Sandwich",
    "Beer-Braised Duck",
]


def _sample_suggestions() -> list[dict]:
    """从数据集里挑几个代表性菜，供「未收录」场景引导用户点击。"""
    out, seen = [], set()
    for name in SAMPLE_ITEMS:
        m = labeled[labeled["item"].str.strip().str.lower() == name.lower()]
        if m.empty:
            continue
        r = m.iloc[0]
        key = str(r["item"]).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        c = str(r["cuisine"])
        out.append({
            "item": str(r["item"]),
            "zh": EN2ZH.get(key, ""),
            "cuisine": CUISINE_ZH.get(c, c),
            "star": int(r["health_star"]),
            "grade": str(r["nutri_grade"]),
            "color": COLORS[str(r["nutri_grade"])],
        })
        if len(out) >= 6:
            break
    return out


def _predict_uncovered(name: str) -> dict:
    """未收录菜品：诚实拒绝——星级由营养标签按 Nutri-Score 计算，仅凭菜名无法可靠判断。"""
    en = resolve_name(name)
    zh_hint = "（中文菜名不在词典时，可换英文名试试，或从下方菜系分类里选）" if has_chinese(en) else ""
    return {
        "found": False,
        "predicted": False,
        "name": name,
        "message": (f"「{name}」不在已收录的 4805 道菜里，无法仅凭菜名判断健康星级"
                    f"——星级是由营养标签按 Nutri-Score 公式算出来的，菜名本身信号不足{zh_hint}。"),
        "samples": _sample_suggestions(),
    }


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/dishes")
def dishes():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    if has_chinese(q):
        # 中文：子串匹配所有中文别名（含 q 的菜全列出）
        ens = [en for en, zh in EN2ZH.items() if q in zh]
    else:
        ql = q.lower()
        m = labeled[labeled["item"].str.strip().str.lower().str.contains(ql, na=False)]
        ens = m["item"].str.strip().dropna().unique().tolist()
    out, seen = [], set()
    for en in ens:
        l = str(en).strip().lower()
        if l in seen:
            continue
        seen.add(l)
        row = labeled[labeled["item"].str.strip().str.lower() == l]
        if row.empty:
            continue
        r = row.iloc[0]
        out.append({
            "item": str(r["item"]),
            "zh": EN2ZH.get(l, ""),
            "cuisine": str(r["cuisine"]),
            "star": int(r["health_star"]),
            "grade": str(r["nutri_grade"]),
            "color": COLORS[str(r["nutri_grade"])],
        })
    # 排序：中文/英文名越短越靠前（精确匹配自然在前）
    out.sort(key=lambda d: len(d["zh"] or d["item"]))
    return jsonify(out[:100])


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"found": False, "message": "请输入菜名"})
    profile = data.get("profile") or {}
    tdee = daily_energy(profile.get("gender"), profile.get("age"),
                        profile.get("height"), profile.get("weight"), profile.get("activity"))
    m = lookup(name)
    if m.empty:
        return jsonify(_predict_uncovered(name))
    row = m.iloc[0]
    result = _predict_one(row, tdee)
    result["healthier"] = healthier_alternatives(row)
    if len(m) > 1:
        result["alternatives"] = m["item"].astype(str).tolist()[:6]
    return jsonify({"found": True, **result})


@app.route("/api/cuisines")
def cuisines():
    """所有菜系/餐厅分类：数量 + 最健康的一道菜（供主界面「菜系分类」展示）。"""
    out = []
    for c, grp in labeled.groupby("cuisine"):
        c = str(c)
        best = grp.sort_values(["health_star", "calories"], ascending=[False, True]).iloc[0]
        out.append({
            "cuisine": c,
            "zh": CUISINE_ZH.get(c, c),
            "emoji": CUISINE_EMOJI.get(c, "🍽"),
            "source": str(grp["source"].iloc[0]),
            "count": int(len(grp)),
            "best_item": str(best["item"]),
            "best_zh": EN2ZH.get(str(best["item"]).strip().lower(), ""),
            "best_star": int(best["health_star"]),
            "best_color": COLORS[str(best["nutri_grade"])],
        })
    # 中式菜系在前、美式餐厅在后，各自按菜品数排序
    out.sort(key=lambda d: (d["source"], -d["count"]))
    return jsonify(out)


@app.route("/api/cuisine_dishes")
def cuisine_dishes():
    """某个菜系/餐厅里最健康的菜（星级高→低），供点击浏览。"""
    c = request.args.get("c", "")
    if not c:
        return jsonify([])
    grp = labeled[labeled["cuisine"] == c].drop_duplicates(subset=["item"])
    grp = grp.sort_values(["health_star", "calories"], ascending=[False, True])
    out = []
    for _, r in grp.head(50).iterrows():
        out.append({
            "item": str(r["item"]),
            "zh": EN2ZH.get(str(r["item"]).strip().lower(), ""),
            "star": int(r["health_star"]),
            "grade": str(r["nutri_grade"]),
            "color": COLORS[str(r["nutri_grade"])],
            "cal": round(float(r["calories"])),
        })
    return jsonify(out)


HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>外卖健康评估系统</title>
<style>
  :root{
    --card:#ffffff; --ink:#15382c; --muted:#6b8579; --line:#e3efe9;
    --primary:#0e9f6e; --primary-2:#0c8a5f; --emerald:#12b585; --blue:#1e88c8;
    --shadow-lg:0 18px 50px rgba(15,60,45,.12); --shadow:0 10px 30px rgba(15,60,45,.09);
    --shadow-sm:0 2px 10px rgba(15,60,45,.06);
    --r-lg:22px; --r-md:16px; --r-sm:12px;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;
       color:var(--ink);min-height:100vh;line-height:1.6;
       background:
         radial-gradient(820px 360px at 12% -6%,rgba(30,136,200,.12),transparent 60%),
         radial-gradient(700px 380px at 90% -4%,rgba(18,181,133,.16),transparent 58%),
         radial-gradient(600px 320px at 50% 112%,rgba(14,159,110,.08),transparent 60%),
         linear-gradient(180deg,#d9f0e7 0%,#ecf8f3 300px,#f8fbfa 100%);}
  .wrap{max-width:840px;margin:0 auto;padding:44px 22px 110px}

  /* 头部 */
  header{text-align:center;margin-bottom:26px;animation:fadeUp .5s ease}
  .logo{width:78px;height:78px;margin:0 auto 16px;border-radius:26px;font-size:40px;line-height:78px;
       background:linear-gradient(135deg,#12b585,#f59e0b);box-shadow:0 12px 30px rgba(245,158,11,.30);
       position:relative;animation:logoBob 3s ease-in-out infinite}
  .logo::after{content:"";position:absolute;inset:0;border-radius:26px;
       background:linear-gradient(135deg,rgba(255,255,255,.35),transparent 45%);pointer-events:none}
  @keyframes logoBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
  header h1{font-size:35px;margin:0 0 10px;font-weight:800;letter-spacing:-.5px;
       background:linear-gradient(120deg,#0c8a5f,#12b585 45%,#1e88c8);
       -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
  .tagline{display:inline-flex;align-items:center;gap:8px;margin:0 auto 16px;padding:8px 18px;font-size:13px;
       font-weight:700;color:#0c8a5f;background:#e6f6ef;border:1px solid #c8ecdc;border-radius:99px}
  .tagline b{color:#0e9f6e;font-weight:800}
  header p{color:var(--muted);margin:0 auto 16px;font-size:15px;max-width:560px}
  .home-btn{margin-top:2px;padding:9px 22px;font-size:13px;font-weight:700;border:1px solid #cde7dc;
    border-radius:99px;background:rgba(255,255,255,.72);cursor:pointer;color:#0c8a5f;
    box-shadow:var(--shadow-sm);transition:all .18s;backdrop-filter:blur(4px)}
  .home-btn:hover{background:#fff;border-color:#9fddc2;transform:translateY(-1px);box-shadow:var(--shadow)}

  /* 搜索 */
  .search{display:flex;gap:10px;margin-bottom:14px;position:relative}
  .sbox{flex:1;display:flex;align-items:center;background:var(--card);border:1px solid var(--line);
       border-radius:var(--r-md);box-shadow:var(--shadow-sm);padding:0 16px;gap:10px;
       transition:border-color .18s,box-shadow .18s}
  .sbox:focus-within{border-color:var(--emerald);box-shadow:0 0 0 4px rgba(14,159,110,.15),var(--shadow-sm)}
  .sbox .ico{font-size:18px;color:#9db8ad;user-select:none}
  .sbox input{flex:1;padding:16px 0;font-size:16px;border:none;outline:none;background:transparent;color:var(--ink)}
  .sbox input::placeholder{color:#a3b8af}
  .sbox .xclr{border:none;background:#eef4f1;color:#6b8579;width:24px;height:24px;border-radius:50%;
       cursor:pointer;font-size:14px;line-height:1;display:none;align-items:center;justify-content:center;
       transition:background .15s}
  .sbox .xclr:hover{background:#dcebe4}
  .search button{padding:16px 32px;font-size:16px;border:none;border-radius:var(--r-md);cursor:pointer;
       background:linear-gradient(135deg,var(--emerald),var(--primary));color:#fff;font-weight:700;
       white-space:nowrap;box-shadow:0 10px 24px rgba(14,159,110,.35);letter-spacing:.5px;
       transition:transform .15s,box-shadow .15s,filter .15s}
  .search button:hover{transform:translateY(-2px);box-shadow:0 14px 30px rgba(14,159,110,.45);filter:brightness(1.04)}
  .search button:active{transform:translateY(0)}

  /* 卡片 */
  .card{background:var(--card);border-radius:var(--r-lg);padding:24px;box-shadow:var(--shadow);
       border:1px solid var(--line);animation:fadeUp .4s ease}
  @keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
  .card h2{font-size:22px;margin:0 0 2px;line-height:1.35}
  .meta{color:var(--muted);font-size:13px;margin-bottom:14px}
  .std{display:inline-block;background:#e6f6ef;color:#0c8a5f;border-radius:99px;padding:4px 14px;
       font-size:12px;font-weight:700;margin-bottom:14px}

  /* 星级/热量格子 */
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .cell{border:1px solid var(--line);border-radius:var(--r-sm);padding:15px;background:#fbfefd}
  .cell .lbl{font-size:12px;color:var(--muted);margin-bottom:6px;font-weight:600}
  .stars{font-size:27px;letter-spacing:2px;line-height:1.2}
  .cal{font-size:23px;font-weight:800}

  /* 每日热量进度条 */
  .dbar-wrap{margin-top:16px;padding:12px 14px;border-radius:var(--r-sm);background:#f3f9f6}
  .dbar-top{display:flex;justify-content:space-between;align-items:baseline;font-size:13px;color:var(--muted);margin-bottom:7px}
  .dbar-top b{color:var(--ink);font-size:15px}
  .dbar{height:9px;border-radius:99px;background:#dfeae5;overflow:hidden}
  .dbar-fill{height:100%;border-radius:99px;transition:width .6s cubic-bezier(.2,.8,.2,1)}

  /* 提醒条 */
  .remind{margin-top:16px;padding:13px 16px;border-radius:var(--r-sm);background:#f3f9f6;font-size:14px;
       border-left:4px solid var(--rc,#1e88c8);line-height:1.6}

  /* 更健康推荐 + 搜索结果 通用列表项 */
  .healthier{margin-top:16px}
  .healthier .hlbl{font-size:13px;font-weight:800;color:#0c8a5f;margin-bottom:8px}
  .hitem,.sitem{display:flex;align-items:center;gap:10px;padding:11px 14px;background:var(--card);
       border:1px solid var(--line);border-radius:var(--r-sm);margin-bottom:8px;cursor:pointer;
       transition:background .15s,transform .12s,box-shadow .15s}
  .hitem:hover,.sitem:hover{background:#f0faf5;transform:translateX(3px);box-shadow:var(--shadow-sm);border-color:#bfe8d5}
  .hitem .g,.sitem .g{color:#fff;border-radius:8px;padding:2px 10px;font-weight:700;font-size:13px;white-space:nowrap;
       box-shadow:0 2px 6px rgba(0,0,0,.12)}
  .hitem .n,.sitem .n{flex:1;font-size:14px}
  .hitem .c,.sitem .c{color:var(--muted);font-size:12px;white-space:nowrap}
  .suggest{margin:-4px 0 16px}
  .scount{font-size:13px;color:var(--muted);margin-bottom:8px;font-weight:700}

  /* 个人信息（可折叠） */
  .profile{margin-bottom:16px;padding:0;overflow:hidden}
  .profile summary{cursor:pointer;list-style:none;padding:15px 20px;font-size:14px;font-weight:700;
       color:#0c8a5f;display:flex;align-items:center;gap:6px;user-select:none}
  .profile summary::after{content:"▾";margin-left:auto;transition:transform .2s}
  .profile[open] summary::after{transform:rotate(180deg)}
  .profile summary::-webkit-details-marker{display:none}
  .prow{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;padding:0 20px 18px}
  .prow label{font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:5px;font-weight:600}
  .prow input,.prow select{padding:9px 12px;border:1px solid var(--line);border-radius:10px;
       font-size:14px;width:100%;background:#fff;outline:none}
  .prow input:focus,.prow select:focus{border-color:var(--emerald);box-shadow:0 0 0 3px rgba(14,159,110,.12)}

  /* 菜系分类 */
  .clbl{font-size:15px;font-weight:800;color:#0c8a5f;margin-bottom:14px}
  .cgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:12px;margin-bottom:16px}
  .cchip{position:relative;border:1px solid var(--line);border-radius:var(--r-md);padding:15px 14px;cursor:pointer;
       background:linear-gradient(180deg,#ffffff 0%,#f6fbf9 100%);overflow:hidden;
       transition:transform .16s,box-shadow .16s,border-color .16s}
  .cchip::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;
       background:linear-gradient(90deg,var(--emerald),var(--blue));opacity:0;transition:opacity .2s}
  .cchip:hover{transform:translateY(-4px);box-shadow:var(--shadow);border-color:#b5e2cd}
  .cchip:hover::before{opacity:1}
  .cemoji{font-size:26px;line-height:1;margin-bottom:8px;display:block}
  .czh{font-weight:800;font-size:15px;margin-bottom:2px}
  .ccount{font-size:12px;color:var(--muted);margin-bottom:7px}
  .cbest{font-size:12px;color:#0c8a5f;line-height:1.5}
  .cbest .gs{display:inline-block;color:#fff;border-radius:6px;padding:0 7px;font-weight:700;font-size:11px;margin-right:4px}

  /* 底部说明 + 图例 */
  .hint{color:var(--muted);font-size:13px;text-align:center;margin-top:26px;line-height:1.8}
  .legend{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:12px}
  .legend span{font-size:12px;padding:5px 14px;border-radius:99px;color:#fff;font-weight:700;
       box-shadow:0 2px 8px rgba(0,0,0,.14)}

  /* 提示类 */
  .err{background:#fff5f5;color:#c0392b;border:1px solid #f5d5d5;border-radius:var(--r-md);padding:16px 18px}
  .en{font-size:13px;color:var(--muted);font-weight:400}
  .portion{font-size:12.5px;color:#4a6357;background:#eef6f2;border-radius:10px;
       padding:10px 14px;margin:0 0 14px;line-height:1.8}
  .tag{font-weight:700}

  /* 未收录卡片 */
  .uncover{text-align:center;padding:30px 24px}
  .uncover-ico{font-size:44px;line-height:1;margin-bottom:8px}
  .uncover h2{font-size:21px;margin:0 0 10px}
  .uncover-msg{color:var(--muted);font-size:14px;margin:0 auto 18px;max-width:480px;line-height:1.8}
  .uncover .healthier{text-align:left}

  @media (max-width:560px){
    header h1{font-size:27px}
    .grid{grid-template-columns:1fr}
    .search{flex-direction:column}
    .search button{width:100%}
    .cgrid{grid-template-columns:repeat(auto-fill,minmax(136px,1fr))}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">🍜</div>
    <h1>外卖健康评估系统</h1>
    <span class="tagline">欧盟官方 <b>Nutri-Score</b> 标准 · 覆盖 <b>4805</b> 道菜 · 八大菜系</span>
    <p>输入菜名，用官方 Nutri-Score 判断健康星级并估计热量</p>
    <button class="home-btn" onclick="goHome()">🏠 回到主界面</button>
  </header>

  <div class="search">
    <div class="sbox">
      <span class="ico">🔍</span>
      <input id="q" placeholder="输入菜名或关键字（支持中文/英文），如 麻婆豆腐 / 鸡 / big mac …" autocomplete="off">
      <button class="xclr" id="qclear" onclick="clearInput()" title="清空">✕</button>
    </div>
    <button onclick="predict()">评估</button>
  </div>

  <details class="card profile">
    <summary>👤 个人信息（选填，用于算你个人的每日所需能量）</summary>
    <div class="prow">
      <label>性别<select id="pgender">
        <option value="">未填</option><option value="male">男</option><option value="female">女</option>
      </select></label>
      <label>年龄<input id="page" type="number" min="1" placeholder="岁"></label>
      <label>身高<input id="pheight" type="number" min="1" placeholder="cm"></label>
      <label>体重<input id="pweight" type="number" min="1" placeholder="kg"></label>
      <label>活动量<select id="pactivity">
        <option value="sedentary">久坐</option><option value="light">轻度</option>
        <option value="moderate">中度</option><option value="active">高强度</option>
        <option value="athlete">运动员</option>
      </select></label>
    </div>
  </details>

  <div id="suggest"></div>

  <div id="result"></div>

  <div class="card">
    <div class="clbl">🍽 菜系分类（点击浏览各菜系最健康的菜）</div>
    <div id="cuisineList" class="cgrid"></div>
    <div id="cuisineDishes"></div>
  </div>

  <div class="hint">
    星级 = Nutri-Score 官方五档（A 最健康 → E 最不健康），按官方公式绝对打分，不搞相对排序。<br>
    两套标准各自独立：<b>美式用完整版（含糖）</b>，<b>中式用去糖简化版</b>，不横向比较。<br>
    <div class="legend">
      <span style="background:linear-gradient(120deg,#52b788,#2e9e6b)">A 健康</span>
      <span style="background:linear-gradient(120deg,#e3b341,#d99a21)">B 较健康</span>
      <span style="background:linear-gradient(120deg,#e8a04b,#d9822b)">C 一般</span>
      <span style="background:linear-gradient(120deg,#e06b5b,#d9534f)">D 较差</span>
      <span style="background:linear-gradient(120deg,#c0392b,#922b21)">E 不健康</span>
    </div>
    <p style="margin-top:12px">结果仅供点餐参考，不构成医疗建议。未收录的菜会<b>明确提示无法判断</b>，不会乱猜。</p>
  </div>
</div>

<script>
let timer=null;
let currentSuggest=[];
let currentHealthier=[];
let currentSamples=[];
let currentCuisines=[];
let currentCuisineDishes=[];
const input=document.getElementById('q');
const clearBtn=document.getElementById('qclear');
const suggest=document.getElementById('suggest');

function renderSuggest(list){
  currentSuggest=list||[];
  if(currentSuggest.length===0){suggest.innerHTML='';return;}
  const items=currentSuggest.map((x,i)=>`<div class="sitem" onclick="pickSug(${i})">
    <span class="g" style="background:${x.color}">${x.grade}</span>
    <span class="n">${x.zh?x.zh:x.item}${x.zh?` <span class="en">${x.item}</span>`:''}</span>
    <span class="c">${x.star}星 · ${x.cuisine}</span>
  </div>`).join('');
  suggest.innerHTML=`<div class="card" style="padding:12px">
    <div class="scount">🔎 共 ${currentSuggest.length} 个匹配菜品，点击选择：</div>${items}</div>`;
}
function pickSug(i){
  const x=currentSuggest[i];
  if(x){input.value=x.item;toggleClear();suggest.innerHTML='';predict();}
}
input.addEventListener('input',()=>{
  toggleClear();
  clearTimeout(timer);
  timer=setTimeout(async()=>{
    const q=input.value.trim();
    if(q.length<1){suggest.innerHTML='';return;}
    const r=await fetch('/api/dishes?q='+encodeURIComponent(q));
    const list=await r.json();
    renderSuggest(list);
  },150);
});
input.addEventListener('keydown',e=>{ if(e.key==='Enter'){suggest.innerHTML='';predict();} });
function toggleClear(){ clearBtn.style.display = input.value ? 'flex' : 'none'; }
function clearInput(){ input.value='';toggleClear();suggest.innerHTML='';document.getElementById('result').innerHTML='';input.focus(); }

function starsHtml(star,color){
  let s='';
  for(let i=1;i<=5;i++) s += i<=star ? '★' : '☆';
  return `<span style="color:${color}">${s}</span>`;
}
function tint(hex,a){
  const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}
function gradeBadge(g,c){
  return `<span style="display:inline-block;background:${c};color:#fff;border-radius:9px;
    padding:3px 12px;font-weight:700;font-size:15px;margin-right:6px">${g}</span>`;
}
function dailyLabel(d){
  return d.personalized ? `你的每日所需 ≈ ${d.tdee} 大卡` : '成人每日参考热量（2000 大卡）';
}
function dailyBar(d){
  const p=Math.min(100,Math.max(0,d.daily_pct||0));
  const color=p>=50?'#ef4444':p>=35?'#f59e0b':'#10b981';
  return `<div class="dbar-wrap">
    <div class="dbar-top"><span>🔥 占${dailyLabel(d)}</span><b>${p}%</b></div>
    <div class="dbar"><div class="dbar-fill" style="width:${p}%;background:${color}"></div></div>
  </div>`;
}
function healthierHtml(h){
  currentHealthier=h||[];
  if(currentHealthier.length===0)
    return '<div class="healthier"><div class="hlbl">🎉 这已经是同菜系里最健康的选择啦</div></div>';
  const items=currentHealthier.map((x,i)=>`<div class="hitem" onclick="pickAlt(${i})">
    <span class="g" style="background:${x.color}">${x.grade}</span>
    <span class="n">${x.zh?x.zh:x.item}${x.zh?` <span class="en">${x.item}</span>`:''}</span>
    <span class="c">${x.star}星 · ${x.cal}大卡</span>
  </div>`).join('');
  return `<div class="healthier"><div class="hlbl">🍃 同菜系更健康的选择</div>${items}</div>`;
}
function pickAlt(i){
  const x=currentHealthier[i];
  if(x){input.value=x.item;toggleClear();predict();}
}
function uncoveredCard(d){
  currentSamples=d.samples||[];
  const samples=currentSamples.map((x,i)=>`<div class="sitem" onclick="pickSample(${i})">
    <span class="g" style="background:${x.color}">${x.grade}</span>
    <span class="n">${x.zh?x.zh:x.item}${x.zh?` <span class="en">${x.item}</span>`:''}</span>
    <span class="c">${x.star}星 · ${x.cuisine}</span>
  </div>`).join('');
  return `<div class="card uncover">
    <div class="uncover-ico">🔍</div>
    <h2>无法仅凭菜名判断</h2>
    <p class="uncover-msg">${d.message}</p>
    <div class="healthier"><div class="hlbl">🍽 试试这些已收录的菜（点击直接评估）：</div>${samples}</div>
  </div>`;
}
function pickSample(i){
  const x=currentSamples[i];
  if(x){input.value=x.item;toggleClear();predict();}
}

async function predict(){
  const name=input.value.trim();
  const box=document.getElementById('result');
  if(!name){box.innerHTML='<div class="card err">请输入菜名</div>';return;}
  box.innerHTML='<div class="card">评估中…</div>';
  const body={name};
  const p=getProfile();
  if(p) body.profile=p;
  const r=await fetch('/api/predict',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(!d.found){box.innerHTML=uncoveredCard(d);return;}
  let alt='';
  if(d.alternatives){alt='<div class="hint">还有 '+(d.alternatives.length-1)+' 个相似菜品，取第一个</div>';}
  box.innerHTML=`<div class="card" style="border:1px solid ${tint(d.pred_color,0.5)};
       border-left:6px solid ${d.pred_color};background:linear-gradient(180deg,${tint(d.pred_color,0.05)} 0%,#fff 24%)">
    <h2>${gradeBadge(d.pred_grade,d.pred_color)}${d.zh?d.zh:d.item}${d.zh?` <span class="en">${d.item}</span>`:''}</h2>
    <div class="meta">${d.cuisine}</div>
    <div class="std">${d.standard}</div>
    <div class="portion">🍽 分量（克）：${d.portion}</div>
    ${dailyBar(d)}
    <div class="grid">
      <div class="cell" style="border-color:${tint(d.pred_color,0.6)};background:${tint(d.pred_color,0.07)}">
        <div class="lbl">模型预测健康星级</div>
        <div class="stars">${starsHtml(d.pred_star,d.pred_color)}</div>
        <div class="meta">${d.pred_grade} 档</div></div>
      <div class="cell"><div class="lbl">真实星级（数据集查表）</div>
        <div class="stars">${starsHtml(d.true_star,d.true_color)}</div>
        <div class="meta">${d.true_grade} 档</div></div>
      <div class="cell"><div class="lbl">估计热量</div>
        <div class="cal">${d.pred_cal} <span style="font-size:13px;color:var(--muted)">大卡</span></div></div>
      <div class="cell"><div class="lbl">真实热量</div>
        <div class="cal">${d.true_cal} <span style="font-size:13px;color:var(--muted)">大卡</span></div></div>
    </div>
    <div class="remind" style="--rc:${d.pred_color};background:${tint(d.pred_color,0.08)}">💡 ${d.remind}</div>
    ${healthierHtml(d.healthier)}
  </div>`+alt;
}
function getProfile(){
  const g=document.getElementById('pgender').value;
  const age=document.getElementById('page').value;
  const height=document.getElementById('pheight').value;
  const weight=document.getElementById('pweight').value;
  const activity=document.getElementById('pactivity').value;
  if(g && age && height && weight)
    return {gender:g, age:parseFloat(age), height:parseFloat(height), weight:parseFloat(weight), activity};
  return null;
}
async function loadCuisines(){
  const r=await fetch('/api/cuisines');
  const list=await r.json();
  currentCuisines=list;
  document.getElementById('cuisineList').innerHTML=list.map((c,i)=>`<div class="cchip" onclick="pickCuisine(${i})">
    <span class="cemoji">${c.emoji||'🍽'}</span>
    <div class="czh">${c.zh}</div>
    <div class="ccount">${c.count} 道菜</div>
    <div class="cbest"><span class="gs" style="background:${c.best_color}">${c.best_star}★</span>${c.best_zh||c.best_item}</div>
  </div>`).join('');
}
async function pickCuisine(i){
  const c=currentCuisines[i];
  if(!c) return;
  const r=await fetch('/api/cuisine_dishes?c='+encodeURIComponent(c.cuisine));
  const list=await r.json();
  currentCuisineDishes=list;
  document.getElementById('cuisineDishes').innerHTML=`<div class="scount">「${c.zh}」最健康的 ${list.length} 道（点击评估）：</div>`+
    list.map((x,j)=>`<div class="sitem" onclick="pickDishFromCuisine(${j})">
      <span class="g" style="background:${x.color}">${x.grade}</span>
      <span class="n">${x.zh?x.zh:x.item}${x.zh?` <span class="en">${x.item}</span>`:''}</span>
      <span class="c">${x.star}星 · ${x.cal}大卡</span>
    </div>`).join('');
}
function pickDishFromCuisine(j){
  const x=currentCuisineDishes[j];
  if(x){input.value=x.item;toggleClear();document.getElementById('cuisineDishes').innerHTML='';predict();}
}
function goHome(){
  input.value='';
  toggleClear();
  suggest.innerHTML='';
  document.getElementById('result').innerHTML='';
  document.getElementById('cuisineDishes').innerHTML='';
  currentSuggest=[];
  currentCuisineDishes=[];
  window.scrollTo({top:0,behavior:'smooth'});
  input.focus();
}
loadCuisines();
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("启动外卖健康评估系统：http://127.0.0.1:5000")
    app.run(debug=False, host="127.0.0.1", port=5000)
