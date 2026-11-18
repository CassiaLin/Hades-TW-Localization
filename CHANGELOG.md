# Changelog

## v0.1.0-beta.1 — 2026-11-19

### Added
- 完整完成《黑帝斯》（Hades 1）台灣繁體中文化（`18` 個 `.sjson` 共 `12,280` 筆欄位，與 `37` 個字幕 `.csv` 共 `14,109` 筆不重複條目）。
- 全部文本從英文原文重譯，角色與機制術語對齊《黑帝斯 II》官方繁中，修復原版簡中錯譯與台灣慣用標點（`「」`、`『』`、`〈〉`、`⋯⋯`）。
- 實作 `tools/xnb_font.py` 無壓縮 `XNBw v6` SpriteFont 擴充引擎，隨附 SIL OFL 1.1 `NotoSansTC-Medium.otf`，於玩家端動態補齊 `Default.xnb`（`+1,364` 字）與六語系 `zh-CN.xnb`（`+2` 字），遊戲內與「語言 / 繁體中文」選單均為 0 缺字。
- 建立 Dual-Mode CLI (`hades_mod_cli.py`)、中文互動安裝程式 (`Install_TW_Mod.bat`)、交易式 SHA-256 備份引擎 (`_Backup_TW_Mod/manifest.json`)、以及 `tools/package_public.py` 公開發布審計管線。
