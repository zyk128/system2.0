"""单位版中餐（figshare 29977027）英文菜名 -> 中文。

机译：词条词典 + 简单规则，仅用于展示（food_name_cn），不影响营养数据。
准确名优先：中餐 320 道（Carbon footprint...xlsx 的 Recipe English name ->
Recipe Chinese name）能对上的菜用人工准确译名；其余用本词典逐词翻译，
未知词保留英文并保留原词，页面标注「机译仅供参考」。
"""

from __future__ import annotations

import re

# 烹饪方法 / 形态
_METHOD = {
    "braised": "红烧", "red braised": "红烧", "stewed": "炖", "simmered": "煨",
    "steamed": "蒸", "fried": "炸", "deep-fried": "炸", "stir-fried": "炒",
    "stir": "炒", "sautéed": "炒", "sauteed": "炒", "roasted": "烤", "baked": "烤",
    "boiled": "煮", "poached": "白灼", "blanched": "焯", "marinated": "卤",
    "salted": "咸", "smoked": "熏", "dried": "干", "fresh": "鲜", "crispy": "酥脆",
    "crisp": "酥脆", "tender": "嫩", "stuffed": "酿", "glazed": "糖裹",
    "pickled": "腌", "fermented": "腐乳", "sliced": "片", "shredded": "丝",
    "diced": "丁", "minced": "末", "pounded": "捶", "whole": "整只",
    "cooked": "烹", "double-cooked": "回锅", "pan-fried": "煎", "dry-fried": "干煸",
    "kung pao": "宫保", "mapo": "麻婆", "raw": "生", "chilled": "凉",
    "cold": "凉", "hot pot": "火锅", "braise": "红烧", "roast": "烤",
    "grilled": "烤", "preserved": "腌", "cured": "腊", "smoke": "熏",
}

# 主料 / 配料
_INGREDIENT = {
    "fish": "鱼", "carp": "鲤鱼", "crucian": "鲫鱼", "croaker": "黄鱼",
    "eel": "鳝鱼", "squid": "鱿鱼", "abalone": "鲍鱼", "shark": "鲨鱼",
    "fin": "翅", "roe": "鱼籽", "sea": "海", "seafood": "海鲜", "crab": "蟹",
    "shrimp": "虾", "prawn": "大虾", "chicken": "鸡", "duck": "鸭",
    "pigeon": "鸽", "quail": "鹌鹑", "pork": "猪肉", "beef": "牛肉",
    "lamb": "羊肉", "mutton": "羊肉", "meat": "肉", "ham": "火腿",
    "ribs": "排骨", "tenderloin": "里脊", "tripe": "肚", "head": "头",
    "meatballs": "丸子", "meatball": "丸子", "balls": "丸子", "ball": "丸",
    "tofu": "豆腐", "bean": "豆", "beans": "豆", "bamboo": "竹",
    "shoots": "笋", "shoot": "笋", "mushroom": "蘑菇", "mushrooms": "蘑菇",
    "fungus": "木耳", "melon": "瓜", "cucumber": "黄瓜", "cabbage": "白菜",
    "vegetable": "蔬菜", "vegetables": "蔬菜", "lotus": "莲藕", "root": "根",
    "winter": "冬", "spring": "春", "pine": "松", "sesame": "芝麻",
    "glutinous": "糯米", "rice": "米饭", "egg": "蛋", "eggs": "蛋",
    "oil": "油", "soy": "酱油", "sauce": "酱", "wine": "酒", "ginger": "姜",
    "scallion": "葱", "oyster": "蚝", "sugar": "糖", "honey": "蜂蜜",
    "paste": "泥", "cake": "糕", "roll": "卷", "rolls": "卷",
    "slices": "片", "shreds": "丝", "dices": "丁", "dumpling": "团子",
    "dumplings": "团子", "noodle": "面", "noodles": "面", "soup": "汤",
    "porridge": "粥", "pot": "锅", "pan": "铁板", "steamer": "蒸笼",
    "skin": "皮", "feet": "爪", "wings": "翅", "breast": "胸", "leg": "腿",
    "belly": "五花肉", "trotters": "猪蹄", "pancake": "饼", "vegetarian": "素",
    "jar": "坛", "earthen": "瓦罐", "kinds": "味", "ways": "吃法",
    "live": "活", "bun": "包", "wonton": "馄饨", "pie": "派",
    "congee": "粥", "vermicelli": "粉丝", "glass noodles": "粉丝",
    "noodle soup": "汤面", "wheat": "麦", "yam": "山药", "taro": "芋头",
    "potato": "土豆", "sweet potato": "红薯", "corn": "玉米", "pea": "豌豆",
    "peas": "豌豆", "carrot": "胡萝卜", "radish": "萝卜", "turnip": "芜菁",
    "celery": "芹菜", "spinach": "菠菜", "leek": "韭菜", "onion": "洋葱",
    "garlic": "蒜", "chili": "辣椒", "pepper": "胡椒", "peppers": "辣椒",
    "eggplant": "茄子", "zucchini": "西葫芦", "pumpkin": "南瓜",
    "winter melon": "冬瓜", "bottle gourd": "葫芦", "apple": "苹果",
    "pear": "梨", "date": "枣", "dates": "枣", "plum": "梅",
    "apricot": "杏", "peach": "桃", "orange": "橘", "tangerine": "橘",
    "pine nut": "松子", "pine nuts": "松子", "walnut": "核桃",
    "chestnut": "栗子", "lotus seed": "莲子", "lotus seeds": "莲子",
    "red date": "红枣", "goji": "枸杞", "chive": "韭", "chives": "韭菜",
    "scallion": "葱", "shallot": "红葱头", "mint": "薄荷", "basil": "罗勒",
    "cilantro": "香菜", "coriander": "香菜", "saffron": "藏红花",
    "truffle": "松露", "oyster sauce": "蚝油", "soy sauce": "酱油",
    "bean curd": "豆腐", "chicken stock": "鸡汤", "broth": "高汤",
    "lard": "猪油", "butter": "黄油", "vinegar": "醋", "sesame oil": "香油",
    "sesame paste": "芝麻酱", "peanut": "花生", "peanuts": "花生",
    "almond": "杏仁", "coconut": "椰", "milk": "奶", "cream": "奶油",
}

