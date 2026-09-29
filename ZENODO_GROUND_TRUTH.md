# 作者 Ground Truth：來源、接法與限制

作者程式已下載並接入。主要 backend 為 `official`，對目前的 324 個 Scenario 都可以產生完整作者輸出。這裡的「官方」指論文所連結的**公開 `v1.0.0` release**，不表示已確認它與期刊最後所有實驗設定完全相同。

## 可以回查的來源

你的 [Vehicles 論文 PDF](<Vehicles (Journal) 2025.pdf>)，以封面算第 1 頁：

| 位置 | 內容 |
|---|---|
| 第 22 頁，Data Availability Statement | 指向 `10.5281/zenodo.14171745` 的 data/code |
| 第 17 頁，Decision-Making and Feedback Results | 說明 Python simulation 的 truth values 與專家驗證 |
| 第 7 頁，Figure 3 | Scenario、movement、conflict、priority、waiting 的生成流程 |
| 第 9–10 頁，Conflict Detection | Conflict／priority 的概念描述 |

- [Concept DOI：14171745](https://doi.org/10.5281/zenodo.14171745)
- [固定版本 DOI：14171746](https://doi.org/10.5281/zenodo.14171746)
- [作者 GitHub v1.0.0](https://github.com/sarimasri3/Intersection-Conflict-Detection/tree/v1.0.0)
- [固定版本 ZIP](https://zenodo.org/api/records/14171746/files/sarimasri3/Intersection-Conflict-Detection-v1.0.0.zip/content)

兩個 DOI 分別代表作品系列與具體版本，不是來源矛盾。此專案固定使用 14171746，仍保留歷史目錄名稱 `vendor/zenodo_14171745/`。

## 安裝內容與完整性

| 項目 | 固定值／位置 |
|---|---|
| Release | `v1.0.0` |
| 發布日期 | 2024-11-15 |
| ZIP MD5 | `c51e921f9273d26fc9f9f08a0b4ef541` |
| 原始 ZIP | `vendor/zenodo_14171745/raw/Intersection-Conflict-Detection-v1.0.0.zip` |
| 作者根目錄 | `vendor/zenodo_14171745/extracted/sarimasri3-Intersection-Conflict-Detection-06ee9d5/` |
| 追溯紀錄 | `vendor/zenodo_14171745/manifest.json` |

Installer 驗證 concept/version DOI 與 ZIP MD5，並保存 ZIP SHA256、每個解壓檔案 SHA256。作者檔案維持原樣；adapter 執行前會檢查 manifest 裡的檔案 hash。下載器使用 Python standard library，不執行下載的程式。

目前不必再次下載。從未安裝的新 checkout 才需要：

```powershell
python install_zenodo_ground_truth.py
```

若已自行下載同一份 ZIP：

```powershell
python install_zenodo_ground_truth.py --archive C:\path\to\Intersection-Conflict-Detection-v1.0.0.zip
```

本地 ZIP 模式仍會連線讀取 Zenodo metadata，再驗證固定 checksum。已安裝時會拒絕覆蓋；沒有 `--force`。要另查另一份安裝可指定新的 `--vendor-dir`，但 active adapter 仍固定使用專案既有 vendor，不能把另一個目錄當成已自動切換。

## 真正執行了哪些作者 function

| 作者檔案／function | 作用 |
|---|---|
| `src/conflict_detection.py::Vehicle` | 依作者規則計算 movement 與 TTI |
| `parse_vehicles()` | 原始車輛資料建立作者 Vehicle |
| `paths_cross()` | movement／direction 的 conflict 規則 |
| `arrival_time_close()` | TTI 差的門檻判斷，預設 4 秒 |
| `apply_priority_rules()` | 車對的優先／禮讓 |
| `compute_waiting_times()` | 車對的等待處理 |
| `detect_conflicts()` | 收集 conflict pairs |
| `src/data_generation.py::generate_vehicle_scenario()` | 隨機抽樣原始 Scenario |
| `generate_dataset()` | 聚合 Scenario-level 標籤、priority 與 waiting |

**不是只呼叫 `detect_conflicts()` 就當成完整作者答案。**`generate_dataset()` 還有自己的全域排序與等待時間聚合，這部分也必須保留。

## 如何替既有 Scenario 產生答案

`official_ground_truth_adapter.py::label_author_scenario()` 使用以下方式：

1. 驗證來源檔案，載入作者的 `src` modules。
2. 將輸入 Scenario 的六個欄位交給 adapter，不使用本地衍生 movement。
3. 在執行期間，暫時讓作者 `generate_vehicle_scenario()` 回傳指定 Scenario，而不是隨機生成另一題。
4. 執行**未修改的**作者 `generate_dataset(total_records=1)`，走完 pair detection 及 dataset-level 聚合。
5. 在 `finally` 中還原原 generator function。
6. 保存完整 row，並將必要表示轉成專案格式。

這是本地介接層的設計，不是宣稱作者原本就提供了單題 JSON CLI。作者磁碟上的 source code 沒有被修改。

本次將 adapter 結果與作者 ZIP 內 `data/generated_dataset.csv` 的 100 筆已發布範例逐筆核對，所有輸出欄位一致。這驗證介接沒有遺失作者的 dataset-level 聚合；不代表已找回論文的全部資料。

使用命令：

```powershell
python generate_ground_truth.py --backend official --input-dir data/scenarios --output-dir data/ground_truth_official
```

## GT JSON 如何解讀

每個 `scenario_XXX_gt.json` 包含：

- `is_conflict`：作者 yes/no 正規化成 boolean，供主要評分使用。
- `number_of_conflicts`、`conflict_vehicles`、`places_of_conflicts`：作者車對結果。
- `priority_ranks`：作者 rank dictionary。
- `priority_order`：把有 rank 的車輛轉成排序清單；未排名者另列 `unranked_vehicle_ids`。
- `decisions`：依作者 yield 敘述轉成簡化 action；以 `decision_normalization` 說明轉換規則。
- `waiting_times`：作者 dataset-level 等待時間。
- `official_raw_output`：完整原始作者 row，是核對原始語意的依據。
- `ground_truth_backend`、`ground_truth_method`、`ground_truth_provenance`：固定版本、checksum、來源與 adapter hash。

`decisions` 的簡化 action 與 `priority_order` 是表示轉換，不是新增交通規則。舊 `evaluate_manual.py` 只評分 `is_conflict`；新 `evaluate_detailed.py` 使用 `official_raw_output` 比較詳細欄位，並明確區分每車 action 的本地轉換、作者 pair decision 與 dataset-level rank/waiting。詳細指標是本專案設計，不宣稱已完全重現論文詳細回饋實驗。

## 新 Scenario 的來源

`generate_scenarios.py` 呼叫 `generate_author_records()`，後者直接執行作者 `generate_dataset()`。新增資料使用作者原始 sampling：

- 從合法 lane 與 destination 隨機選取。
- Speed：uniform 20–80 km/h。
- Distance：uniform 50–500 m。
- Fixed 組：4 車或 8 車；mixed 組：2–8 車。
- 作者 rejection sampling 直到每組 conflict／no-conflict 各半。

本地新增控制是 seed、分組、檔案編號、provenance 和去重檢查。去重忽略任意 vehicle ID 與車輛順序，比較實際輸入狀態；不改動作者抽樣或 conflict 規則。Scenario 保存原始 float，Prompt 另外依作者模板顯示兩位小數。

## 必須保留的限制

1. **Movement mapping 不同。**作者 `get_movement_type()` 對偶數 lane 的合法 destination 全部視為 left；奇數 lane 依清單索引指定 right／straight。這與本專案先前依 Figure 4 重建的 mapping 不同。官方流程沿用作者程式，不偷偷替換成 reconstruction。
2. **Conflict 是規則參考答案。**作者以 movement／direction 條件及 4 秒 TTI 差判斷，並非車身幾何碰撞模擬。論文專家驗證的細節不足以由本專案獨立重建。
3. **Pair 與全域結果可能有差異。**作者 pair yielding 與 dataset-level priority/waiting 不一定形成直觀一致的全域排程；保留 raw output，不自行修正後稱為原結果。
4. **Prompt 資訊不完整描述幾何。**作者分類 Prompt 沒有顯式提供完整出口座標、movement mapping 或 4 秒 threshold；為重現公開條件，本專案沒有自動補進去。
5. **版本與完整實驗仍有界線。**公開 ZIP 有 100 筆範例；本次 300 筆是新生成樣本，沒有取得全部原始 10,000 筆與指定 fine-tuning checkpoints。

`ground_truth_reconstruction.py` 仍保留作為另外的歷史／敏感度基準，需明確指定 `--backend reconstruction`。它不是作者 simulator，不能與 official 的標籤或 metrics 混用。
