# v0.1.0-beta.1 — 首次公開測試版

《黑帝斯》（Hades 1）台灣繁體中文化公開測試版發布，所有專有名詞對齊《黑帝斯 II》官方繁體中文版，並自英文原文重譯以修正原簡中版本錯漏。

## 翻譯覆蓋統計

| 項目 | 檔案數 | 條目／欄位數 | 說明 |
|---|---:|---:|---|
| UI / 祝福 / 法典 / NPC 對話（`.sjson`） | 18 | 12,280 | 對齊 Hades II 術語、全控制碼與標籤驗證通過 |
| 語音台詞與現場對白字幕（`.csv`） | 37 | 14,109 | 全數自英文重譯，台灣標準標點「」『』〈〉⋯⋯ |
| 字型補字（`Default.xnb` / `zh-CN.xnb`） | 7 | +1,366 字形 | 內附 OFL 開源 NotoSansTC-Medium.otf，本機自動重建 0 缺字 |

## 一般玩家安裝（Player Mode）

1. 下載本頁 ZIP 壓縮包並解壓縮至獨立資料夾。
2. 確認 Steam 正版《Hades》已安裝並關閉，電腦已安裝 Python 3.10 以上版本。
3. 於資料夾開啟終端機執行：`python -m pip install -r requirements.txt`
4. 雙擊執行 `Install_TW_Mod.bat` 並選擇 **[1] 安裝／更新《黑帝斯 Hades》繁體中文化**。
5. 啟動《Hades》，於「設定 → 語言」選擇 **「繁體中文」** 即可遊玩（支援隨時一鍵還原原版簡中）。

> 不需要任何 AI API Key、也不需安裝《黑帝斯 II》。

## 譯者與 AI 翻譯模式（Developer Mode）

下載程式碼後可依 [Developer Guide](DEVELOPER_GUIDE.md) 執行：
`dev extract`（轉為 AI 好處理的 JSON）→ `dev prepare`（切批並附術語表 Prompt）→ `dev import` → `dev build` → `dev qa` → `dev install`。

## 已知事項

- 已完成開發者實機開啟檢查、選單「語言／繁體中文」跨語系字型修正、全 18 個 SJSON 標籤檢查、全 37 個 CSV 檢查與 3,543 個全文本可印字元 0 缺字驗證；完整全成就長時通關實機回饋歡迎於 [GitHub Issues](https://github.com/CassiaLin/Hades-TW-Localization/issues) 回報。

程式碼採 MIT 授權；隨附字型採 SIL OFL 1.1；翻譯資料權利說明見 [Translation Data Notice](TRANSLATION_NOTICE.md)。