# 口味 / 颜色 / 形状 / 修饰
_ADJ = {
    "spicy": "辣", "hot": "辣", "sweet": "甜", "sour": "酸", "salty": "咸",
    "fragrant": "香", "golden": "金黄", "clear": "清", "assorted": "什锦",
    "double": "双", "one": "一", "two": "二", "three": "三", "four": "四",
    "five": "五", "six": "六", "seven": "七", "eight": "八", "nine": "九",
    "ten": "十", "treasure": "珍", "pearl": "珍珠", "jade": "翡翠", "silver": "银",
    "snow": "雪", "phoenix": "凤", "mandarin": "鸳鸯", "red": "红",
    "yellow": "黄", "white": "白", "green": "绿", "black": "黑", "purple": "紫",
    "brown": "棕", "flavored": "味", "style": "风", "old": "老", "young": "嫩",
    "small": "小", "large": "大", "big": "大", "boneless": "去骨", "dry": "干",
    "oily": "油", "crystal": "水晶", "knuckle": "猪蹄", "wuxi": "无锡",
    "squirrel": "松鼠", "four": "四", "kinds": "味", "ways": "吃法",
    "live": "活", "tender": "嫩",
}

# 连接词 / 虚词（丢弃）
_DROP = {"with", "and", "in", "of", "the", "a", "an", "s", "on", "at", "for", "by", "to", "as", "or", "per", "no", "de", "la", "du"}

# 多词习语：先整体替换成单个中文 token，再拆词翻译
_PHRASES = [
    ("kung pao", "宫保"), ("mapo", "麻婆"), ("sweet and sour", "糖醋"),
    ("red braised", "红烧"), ("double-cooked", "回锅"), ("shark's fin", "鱼翅"),
    ("lotus root", "莲藕"), ("winter melon", "冬瓜"), ("bottle gourd", "葫芦"),
    ("sesame oil", "香油"), ("soy sauce", "酱油"), ("oyster sauce", "蚝油"),
    ("bean curd", "豆腐"), ("black bean", "豆豉"), ("sweet potato", "红薯"),
    ("pine nut", "松子"), ("pine nuts", "松子"), ("red date", "红枣"),
    ("lotus seed", "莲子"), ("lotus seeds", "莲子"), ("glass noodles", "粉丝"),
    ("noodle soup", "汤面"), ("rice flour", "米粉"), ("clear soup", "清汤"),
    ("hot pot", "火锅"), ("spring roll", "春卷"), ("lion's head", "狮子头"),    ("iron plate", "铁板"), ("dongpo", "东坡"), ("beggar's chicken", "叫花鸡"),
    ("peking duck", "北京烤鸭"), ("squirrel fish", "松鼠鱼"),]


def translate(item: str) -> str:
    """把单位版英文菜名翻成中文（机译，仅供参考）；未知词保留英文。"""
    text = " " + item.lower() + " "
    text = text.replace("'s ", " ")  # 去掉所有格
    for phrase, zh in _PHRASES:
        text = text.replace(f" {phrase} ", f" {zh} ")
    text = text.strip()
    parts = re.split(r"([\s\-/&()]+)", text)
    out: list[str] = []
    for raw in parts:
        if not raw:
            continue
        t = raw.strip("®'\".,;").strip()
        if not t:
            continue
        if re.fullmatch(r"[\d.]+", t):
            out.append(t)
            continue
        low = t.lower()
        mapped = _METHOD.get(low) or _INGREDIENT.get(low) or _ADJ.get(low)
        if mapped is not None:
            out.append(mapped)
        elif low in _DROP:
            continue
        else:
            out.append(t)  # 未知词保留英文
    return "".join(out)
