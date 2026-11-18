# Hades-TW-Localization Developer Guide

本專案支援 **Dual-Mode** 架構：
- **Player Mode**：僅依賴 `translations/hades1/` 純中文譯文包與內附 SIL OFL 1.1 `NotoSansTC-Medium.otf`，於玩家本機從原版遊戲即時提取、合成、補字並交易式安裝。
- **Developer / Translator Mode**：整合 `M1 ~ M5` 流程，讓任何開發者、譯者或 AI Agent 能將遊戲文本轉為結構化 JSON、批次重翻／微調、QA 驗證並回填回遊戲。

## Developer CLI 工作流程 (`dev`)

```bash
# 1. M1：從本機遊戲（若已安裝 Mod 則自動讀取 _Backup_TW_Mod/Content 原檔）抽出 AI 友善 JSON
python hades_mod_cli.py dev extract

# 2. M2：將抽出來的文本依每批 200 筆切成 batch_XXXX_*.input.json，並附上含術語表的 AI Prompt
python hades_mod_cli.py dev prepare --batch-size 200

# 3. 人工或 AI Agent 產出修改後的 *.json / *.jsonl 後，匯入至譯文包
python hades_mod_cli.py dev import --from-dir path/to/outputs

# 4. M5：重新合成 .sjson、.csv 與自動補字後的 .xnb 至 dist/Hades_TW_Mod/
python hades_mod_cli.py dev build

# 5. M4：執行全面 QA（檢查 ID、標籤數量、標點符號與 Default.xnb / zh-CN.xnb 缺字）
python hades_mod_cli.py dev qa

# 6. 交易式安裝回 Steam 遊戲目錄測試
python hades_mod_cli.py dev install

# 7. 若從已修改的遊戲/輸出目錄反向匯出純中文譯文包至 translations/hades1/
python hades_mod_cli.py dev export
```

## 資料格式說明

- **M1 提取輸出 (`workspace/hades1/extracted/`)**：
  - `sjson/<File>.json`：`{"id", "field", "cn", "en", ["speaker"], ["en_context"], ["tags"]}`（僅保留於本機，不進入公開倉庫）。
  - `subtitles/<File>.json`：`{"file", "row_id", "status", "en", "cn"}`。
- **M3 匯入格式 (`dev import --from-dir`)**：
  - 支援 JSON 陣列（`.json`）或每行一筆 JSON（`.jsonl`）：
    - SJSON：`{"file": "HelpText.zh-CN.sjson", "id": "GodMode", "field": "DisplayName", "zh": "神力模式"}`
    - Subtitles：`{"file": "ZagreusHome.csv", "row_id": "ZagreusHome_0002a", "zh": "我回家了⋯⋯"}`
- **公開純中文譯文包 (`translations/hades1/`)**：
  - `sjson_zh_tw.jsonl`（18 檔、12,280 筆欄位）、`subtitles_zh_tw.jsonl`（37 檔、14,109 筆 RowId）、`languages_zh_tw.json` 與 `manifest.json`（SHA-256 驗證）。
  - 完全不含任何遊戲英文原文或 `.sjson`/`.csv`/`.xnb` 二進位檔。

## XNB 字型動態補字機制 (`tools/xnb_font.py`)
- 《黑帝斯 1》採用無壓縮 `XNBw\x06\x00`（`SurfaceFormat = 12`，8-bit 灰階 Alpha 圖集）且 `CharacterMap` 須嚴格依 Unicode 碼位遞增排列。
- `tools/m5_build.py` 會先掃描全數翻譯完成後的文本，保留原版字型所有既有字形與座標，並以 `NotoSansTC-Medium.otf` 自動渲染缺少的繁體中文字形與台灣標點追加至圖集下方，確保零缺字且不影響原英文字距。
