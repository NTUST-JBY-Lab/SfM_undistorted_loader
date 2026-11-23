import bpy
from bpy.props import *
from .camera import *

class JBY_OP_CreateZForwardCamera(bpy.types.Operator):
    """
    建立一個 Z Forward 的相機。
    如果有選取的相機，則會轉成 Z Forward 相機（如果 add_arrows 參數為 True ，否則什麼都不做）。
    """
    bl_idname = "jby.create_z_forward_camera"
    bl_label = "Z Forward Camera"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Create a camera with Z forward orientation"

    add_arrows: BoolProperty(
        name="Add Arrows",
        description="Add arrows to indicate camera orientation",
        default=True
    ) #type: ignore

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        if context.object and context.object.type == 'CAMERA':
            camera_obj = context.object
            camera = ZForwardCamera(add_arrows=self.add_arrows, camera_obj=camera_obj)
            if not self.add_arrows:
                self.report({'INFO'}, "沒有加上箭頭的話，其實什麼都不會做。")
        else:
            camera = ZForwardCamera(add_arrows=self.add_arrows)

        bpy.ops.object.select_all(action='DESELECT')
        camera.get_camera_obj().select_set(True)
        context.view_layer.objects.active = camera.get_camera_obj()

        return {'FINISHED'}

class JBY_OP_RemoveArrowOfZForwardCamera(bpy.types.Operator):
    """
    移除 Z Forward 相機的箭頭。
    """
    bl_idname = "jby.remove_arrow_of_z_forward_camera"
    bl_label = "Remove Arrow of Z Forward Camera"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Remove the arrow of a Z Forward camera"

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.object and context.object.type == 'CAMERA'

    def execute(self, context):
        camera_obj = context.object
        camera = ZForwardCamera(camera_obj=camera_obj)
        camera.remove_arrow()
        return {'FINISHED'}
