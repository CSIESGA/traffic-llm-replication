# Traffic LLM Replication：詳細輸出比較

**目前主要流程已改為詳細 JSON 輸出**，使用與 `archive/legacy_reconstruction_20260928/manual_llm/` 相同的八個欄位：
`is_conflict`、`number_of_conflicts`、`places_of_conflicts`、`conflict_vehicles`、`decisions`、`priority_order`、`waiting_times`、`explanation`。

324 份詳細 Prompt 已產生於 `prompts/detailed/`。這是本專案擴充的詳細實驗，**不是作者原始 yes/no 分類 Prompt**。輸入仍為六個原始欄位的自然語言描述，保留數值精度，不提供 GT 或先前 reconstruction 的 movement hints。

## 詳細實驗：現在應該使用這些檔案

1. 按 `data/manual_trial_order_detailed.csv` 開啟 `prompts/detailed/scenario_XXX.txt`。
2. 每題使用新的、相同模型設定的對話，完整貼入 Prompt，保留第一次完整原始回答。
3. 回答放入 `outputs/detailed_llm/scenario_XXX.txt`；手動保存純 JSON 也可以用 `.json`，但同題不能同時存在兩種檔案。
4. 記錄模型與設定至 `outputs/browser_detailed_324/run_metadata.json`。未知底層版本保持 `null`，不能依介面名稱猜型號。
5. 執行 `python evaluate_detailed.py`。結果在 `outputs/evaluation_detailed/`。

```powershell
$py = 'C:\Users\黃翊峰\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py evaluate_detailed.py
```

詳細 evaluator 評分二元分類、Conflict Pair、衝突數量、每車 action、衝突車輛優先序、Waiting Time 與粗略位置。理由及 explanation 完整保存，但沒有理由 GT，因此不宣稱評估其語意正確性。作者 GT 有 pair/global priority 不一致的案例，報告會列出，並另外提供一致／不一致子集的分數。

**目前只有舊 binary 試跑的 6 份真實回答；新的詳細實驗尚未收集答案。測試 fixture 不是 LLM output，不會寫入正式回答目錄。**

| 檔案／目錄 | 詳細流程用途 |
|---|---|
| `prompt_builder.py::build_detailed_prompt` | 自然語言輸入與八欄位 JSON 回答規格 |
| `export_manual_prompts.py --protocol detailed` | 批次匯出詳細 Prompt 與 hashes |
| `prepare_detailed_experiment.py` | 匯出 324 題、沿用原隨機順序、準備實驗紀錄 |
| `detailed_output.py` | 完整輸出驗證、作者 raw GT 的明確轉換 |
| `evaluate_detailed.py` | 逐欄位比較、coverage、分組與 GT 矛盾分析 |
| `browser_output_collector.py` | 僅本機的收集表單，原樣保存瀏覽器回答，無 LLM API |
| `outputs/detailed_llm/` | 詳細實驗原始回答 |
| `outputs/browser_detailed_324/` | 實驗模型、時間、每題狀態與來源紀錄 |
| `outputs/evaluation_detailed/` | CSV、完整逐題比較、解析結果與總體指標 |
| `outputs/manual_llm/` | 保留 6 份舊 binary 試跑，勿與詳細實驗混用 |

完整欄位規則、計分方式、限制、操作命令與續跑方式見 [DETAILED_EXPERIMENT_PROTOCOL.md](DETAILED_EXPERIMENT_PROTOCOL.md)。作者 GT 的原始檔案無需更換，仍使用 `data/ground_truth_official/`。

## 原二元分類流程（保留作為歷史 baseline）

現在可以直接開始：開啟 `prompts/scenario_XXX.txt`，完整複製到一個新的 GPT 對話，將第一次回答的 `yes` 或 `no` 存成 `outputs/manual_llm/scenario_XXX.txt`，再執行評分。**不需要 API key。**

本專案參照 Masri、Ashqar 與 Elhenawy 的 *Vehicles* 論文。這次工作以「是否有 conflict」為主，使用作者公開 `v1.0.0` 程式產生參考答案，使用作者分類實驗的自然語言格式提供題目。詳細實驗規範見 [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)。

## 先開始一筆實驗

1. 在 `EXPERIMENT_RUN.json` 填入實際使用的 GPT 型號、介面與實驗日期；無法取得精確版本的項目保持未知，不要猜填。
2. 依 `data/manual_trial_order.csv` 的順序開啟對應 `prompts/scenario_XXX.txt`。這份順序表不含 GT 標籤。
3. 每一題開新對話，完整貼上 Prompt。使用相同模型、相同設定，不加入提示或修正；保存第一次回答。
4. 將原始回答存為 `outputs/manual_llm/scenario_XXX.txt`。例如 `scenario_001.txt` 只能對應 `scenario_001.json`。不要同時保存同題的 `.txt` 與 `.json`。
5. 執行：

