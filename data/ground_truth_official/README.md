# 作者 v1.0.0 Ground Truth

此資料夾由固定作者版本 DOI 10.5281/zenodo.14171746 產生。
每份 *_gt.json 包含完整 official_raw_output、輸入 SHA256 與作者來源 hashes。
ground_truth_summary.csv 提供每題 conflict / pair 數，ground_truth_manifest.json 保存檔案 hashes。
答案與 Prompt 分開保存；手動做題時不要把這些檔案提供給 LLM。

重新產生（內容若改變會拒絕覆寫，請另選輸出資料夾）：

```powershell
python generate_ground_truth.py --backend official --input-dir data/scenarios --output-dir data/ground_truth_official
```
