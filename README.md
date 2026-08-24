# AI 工程营最终项目：外卖健康星级评估（Nutri-Score 官方标准）

一个端到端可运行的小型真实数据项目：根据一道菜的「菜名 + 菜系/餐厅 + 公开营养标签」判断健康星级（1~5，对应**欧盟官方 Nutri-Score A~E**），并顺带估计热量。主任务是**分类（健康星级）**，热量是辅助回归。

覆盖**两套真实数据、两个独立模型**：美式快餐（完整 Nutri-Score）+ 中国菜（八大菜系，去糖简化 Nutri-Score）。提供控制台演示和**网页版交互界面**C:\2026ai\ai-summer-camp-2026\student-work\另存无\数据集。

## 问题

- **使用者**：想控水肿/控盐/控油/控热量的外卖党，点餐前想快速判断某道菜是否健康、大概多少热量。
- **真实输入**：
  - 美式：Kaggle Fast Food Nutrition 的 `fastfood.csv`（8 家连锁、515 道菜）；
  - 中式：Figshare 公开数据集 `29977027` 的营养表 `Nutritional_content-unit.xlsx`（闽/徽/浙/鲁/苏/湘 6 大菜系、3302 道菜）+ 同源姊妹数据集 `28457018` 的 `Sichuan cuisines.xlsx` / `Cantonese cuisines.xlsx`（川/粤 2 大菜系、各 500 道），共八大菜系、4302 道菜。
- **核心问题**：把「菜名 + 营养标签」映射成 1~5 的健康星级，帮使用者避开高油高盐高热量。
- **任务类型**：分类（健康星级 1~5，Nutri-Score A~E）；热量估计是辅助回归。

## 真实数据

| 数据 | 文件 | 规模 | 菜系/餐厅 |
| --- | --- | --- | --- |
| 美式快餐 | `data/raw/fastfood.csv` | 515 → 清洗后 503 | 8 家美国连锁 |
| 中国菜（6 菜系） | `data/raw/nutritional_content_unit.xlsx` | 3302（无缺失） | 闽/徽/浙/鲁/苏/湘 |
| 中国菜（川/粤） | `data/raw/Sichuan cuisines.xlsx` + `Cantonese cuisines.xlsx` | 1000（各 500） | 川/粤 |

- 校验：`python data_process.py --check-data` 输出 `REAL DATA CHECK PASSED`。
- 注：中国菜数据集的菜名是**英文**（如 Mapo Tofu=麻婆豆腐、Yangzhou Fried Rice with Eggs=扬州炒饭），搜索时用英文名。

### 健康星级怎么来（官方标准 Nutri-Score，可复现）

星级 = **欧盟官方营养标签系统 Nutri-Score（A~E）**，A 最健康、E 最不健康。按官方公式**绝对打分**：

- **扣分（0~40）**：热量（能量 kJ）、糖、饱和脂肪、钠，各按官方阈值表 0~10 分；
- **加分**：纤维、蛋白（蔬果/坚果含量数据缺失，按 0，偏保守）；
- 得分映射 A~E：`A(≤-1) / B(0~2) / C(3~10) / D(11~18) / E(≥19)`，再 A~E → 1~5 星（A=5、B=4、C=3、D=2、E=1）。

这是**绝对标准**，不是相对排序：即使所有菜都是垃圾食品也全落 D/E，**不会「矮子里拔高个」**。

### 两套标准（数据限制，非糊弄）

因为中国菜成分表**只记录总碳水化合物、不单列「糖」**（糖是 Nutri-Score 的 6 项输入之一），所以：

- **美式**：6 项输入齐全 → 用**完整 Nutri-Score（含糖项）**；
- **中式**：只有 5 项 → 用**去糖简化 Nutri-Score**。

中式缺糖、扣分少一项，得分整体偏低（偏健康），因此**两套标签不横向比较**，各自独立建模。这是数据缺口导致的诚实取舍，不是糊弄。

三个必须说清的近似：1) 官方按每 100g 算，本数据无每份重量，按每份近似（中式按整盘报告，除以 `Serving` 份数对齐到一份）；2) 蔬果/坚果含量按 0（真实沙拉会被算得偏严，但绝不虚高）；3) 川/粤数据集缺「饱和/单/多不饱和脂肪酸」三列（饱和脂肪是 Nutri-Score 扣分输入），用 6 菜系数据拟合的「总脂肪 → 各脂肪酸」中位比例估算（饱和脂肪 ≈ 总脂肪 × 0.132），近似值、已显式标注。

### 防泄漏（关键）

标签由营养素列按 Nutri-Score 派生，因此特征里**刻意排除这些列**，以及会间接泄露它们的列：

