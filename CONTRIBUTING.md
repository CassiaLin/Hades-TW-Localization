# Contributing Guide

感謝您協助改善《黑帝斯》（Hades 1）台灣繁體中文化！

## 回報翻譯錯誤或提出 PR
1. 若僅回報錯字、漏譯或語氣建議，請直接使用 [Translation Feedback Issue 範本](.github/ISSUE_TEMPLATE/translation_feedback.yml)。
2. 若想提交修改 PR：
   - 請先在本機依 [Developer Guide](docs/DEVELOPER_GUIDE.md) 執行 `dev extract`、`dev import`、`dev build`、`dev qa` 與 `dev export`。
   - 嚴禁將遊戲原始 `.sjson`、`.csv`、`.xnb` 或本機 `workspace/`、`extracted/` 目錄納入 Git 提交，僅提交 `translations/hades1/`、`tools/`、`docs/`、`glossary/` 或 `tests/` 的變更。
   - 提交前請務必確認 `pytest` 與 `python tools/package_public.py --out-dir ... --overwrite` 全數通過。
