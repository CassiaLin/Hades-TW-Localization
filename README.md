# Hades（黑帝斯）— 台灣繁體中文化（Taiwan Traditional Chinese Localization）

本專案提供 **《黑帝斯》（Hades 1）** 的台灣繁體中文化工具鏈與純中文譯文包，所有專有名詞與劇情譯名全面對齊官方 **《黑帝斯 II》（Hades II）繁體中文版**，並修正原 1 代官方簡體中文的多處錯漏與機翻（直接從英文原文重新翻譯）。

公開發布版本**不包含任何遊戲英文原文或原版／修改後遊戲二進位資源**，所有中文化檔案與 `.xnb` 字型均於玩家本機端由合法 Steam 原版遊戲即時提取、回填並重建安裝。

> [!NOTE]
> 本專案比照 Dual-Mode（雙模式）架構：
> - **Player Mode（一般玩家模式）**：一鍵讀取純中文譯文包、從原版遊戲合成 `.sjson` / `.csv`、自動補字至 `.xnb` 字型檔並交易式安裝／還原。
> - **Developer Mode（翻譯／開發者模式）**：支援將遊戲中 `.sjson` 與 `.csv` 抽出轉換為對 AI 友善的 JSON（含英文原文、上下文與控制碼清單），經 AI 或人工翻譯修改後，自動驗證標籤與缺字並回填回遊戲。

---

## Player Mode（一般玩家使用方式）

請從 [GitHub Releases](https://github.com/CassiaLin/Hades-TW-Localization/releases) 下載最新公開測試版 ZIP，解壓縮至獨立資料夾（或 `git clone` 本倉庫）。首次安裝前請確認遊戲已安裝且關閉，建議先於 Steam 保持原版遊戲檔案狀態。

### 系統需求
- **作業系統**：Windows 10 / 11（64 位元）
- **遊戲版本**：合法 Steam 正版《Hades》
- **Python 環境**：Python 3.10 以上，並安裝相依套件：
  ```bash
  python -m pip install -r requirements.txt
  ```
- **不需要任何 AI API Key、額外字型或《黑帝斯 II》本體**（本倉庫已隨附 SIL OFL 1.1 開源 `NotoSansTC-Medium.otf`）。

### 安裝與操作

1. **中文選單入口（推薦）**：直接雙擊執行 [Install_TW_Mod.bat](Install_TW_Mod.bat)，依中文選單選擇安裝／更新、檢視狀態或解除安裝還原。
2. **CLI 指令入口**：
   ```bash
   # 查看 Steam 遊戲偵測、備份狀態與 Translation Pack 完整性
   python hades_mod_cli.py player status

   # 安裝繁體中文化（自動執行：偵測 -> 備份原版 -> 合成文本與補字重建字型 -> M4 QA -> 交易式安裝）
   python hades_mod_cli.py player install

   # 取得新版譯文包後更新
   python hades_mod_cli.py player update-pack

   # 解除安裝並無損還原原版簡體中文檔案
   python hades_mod_cli.py player uninstall
   ```
   若遊戲不在預設 Steam 路徑，可加上 `--game-dir "你的\Hades\路徑"`。

3. **進入遊戲**：從 Steam 啟動《Hades》，至「設定（Settings）→ 語言（Language）」選擇 **「繁體中文」** 即可（若先前已為簡體中文則會直接生效）。

### Steam 更新與備份安全機制
- 首次安裝時會於遊戲根目錄建立 `_Backup_TW_Mod/manifest.json`，完整記錄 65 個受影響檔案的 `original_sha256` 與 `installed_sha256`。
- 若偵測到 Steam 更新覆蓋或外部不明修改，安裝／還原程序會**安全中止**，不會以舊備份誤蓋新版遊戲檔。

---

## Developer Mode（譯者／AI 翻譯模式）

任何玩家或譯者下載程式碼後，皆可用本機遊戲重新抽出 AI 好處理的 JSON，自行重翻或微調特定台詞，再一鍵驗證並回填回遊戲：

```bash
# M1：從本機遊戲（或 _Backup_TW_Mod 原版備份）抽出 18 個 .sjson 與 37 個 .csv 為 AI 友善 JSON
python hades_mod_cli.py dev extract

# M2：依每批 200 筆切分 batch_XXXX_*.input.json，並內嵌 glossary_v1.md 產生 AI Prompt
python hades_mod_cli.py dev prepare

# M3：將 AI 或人工編輯完的 JSON / JSONL 匯入回譯文包（支援只更新局部條目）
python hades_mod_cli.py dev import --from-dir path/to/outputs

# M5 + M4：重建 SJSON / CSV / XNB 字型至 dist/，並驗證標籤、標點與 0 缺字
python hades_mod_cli.py dev build
python hades_mod_cli.py dev qa

# 安裝至遊戲測試，或匯出最新純中文譯文包至 translations/hades1/
python hades_mod_cli.py dev install
python hades_mod_cli.py dev export
```

詳細格式與流程請參閱：[Developer Guide](docs/DEVELOPER_GUIDE.md) 與 [AI Agent Template](docs/AI_AGENT_TEMPLATE.md)。

---

## 目前譯文統計與品質特色

- **UI、神祇祝福、法典、武器形態與 NPC 對話（`.sjson`）**：共 `18` 檔、`12,280` 筆欄位。
- **全語音即時台詞與字幕（`.csv`）**：共 `37` 檔、`14,109` 筆不重複條目。
- **術語對齊《黑帝斯 II》官方繁中**：札格列歐斯、黑帝斯、波瑟芬妮、涅克絲、阿基里斯、帕特羅克洛斯、卡俄斯、荻米特、史骷肋米烏斯（骨頭）、絕處逢生、法陣、擊穿護甲等全面統一。
- **字型補字技術**：`NotoSansTC-Medium.otf` 自動將全文本新增字形渲染入無壓縮 `XNBw v6` 貼圖圖集（原簡中字庫缺少約 1,364 個繁中漢字與台灣標點），確保遊戲內「語音字幕、選單、武器名稱、法典與成就」皆 **0 缺字**。

---

## 問題回報與授權

- 問題與勘誤歡迎至 [GitHub Issues](https://github.com/CassiaLin/Hades-TW-Localization/issues) 回報（請勿上傳完整遊戲資源檔案）。
- 自編程式碼與技術文件採 [MIT License](LICENSE)；隨附字型採 Google Noto Fonts SIL OFL 1.1（見 [assets/fonts/OFL.txt](assets/fonts/OFL.txt)）；遊戲譯文之第三方權利聲明詳見 [docs/TRANSLATION_NOTICE.md](docs/TRANSLATION_NOTICE.md)。
