# 領域知識（Domain Knowledge）

> 在 Sidebar 的 Knowledge 頁面編輯這份檔案。切換到「+Knowledge」模式時，這些內容會被加進 prompt。

## 範例：半導體製程常見失效判斷

- **Edge particle 異常**：如果 edge 的 particle 數遠高於 center（超過 10 倍），通常不是量測誤報，優先懷疑 edge exclusion 區域的汙染源 —— 例如 robot arm、edge bead remover 或 load port 環境。
- **膜厚 center-to-edge 偏差擴大**：若從 ~1% 升到 >3%，先查 showerhead / gas flow uniformity，再查 chuck 溫度分布。
- **CD 跳動與溫度**：如果 CD 量測值與 chamber 溫度呈正相關（溫度高時 CD 偏大），幾乎可確定是量測腔體溫控問題，而不是製程問題 —— 應先暫停量測、校正溫控。

> （使用者可以自由編輯這份文件，寫下任何你希望 AI 在 +Knowledge 模式下參考的規則、經驗法則、判斷準則。）
