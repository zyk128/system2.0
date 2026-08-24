"""FINAL · 数据契约测试：真实数据规模、标签范围、防泄漏、必要特征。

中美两套标准、两个独立模型，各自防泄漏：
- 美式标签列 = calories/sat_fat/sodium/fiber/sugar/protein；
- 中式标签列 = calories/sat_fat/sodium/fiber/protein（无 sugar）；
- 两者特征都不能含标签列，也不能含会间接泄露的 total_fat/total_carb/cal_fat。

用法：python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd

LABELED = Path("data/processed/food_labeled.csv")
US_TR = Path("data/processed/us_train.csv")
CN_TR = Path("data/processed/cn_train.csv")

US_LABEL = ["calories", "sat_fat", "sodium", "fiber", "sugar", "protein"]
CN_LABEL = ["calories", "sat_fat", "sodium", "fiber", "protein"]
LEAK = ["total_fat", "total_carb", "cal_fat"]


class TestDataContract(unittest.TestCase):
    def setUp(self):
        self.df = pd.read_csv(LABELED)
        self.us = pd.read_csv(US_TR)
        self.cn = pd.read_csv(CN_TR)

    @staticmethod
    def _feat_cols(df: pd.DataFrame) -> list[str]:
        """特征列 = 训练表里去掉目标列(health_star/calories)。"""
        return [c for c in df.columns if c not in ("health_star", "calories")]

    def test_row_count(self):
        """合并后至少 3500 道真实菜（美式 500 + 中式 3300）。"""
        self.assertGreaterEqual(len(self.df), 3500)

    def test_two_sources(self):
        """必须同时覆盖美式与中式两套数据。"""
        self.assertEqual(set(self.df["source"].unique()), {"us", "china"})

    def test_star_range(self):
        """健康星级必须是 1~5。"""
        self.assertTrue(self.df["health_star"].between(1, 5).all())

    def test_nutri_grade_range(self):
        """Nutri-Score 档位必须是 A~E。"""
        self.assertTrue(self.df["nutri_grade"].isin(list("ABCDE")).all())

    def test_us_features_exclude_label_cols(self):
        """防泄漏：美式特征列不能含完整 Nutri-Score 的 6 项输入。"""
        feats = self._feat_cols(self.us)
        for col in US_LABEL:
            self.assertNotIn(col, feats)

    def test_cn_features_exclude_label_cols(self):
        """防泄漏：中式特征列不能含简化 Nutri-Score 的 5 项输入。"""
        feats = self._feat_cols(self.cn)
        for col in CN_LABEL:
            self.assertNotIn(col, feats)

    def test_features_exclude_leak_cols(self):
        """防泄漏：会间接泄露标签的列不能出现在任一来源的特征列里。"""
        for col in LEAK:
            self.assertNotIn(col, self._feat_cols(self.us))
            self.assertNotIn(col, self._feat_cols(self.cn))

    def test_required_features_present(self):
        """每个来源模型需要的特征列齐全。"""
        for col in ["item", "cuisine", "trans_fat", "cholesterol"]:
            self.assertIn(col, self.us.columns)
        for col in ["item", "cuisine", "cholesterol", "vit_c", "iron", "mono"]:
            self.assertIn(col, self.cn.columns)


if __name__ == "__main__":
    unittest.main()
