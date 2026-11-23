"""
Importer 該做的工作如下：
1. 從檔案 parse 出相機參數並存在 ExtrinsicParameter, IntrinsicParameter 中
2. 建立 ZForwardCamera 並應用參數
3. 將原圖片路徑寫入 ZForwardCamera 的 Prop.img_path 屬性，以確保 Exporter 可以找到原圖片
4. (Optional) 載圖片後 -> set_bg_image
"""
