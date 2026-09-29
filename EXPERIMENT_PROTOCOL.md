# 手動 GPT Conflict Classification 實驗規範

> 此文件保留二元分類 baseline。新的詳細 JSON 實驗請使用 [DETAILED_EXPERIMENT_PROTOCOL.md](DETAILED_EXPERIMENT_PROTOCOL.md)、`prompts/detailed/` 與 `evaluate_detailed.py`。

使用 `prompts/scenario_XXX.txt`，每題新開 GPT 對話，把第一次回覆存為 `outputs/manual_llm/scenario_XXX.txt`，最後執行 `python evaluate_manual.py --run-metadata EXPERIMENT_RUN.json`。本階段不需要 API key，也不做 fine-tuning。

## 這次測量什麼

主要問題是：**GPT 讀取作者格式的自然語言 Scenario 後，是否能預測作者 `v1.0.0` 規則程式的 conflict label？**

- 輸入：固定 lane/destination 指令與六欄車輛資料的自然語言描述。
- 輸出：單一 `yes` 或 `no`，分別代表有 conflict／無 conflict。
- 參考答案：`data/ground_truth_official/`，來源為作者公開程式。
- 正類：conflict／yes／true。
- 指標：Accuracy、Precision、Recall、F1、confusion counts，以及完成率 coverage。

本實驗不評分 conflict pair、priority、action、waiting time、explanation 或 ROUGE-L。GT 中仍保留完整作者輸出，方便未來設計另一個獨立實驗。此處的高分類表現表示與作者標籤一致，不自動代表正確理解真實路口幾何或安全控制能力。

## 開始前固定條件

1. 填寫根目錄 `EXPERIMENT_RUN.json`：GPT 介面所顯示的模型名稱、可以確認的版本、日期、平台與備註。無法確認的欄位保持未知。
2. 保留 `prompts/prompt_manifest.json`、`data/scenario_generation_manifest.json`、`vendor/zenodo_14171745/manifest.json` 和 `official_adapter_config.json`。它們能追溯輸入、作者來源與轉換規則。
3. 本次使用全部 324 題，或在開始前明確選定子集。不要看完表現後才挑選較容易的案例。
4. 按 `data/manual_trial_order.csv` 的固定洗牌順序做題，seed 為 `20260928`。這份表不提供 GT。
5. 使用同一模型與相同設定，盡量在短時間內完成。若模型或平台改變，開始新的 run，保留原 run。

Prompt 沒有提供衍生 movement、TTI、GT 的 4 秒 threshold 或答案示例。模型看到的速度／距離有作者規定的兩位小數；GT 使用 Scenario 原始數值。這是公開作者流程的資訊精度差異，不要在收集答案期間自行改動。

## 每題怎麼做

1. 開啟該題 `prompts/scenario_XXX.txt`，複製**整份**文字。
2. 開新的 GPT 對話；可以使用 Temporary Chat。每題設定保持一致，避免先前對話、記憶或自訂指令提供額外交通資訊。
3. 貼上 Prompt，等待第一次回答。不要同時貼入 GT、generation manifest、前一題答案或資料夾中的其他檔案。
4. 不要求重新生成、不糾正、不追加提示。
5. 保存第一次回覆為 UTF-8 的 `outputs/manual_llm/scenario_XXX.txt`。相同 scenario ID 必須對應相同檔名。

例如模型只回答 `no`，檔案內容就是：

```text
no
```

在 Windows 檔案總管開啟副檔名顯示，確認不是 `scenario_001.txt.txt`。不要在檔案內加車號、時間、模型名稱或自己的註解；這些放在 run metadata 或另行紀錄。

手動合併訊息中的 `SYSTEM INSTRUCTION` 是文字標示，**不是 API 的真正 system role**。此處保留作者兩段文字內容，但 UI 的角色層級不同，報告研究方法時必須寫明。

## 回答格式與失敗處理

| 情形 | 評分器行為 | 你應如何處理 |
|---|---|---|
| 純 `yes`／`no` | 正常評分，忽略大小寫及外圍空白 | 原樣保存 |
| 只有 Markdown code fence 包住 yes/no | 支援純文字 fence 的嚴格解析 | 保留模型原始格式 |
| 額外解釋，例如 `Yes, because ...` | `invalid_prediction` | 保留原始回覆，不主觀摘取答案 |
| 拒答、無結果或其他文字 | 格式錯誤或缺漏 | 不偽造回答；在備註記錄 |
| 同題同時有 `.txt` 與 `.json` | `ambiguous_prediction` | 留下一份原始正式答案，另一份移至獨立 run／備份 |
| 沒有對應 GT 的回答檔 | 列為 extra prediction | 檢查檔名／run 是否放錯 |

相容的 JSON 形式為 `{"is_conflict": true}` 或 `{"is_conflict": "yes"}`，no 對應 false；只讀取 `is_conflict`。本階段 Prompt 不要求 JSON，優先保存模型原始 `.txt`。舊詳細 JSON 即使可解析，也不能和新 Prompt 的結果混成同一實驗。

## 評分與解讀

```powershell
python evaluate_manual.py --run-metadata EXPERIMENT_RUN.json
```

預設比較 `outputs/manual_llm/` 與 `data/ground_truth_official/`，輸出到 `outputs/evaluation_official/`。

- `evaluation.csv` 每題都有一列，含 `evaluated`、`missing_prediction`、`invalid_prediction`、`ambiguous_prediction` 等狀態。
- `evaluation_summary.json` 保存 metric、缺漏清單、input hashes、GT 來源、人工填寫的 metadata。
- 沒有有效回答：`status=pending`，四項 metrics 為 `null`。
- 只完成部分題目：`status=partial`；metrics 只計有效且唯一的回答，必須同時報告 coverage。
- 全部有可評分回答：`status=complete`。其他 extra files 仍應檢查。
- 分母為 0 的 metric 為 `null`，不假裝為完美分數。

定義：

```text
Accuracy  = (TP + TN) / N_evaluated
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2TP / (2TP + FP + FN)
Coverage  = N_evaluated / N_ground_truth_files
```

不要只報告 Accuracy 而隱藏 invalid、missing 或 coverage。新資料 4 車／8 車／mixed 每組刻意平衡，原有 24 題是另一來源；總體結果與分組結果應在報告中區分。評分器預設讀取既有 generator manifest，於 summary 的 `by_group` 分開報告 four／eight／mixed 與 original_or_unassigned（目前為原24題），每組都有 coverage。另一批資料請以 `--scenario-manifest` 指定對應 manifest。

## 重複實驗與歷史結果

若要研究穩定性，可在完成第一輪後，另建 `outputs/manual_llm_run02/`、新的 metadata，全部重新開對話收集。評分時指定不同資料夾：

```powershell
python evaluate_manual.py --pred-dir outputs/manual_llm_run02 --output-dir outputs/evaluation_run02 --run-metadata EXPERIMENT_RUN_02.json
```

第二輪的 metadata 檔案需由你先建立。不要覆蓋第一輪回答，也不要只重試第一輪答錯的題目後將兩輪混合。

`archive/legacy_reconstruction_20260928/` 是舊 structured JSON Prompt、5 份舊回答與舊 metrics。這些結果對應不同 Prompt 與 reconstruction GT，僅供歷史查閱；新實驗從空白回答資料夾開始。
