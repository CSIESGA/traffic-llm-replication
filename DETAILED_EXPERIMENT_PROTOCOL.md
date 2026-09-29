# 詳細輸出比較：project_detailed_v1_full_precision

## 本次改了什麼

輸出欄位沿用 archive/manual_llm 的格式。這次擴充 Prompt、JSON validator、詳細 evaluator、實驗 manifest 與本機瀏覽器收集表單；作者原始程式、324 個 Scenario 與 official GT 保持原樣。

這是「作者 GT + 本專案詳細輸出 Prompt／指標」的實驗。作者公開 GPT fine-tuning 腳本使用 yes/no 分類，不可把這個新 Prompt 稱為完全相同的原始實驗。

## 流程與位置

```text
data/scenarios/scenario_XXX.json
  ├─ 作者程式 → data/ground_truth_official/scenario_XXX_gt.json
  └─ build_detailed_prompt() → prompts/detailed/scenario_XXX.txt
       → ChatGPT 新的非個人化暫存對話 → 第一次完整回答
       → outputs/detailed_llm/scenario_XXX.txt
       → parse_detailed() → author_reference() → compare() → aggregate()
       → outputs/evaluation_detailed/
```

GT 和 Prompt 分路處理。Prompt 生成器不讀 GT；也不提供已計算的 TTI、movement hints 或標準答案。速度與距離使用 Scenario 浮點數的完整表示，避免二位小數四捨五入造成排序／Waiting Time 誤差。這一點與先前作者分類模板不同，protocol 已另取名稱。

## 輸出格式

八個頂層 key 必須全部存在，不增加其他 key：

| key | 型別與語意 |
|---|---|
| `is_conflict` | JSON boolean |
| `number_of_conflicts` | 非負整數，代表不同的無方向衝突車對數量 |
| `places_of_conflicts` | 每個報告車對一個位置字串；未知更精細位置時使用 `intersection` |
| `conflict_vehicles` | 陣列，每筆包含 `vehicle1_id`、`vehicle2_id`、`reason` |
| `decisions` | 每車一筆 `vehicle_id`、`action`、`reason` |
| `priority_order` | 全部車輛 ID 各一次，由高到低；模型判為衝突的車輛在前，其餘依輸入順序放後面 |
| `waiting_times` | 每車 ID 對應非負、有限的秒數 |
| `explanation` | 簡短總體理由，必要時說明不確定性 |

`action` 接受 `proceed`、`slow_down`、`yield`、`stop`。不把 stop/slow_down 偷換成 yield。

無衝突時，boolean 為 false、數量 0、車對與位置陣列空白；仍需在 decisions、priority_order、waiting_times 列出全部車輛。Prompt 要求每個理由約 20 個英文單字、explanation 約 40 個英文單字，控制回應長度；不因超長而修改原始回答。

沒有附上帶實際 Scenario ID 的已解答例子，避免舊 scenario_001 範例洩漏答案。五份 archive JSON 均已驗證可以由新 parser 讀取，但不因此宣稱舊答案符合作者 GT。

## 評分方式（本專案新增設計）

| 項目 | 分數與適用範圍 |
|---|---|
| Binary | TP/TN/FP/FN、Accuracy、Precision、Recall、F1 |
| Conflict Pair | 無方向車對集合的 micro Precision/Recall/F1、整題集合完全一致率、GT 有衝突子集一致率 |
| 數量 | `number_of_conflicts` 完全一致率與 MAE；不以車對陣列長度覆蓋模型自己填的數量 |
| 每車 action | 每車 accuracy、整題完全一致率、動作混淆計數 |
| Priority | 只評作者有 rank 的車輛之相對順序；順序完全一致率、rank accuracy、pairwise order accuracy |
| Waiting Time | 秒數 MAE、容差內比例、整題一致率；分別報全部車輛及 GT 衝突車輛 |
| 位置 | 粗略位置 multiset 一致率；明確把 archive 的 `intersection_center` 映射為 `intersection` |
| 全欄位 | 以上可評欄位全部一致，且已定義的一致性檢查通過；不包括理由、精細位置或 GT 未排名車輛順序 |
| 理由/explanation | 驗證文字存在並保留，不計算語意正確率；沒有完整理由 GT，不宣稱 ROUGE 是正確性 |

Waiting Time 預設浮點容差 `1e-6` 秒，可使用 `--waiting-tolerance` 明確改變並記錄。這不是 1 秒寬容，也不是模型輸出必須為整數。

`decisions` 參考值是本專案從作者每車對句子作的映射：只要某車在任何車對被要求 yield，該車 action 為 yield，否則 proceed。這不是作者原始 per-vehicle 欄位，也不能衡量「讓給誰」是否正確，因為 archive schema 沒有結構化 yield-to ID。

作者對非衝突車輛設定 rank=null；為相容 archive 的全車排列，本專案只比較 GT 衝突車輛的相對順序。不評其餘車輛順序。沒有可評排名的題目不納入 Priority 分母；若全部無適用題，分數是 null。