```powershell
python evaluate_manual.py --run-metadata EXPERIMENT_RUN.json
```

結果位於：

- `outputs/evaluation_official/evaluation.csv`：每題評分或缺漏狀態。
- `outputs/evaluation_official/evaluation_summary.json`：Accuracy、Precision、Recall、F1、TP/TN/FP/FN、coverage、輸入檔案 hash 與實驗紀錄。

尚未保存任何模型回答時，狀態是 `pending`、有效回答數是 0，metrics 為 `null`。這表示實驗尚未開始，不是 0% 或 100%。可以分批做題；未完成時報告會標為 `partial`，並清楚列出 coverage。

若回答包含額外解釋，請原樣保存，不要人工摘出一個符合預期的答案。評分器會將非純 `yes/no` 文字標成 `invalid_prediction`，讓格式失敗可被追蹤。其他輸出規則見實驗規範。

## 已準備的資料

| 集合 | Scenario | 數量 | 來源 |
|---|---|---:|---|
| 原有案例 | `scenario_001`–`scenario_024` | 24 | 保留原檔內容，重新套用作者程式標記 |
| 新增 4 車 | `scenario_025`–`scenario_124` | 100 | 作者 generator，seed `20260928` |
| 新增 8 車 | `scenario_125`–`scenario_224` | 100 | 作者 generator，seed `20260929` |
| 新增 mixed | `scenario_225`–`scenario_324` | 100 | 作者 generator，2–8 車，seed `20260930` |

新增每組均為 50 conflict、50 no-conflict。這是作者 generator 的平衡篩選結果，**不是實際道路 conflict 發生率**。原有 24 筆不假設平衡。新增資料的參數、每題 hash、車數與來源寫在 `data/scenario_generation_manifest.json`；該檔含標籤，不可貼給 LLM。

原有 24 筆的作者標籤為 21 conflict、3 no-conflict；全部 324 筆合計 171／153。
有 7 筆原案例從舊 reconstruction 的 no-conflict 改為作者的 conflict：
`005、006、012、014、016、018、020`。逐題結果見
`data/original_24_ground_truth_comparison.csv`，全部標籤摘要見
`data/ground_truth_official/ground_truth_summary.csv`。做題期間不要把答案摘要提供給 GPT。

這 300 筆是用作者程式**重新抽樣的本地資料**，不是找回論文的原始 10,000 筆。尚未重現論文的正式 train/validation/test splits、fine-tuning、多模型比較或 ROUGE-L 實驗。手動 GPT 介面也不等同論文的指定 API checkpoint。

## 實際流程與每一步的目的

```text
Scenario JSON：六個原始車輛欄位
│
├─ parser.load_scenario() → 驗證資料與合法 lane/destination
│   └─ 官方 adapter → 作者 generate_dataset(total_records=1)
│       └─ data/ground_truth_official/*_gt.json：評分答案
│
└─ scenario_to_text() → 作者自然語言格式
    └─ build_manual_prompt() → 固定指令 + 該題車輛描述
        └─ prompts/*.txt → 人工貼入新的 GPT 對話
            └─ outputs/manual_llm/*.txt：模型第一次回答
                └─ evaluate_manual.py + 官方 GT → classification metrics
```

GT 與 Prompt 是兩條分支；**答案不會放入 Prompt**。Prompt 只含 `vehicle_id`、`lane`、`speed`、`distance_to_intersection`、`direction`、`destination`，速度與距離按照作者格式顯示到小數第 2 位，不注入本地 `movement` 或 `time_to_intersection`。

目前 Prompt 的目標是忠實重現作者公開分類輸入，不額外補上論文沒有提供給模型的幾何定義。作者的 lane/destination → movement 規則與本專案先前依 Figure 4 重建的 mapping 有差異，官方 GT 保留作者行為。這個差異是研究限制，詳見 [ZENODO_GROUND_TRUTH.md](ZENODO_GROUND_TRUTH.md)。

## 專案結構

```text
data/
  scenarios/                       324 個原始格式輸入
  ground_truth_official/            324 份作者程式 GT，含 raw output 與 provenance
  ground_truth_reconstruction/      舊 24 份非作者標籤，供歷史／敏感度比較
  scenario_generation_manifest.json  新增 300 筆來源、seed、參數、hash
  manual_trial_order.csv             固定 seed 洗牌的做題順序，不含標籤
prompts/
  scenario_XXX.txt                   每題完整可貼上的自然語言 Prompt
  prompt_manifest.json               Prompt／Scenario SHA256 與 protocol
outputs/
  manual_llm/                        保存你的新模型回答
  evaluation_official/               新實驗分類評分結果
archive/legacy_reconstruction_20260928/
                                     舊 Prompt、5 份舊回答及舊 metrics
vendor/zenodo_14171745/
  raw/                               作者原始 ZIP
  extracted/                         未修改的作者程式與範例資料
  manifest.json                      DOI、ZIP checksum、各作者檔案 SHA256
  record_metadata.json               Zenodo 原始 metadata
EXPERIMENT_RUN.json                  人工填寫的實驗條件
tests/                              作者輸出一致性、Prompt 與評分器測試
```

