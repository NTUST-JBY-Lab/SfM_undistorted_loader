import bpy
from bpy.props import *
from ..camera import ZForwardCamera, ExtrinsicParameter, IntrinsicParameter

from pathlib import Path
import shutil

class CommonExporterProperty:
    only_export_selection: BoolProperty(
        name="Export Selection Only",
        description="是否只匯出選取的相機",
        default=False
    ) #type: ignore

    should_export_camera_image: BoolProperty(
        name="Export Image",
        description=
        """
        是否匯出相機的圖片。

        如果相機是使用本插件的 Importer 匯入的，則直接將原圖片複製到匯出目錄。
        否則，使用 Blender 的 Render 功能渲染相機視角的圖片並匯出。
        """,
        default=True
    ) #type: ignore

    def gather_camera_to_export(self) -> list[tuple[ZForwardCamera, ExtrinsicParameter, IntrinsicParameter]]:
        """Gather cameras to export based on the export_selection_only property."""
        if self.only_export_selection:
            cameras = [obj for obj in bpy.context.selected_objects if obj.type == 'CAMERA']
        else:
            cameras = [obj for obj in bpy.context.scene.objects if obj.type == 'CAMERA']

        # Convert the camera objects to the expected format
        result = []
        for camera_obj in cameras:
            z_forward_camera = ZForwardCamera(camera_obj=camera_obj)
            extrinsic_param = z_forward_camera.extract_extrinsic_param()
            intrinsic_param = z_forward_camera.extract_intrinsic_param()
            result.append((z_forward_camera, extrinsic_param, intrinsic_param))
        return result

    def export_image_of_camera(self, camera: ZForwardCamera, target_path: Path):
        """Export the image associated with the camera to the target path."""
        if not self.should_export_camera_image:
            return  # Skip exporting if the property is False

        src_img_path = camera.get_property(ZForwardCamera.Prop.img_path)

        if src_img_path:
            shutil.copy(src_img_path, target_path)
        else:
            raise NotImplementedError(f"Rendering then export is not implemented.")
        
        