## Ground Truth 的限制必須與分數一起報告

作者 `apply_priority_rules()` 與 `generate_dataset()` 的全域 TTI 排序不同。當 pair decision 要求 A 讓 B，但全域 rank 卻把 A 排在 B 前，evaluator 會標記 `pair_yield_vs_global_rank:A->B`。

本次 324 題共有 52 題具有這種差異。報告包含所有題目之主結果，也提供 `by_ground_truth_consistency` 中有／無此差異的子集分數。這些分數代表與作者程式輸出的一致程度，不是道路安全性證明。

不偷偷修正作者 rank/waiting，也不強迫 LLM 的文字理由符合矛盾答案。`ground_truth_warning_scenarios` 保留逐題細節。

位置 GT 全為 intersection，所以沒有精細幾何位置的標準答案。此實驗也沒有專家逐條理由標註。

## 原始回答與格式錯誤

- 原始回答放 `outputs/detailed_llm/scenario_XXX.txt`，不要人工刪除多餘解釋、修正 ID 或補欄位。
- 純 JSON 可以保存為 `.json`；同題 `.txt` 與 `.json` 同時存在時，標記 ambiguous，不擅自選一個。
- 接受單一 JSON Markdown fence，並記錄格式；不從一大段 prose 中猜取 JSON。
- 缺欄位、非有限數字、重複 JSON key、自我車對、重複車對、未知 ID 或漏車等屬於 invalid，完整保留原檔。
- 型別完整但 boolean/count 與 pair 不一致時，仍逐欄位評分並加 consistency warnings，不替模型修正。
- Missing/invalid/ambiguous 都不當作正確答案；目前完整欄位指標僅計有效完整輸出，必須同時報 coverage。
- 無有效回答時 status=pending，準確率等為 null。零分母保持 null；不以空集合 micro F1 冒充 100%。

## 如何執行

準備工作已做完。若要核對／重建同樣的檔案：

```powershell
python prepare_detailed_experiment.py
python main.py --protocol detailed --scenario data/scenarios/scenario_174.json
```

手動貼題依 `data/manual_trial_order_detailed.csv`。它沿用原 seed 的隨機順序，只換詳細 Prompt 路徑；沒有依答案挑題。每題開新的相同模型對話；若介面支援「非個人化暫存對話」，確認忽略記憶、外掛及自訂指令。

瀏覽器收集表單（不會自行呼叫模型）：

```powershell
python browser_output_collector.py
```

在 Chrome 開 `http://127.0.0.1:8766/`。表單提供下一題 Prompt、原始回答與 evidence 欄位，由瀏覽器操作者逐題送往 ChatGPT，再貼回原始回應。它只監聽本機，沒有 LLM API/key。

現有 collector 的開始紀錄要求 evidence 包含 `model_name_as_shown: "即時"`、`personalization: "非個人化"`、`temporary_chat: true`；保存紀錄要求正確的 scenario_id 與相同 model label。操作者還應記錄對話 URL、時間與完成狀態。若要測試不同模型，建立另一組 run，不混寫此目錄。

Collector 會拒絕覆蓋答案；已開始但未保存的題目保持 in_progress，需要回到同一個 ChatGPT 對話取回首次答案，不能直接重送。不要在收集時手動編輯它正在使用的 manifest。暫存對話不保留在歷史列表，URL 不保證日後可開啟，因此每題立即保存原文與觀察紀錄。

評分：

```powershell
python evaluate_detailed.py
```

本機可用 Python：

```powershell
$py = 'C:\Users\黃翊峰\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py evaluate_detailed.py
```

輸出：

- `evaluation_summary.json`：總體、4/8/mixed/原24分組、GT 一致性子集、coverage、provenance。
- `evaluation.csv`：每題主要分數及缺漏狀態。
- `per_scenario.json`：漏報／誤報車對、每車 action、rank、等待誤差、GT 警告。
- `parsed_predictions.json`：成功解析的完整 JSON、原始檔 hash、格式／一致性檢查；不取代原始檔。

## 保留舊 baseline

`prompts/*.txt`、`outputs/manual_llm/` 的六份 yes/no 與 `outputs/browser_baseline_324/` 保留，binary 收集已停止；詳細實驗從新的 Prompt／輸出目錄開始。過去 74 題 run 是尚未執行的規劃記錄。

原作者分類 Prompt 的程式仍在：`build_manual_prompt()`、`export_manual_prompts.py --protocol binary`、`evaluate_manual.py`。`main.py` 與 exporter CLI 現在預設 detailed。

## 驗證與研究界線

執行 `python -B -m unittest discover -s tests -v`。測試包括五份 archive 格式、手算車對/排序/時間錯誤、無衝突分母、格式錯誤、作者矛盾、所有 324 題 fixture 的評分路徑，以及原有 100 筆作者公開資料一致性檢查。

人工構造的 fixture 只在暫存資料夾，用來驗證程式，不是 LLM 實驗結果，不能混入 `outputs/detailed_llm/`。本次準備時 detailed collected=0。
