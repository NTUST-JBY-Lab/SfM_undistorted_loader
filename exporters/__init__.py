"""
Exporter 該做的工作如下：
1. CommonExporterProperty.gather_camera_to_export() -> 取得要匯出的相機列表
2. 提取每個相機的 ExtrinsicParameter, IntrinsicParameter 並匯出到檔案
3. CommonExporterProperty.export_image_of_camera() -> 匯出相機的圖片
"""
