# 2026-09-28：作者 Simulator 與手動流程更新

本次把原本「等待下載與設定」的狀態，改為可直接使用作者 Ground Truth、自然語言 Prompt 與手動 binary 評分的實驗。

## 使用者要求的工作

1. **下載與接通作者程式。**固定 Zenodo `14171746`／`v1.0.0`，保留原始 ZIP 與未修改的解壓檔案。修正 concept DOI `14171745` 與 version DOI `14171746` 的區別，不再誤判 mismatch。
2. **24 題重新標記。**保留 `scenario_001`–`scenario_024` 原始內容，改用作者程式產生 `data/ground_truth_official/` 標籤；舊 reconstruction 標籤獨立保留。
3. **改成手動操作。**移除專案層級的 `llm_client.py`、`batch_run.py`、`config.py`、`schemas.py`、`.env.example`；`main.py` 僅預覽／儲存 Prompt，沒有 API 呼叫。
4. **自然語言轉換。**採用作者 GPT 分類程式的 wording 與兩位小數格式，僅提供原始六欄資料；不再輸出 enriched JSON、不加入本地 movement／TTI、不放 V101／V102 答案示例。
5. **新增 300 題。**直接使用作者 generator；4 車、8 車、mixed 各 100 題，每組 50 yes／50 no，seeds 分別為 `20260928`、`20260929`、`20260930`。連同原有 24 題共 324 題。
6. **更新文件。**README 提供目前結構、立即操作步驟、擴增資料命令；實驗規範與來源文件分開描述。

## 為了可核對與避免混用，額外完成的工作

- Adapter 使用作者完整 `generate_dataset(total_records=1)` 聚合流程，而非只轉接 `detect_conflicts()`。
- 與作者已發布 100 筆 CSV 全欄位比對，確認 adapter 輸出一致。
- 保存 `official_raw_output`、ZIP checksum、作者檔案 SHA256、adapter／config hash。
- 為新生成資料加入 seed、參數、每題 hash、組別與物理狀態去重；原始作者浮點數不被截斷。
- Prompt exporter 保存 Scenario／Prompt SHA256，拒絕不明覆蓋舊內容。
- 驗證原有 24 題自然語言輸出與作者 converter 一致，並加入避免 GT／derived state 洩漏的測試。
- 產生不含 label 的固定洗牌順序，以及 `EXPERIMENT_RUN.json` 人工模型／時間紀錄範本。
- 評分器加入 missing、invalid、ambiguous、extra prediction 與 coverage；沒有模型回答時，metrics 顯示 `null`，不產生虛假的新成績。
- 分組報告 four／eight／mixed 與原案例，避免將不同來源混為單一論文 benchmark。
- 原24題重算為21 conflict／3 no-conflict，其中7題與舊二元標籤不同；逐題比較保存為 `data/original_24_ground_truth_comparison.csv`。
- 22項測試通過；新增300題以相同seeds重生及全部raw labels核對一致，驗證摘要保存於 `outputs/setup_validation.json`。
- GT exporter 拒絕用單題或不同範圍的批次覆寫既有整批 manifest，避免縮減或混淆實驗範圍。
- 將舊 24 份 Prompt、5 份回答與舊 metrics 移到 `archive/legacy_reconstruction_20260928/`。新回答資料夾保持乾淨，避免不同 Prompt／GT 的結果混用。
- 根目錄依賴簡化為 pandas；作者封存內原有 API／fine-tuning 程式維持原貌，但不屬於 active workflow。

## 研究範圍的明確調整

目前主要任務是作者公開分類流程的 **yes/no conflict classification**。GT 保存的 pair、priority、waiting 等結果方便來源檢查與之後擴充；本階段不要求 GPT 生成它們，也不計算舊 structured-field metrics。

手動將兩段 Prompt 合成一則 GPT 訊息，不能完全重現 API system-role。新增樣本不是論文原始資料，作者 movement mapping 與 Figure 4 重建存在差異。這些限制已記錄在文件，沒有透過改寫作者程式來掩蓋。

本次沒有執行 fine-tuning、沒有使用模型 API、沒有建立新的 LLM prediction，也沒有把舊 5 筆回答當作新實驗結果。完整期刊 replication 所需的正式 splits、指定 checkpoint、多模型比較與 ROUGE-L，仍是後續工作。
# 詳細輸出擴充（2026-09-29）

- 保留 archive 八欄位 JSON 格式，新增 `build_detailed_prompt()`；保留原始數值精度，不提供 GT、TTI 或舊 movement hints。
- 已產生 `prompts/detailed/` 的 324 份 Prompt 與獨立 hash manifest，沿用原隨機順序。
- 新增 `detailed_output.py` 的嚴格格式驗證與作者 raw GT 轉換、`evaluate_detailed.py` 的逐欄位比較。
- 分別報 Conflict Pair、數量、每車 action、Priority、Waiting Time、粗略位置與 coverage；理由只保存，不宣稱有語意 GT。
- 作者 324 題中 52 題 pair yield/global rank 不一致，逐題列出，並提供一致性子集分數。
- 詳細原始回答放 `outputs/detailed_llm/`，收集紀錄在 `outputs/browser_detailed_324/`；保留舊 6 份 binary 回答，舊收集 run 標為 stopped_for_protocol_change。
- `main.py` 和 Prompt exporter CLI 預設 detailed；binary 可明確選用。
- 新增 `DETAILED_EXPERIMENT_PROTOCOL.md`，34 項測試通過。合成 fixture 僅在暫存資料夾，詳細正式回答目前為 0。
