from bpy.props import *

class CommonImporterProperty:
    add_arrows: BoolProperty(
        name="Add Arrows to Camera",
        description="是否要為相機多加一個箭頭作為父物件，輔助顯示相機的區域座標系",
        default=False
    ) #type: ignore

    add_background: BoolProperty(
        name="Add Background Image to Camera",
        description="是否要讀入相片並設置成相機的背景",
        default=True
    ) #type: ignore
