# AI Agent Translation Batch Template

使用 Developer Mode 進行 AI 輔助翻譯或重翻時，請執行 `python hades_mod_cli.py dev prepare`，將 `workspace/hades1/prepared/batch_XXXX_*.prompt.txt` 與 `workspace/hades1/batches/batch_XXXX_*.input.json` 交由 AI Agent（或人工譯者）處理。

## 強制規則

1. **格式**：輸出為 `.json` 陣列或 `.jsonl`（每行一筆 JSON）：
   - SJSON 條目：
     ```json
     {"file": "HelpText.zh-CN.sjson", "id": "DeathDefiance", "field": "DisplayName", "zh": "絕處逢生"}
     ```
   - Subtitles 條目：
     ```json
     {"file": "ZagreusField.csv", "row_id": "ZagreusField_0423", "zh": "都有些什麼貨？"}
     ```
2. **控制碼與大括號保護**：所有 `{$Keywords...}`、`{#...}`、`{!Icons...}`、`\n` 與 `\Column ...` 必須原樣保留且種類／數量一致。
3. **台灣繁體中文與《黑帝斯 II》對齊**：
   - 遵守 [glossary/glossary_v1.md](../glossary/glossary_v1.md)（例如 `Zagreus` → 札格列歐斯、`Persephone` → 波瑟芬妮、`Nyx` → 涅克絲、`Demeter` → 荻米特、`Skelly` → 骨頭／史骷肋米烏斯、`Cast` → 法陣）。
   - 使用台灣標點 `「」`、`『』`、`〈〉`、`《》`、`⋯⋯`（禁用 `“”`、`……`）。
4. **Provider 中立**：工具鏈無任何外部 API Key 綁定；譯文產出後直接以 `python hades_mod_cli.py dev import --from-dir <dir>` 匯入並執行 `dev build` 與 `dev qa`。
