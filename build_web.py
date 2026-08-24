"""生成本地网页版演示 index.html（无服务器，浏览器双击打开即可）。

使用与 console 版（demo.py）完全相同的真实数据与星级规则；
数据以 JSON 内嵌在 HTML 中，无需网络、无需后端。

运行：
    python build_web.py
"""
import json
import os

import pandas as pd

PROC = os.path.join("data", "processed")
HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "index.html")

ADVICE = {
    1: "高油高热量，尽量少点，换清淡的",
    2: "偏高油热量，少吃，选蒸/煮/清炒",
    3: "正常水平，偶尔吃",
    4: "相对清淡，可常吃",
    5: "低油低热量，优先选",
}
LEVEL = {1: "最高（最不健康）", 2: "偏高", 3: "中等", 4: "较清淡", 5: "最清淡"}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>外卖健康星级评估</title>
<style>
  *{box-sizing:border-box;}
  body{font-family:"Microsoft YaHei",system-ui,sans-serif;max-width:860px;margin:0 auto;padding:24px 20px 48px;color:#1f3a33;background:linear-gradient(180deg,#dff3ec 0%,#eef8f4 260px,#f7faf8 100%);min-height:100vh;}
  .head{display:flex;align-items:center;gap:12px;margin-bottom:4px;}
  .head .logo{font-size:36px;}
  .head h1{font-size:28px;margin:0;background:linear-gradient(90deg,#0e9f6e,#1e88c8);-webkit-background-clip:text;background-clip:text;color:transparent;}
  .sub{color:#4d6a60;font-size:13px;margin:0 0 14px;}
  .note{background:#fff8e8;border:1px solid #f4cf7a;border-radius:12px;padding:12px 16px;font-size:13px;color:#6b5410;line-height:1.7;box-shadow:0 2px 8px rgba(180,140,40,.06);}
  .stat{background:#e9f7f1;border:1px solid #a9e2c8;border-radius:12px;padding:12px 16px;font-size:13px;margin:12px 0;line-height:1.7;color:#14532d;}
  .search{margin:16px 0;display:flex;gap:8px;flex-wrap:wrap;}
  .profile{margin:12px 0;background:#fff;border:1px solid #d8e9e2;border-radius:14px;overflow:hidden;}
  .profile summary{cursor:pointer;padding:12px 16px;font-size:14px;font-weight:700;color:#0d4936;background:#eef6f2;}
  .prow{display:grid;grid-template-columns:repeat(auto-fit,minmax(128px,1fr));gap:12px 14px;padding:14px 16px 18px;}
  .prow label{display:flex;flex-direction:column;gap:5px;font-size:12px;color:#4d6a60;font-weight:600;}
  .prow input,.prow select{flex:none;min-width:0;width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #c3d8cf;border-radius:9px;font-size:14px;background:#fff;color:#1f3a33;font-family:inherit;}
  .prow input:focus-visible,.prow select:focus-visible{outline:3px solid #a7e8d0;outline-offset:1px;}
  .prow select{height:40px;}
  input{flex:1;min-width:200px;padding:12px 14px;font-size:16px;border:1px solid #bfd6cc;border-radius:10px;background:#fff;color:#1f3a33;}
  input:focus-visible,button:focus-visible{outline:3px solid #a7e8d0;outline-offset:1px;}
  button{padding:12px 22px;font-size:16px;border:0;border-radius:10px;background:linear-gradient(180deg,#12b585,#0e9f6e);color:#fff;cursor:pointer;font-weight:bold;box-shadow:0 3px 8px rgba(14,159,110,.25);}
  button:hover{filter:brightness(1.05);}
  .card{background:#fff;border:1px solid #d8e9e2;border-radius:20px;margin-top:16px;box-shadow:0 12px 32px rgba(20,60,45,.10);overflow:hidden;}
  .candcard{padding:18px 20px;}
  .cand-title{font-size:16px;font-weight:bold;color:#0d4936;margin:0 0 12px;line-height:1.5;}
  .cand-grid{display:flex;flex-wrap:wrap;gap:10px;}
  .candmore{margin-top:12px;text-align:center;}
  .morebtn{padding:8px 20px;font-size:13px;border:1px solid #bfd6cc;background:#fff;border-radius:18px;cursor:pointer;color:#0d4936;font-family:inherit;}
  .morebtn:hover{border-color:#12b585;background:#ecf8f3;}
  .card-top{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:18px 22px 14px;flex-wrap:wrap;}
  .card .name{font-size:22px;font-weight:800;color:#0d4936;line-height:1.35;}
  .src{font-size:12px;color:#4d6a60;background:#eef4f1;border:1px solid #d8e9e2;border-radius:20px;padding:3px 12px;white-space:nowrap;}
  .star-banner{display:flex;align-items:center;gap:16px;padding:14px 22px;color:#fff;background:linear-gradient(120deg,#0e9f6e,#1e88c8);flex-wrap:wrap;}
  .star-banner.s1{background:linear-gradient(120deg,#e06b5b,#c0392b);}
  .star-banner.s2{background:linear-gradient(120deg,#e8a04b,#d9822b);}
  .star-banner.s3{background:linear-gradient(120deg,#e3b341,#d99a21);}
  .star-banner.s4{background:linear-gradient(120deg,#52b788,#2e9e6b);}
  .star-banner.s5{background:linear-gradient(120deg,#2ec4a0,#0e9f6e);}
  .bigscore{font-size:44px;font-weight:900;line-height:1;}
  .bigscore small{font-size:16px;font-weight:600;opacity:.9;}
  .stars{font-size:32px;letter-spacing:3px;line-height:1;text-shadow:0 2px 5px rgba(0,0,0,.20);}
  .starcap{font-size:12px;opacity:.94;margin-top:4px;line-height:1.5;}
  .cbody{padding:16px 22px 20px;}
  .stats{display:flex;gap:12px;margin:2px 0 4px;flex-wrap:wrap;}
  .statbox{flex:1;min-width:120px;background:#f3faf7;border:1px solid #d8e9e2;border-radius:14px;padding:10px 14px;text-align:center;}
  .statbox .k{font-size:12px;color:#4d6a60;}
  .statbox .v{font-size:24px;font-weight:800;color:#0d4936;margin-top:2px;}
  .statbox .u{font-size:12px;color:#4d6a60;font-weight:400;}
  .bars{margin-top:12px;}
  .bar{margin:8px 0;}
  .bar .bl{display:flex;justify-content:space-between;font-size:12px;color:#4d6a60;margin-bottom:3px;}
  .track{height:8px;background:#eef4f1;border-radius:6px;overflow:hidden;}
  .fill{height:100%;border-radius:6px;background:linear-gradient(90deg,#52b788,#2ec4a0);transition:width .5s ease;}
  .fill.warn{background:linear-gradient(90deg,#e8a04b,#e06b5b);}
  @media (prefers-reduced-motion: reduce){.fill{transition:none;}}
  .levels{display:flex;gap:14px;margin-top:12px;flex-wrap:wrap;font-size:13px;color:#1f3a33;}
  .lvl{display:flex;align-items:center;gap:8px;}
  .dots{display:flex;gap:4px;}
  .dots i{width:11px;height:11px;border-radius:50%;background:#e2ece7;}
  .dots i.on{background:#0e9f6e;box-shadow:0 1px 3px rgba(14,159,110,.4);}
  .advice{margin-top:14px;border-radius:14px;padding:12px 16px;font-size:14px;line-height:1.6;border:1px solid;}
  .advice.a1{background:#fdf0ee;border-color:#f0c4bc;color:#9c3a2c;}
  .advice.a2{background:#fdf6ec;border-color:#f0d5ae;color:#96632a;}
  .advice.a3{background:#fdfbf0;border-color:#e8dfb5;color:#7d7030;}
  .advice.a4{background:#eefaf5;border-color:#b7e3d0;color:#1f6d4c;}
  .advice.a5{background:#ecfbf8;border-color:#a9e8d8;color:#0f7a5c;}
  .advice b{display:block;margin-bottom:2px;}
  .alt{border-top:1px dashed #cfe0d9;margin-top:14px;padding-top:12px;font-size:14px;}
  .alt b{display:block;margin-bottom:6px;color:#0d4936;}
  .alt li{margin:6px 0;background:#f6faf8;border:1px solid #e0ece7;border-radius:10px;padding:8px 12px;}
  .alt .mini{display:flex;justify-content:space-between;gap:8px;align-items:center;flex-wrap:wrap;}
  .alt .s{color:#b8860b;font-weight:700;}
  .alt .ok{color:#4d6a60;font-size:14px;line-height:1.7;}
  .muted{color:#4d6a60;font-size:12px;}
  .err{background:#fff5f5;border:1px solid #f0b0b0;border-radius:12px;padding:16px 18px;margin-top:16px;color:#a33;}
  .miss{background:#fffaf0;border:1px solid #f2c47a;border-left:6px solid #f0a500;border-radius:14px;padding:16px 18px;margin-top:16px;box-shadow:0 6px 18px rgba(180,140,40,.08);}
  .miss-title{font-size:19px;font-weight:bold;color:#8a5a00;margin:0 0 8px;}
  .miss-hint{font-size:15px;line-height:1.8;margin:6px 0;}
  .pill{display:inline-block;background:#ffe9a8;border:1px solid #f0b020;color:#7a5c00;font-weight:bold;border-radius:20px;padding:5px 14px;font-size:16px;}
  .miss-note{color:#4d6a60;font-size:12px;margin-top:10px;line-height:1.7;}
  .allwrap{margin-top:24px;}
  .allwrap h2{font-size:16px;color:#0d4936;margin:0 0 8px;}
  .grid{display:flex;flex-wrap:wrap;gap:10px;max-height:400px;overflow:auto;background:#fff;border:1px solid #d8e9e2;border-radius:16px;padding:14px;box-shadow:0 3px 10px rgba(20,60,45,.05);}
  .chip{display:flex;align-items:stretch;border:1px solid #e0eae5;background:#fff;border-radius:12px;padding:0;font-family:inherit;cursor:pointer;color:#1f3a33;overflow:hidden;box-shadow:0 1px 3px rgba(20,60,45,.05);flex:1 1 230px;min-width:200px;transition:transform .12s ease,box-shadow .12s ease,border-color .12s ease;}
  .chip:hover{border-color:#12b585;box-shadow:0 4px 12px rgba(14,159,110,.14);transform:translateY(-1px);}
  .chip:focus-visible{outline:3px solid #a7e8d0;outline-offset:1px;}
  .chip-bar{width:5px;flex:none;}
  .chip-main{display:flex;flex-direction:column;gap:3px;padding:8px 11px;text-align:left;flex:1;}
  .chip-name{font-weight:600;color:#0d4936;line-height:1.35;font-size:13px;}
  .chip-meta{display:flex;align-items:center;gap:6px;font-size:11px;color:#4d6a60;}
  .chip-src{background:#eef4f1;border:1px solid #d8e9e2;border-radius:10px;padding:0 7px;}
  @media (prefers-reduced-motion: reduce){.chip{transition:none;}}
  .filters{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px;}
  .fbtn{border:1px solid #cfe0d9;background:#fff;border-radius:16px;padding:6px 13px;font-size:13px;cursor:pointer;color:#1f3a33;font-family:inherit;transition:background .12s ease,color .12s ease,border-color .12s ease;}
  .fbtn:hover{border-color:#12b585;}
  .fbtn.active{background:#2f6fed;color:#fff;border-color:#2f6fed;}
  .dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none;}
  .cat{width:100%;font-size:13px;color:#4d6a60;margin:12px 0 6px;font-weight:bold;display:flex;align-items:center;gap:8px;padding-left:10px;border-left:4px solid currentColor;line-height:1.4;}
  footer{margin-top:28px;color:#4d6a60;font-size:12px;text-align:center;line-height:1.8;}
</style>
</head>
<body>
<div class="head"><span class="logo">&#127869;&#65039;</span><h1>外卖健康星级评估</h1></div>
<p class="sub">输入菜名，查 Nutri-Score 健康星级（A~E）· 中餐（八大菜系 + 川/粤）+ 快餐 + 单位版中餐 __N__ 道真实数据 · 星级为官方绝对标准</p>
<div class="note">星级 = 欧盟 <b>Nutri-Score 官方公式</b>（绝对标准，A 最健康 ~ E 最不健康，A=5 星）；中式为去糖简化版、按每份近似、蔬果含量按 0、川/粤饱和脂肪为估算（详见 README）。分量换算：单位版菜按「整盘真实克重 ÷ 份数」得每人份；其余按「1 盘 ≈ 1 人份 ≈ 250 克」统一估算（非实测）。另有相对星级（脂肪+热量分位）作参考。涉及健康判断，仅供参考，非医学建议。</div>
<div class="stat" id="pool"></div>
<div class="search"><input id="q" placeholder="输入菜名，如：宫保鸡丁 / chicken sandwich" autocomplete="off"><button onclick="lookup()">查询</button></div>
<details class="profile"><summary>&#128100; 个人信息（选填，用于算你个人的每日所需能量）</summary>
  <div class="prow">
    <label>性别<select id="pgender"><option value="">未填</option><option value="male">男</option><option value="female">女</option></select></label>
    <label>年龄<input id="page" type="number" min="1" placeholder="岁"></label>
    <label>身高<input id="pheight" type="number" min="1" placeholder="cm"></label>
    <label>体重<input id="pweight" type="number" min="1" placeholder="kg"></label>
    <label>活动量<select id="pactivity"><option value="sedentary">久坐</option><option value="light">轻度</option><option value="moderate">中度</option><option value="active">高强度</option><option value="athlete">运动员</option></select></label>
  </div>
</details>
<div id="result"></div>
<div class="allwrap">
  <h2>全部可查菜品（<span id="allcount"></span> 道，滚动查看；川/粤/快餐中文名为人工译名，单位版菜名仅英文，仅供参考）</h2>
  <div class="filters" id="filters"></div>
  <div id="all" class="grid"></div>
</div>
<script>
const DATA = __DATA__;
const ADVICE = __ADVICE__;
const LEVEL = __LEVEL__;
const POOL = __POOL__;
const BRAND_COLORS = {
  '中餐': '#c0392b', '麦当劳': '#f5a623', 'Chick-fil-A': '#c8102e', 'Sonic': '#2f80ed',
  "Arby's": '#a0522d', '汉堡王': '#d94f00', 'DQ': '#d35400', '赛百味': '#00843d', '塔可钟': '#7d3f98',
  '川菜': '#c0392b', '鲁菜': '#8e5f2b', '粤菜': '#2e9e6b', '苏菜': '#e67e22',
  '闽菜': '#f39c12', '浙菜': '#27ae60', '徽菜': '#a0522d', '湘菜': '#e74c3c'
};
function colorFor(cat){
  if (BRAND_COLORS[cat]) return BRAND_COLORS[cat];
  const fallback = ['#16a085','#2980b9','#c0392b','#8e44ad','#d35400','#27ae60','#f39c12','#8e5f2b','#7a8c9e','#2c3e50'];
  let h = 0;
  for (const ch of cat) h = (h * 31 + ch.codePointAt(0)) >>> 0;
  return fallback[h % fallback.length];
}
const EMOJI = {
  '川菜':'\U0001F336','鲁菜':'🥟','粤菜':'🍵','苏菜':'🦐','闽菜':'\U0001F980','浙菜':'\U0001F969','徽菜':'🍲','湘菜':'🥘',
  '麦当劳':'🍟','汉堡王':'🍔','Chick-fil-A':'🐔','Sonic':'🌭',"Arby's":'🥩','DQ':'🍦','赛百味':'🥪','塔可钟':'🌮'
};
function emojiOf(c){ return EMOJI[c] || '🍽'; }

document.getElementById('pool').textContent = POOL;

const SC_DEDUP = __SC_DEDUP__;
const ACTIVITY = {'sedentary':1.2,'light':1.375,'moderate':1.55,'active':1.725,'athlete':1.9};
function getTdee(){
  // Mifflin-St Jeor 基础代谢 + 活动系数 = 每日总能量消耗(TDEE)；未填或无效则回退 2000
  const g = document.getElementById('pgender').value;
  const age = parseFloat(document.getElementById('page').value);
  const h = parseFloat(document.getElementById('pheight').value);
  const w = parseFloat(document.getElementById('pweight').value);
  const act = document.getElementById('pactivity').value;
  if (!g || !(age > 0) || !(h > 0) || !(w > 0)) return { tdee: 2000, personalized: false };
  const bmr = 10 * w + 6.25 * h - 5 * age + (g === 'male' ? 5 : -161);
  const tdee = Math.round(bmr * (ACTIVITY[act] || 1.2));
  return { tdee: tdee, personalized: true };
}
function matchExact(name){
  // 仅精确匹配：英文原名、川粤英文译回中文、中文译名
  const key = name.trim().toLowerCase();
  let hit = DATA.find(d => d.food_name.trim().toLowerCase() === key);
  if (hit) return hit;
  const trans = SC_DEDUP[name.trim()];
  if (trans){
    hit = DATA.find(d => String(d.food_name_cn || '').trim() === trans);
    if (hit) return hit;
  }
  const cn = name.trim();
  hit = DATA.find(d => String(d.food_name_cn || '').trim() === cn);
  return hit || null;
}

function matchCandidates(name){
  // 模糊候选：所有英文名或中文译名包含输入词的菜（去重）
  const key = name.trim().toLowerCase();
  const cn = name.trim();
  const seen = new Set();
  const out = [];
  const push = d => { if (!seen.has(d.food_name)) { seen.add(d.food_name); out.push(d); } };
  for (const d of DATA){
    const en = d.food_name.toLowerCase();
    const zh = String(d.food_name_cn || '');
    if (en.includes(key) || zh.includes(cn)) push(d);
  }
  return out;
}

function match(name){
  // 兼容旧调用：先精确，再取模糊候选第一条（demo 风格）
  const exact = matchExact(name);
  if (exact) return exact;
  const cands = matchCandidates(name);
  return cands.length ? cands[0] : null;
}

function alternatives(row){
  if (row.nutri_star >= 4) return null;
  const cand = DATA.filter(d => d.source === row.source && d.nutri_star >= 4);
  if (!cand.length) return null;
  cand.sort((a,b) => (b.nutri_star - a.nutri_star) || (a.calories - b.calories));
  return cand.slice(0,2);
}

function lookup(){
  const el = document.getElementById('q');
  const box = document.getElementById('result');
  const name = el.value;
  if (!name.trim()){ box.innerHTML = '<div class="err">请输入菜名</div>'; return; }
  const row = matchExact(name);
  if (row){ renderCard(row, box); return; }
  const cands = matchCandidates(name);
  if (cands.length){
    renderCandidates(cands, name, box);
    return;
  }
  const hint = keywordHint(name);
  box.innerHTML = '<div class="miss">'
    + '<div class="miss-title">\u2753 数据里没有这道菜</div>'
    + '<div class="miss-hint">关键词提示：<span class="pill">' + hint + '</span></div>'
    + '<div class="miss-note">（控制台版可用模型粗估星级；网页版为纯静态页面，仅做关键词猜测）<br>请人工判断，以真实菜单营养信息为准。</div>'
    + '</div>';
}

let candState = { cands: [], shown: 0 };
const CAND_PAGE = 24;

function renderCandidates(cands, name, box){
  candState = { cands, shown: CAND_PAGE };
  drawCandidates(name, box);
}

function drawCandidates(name, box){
  const { cands, shown } = candState;
  let html = '<div class="card candcard"><div class="cand-title">\u2753 找到 ' + cands.length
    + ' 道含「' + esc(name) + '」的菜，请选择：</div><div class="cand-grid">';
  cands.slice(0, shown).forEach(d => { html += chip(d); });
  html += '</div>';
  if (cands.length > shown){
    html += '<div class="candmore"><button type="button" class="morebtn" onclick="candMore()">'
      + '显示更多（' + shown + '/' + cands.length + '）</button></div>';
  } else if (shown > CAND_PAGE){
    html += '<div class="candmore"><button type="button" class="morebtn" onclick="candLess()">收起</button></div>';
  }
  html += '</div>';
  box.innerHTML = html;
}

function candMore(){
  const box = document.getElementById('result');
  candState.shown = Math.min(candState.shown + CAND_PAGE, candState.cands.length);
  drawCandidates(document.getElementById('q').value, box);
}

function candLess(){
  const box = document.getElementById('result');
  candState.shown = CAND_PAGE;
  drawCandidates(document.getElementById('q').value, box);
}

function renderCard(row, box){
  const star = row.nutri_star, grade = row.nutri_grade || '';
  const fatL = row.fat_level, calL = row.cal_level;
  const reason = fatL < calL ? '脂肪偏高' : (calL < fatL ? '热量偏高' : '脂肪、热量同档');
  const t = getTdee();
  const daily = Math.round(row.calories / t.tdee * 100);
  const calR = Math.round(row.calories), fatR = Math.round(row.fat * 10) / 10;
  const cn = (row.food_name_cn && row.food_name_cn !== row.food_name) ? '（' + row.food_name_cn + '）' : '';
  const starCap = {1:'高油高热量，尽量少点',2:'偏高油热量，少吃',3:'正常水平，偶尔吃',4:'相对清淡，可常吃',5:'低油低热量，优先选'};
  let html = '<div class="card">';
  html += '<div class="card-top"><div class="name">' + row.food_name + cn + '</div><span class="src">' + row.source + '</span></div>';
  html += '<div class="star-banner s' + star + '">'
        + '<div class="bigscore">' + star + '<small>/5 · ' + grade + '</small></div>'
        + '<div><div class="stars">' + stars(star) + '</div>'
        + '<div class="starcap">' + starCap[star] + ' · 星级 = 欧盟 Nutri-Score 官方公式（绝对标准）</div></div>'
        + '</div>';
  html += portionNote(row);
  html += '<div class="cbody">';
  let extraStats = '';
  if (row.sodium_mg != null && Number.isFinite(row.sodium_mg)) {
    extraStats += '<div class="statbox"><div class="k">钠</div><div class="v">' + Math.round(row.sodium_mg) + '<span class="u"> 毫克</span></div></div>';
  }
  if (row.carbon_g != null && Number.isFinite(row.carbon_g)) {
    extraStats += '<div class="statbox"><div class="k">碳足迹</div><div class="v">' + Math.round(row.carbon_g) + '<span class="u"> 克</span></div></div>';
  }
  html += '<div class="stats">'
        + '<div class="statbox"><div class="k">热量</div><div class="v">' + calR + '<span class="u"> 大卡</span></div></div>'
        + '<div class="statbox"><div class="k">脂肪</div><div class="v">' + fatR + '<span class="u"> 克</span></div></div>'
        + extraStats
        + '<div class="statbox"><div class="k">' + (t.personalized ? '你的每日所需 ≈ ' + t.tdee + ' 大卡' : '每日 2000 大卡参考') + '</div><div class="v">' + daily + '<span class="u">%</span></div></div>'
        + '</div>';
  html += '<div class="bars">'
        + '<div class="bar"><div class="bl"><span>热量高于全表</span><span>' + row.cal_pct + '%</span></div><div class="track"><div class="fill' + (row.cal_pct > 66 ? ' warn' : '') + '" style="width:' + row.cal_pct + '%"></div></div></div>'
        + '<div class="bar"><div class="bl"><span>脂肪高于全表</span><span>' + row.fat_pct + '%</span></div><div class="track"><div class="fill' + (row.fat_pct > 66 ? ' warn' : '') + '" style="width:' + row.fat_pct + '%"></div></div></div>'
        + '</div>';
  html += '<div class="levels">'
        + '<div class="lvl">脂肪档 <b>' + fatL + '/5</b><span class="dots">' + dots(fatL) + '</span></div>'
        + '<div class="lvl">热量档 <b>' + calL + '/5</b><span class="dots">' + dots(calL) + '</span></div>'
        + '<div class="lvl">拉低主因：<b>' + reason + '</b></div>'
        + '</div>';
  html += '<div class="advice a' + star + '"><b>' + star + ' 星：' + ADVICE[star] + '</b>相对全表，这道 ' + reason + '，请结合整餐安排判断（参考值，非医学建议）。</div>';
  const alt = alternatives(row);
  if (alt){
    html += '<div class="alt"><b>\u2728 更清淡的同源替代</b><ul>';
    alt.forEach(a => {
      const acn = (a.food_name_cn && a.food_name_cn !== a.food_name) ? '（' + a.food_name_cn + '）' : '';
      html += '<li><div class="mini"><span>' + a.food_name + acn + '</span><span class="s">' + a.health_star + ' \u2605</span></div>'
            + '<div class="muted">' + Math.round(a.calories) + ' 大卡 / 脂肪 ' + (Math.round(a.fat * 10) / 10) + ' 克</div></li>';
    });
    html += '</ul></div>';
  } else {
    html += '<div class="alt"><b>\u2728 更清淡的同源替代</b><div class="ok">\u2714 这道在同源菜里已算清淡，无需替换</div></div>';
  }
  html += '</div></div>';
  box.innerHTML = html;
}
document.getElementById('q').addEventListener('keydown', e => { if (e.key === 'Enter') lookup(); });

function portionNote(row){
  // 分量换算：不同菜盘大小重量不同，统一折算成「每人份」再显示。
  //   单位版菜：真实克重 Weight(g) ÷ 份数 servings = 每份克数；每份热量 = 整盘热量 ÷ 份数
  //   其他菜：数据无真实克重，按「1 盘 ≈ 1 人份 ≈ 250 克」统一估算；每份热量 = 整盘热量
  const s = row.servings && row.servings > 0 ? row.servings : 1;
  const kcal = Math.round(row.calories / s);
  const base = '<div style="font-size:12.5px;color:#4a6357;background:#eef6f2;border-radius:10px;padding:10px 14px;margin:0 0 12px;line-height:1.7">';
  if (row.weight_g != null && Number.isFinite(row.weight_g)){
    const g = Math.round(row.weight_g / s);
    return base + '\U0001F37D 分量：每份约 <b>' + g + ' 克</b> · 每份约 <b>' + kcal + ' 大卡</b>' +
      '<div style="margin-top:4px;opacity:.85">怎么算：整盘 ' + Math.round(row.weight_g) + ' 克 \u00f7 ' + s + ' 人份 = 每份约 ' + g + ' 克；整盘 ' + Math.round(row.calories) + ' 大卡 \u00f7 ' + s + ' 人份 = 每份约 ' + kcal + ' 大卡（数据带真实克重）</div></div>';
  }
  return base + '\U0001F37D 分量：每份约 <b>250 克</b> · 每份约 <b>' + kcal + ' 大卡</b>' +
    '<div style="margin-top:4px;opacity:.85">怎么算：数据没有真实克重，按「1 盘 \u2248 1 人份 \u2248 250 克」统一估算；每份热量 = 整盘 ' + Math.round(row.calories) + ' 大卡 \u00f7 1 人份（统一参照值，非实测）</div></div>';
}
function stars(n){ return '\u2605'.repeat(n) + '\u2606'.repeat(5 - n); }
function dots(n){ let s=''; for (let i=1;i<=5;i++){ s += '<i' + (i<=n ? ' class="on"' : '') + '></i>'; } return s; }
function keywordHint(name){
  const heavy = ['炸','煎','酥','红烧','干煸','回锅','干锅','炸鸡','脆'];
  const light = ['蒸','煮','清炒','清汤','白灼','凉拌','炖','涮'];
  if (heavy.some(w => name.includes(w))) return '按常见做法通常偏油（猜测）';
  if (light.some(w => name.includes(w))) return '按常见做法通常较清淡（猜测）';
  return '无法仅凭菜名判断（猜测）';
}
function esc(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function renderAll(){
  const sorted = [...DATA].sort((a,b) => a.source === b.source
    ? a.food_name.localeCompare(b.food_name, 'zh')
    : a.source.localeCompare(b.source, 'zh'));
  document.getElementById('allcount').textContent = DATA.length;
  const cat = currentCat === '全部' ? null : currentCat;
  const rows = cat ? sorted.filter(d => d.category === cat) : sorted;
  let html = '';
  if (cat){
    html = rows.map(chip).join('');
  } else {
    const cats = ['中餐', ...[...new Set(DATA.map(d => d.category))].filter(c => c !== '中餐')];
    for (const c of cats){
      const group = rows.filter(d => d.category === c);
      if (!group.length) continue;
      html += '<div class="cat" style="color:' + colorFor(c) + '">' + emojiOf(c) + ' ' + esc(c) + '（' + group.length + '）</div>';
      html += group.map(chip).join('');
    }
  }
  document.getElementById('all').innerHTML = html;
}
function chip(d){
  const col = colorFor(d.category);
  const main = esc(d.food_name);
  const cn = (d.food_name_cn && d.food_name_cn !== d.food_name) ? '（' + esc(d.food_name_cn) + '）' : '';
  return '<button type="button" class="chip" onclick="go(' + DATA.indexOf(d) + ')">' +
    '<span class="chip-bar" style="background:' + col + '"></span>' +
    '<span class="chip-main">' +
      '<span class="chip-name">' + main + cn + '</span>' +
      '<span class="chip-meta">' +
        '<span class="chip-src" style="color:' + col + '">' + emojiOf(d.category) + ' ' + esc(d.category) + '</span>' +
      '</span>' +
    '</span>' +
    '</button>';
}
let currentCat = '全部';
function renderFilters(){
  const cats = ['全部', ...new Set(DATA.map(d => d.category))];
  document.getElementById('filters').innerHTML = cats.map(c => {
    const col = colorFor(c);
    const active = c === currentCat;
    return '<button type="button" class="fbtn' + (active ? ' active' : '') + '" data-cat="' + esc(c) + '"' +
      (active ? ' style="background:' + col + ';border-color:' + col + ';color:#fff"' : '') + '>' +
      '<span class="dot" style="background:' + col + '"></span>' + (c === '全部' ? '全部' : emojiOf(c) + ' ' + esc(c)) + '</button>';
  }).join('');
}
document.getElementById('filters').addEventListener('click', e => {
  const b = e.target.closest('.fbtn');
  if (b) setCat(b.dataset.cat);
});
function setCat(c){ currentCat = c; renderFilters(); renderAll(); }
renderFilters();
renderAll();

function go(i){
  document.getElementById('q').value = DATA[i].food_name;
  lookup();
  document.getElementById('result').scrollIntoView({behavior:'smooth', block:'start'});
}
</script>
<footer>本工具为课程项目演示：星级按欧盟 Nutri-Score 公式派生（中式去糖简化、每份近似、蔬果按 0）；营养参考值非医学建议。<br>数据：__N__ 道真实菜（中餐八大菜系 320 + 川菜/粤菜 __SC__ + 快餐 515 + 单位版中餐 __U__）；钠/碳足迹仅单位版菜有值，查不到的菜请以真实菜单营养信息为准。</footer>
</body>
</html>
"""


# 川粤数据中与八大菜系同名的 27 道菜（去重掉），英文名 -> 中文名，
# 供网页版英文搜索仍能命中八大菜系里的同一道菜。
SC_DEDUP = {
    "Ants Climbing Trees (Spicy Vermicelli with Minced Pork)": "蚂蚁上树",
    "Bang Bang Chicken Shreds": "棒棒鸡丝",
    "Blanched Vegetable Stems": "白灼菜心",
    "Boiled Pork Slices": "水煮肉片",
    "Clear Stewed Soft-Shelled Turtle": "清炖甲鱼",
    "Cold Mixed Purslane": "凉拌马齿苋",
    "Couple's Sliced Beef and Ox Tripe": "夫妻肺片",
    "Cured Meat Clay Pot Rice": "腊味煲仔饭",
    "Dongjiang Salted Chicken": "东江盐焗鸡",
    "Dry Fried Beef Ho Fun": "干炒牛河",
    "Dry-fried Green Beans": "干煸四季豆",
    "Fish-flavored Pork Shreds": "鱼香肉丝",
    "Golden Corn": "金沙玉米",
    "Kung Pao Chicken": "宫保鸡丁",
    "Lychee Pork": "荔枝肉",
    "Mapo Tofu": "麻婆豆腐",
    "Pickled Pepper Bullfrog": "泡椒牛蛙",
    "Pickled Pepper Chicken Feet": "泡椒凤爪",
    "Pineapple Sweet and Sour Pork": "菠萝咕噜肉",
    "Poached Chicken": "白切鸡",
    "Sliced Pork with Garlic Sauce": "蒜泥白肉",
    "Spicy Shrimp": "香辣虾",
    "Steamed Ribs in Black Bean Sauce": "豉汁蒸排骨",
    "Sweet and Sour Pork": "糖醋里脊",
    "Taiji Taro Paste": "太极芋泥",
    "Twice-cooked Pork": "回锅肉",
    "White-cut Chicken": "白切鸡",
}


def main():
    df = pd.read_csv(os.path.join(PROC, "merged.csv"))
    df["cal_pct"] = df["calories"].rank(pct=True).mul(100).round().astype(int)
    df["fat_pct"] = df["fat"].rank(pct=True).mul(100).round().astype(int)

    rows = df[["food_name", "food_name_cn", "source", "category", "calories", "fat",
               "health_star", "nutri_star", "nutri_grade",
               "fat_level", "cal_level", "cal_pct", "fat_pct",
               "sodium_mg", "sat_fat_g", "carbon_g", "water_l", "land_m2",
               "servings", "weight_g"]].to_dict("records")
    avg_cal = df["calories"].mean()
    avg_fat = df["fat"].mean()
    pool_text = (
        f"全表统计：共 {len(df)} 道菜，平均 {avg_cal:.0f} 大卡 / 脂肪 {avg_fat:.1f} 克 "
        f"—— 若整体偏高，星级只是相对排序。"
    )

    sc_n = int(df["source"].isin(["川菜", "粤菜"]).sum())
    unit_n = int(df["source"].eq("中餐单位版").sum())
    html = (HTML_TEMPLATE
            .replace("__DATA__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__ADVICE__", json.dumps(ADVICE, ensure_ascii=False))
            .replace("__LEVEL__", json.dumps(LEVEL, ensure_ascii=False))
            .replace("__POOL__", json.dumps(pool_text, ensure_ascii=False))
            .replace("__SC_DEDUP__", json.dumps(SC_DEDUP, ensure_ascii=False))
            .replace("__N__", str(len(df)))
            .replace("__SC__", str(sc_n))
            .replace("__U__", str(unit_n)))

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成:", TARGET)
    print("双击用浏览器打开即可使用（无服务器）。")


if __name__ == "__main__":
    main()
