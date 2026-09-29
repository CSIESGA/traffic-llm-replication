# 手動實驗回覆

每個 Scenario 開新的 GPT 對話，貼上 `prompts/scenario_XXX.txt` 全文。
將第一個回覆原樣存成此資料夾的 `scenario_XXX.txt`（UTF-8）。
預期只有 `yes` 或 `no`；不要修改錯誤答案，格式錯誤會在評分時列出。
沒有完成的案例不要建立空白檔，也不要複製 Ground Truth 當答案。
同一案例不要同時保留 `.txt` 和 `.json`，避免評分來源不明。

新版輸入為自然語言，舊 JSON Prompt 的 5 筆結果已移到
`archive/legacy_reconstruction_20260928/manual_llm/`，不納入新實驗。
