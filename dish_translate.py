"""中文菜名别名：给英文菜名（数据集原版）加中文别名，便于中文搜索与中文展示。

说明：这是「菜名翻译」，不是营养数据。营养数值 100% 来自原始数据集；
这里只做菜名层面的中英对照，方便输入中文也能查、结果能同时显示中英文。
词典用「精准词典 + 程序化兜底」两层：常见/名菜/健康菜精准收录，其余描述性菜名
用词/短语词典按最长匹配逐段翻译（离线、不调外部 API、不联网）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# ---------- 精准词典：英文菜名（小写）→ 中文名 ----------
CURATED = {
    # 川菜 / 名菜
    "mapo tofu": "麻婆豆腐",
    "kung pao chicken": "宫保鸡丁",
    "kung pao baby cuttlefish": "宫保鱿鱼丁",
    "dongpo pork": "东坡肉",
    "twice cooked pork": "回锅肉",
    "shredded pork with garlic sauce": "鱼香肉丝",
    "sweet and sour pork": "糖醋里脊",
    "sweet and sour pork tenderloin": "糖醋里脊",
    "sweet and sour braised pork tenderloin": "糖醋烧里脊",
    "hot and sour soup": "酸辣汤",
    "wonton soup": "馄饨汤",
    "peking duck": "北京烤鸭",
    "beggar's chicken": "叫花鸡",
    "fried spring rolls": "炸春卷",
    "spring rolls": "春卷",
    "chow mein": "炒面",
    "fried rice": "炒饭",
    "egg fried rice": "蛋炒饭",
    "yangzhou fried rice with eggs": "扬州炒饭",
    # 肉类
    "braised pork": "红烧肉",
    "braised pork belly": "红烧五花肉",
    "braised pork in brown sauce": "红烧肉",
    "red-cooked pork": "红烧肉",
    "steamed pork with rice flour": "粉蒸肉",
    "stir-fried pork": "炒肉片",
    "shredded pork": "肉丝",
    "sliced pork": "肉片",
    "pork chop": "猪排",
    "braised beef": "红烧牛肉",
    "stewed beef": "炖牛肉",
    "beef brisket": "牛腩",
    "lamb": "羊肉",
    "braised chicken": "红烧鸡",
    "stewed chicken": "炖鸡",
    "steamed chicken": "蒸鸡",
    "fried chicken": "炸鸡",
    "roast duck": "烤鸭",
    "braised duck": "红烧鸭",
    "steamed duck": "蒸鸭",
    # 水产
    "steamed fish": "清蒸鱼",
    "braised fish": "红烧鱼",
    "fried fish": "炸鱼",
    "boiled fish": "水煮鱼",
    "fish head": "鱼头",
    "clay pot fish head tofu": "砂锅鱼头豆腐",
    "fish ball hot pot": "鱼丸火锅",
    "crystal shrimp": "水晶虾仁",
    "golden cup crystal shrimp": "金杯水晶虾仁",
    "stir-fried shrimp": "清炒虾仁",
    "braised shrimp": "油焖大虾",
    "steamed crab": "清蒸蟹",
    "fried crab": "炒蟹",
    # 豆腐 / 素菜
    "tofu": "豆腐",
    "braised tofu": "红烧豆腐",
    "steamed tofu": "蒸豆腐",
    "fried tofu": "炸豆腐",
    "citron tofu": "香橼豆腐",
    "braised vegetarian ham": "素火腿",
    "stir-fried vegetable": "炒时蔬",
    "stir-fried greens": "清炒青菜",
    "bok choy": "小白菜",
    "chinese cabbage": "大白菜",
    "bamboo shoots": "竹笋",
    "mushroom": "蘑菇",
    # 汤羹 / 主食
    "soup": "汤",
    "clear soup": "清汤",
    "fish soup": "鱼汤",
    "chicken soup": "鸡汤",
    "beef soup": "牛肉汤",
    "egg drop soup": "蛋花汤",
    "noodle": "面",
    "noodles": "面条",
    "fried noodles": "炒面",
    "dumpling": "饺子",
    "dumplings": "饺子",
    "steamed bun": "包子",
    "bun": "包子",
    "pancake": "饼",
    "congee": "粥",
    "rice porridge": "米粥",
    "glutinous rice": "糯米",
    "fried rice noodles": "炒河粉",
    # 蛋
    "steamed egg": "蒸蛋",
    "egg custard": "蒸水蛋",
    "scrambled egg": "炒鸡蛋",
    "egg": "蛋",
    "preserved egg": "皮蛋",

    # ---------- 各菜系「更健康推荐」候选菜（A 档最健康，推荐列表正是这些）----------
    # 徽菜 Anhui
    "fennel-flavored broad beans": "茴香蚕豆",
    "sliced pigeon eggs": "鸽蛋片",
    "golden bird's tongue": "金雀舌",
    "fish dumplings in green broth": "碧绿鱼饺",
    "jade-like ice blossom": "玉兰冰花",
    "lotus seed and beef soup": "莲子牛肉汤",
    "vegetarian shreds in superior soup": "素丝高汤",
    "southern pork with spring bamboo shoots": "春笋南肉",
    "egg white crucian carp": "芙蓉鲫鱼",
    "sweet potato puree": "红薯泥",
    "salted green beans": "盐渍青豆",
    "wild vegetable with braised quail": "野蔬焖鹌鹑",
    "steamed flower mushrooms": "清蒸花菇",
    "poached cuttlefish flowers": "白灼墨鱼花",
    "sliced white chicken": "白切鸡",
    "spicy and numbing pig blood cake": "麻辣猪血糕",
    "rose fish slices": "玫瑰鱼片",
    "poached duck heart flowers": "白灼鸭心花",
    "double fresh tofu": "双鲜豆腐",
    "orchid firewood bundle fern": "柴把蕨菜",
    # 闽菜 Fujian
    "cabbage simmered in earthen jar": "砂锅焖白菜",
    "spinach soup": "菠菜汤",
    "vegetable oil-fried bean sprouts": "油炒豆芽",
    "mixed three diced vegetables": "三丁杂蔬",
    "corn and cauliflower soup": "玉米花椰菜汤",
    "vegetable rolls in chicken broth": "鸡汤菜卷",
    "crystal scallops": "水晶干贝",
    "fujian-style sautéed bamboo shoots": "闽式炒笋",
    "sea worm jelly": "土笋冻",
    "chilled crab claws": "凉拌蟹钳",
    "sour eight-treasure vegetable": "酸八宝菜",
    "silk rain and lonely cloud": "丝雨孤云",
    "white mixed yellow conch": "白拌黄螺",
    "shredded squid with green chives": "韭黄炒鱿鱼丝",
    "three-color cauliflower": "三色花椰菜",
    "hericium erinaceus and squid dumplings": "猴头菇鱿鱼饺",
    "yellow conch with white honey": "蜜汁黄螺",
    "straw mushroom with tofu": "草菇豆腐",
    "mushroom with ginkgo": "银杏蘑菇",
    "stir-fried chicken slices in fermented rice sauce": "酒酿炒鸡片",
    # 湘菜 Hunan
    "steamed chinese cabbage": "清蒸大白菜",
    "stewed kiwi with rock sugar": "冰糖炖猕猴桃",
    "orange juice egg tofu": "橙汁鸡蛋豆腐",
    "strange-flavored bitter gourd": "怪味苦瓜",
    "sour and spicy shredded eggplant": "酸辣茄丝",
    "pan-fried and braised bitter gourd": "煎焖苦瓜",
    "sautéed laba beans": "炒腊八豆",
    "sour and spicy green beans": "酸辣四季豆",
    "two-color radish dices": "双色萝卜丁",
    "ginseng and fungus papaya soup": "人参木耳木瓜汤",
    "pepper leaf braised pork liver": "辣椒叶焖猪肝",
    "stir-fried pork with cabbage stems": "白菜梗炒肉",
    "chicken shreds with bean starch sheets": "鸡丝凉粉",
    "scallion braised dried tofu": "葱烧豆腐干",
    "rock sugar loquat": "冰糖枇杷",
    "pan-fried edamame with stinky tofu": "煎毛豆臭豆腐",
    "stir-fried squid shreds": "炒鱿鱼丝",
    "high mountain vegetable boiled meat slices": "高山菜汆肉片",
    "yellow flower pinched vegetable": "黄花掐菜",
    "soy sauce green pepper eggplant": "酱油青椒茄子",
    # 苏菜 Jiangsu
    "crystal shrimps": "水晶虾仁",
    "wine-fermented tremella": "酒酿银耳",
    "asparagus, fresh shrimp and tofu": "芦笋鲜虾豆腐",
    "cabbage heart with cream": "奶油菜心",
    "clear soup with five-shred tofu": "五丝豆腐清汤",
    "egg white pigeon fillets": "芙蓉鸽脯",
    "cabbage-wrapped shrimp": "白菜包虾",
    "pearl and jadeite soup": "珍珠翡翠汤",
    "stir-fried mung bean sprout with pigeon shreds": "绿豆芽炒鸽丝",
    "assorted vegetables": "什锦蔬菜",
    "stir-fried cuttlefish flowers": "炒墨鱼花",
    "meiling heart of cabbage": "梅岭菜心",
    "fermented rice fish": "酒酿鱼",
    "steamed clear juice fish": "清蒸鱼",
    "tripe braised tofu": "牛肚烧豆腐",
    "toona tofu": "香椿豆腐",
    "tofu with toona sprouts": "香椿芽豆腐",
    "ham and chicken oil heart of cabbage": "火腿鸡油菜心",
    "braised duck webs": "红烧鸭掌",
    "five-flavor celery": "五味芹菜",
    # 鲁菜 Shandong
    "sautéed winter bamboo shoots with shepherd's purse": "荠菜炒冬笋",
    "toona sinensis with tofu": "香椿拌豆腐",
    "oil-splashed doujian": "油泼豆尖",
    "chinese cabbage stewed with fish roe": "白菜炖鱼籽",
    "sautéed shredded pork with celery": "芹菜炒肉丝",
    "pineapple and tremella": "菠萝银耳",
    "sautéed squid rolls with cilantro": "香菜炒鱿鱼卷",
    "vinegar-fried mung bean sprouts": "醋炒绿豆芽",
    "oil-splashed bean sprouts": "油泼豆芽",
    "sautéed tender meat with fresh mushrooms": "鲜菇炒嫩肉",
    "pan-fried egg tofu": "煎鸡蛋豆腐",
    "southern pan-fried tofu": "南煎豆腐",
    "fish slices in fermented rice sauce": "酒酿鱼片",
    "braised eggplant in sweet sauce": "酱烧茄子",
    "braised tofu with mushroom": "蘑菇烧豆腐",
    "stir-fried scallop dices in soy sauce": "酱油炒带子",
    "stir-fried tenderloin shreds": "炒里脊丝",
    "braised cuttlefish roe with baby cuttlefish": "墨鱼籽烧小墨鱼",
    "sesame paste assorted vegetarian": "麻酱什锦素",
    "stir-fried eel shreds": "炒鳝丝",
    # 浙菜 Zhejiang
    "phoenix tail bamboo shoot soup": "凤尾笋汤",
    "chilled chinese broccoli": "凉拌芥蓝",
    "mixed greens": "拌时蔬",
    "braised scallops": "烧干贝",
    "salted pork with black carp": "咸肉青鱼",
    "egg white and hair moss soup": "芙蓉发菜汤",
    "ningbo-style shaken clams": "宁波摇蚶",
    "chrysanthemum-shaped tofu": "菊花豆腐",
    "mushroom holders": "蘑菇托",
    "wulin-style sauce diced vegetables": "武林酱丁",
    "steamed eggplant": "清蒸茄子",
    "white oil green balls": "白油青菜丸",
    "mushroom with pork tenderloin": "蘑菇里脊",
    "three-layer fish slices": "三层鱼片",
    "chrysanthemum greens with garlic": "蒜蓉茼蒿",
    "sautéed shredded dried eel": "炒干鳝丝",
    "bracken with shredded cuttlefish": "蕨菜墨鱼丝",
    "southern-style sautéed kidney": "南式炒腰花",
    "three-color shredded fish": "三色鱼丝",
    "six-flavor casserole": "六味砂锅",
}

# ---------- 程序化兜底：词/短语词典（长词优先） ----------
_ZH = {
    # 烹饪法
    "sweet and sour": "糖醋", "sour and spicy": "酸辣", "spicy and numbing": "麻辣",
    "stir-fried": "炒", "stir fried": "炒", "pan-fried": "煎", "pan fried": "煎",
    "deep-fried": "炸", "deep fried": "炸", "oil-fried": "油炒", "oil-splashed": "油泼",
    "oil-splashed": "油泼", "dry-fried": "干煸", "double-cooked": "回锅",
    "vinegar-fried": "醋炒", "wine-fermented": "酒酿", "fermented rice": "酒酿",
    "soy sauce": "酱油", "scallion braised": "葱烧", "scallion": "葱",
    "sautéed": "炒", "sauted": "炒", "sauté": "炒", "steamed": "蒸", "braised": "红烧",
    "stewed": "炖", "simmered": "焖", "roasted": "烤", "roast": "烤", "boiled": "煮",
    "smoked": "熏", "grilled": "烤", "chilled": "凉拌", "cold": "凉拌", "fried": "炒",
    "poached": "白灼", "shredded": "丝", "sliced": "片", "diced": "丁", "mashed": "泥",
    "crystal": "水晶", "salted": "盐", "pickled": "腌",
    # 蔬菜
    "chinese cabbage": "大白菜", "bok choy": "小白菜", "chinese broccoli": "芥蓝",
    "broccoli": "西兰花", "cauliflower": "花椰菜", "spinach": "菠菜",
    "mung bean sprout": "绿豆芽", "mung bean": "绿豆", "bean sprouts": "豆芽",
    "soybean sprouts": "黄豆芽", "winter bamboo shoots": "冬笋", "bamboo shoots": "竹笋",
    "bamboo shoot": "竹笋", "egg tofu": "鸡蛋豆腐", "dried tofu": "豆腐干",
    "stinky tofu": "臭豆腐", "tofu": "豆腐", "bean curd": "豆腐",
    "straw mushroom": "草菇", "flower mushrooms": "花菇", "flower mushroom": "花菇",
    "mushrooms": "蘑菇", "mushroom": "蘑菇", "tremella": "银耳", "black fungus": "黑木耳",
    "fungus": "木耳", "hericium erinaceus": "猴头菇", "ginkgo": "银杏", "eggplant": "茄子",
    "bitter gourd": "苦瓜", "green beans": "四季豆", "broad beans": "蚕豆",
    "laba beans": "腊八豆", "edamame": "毛豆", "radish": "萝卜", "carrot": "胡萝卜",
    "celery": "芹菜", "cilantro": "香菜", "green chives": "韭黄", "chives": "韭菜",
    "shepherd's purse": "荠菜", "bracken": "蕨菜", "fern": "蕨菜", "seaweed": "海带",
    "loquat": "枇杷", "kiwi": "猕猴桃", "pineapple": "菠萝", "papaya": "木瓜",
    "cucumber": "黄瓜", "pumpkin": "南瓜", "gourd": "瓜", "asparagus": "芦笋",
    "corn": "玉米", "green pepper": "青椒", "pepper": "辣椒", "chili": "辣椒",
    "chilli": "辣椒", "garlic": "蒜", "ginger": "姜", "onion": "洋葱",
    "lotus seed": "莲子", "lotus": "莲藕", "potato": "土豆", "sweet potato": "红薯",
    "taro": "芋头", "yam": "山药", "water chestnut": "荸荠", "toona sinensis": "香椿",
    "toona": "香椿", "vegetable": "时蔬", "vegetables": "时蔬", "greens": "青菜",
    "fennel": "茴香", "sesame": "芝麻", "ginseng": "人参", "wolfberry": "枸杞",
    "red dates": "红枣", "lily": "百合",
    # 肉 / 水产 / 蛋
    "chicken": "鸡", "duck": "鸭", "pork": "猪肉", "beef": "牛肉", "lamb": "羊肉",
    "mutton": "羊肉", "fish": "鱼", "shrimps": "虾仁", "shrimp": "虾仁", "prawns": "虾",
    "prawn": "虾", "scallops": "干贝", "scallop": "干贝", "cuttlefish": "墨鱼",
    "squid": "鱿鱼", "crab": "蟹", "clams": "蛤蜊", "conch": "海螺", "eel": "鳝鱼",
    "black carp": "青鱼", "crucian carp": "鲫鱼", "carp": "鲤鱼", "pigeon": "鸽",
    "quail": "鹌鹑", "egg white": "蛋白", "eggs": "蛋", "egg": "蛋", "meat": "肉",
    "tenderloin": "里脊", "kidney": "腰", "tripe": "牛肚", "liver": "肝",
    "duck webs": "鸭掌", "duck heart": "鸭心", "pig blood": "猪血", "pork blood": "猪血",
    "ham": "火腿", "bacon": "培根", "sausage": "香肠", "meatball": "肉丸", "fish roe": "鱼籽",
    # 形态 / 后缀
    "soup": "汤", "broth": "汤", "sauce": "酱", "paste": "酱", "rice": "饭",
    "noodles": "面条", "noodle": "面", "dumplings": "饺", "dumpling": "饺",
    "steamed bun": "包子", "bun": "包", "pancake": "饼", "congee": "粥",
    "porridge": "粥", "slices": "片", "shreds": "丝", "dices": "丁", "balls": "丸",
    "rolls": "卷", "fillets": "片", "puree": "泥", "jelly": "冻", "casserole": "砂锅",
    "hot pot": "火锅", "rock sugar": "冰糖", "honey": "蜜", "orange juice": "橙汁",
    "stems": "梗", "heart": "心", "flowers": "花",
    # 修饰（颜色/数字）
    "three-color": "三色", "three color": "三色", "two-color": "双色", "two color": "双色",
    # 补充常见食材/做法
    "tea": "茶", "date": "枣", "roll": "卷", "clam": "蛤蜊", "pearl": "珍珠",
    "stone pot": "石锅", "acorn": "橡子", "cicada": "蝉", "three treasures": "三宝",
    "red oil": "红油", "home-style": "家常", "home style": "家常", "wine": "酒",
    "walnut": "核桃", "kernels": "仁", "kernel": "仁", "marinated": "腌",
    "duck tongue": "鸭舌", "cattail": "蒲菜", "crispy": "脆", "whole fish": "全鱼",
    "stuffed": "酿", "eight flavors": "八宝", "eight treasures": "八宝", "lobster": "龙虾",
    "cabbage": "白菜", "soaked": "浸", "rice wine": "米酒", "tongue": "舌",
    "crab claws": "蟹钳", "roe": "籽", "baby": "小", "tender": "嫩", "tendon": "筋",
    "sea cucumber": "海参", "abalone": "鲍鱼", "shark fin": "鱼翅", "sharks fin": "鱼翅",
    "jellyfish": "海蜇", "frog": "田鸡", "snail": "田螺", "turtle": "甲鱼",
    "pigeon eggs": "鸽蛋", "bean paste": "豆瓣酱", "chili oil": "辣椒油", "vinegar": "醋",
    "sesame oil": "香油", "sesame paste": "麻酱", "soy bean": "黄豆", "red bean": "红豆",
    "snow pea": "荷兰豆", "pea": "豌豆", "mustard": "芥末", "sprouts": "苗", "sprout": "苗",
    "heart of cabbage": "菜心", "cabbage heart": "菜心", "salted": "咸", "dried": "干",
    "shredded": "丝", "minced": "末", "smashed": "拍", "spare ribs": "排骨", "ribs": "排骨",
    "wings": "翅", "drumstick": "鸡腿", "breast": "胸", "thigh": "腿", "gizzard": "胗",
    "intestine": "肠", "stomach": "肚", "feet": "爪", "head": "头", "skin": "皮",
    "bamboo": "竹", "lotus root": "莲藕", "water bamboo": "茭白", "day lily": "黄花菜",
    "chrysanthemum greens": "茼蒿", "shepherds purse": "荠菜", "winter melon": "冬瓜",
    "bitter melon": "苦瓜", "wax gourd": "冬瓜", "long bean": "豇豆", "string bean": "四季豆",
    "egg": "蛋", "century egg": "皮蛋", "salted egg": "咸蛋", "tea egg": "茶叶蛋",
    "bean curd": "豆腐", "dried bean curd": "豆腐干", "fried dough": "油条",
    "glutinous": "糯米", "millet": "小米", "buckwheat": "荞麦", "barley": "大麦",
    "oat": "燕麦", "wonton": "馄饨", "shaomai": "烧卖", "zongzi": "粽子",
    "five spice": "五香", "five-spice": "五香", "three cup": "三杯", "general tsos": "左宗棠",
}

# 把连字符键统一成空格，配合下方输入归一化
_ZH = {k.replace("-", " "): v for k, v in _ZH.items()}

# 连接词/修饰词/地名：跳过（不翻、不保留）
_DROP = {
    "and", "with", "in", "of", "the", "a", "an", "or", "style", "flavored", "flavoured",
    "flavor", "flavour", "flavors", "shaped", "southern", "northern", "western", "eastern",
    "wulin", "ningbo", "fujian", "meiling", "superior", "clear", "mixed", "assorted",
    "eight", "three", "five", "six", "two", "double", "single", "fresh", "sour", "spicy",
    "sweet", "strange", "white", "green", "red", "yellow", "black", "color", "colour",
    "colored", "coloured", "holder", "holders", "high", "mountain", "wild", "vegetarian",
    "silk", "rain", "lonely", "cloud", "jade", "like", "golden", "silver", "pearl",
    "bird", "tongue", "ice", "blossom", "phoenix", "tail", "dragon", "orchid", "firewood",
    "bundle", "sea", "worm", "rose", "chrysanthemum", "jadeite", "treasure", "hair",
    "moss", "shaken", "boiled", "braised", "stewed", "steamed", "fried", "simmered",
}


def _programmatic_zh(name_lower: str) -> str:
    """词/短语最长匹配翻译；生词跳过，但丢词太多（翻出的字过少）则回退英文。"""
    name_lower = name_lower.replace("-", " ")  # 连字符当空格，统一分词
    words = [w for w in re.split(r"[^a-z']+", name_lower.lower()) if w]
    out: list[str] = []
    dropped = 0
    i, n = 0, len(words)
    while i < n:
        hit = False
        for span in range(min(4, n - i), 0, -1):
            phrase = " ".join(words[i:i + span])
            if phrase in _ZH:
                out.append(_ZH[phrase])
                i += span
                hit = True
                break
        if hit:
            continue
        w = words[i]
        if w in _ZH:
            out.append(_ZH[w])
        else:
            dropped += 1  # 连接词/修饰词/生词：跳过
        i += 1
    text = "".join(out)
    # 质量门槛：没翻出东西，或丢的词比翻出的还多，回退英文（避免误导性的残缺中文）
    if not text or len(text) < 2 or dropped > len(out):
        return ""
    return text


def build_zh_lookup(english_names_lower: set[str]) -> dict[str, str]:
    """中文 → 英文（由精准词典反转，仅保留数据集中真实存在的菜）。"""
    zh2en: dict[str, str] = {}
    for en, zh in CURATED.items():
        if en in english_names_lower:
            if zh not in zh2en or len(en) < len(zh2en[zh]):
                zh2en[zh] = en
    return zh2en


def build_en_lookup(chinese_names_lower: set[str]) -> dict[str, str]:
    """英文 → 中文：精准词典优先，其次程序化兜底（只对中式菜，美式菜保持原名）。"""
    en2zh: dict[str, str] = {}
    for en, zh in CURATED.items():
        if en in chinese_names_lower:
            en2zh[en] = zh
    for en in chinese_names_lower:
        if en not in en2zh:
            z = _programmatic_zh(en)
            if z:
                en2zh[en] = z
    return en2zh


def build_us_lookup() -> dict[str, str]:
    """美式菜英文 → 中文（来自参考站点的中文菜名对照表，覆盖 100% 美式菜）。"""
    path = Path("data/processed/us_zh.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def has_chinese(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)
