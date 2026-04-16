# CASE_001：晶圓邊緣 particle 異常

## 現象
2025-12-19 LOT-2512-038 edge inspection 發現 particle 計數突然暴增，集中在 **wafer edge 外圈 3mm 內**，且在 **3, 6, 9, 12 點鐘位置**（即 4 個方位角）顯著高於其他角度。

## 影響範圍
- 批次：LOT-2512-038（25 片 wafer，全數命中）
- 機台：Inspector-A2 / 量測配方 EDGE_SCAN_v3
- particle 平均 0.25–0.4 μm
- 前 30 個 lot 歷史 edge particle 平均 3.2 / wafer，**本 lot 平均 28.5 / wafer**（9 倍）

## 已知線索
- 4 個方位角 pattern 很可疑：可能是機械手臂 end-effector 碰觸 edge
- 膜厚量測正常（排除沉積問題）
- chamber particle count 本身正常（排除反應室汙染）
