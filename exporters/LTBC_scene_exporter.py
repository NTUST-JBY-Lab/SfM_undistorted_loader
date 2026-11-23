"""
SCENE_FOLDER:
Within a scene folder a .cam file has to be given for each image.
A .cam file is structured as follows:
    tx ty tz R00 R01 R02 R10 R11 R12 R20 R21 R22
    f d0 d1 paspect ppx ppy
First line: Extrinsics - translation vector and rotation matrix (the transform from world to camera)
Second line: Intrinsics - focal length, distortion coefficients, pixel aspect ratio and principal point
The focal length is the distance between camera center and image plane normalized by dividing with the larger image dimension.
For non-zero distortion coefficients the image will be undistorted prior to the texturing process. If only d0 is non-zero then the radial distortion model of VisualSFM is assumed, otherwise the Bundler distortion model is assumed.
The pixel aspect ratio is usually 1 or close to 1. If your SfM system doesn't output it, but outputs a different focal length in x and y direction, you have to encode this here.
The principal point has to be given in unit dimensions (e.g. 0.5 0.5).

ppx -> normalized by image width
ppy -> normalized by image height
影像左上角為 (0, 0) 、 +y 向下 、 +X 向右
"""
import bpy
from bpy.props import *
from bpy_extras.io_utils import ExportHelper
import mathutils
from pathlib import Path

from .base import CommonExporterProperty
from ..camera import *

class JBY_OT_LTBCSceneExporter(bpy.types.Operator, ExportHelper, CommonExporterProperty):
    """ Export the cameras into LTBC scene folder """
    bl_idname = "jby.export_ltbc_scene_undistorted"
    bl_label = "LTBC Scene Folder Undistorted (folder with images + .cam)"
    bl_options = {'REGISTER', 'UNDO'}

    # property for ExportHelper
    # 覆寫或新增 directory 屬性，檔案瀏覽器會優先抓這個來當作目錄選擇模式
    directory: StringProperty(subtype='DIR_PATH') #type: ignore 
    filepath: StringProperty(subtype='FILE_PATH') #type: ignore
    filename_ext = ""
    
    def execute(self, context):
        export_list = self.gather_camera_to_export()
        already_exported_cameras = set()

        for z_forward_camera, extrinsic_param, intrinsic_param in export_list:
            save_img_name = z_forward_camera.get_save_img_name()
            cam_path = Path(self.directory) / (Path(save_img_name).stem + '.cam')
            img_path = Path(self.directory) / save_img_name

            # 確保不重複匯出相機
            if cam_path in already_exported_cameras:
                self.report({'WARNING'}, f"Camera {cam_path} already exported. Skipping.")
                continue
            already_exported_cameras.add(cam_path)

            # 寫入 .cam 檔案
            with open(cam_path, 'w') as f:
                # Extrinsic parameters
                R = extrinsic_param.R
                T = extrinsic_param.T
                f.write(f"{T.x} {T.y} {T.z} {R[0][0]} {R[0][1]} {R[0][2]} {R[1][0]} {R[1][1]} {R[1][2]} {R[2][0]} {R[2][1]} {R[2][2]}\n")
                
                # Intrinsic parameters
                f.write(f"{intrinsic_param.flen_normalized} 0 0 {intrinsic_param.pixel_aspect_ratio} {0.5 - intrinsic_param.shiftX} {0.5 + intrinsic_param.shiftY}\n")

            # 匯出相機對應的圖片
            self.export_image_of_camera(z_forward_camera, img_path)
        
        self.report({'INFO'}, f"Exported {len(already_exported_cameras)} cameras to {self.directory}")
        return {'FINISHED'}