- 美式标签列 = `calories/sat_fat/sodium/fiber/sugar/protein`；泄露列 = `cal_fat/total_fat/total_carb`。特征 = **菜名 + 餐厅 + 反式脂肪 + 胆固醇**。
- 中式标签列 = `calories/sat_fat/sodium/fiber/protein`（无糖）；泄露列 = `total_fat/total_carb`。特征 = **菜名 + 菜系 + 胆固醇 + 灰分/维生素/矿物质/单多不饱和脂肪酸（20 个非标签营养素）**。

## 环境

- Windows 11 + Python 3.12
- 依赖见 `requirements.txt`（核心 pandas/scikit-learn/numpy/joblib/openpyxl；网页需要 flask）

## 目录结构

```
.
├── README.md / report.md / submission.json / presentation.pptx
├── requirements.txt / .gitignore
├── data_process.py     # 数据契约 + 清洗 + Nutri-Score 星级 + 两来源划分
├── baseline.py         # 多数类基线（中美分开）
├── train_model.py      # 两个候选模型 + 指标 + 特征重要性
├── demo.py             # 控制台交互演示
├── app.py              # 网页版前端（Flask，交互界面）
├── tests/test_data.py  # 数据契约 + 防泄漏测试
├── data/raw/           # 真实数据（不提交）
├── data/processed/     # 生成的划分（不提交）
└── models/             # 训练好的模型（不提交）
```

## 安装

```powershell
python -m pip install -r requirements.txt
```

## 运行命令（仓库根目录 final-project）

```powershell
python data_process.py --check-data   # 1. 数据契约
python data_process.py                # 2. 清洗+打标签+划分
python baseline.py                    # 3. 基线（中美分开）
python train_model.py                 # 4. 两个候选模型
python demo.py                        # 5. 控制台演示
python app.py                         # 6. 网页版前端 → 浏览器打开 http://127.0.0.1:5000
python -m unittest discover -s tests -v   # 7. 单元测试（8 个）
```

## 网页版前端（app.py）

`python app.py` 后浏览器打开 http://127.0.0.1:5000，功能：

- **中文/英文输入**：中国菜数据集的菜名是英文（Mapo Tofu、Kung Pao Chicken…），内置了中文别名词典（`dish_translate.py`），输入「麻婆豆腐」「糖醋里脊」等常见中文菜名也能查到（营养数值 100% 来自原始数据，词典只是菜名翻译）。
- **自动补全**：输入即提示中/英文菜名。
- **彩色星级卡片**：不同 Nutri-Score 档位（A~E）配对应颜色（绿→黄→橙→红），结果卡片边框/底纹随星级变色。
- **更健康的同类建议**：推荐「同菜系/同餐厅里星级更高」的真实菜品，点击可切换查看。
- **明确拒绝**：不在 4805 道菜范围内的菜名不硬猜。

## 结果速览（本机真实运行）

| 项目 | 美式（完整 Nutri-Score） | 中式（简化 Nutri-Score） |
| --- | ---: | ---: |
| 规模 | 503 道 | 4302 道 |
| Nutri-Score 分布 | A19/B25/C49/D161/E249 | A498/B891/C997/D1462/E454 |
| 星级准确率 | **69.31%**（70/101） | **48.55%**（418/861） |
| 多数类基线 | 49.50% | 34.03% |
| 严重误判率（≤2↔≥4） | 2.97% | 9.52% |
| 热量 MAE | 86.8 大卡（基线 213.2） | 76.4 大卡（基线 143.8） |

- 成功案例：`Big Mac` → 判 E/真 E（估 557/真 540 大卡）；`Mapo Tofu` → 判 D/真 D；`Beer-Braised Duck` → 判 A/真 A。
- 失败案例：`Premium Asian Salad w/o Chicken` 真 A（5 星）被判 D（2 星）——菜名里 "Asian"（高钠酱汁共现）和 "Chicken"（炸鸡三明治共现）把模型带偏。

## 限制

- 只覆盖 8 家美国连锁 + 八大中国菜系的 4805 道菜；数据外的菜明确拒绝评估。
- 星级是 Nutri-Score **每份近似**（无每份重量、无蔬果含量），不是官方每 100g 标签；中式为去糖简化版，与美式不直接可比。
- 中式 5 档更均衡、任务更难，准确率 48.55% 虽低于美式 69.31%，但仍是基线的约 1.4 倍；美式准确率高有「约 82% 集中在 D/E 两档」的成分。
- 结果仅供点餐参考，**不构成医疗/营养建议**；涉及水肿、高血压等健康问题请咨询医生/营养师。
