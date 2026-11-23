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
from bpy_extras.io_utils import ImportHelper
import mathutils
from pathlib import Path

from .base import CommonImporterProperty
from ..camera import *

class JBY_OT_LTBCSceneImporter(bpy.types.Operator, ImportHelper, CommonImporterProperty):
    """ Load the cameras from LTBC scene folder """
    bl_idname = "jby.load_ltbc_scene_undistorted"
    bl_label = "LTBC Scene Folder Undistorted (folder with images + .cam)"
    bl_options = {'REGISTER', 'UNDO'}

    # property for ImportHelper
    # filename_ext = ".json"
    # filter_glob: StringProperty(default="*.json", options={'HIDDEN'}) #type: ignore
    # 覆寫或新增 directory 屬性，檔案瀏覽器會優先抓這個來當作目錄選擇模式
    directory: StringProperty(subtype='DIR_PATH') #type: ignore 
    filepath: StringProperty(subtype='FILE_PATH') #type: ignore

    def execute(self, context):
        scene_path = Path(self.directory or self.filepath)
        if not scene_path.is_dir():
            self.report({'ERROR'}, "Please select an LTBC scene folder")
            return {'CANCELLED'}

        image_extensions = {
            ".bmp", ".exr", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff"
        }
        scene_files = [
            path for path in scene_path.iterdir()
            if path.is_file()
        ]
        cam_paths = {
            path.stem.casefold(): path
                for path in scene_files
                if path.suffix.lower() == ".cam"
        }
        image_paths = [
            path for path in scene_files
                 if path.suffix.lower() in image_extensions
        ]
        if not cam_paths:
            self.report({'ERROR'}, f"No .cam files found in {scene_path}")
            return {'CANCELLED'}

        # Create Collection
        collection = bpy.data.collections.new("LTBC Scene Undistorted")
        bpy.context.scene.collection.children.link(collection)

        # For each image
        for image_path in image_paths:
            # Find corresponding .cam
            cam_path = cam_paths.get(image_path.stem.casefold())
            if cam_path is None:
                continue

            camera = None
            blender_img = None
            try:
                ######################################################################
                # 讀圖片
                ######################################################################
                blender_img = bpy.data.images.load(str(image_path))
                img_width, img_height = blender_img.size
                if not img_width or not img_height:
                    raise ValueError("Image has an invalid resolution")
                print(f"{image_path} is loaded")
                
                with cam_path.open(encoding="utf-8") as cam_file:
                    lines = [
                        line.split("#", 1)[0].split()
                        for line in cam_file
                        if line.split("#", 1)[0].strip()
                    ]
                if len(lines) < 2:
                    raise ValueError("A .cam file must contain two data lines")

                ######################################################################
                # Parse .cam
                ######################################################################
                extrinsic_values = [float(value) for value in lines[0]]
                intrinsic_values = [float(value) for value in lines[1]]
                if len(extrinsic_values) != 12:
                    raise ValueError("Extrinsics must contain 12 values")
                if len(intrinsic_values) != 6:
                    raise ValueError("Intrinsics must contain 6 values")

                tx, ty, tz = extrinsic_values[:3]
                rotation_values = extrinsic_values[3:]
                R_w2c = mathutils.Matrix((
                    tuple(rotation_values[0:3]),
                    tuple(rotation_values[3:6]),
                    tuple(rotation_values[6:9])
                ))

                focal, d0, d1, pixel_aspect, ppx, ppy = intrinsic_values
                if pixel_aspect <= 0:
                    raise ValueError("Pixel aspect ratio must be positive")
                if pixel_aspect != 1:
                    self.report(
                        {'WARNING'},
                        f"SHOT: {cam_path.stem} pixel aspect ratio is {pixel_aspect}"
                    )
                if d0 != 0 or d1 != 0:
                    self.report({'WARNING'}, f"SHOT: {cam_path.stem} is distorted")

                ######################################################################
                # 建立相機 + 設定參數
                ######################################################################
                camera = ZForwardCamera(add_arrows=self.add_arrows)
                camera.rename(image_path.name)
                camera.set_property(ZForwardCamera.Prop.img_path, str(image_path))
                camera.apply_intrinsic_param(IntrinsicParameter(
                    focal,
                    img_width,
                    img_height,
                    0.5 - ppx,
                    ppy - 0.5,
                    pixel_aspect
                ))
                camera.apply_extrinsic_param(ExtrinsicParameter(
                    R_w2c,
                    mathutils.Vector((tx, ty, tz))
                ))

                if self.add_background:
                    camera.set_bg_image(blender_img)
                    blender_img = None
                camera.move_to_collection(collection)
            except (OSError, RuntimeError, ValueError, TypeError) as error:
                self.report({'ERROR'}, f"Cannot load {cam_path.name}: {error}")
                if camera is not None:
                    camera.delete()
            finally:
                if blender_img is not None:
                    bpy.data.images.remove(blender_img)

        return {'FINISHED'}