| 程式 | 用途 |
|---|---|
| `main.py` | 預覽或保存一題 Prompt；可另列 GT，無 API 呼叫 |
| `parser.py`、`vehicle.py`、`intersection.py` | 載入並驗證六欄資料；本地 movement helper 不作為官方判斷依據 |
| `prompt_builder.py` | 作者 system instruction、自然語言轉換、合併成手動訊息 |
| `export_manual_prompts.py` | 批次匯出 Prompt 與 hash manifest |
| `ground_truth.py` | 選擇 official／reconstruction backend |
| `official_ground_truth_adapter.py` | 執行作者判斷及 dataset-level 聚合，保留 raw result |
| `official_adapter_config.json` | 已完成的固定作者版本設定 |
| `generate_ground_truth.py` | 對現有 Scenario 產生官方 GT |
| `generate_scenarios.py` | 呼叫作者 generator 生成 4 車、8 車、mixed 三組新資料 |
| `evaluate_manual.py` | 嚴格解析 yes/no，評分並記錄缺漏、重複與格式錯誤 |
| `prepare_manual_run.py` | 驗證 Prompt hashes，建立不含答案的洗牌順序與空白模型紀錄 |
| `install_zenodo_ground_truth.py` | 下載、驗證、解壓固定版本，已安裝時拒絕覆蓋 |
| `inspect_zenodo_ground_truth.py` | 靜態查看作者檔案的 function／class |
| `ground_truth_reconstruction.py` | 舊自建幾何 baseline，與官方結果分開使用 |

作者封存中的 `gpt_finetuning/` 等檔案保持原樣，供來源查核；本專案的手動實驗不執行它們。原本專案層級的 `llm_client.py`、`batch_run.py`、`config.py`、`schemas.py` 與 `.env.example` 已移除。

## 本機命令

作者程式已下載並接通，不需要再次安裝。重新準備環境時，使用 Python 3.10 以上；目前執行流程的額外 package 只有 pandas：

```powershell
python -m pip install -r requirements.txt
```

如果此電腦的 `python` 找不到，可用已驗證的內建 interpreter：

```powershell
$py = 'C:\Users\黃翊峰\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py evaluate_manual.py --run-metadata EXPERIMENT_RUN.json
```

預覽一題，不會向 GPT 傳送資料：

```powershell
python main.py --protocol binary --scenario data/scenarios/scenario_001.json
```

重新計算官方 GT：

```powershell
python generate_ground_truth.py --backend official --input-dir data/scenarios --output-dir data/ground_truth_official
```

重新匯出相同 Prompt：

```powershell
python export_manual_prompts.py --protocol binary --input-dir data/scenarios --output-dir prompts
```

若既有內容不同，exporter 會拒絕覆寫。開始收集答案後應凍結資料與 Prompt；修改內容時另開實驗版本，不要覆蓋正在評估的輸入。

要再生成更多資料，可先放到另一個資料夾：

```powershell
python generate_scenarios.py --per-group 100 --seed 20261001 --output-dir data/next_batch/scenarios --manifest data/next_batch/generation_manifest.json
python generate_ground_truth.py --backend official --input-dir data/next_batch/scenarios --output-dir data/next_batch/ground_truth
python export_manual_prompts.py --protocol binary --input-dir data/next_batch/scenarios --output-dir data/next_batch/prompts
```

`--per-group` 必須是正偶數；100 表示三組合計新增 300 題。在新目錄產生的檔名從 `scenario_001` 開始，回答也應另放新目錄，評分時指定對應 `--gt-dir`、`--pred-dir`、`--output-dir`，不能混入本次 324 題。

作者來源、整合方式與限制：[ZENODO_GROUND_TRUTH.md](ZENODO_GROUND_TRUTH.md)。本次額外新增與移除項目：[CHANGES_ZENODO.md](CHANGES_ZENODO.md)。

## 已完成的驗證

- 22 項 unittest 通過：`python -B -m unittest discover -s tests -v`。
- 作者公開 CSV 的 100 筆結果與 adapter 的完整輸出欄位一致。
- 300 筆新增資料以相同 seeds 在記憶體重生，Scenario 與作者 raw output 完全一致。
- 原有 24 個輸入未變更；324 份 Prompt／GT hashes 核對通過。
- 新評分報告是 `pending`、0／324，尚無新 LLM 成績。
- 評分摘要的 `by_group` 分開報告 four／eight／mixed 與 original_or_unassigned；
  CLI 預設讀取既有 generation manifest，或以 `--scenario-manifest` 指定另一批。

本次驗證結果保存於 `outputs/setup_validation.json`。
