import bpy
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
import mathutils
import json
import math
import os

class ExtrinsicParameter:
    """
    描述相機的位置和旋轉。外參可用來將世界座標轉換到相機座標。

    Camera Space := z forward, x right, -y up

    ```
    world_to_camera_matrix = 
        [[ R      , T ],
         [ 0, 0, 0, 1 ]]
    ```
    """
    R: mathutils.Matrix
    T: mathutils.Vector
    
    def __init__(self, R: mathutils.Matrix, T: mathutils.Vector):
        self.R = R
        self.T = T
        
    def get_world_to_cam_matrix(self) -> mathutils.Matrix:
        return mathutils.Matrix([
            [self.R[0][0], self.R[0][1], self.R[0][2], self.T[0]],
            [self.R[1][0], self.R[1][1], self.R[1][2], self.T[1]],
            [self.R[2][0], self.R[2][1], self.R[2][2], self.T[2]],
            [0           , 0           , 0           , 1        ]
        ])
    
    def get_cam_to_world_matrix(self) -> mathutils.Matrix:
        M = self.get_world_to_cam_matrix()
        M.invert()
        return M

class IntrinsicParameter:
    """
    成像平面在相機座標系中的相對位置、大小。
    """
    flen_normalized: float
    """ 
    The focal length is the distance between camera center and image plane normalized by dividing with the larger image dimension.
    """
    img_width: int
    img_height: int
    
    def __init__(self, flen_normalized: float, img_width: int, img_height: int):
        self.flen_normalized = flen_normalized
        self.img_width = img_width
        self.img_height = img_height

class ZForwardCamera:
    __base_obj: bpy.types.Object
    __camera_obj: bpy.types.Object
    
    def __init__(self, *, add_arrows: bool=True):
        """
        :param add_arrows: 是否要為相機多加一個箭頭作為父物件，輔助顯示相機的區域座標系
        """
        bpy.ops.object.camera_add(enter_editmode=False, align='VIEW', location=(0, 0, 0), rotation=(math.pi, 0, 0), scale=(1, 1, 1))
        self.__camera_obj = bpy.context.object

        if add_arrows:
            self.__camera_obj.use_camera_lock_parent = True
            self.__camera_obj.lock_rotation[:] = [True, True, True]
            self.__camera_obj.lock_location[:] = [True, True, True]

            bpy.ops.object.empty_add(type='ARROWS', align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
            self.__base_obj = bpy.context.object            
            self.__camera_obj.parent = self.__base_obj
        else:
            self.__camera_obj.rotation_axis_angle = (0, 0, 0, 0)
            self.__base_obj = self.__camera_obj

        self.rename('Z Forward Camera')

    def has_arrows(self) -> bool:
        """ 是否有箭頭父物件 """
        return self.__base_obj is not self.__camera_obj

    def rename(self, name: str):
        self.__base_obj.name = name
        if self.has_arrows():
            self.__camera_obj.name = f"{name} Camera"

    def move_to_collection(self, collection: bpy.types.Collection):
        cs = self.__base_obj.users_collection
        for c in cs:
            c.objects.unlink(self.__base_obj)

        collection.objects.link(self.__base_obj)
        
    def apply_extrinsic_param(self, param: ExtrinsicParameter):
        if self.has_arrows():
            self.__base_obj.matrix_world = param.get_cam_to_world_matrix()
        else:
            self.__base_obj.matrix_world = param.get_cam_to_world_matrix() @ mathutils.Matrix.Rotation(math.pi, 4, (1, 0, 0))
        
    def apply_intrinsic_param(self, param: IntrinsicParameter):
        if param.img_height >= param.img_width:
            # Fit Vertical -> 成像平面的高固定為 sensor_height
            self.__camera_obj.data.sensor_fit = 'VERTICAL'
            
            # 固定成像平面的高度，然後按比例將 focal length 縮放為 f'
            # f : img_height = f' : sensor_height
            # f' = f * sensor_height / img_height = f_normalized * sensor_height
            self.__camera_obj.data.lens = param.flen_normalized * self.__camera_obj.data.sensor_height
        else:
            # Fit Horizontal -> 成像平面的寬固定為 sensor_width
            self.__camera_obj.data.sensor_fit = 'HORIZONTAL'
            
            # 固定成像平面的寬度，然後按比例將 focal length 縮放為 f'
            # f : img_width = f' : sensor_width
            # f' = f * sensor_width / img_width = f_normalized * sensor_width
            self.__camera_obj.data.lens = param.flen_normalized * self.__camera_obj.data.sensor_width

    def set_bg_image(self, img: bpy.types.Image):
        # 設置圖片
        camera_data : bpy.types.Camera = self.__camera_obj.data
        camera_data.show_background_images = True
        if len(camera_data.background_images) == 0:
            camera_data.background_images.new()
        camera_data.background_images[0].image = img
        camera_data.background_images[0].source = 'IMAGE'

        # 顯示在前
        camera_data.background_images[0].display_depth = 'FRONT'
        camera_data.background_images[0].alpha = 0.5

        # 調整長寬
        res_width = bpy.context.scene.render.resolution_x
        res_height = bpy.context.scene.render.resolution_y

        if camera_data.sensor_fit == 'VERTICAL':
            # 將圖片高度縮放到和 res_height 一樣
            # img_height : img_width = res_height : w'
            # w' = img_width * res_height / img_height
            w = img.size[0] * res_height / img.size[1]
            camera_data.background_images[0].frame_method = 'FIT' if w <= res_width else 'CROP'
        elif camera_data.sensor_fit == 'HORIZONTAL':
            # 將圖片寬度縮放到和 res_width 一樣
            # img_width : img_height = res_width : h'
            # h' = img_height * res_width / img_width
            h = img.size[1] * res_width / img.size[0]
            camera_data.background_images[0].frame_method = 'FIT' if h <= res_height else 'CROP'

#########################################
#region Operator
#########################################

class JBY_OT_OpenSfmLoader(bpy.types.Operator, ImportHelper):
    """ Load the cameras from OpenSfm reconstruction.json """
    bl_idname = "jby.load_opensfm_undistorted"
    bl_label = "OpenSfM Undistorted (.json)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'}) #type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore
    add_arrows: BoolProperty(
        name="Add Arrows to Camera",
        description="是否要為相機多加一個箭頭作為父物件，輔助顯示相機的區域座標系",
        default=False
    ) #type: ignore

    def execute(self, context):
        # Parse
        with open(self.filepath, encoding='utf8') as fp:
            try:
                recons = json.load(fp)
            except json.JSONDecodeError:
                self.report({'ERROR'}, "Invalid JSON")
                return {'CANCELLED'}

        collection = bpy.data.collections.new("OpenSfM Undistorted")
        bpy.context.scene.collection.children.link(collection)

        for recon in recons:
            for shot_id, shot in recon['shots'].items():
                # intrinsic
                camera_model = recon['cameras'][shot['camera']]
                if camera_model['projection_type'] != 'perspective' or camera_model['k1'] != 0 or camera_model['k2'] != 0:
                    self.report({'WARNING'}, f"SHOT: {shot_id} is distorted, not load")
                    continue

                camera = ZForwardCamera(add_arrows=self.add_arrows)
                camera.rename(shot_id)
                camera.apply_intrinsic_param(IntrinsicParameter(camera_model['focal'], camera_model['width'], camera_model['height']))

                # extrinsic
                axis_angle_vec = mathutils.Vector(shot['rotation'])
                angle = axis_angle_vec.length
                axis_vec = axis_angle_vec / angle
                R = mathutils.Matrix.Rotation(angle, 3, axis_vec)
                T = mathutils.Vector(shot['translation'])
                camera.apply_extrinsic_param(ExtrinsicParameter(R, T))

                # load image
                img = bpy.data.images.load(os.path.join(os.path.dirname(self.filepath), "images", shot_id))
                camera.set_bg_image(img)

                camera.move_to_collection(collection)
        return {'FINISHED'}

#########################################
#region Menu
#########################################

class JBY_MT_SfM_Undistorted_Loader(bpy.types.Menu):
    bl_idname = "JBY_MT_SfM_Undistorted_Loader"
    bl_label = "SfM Undistorted Loader"

    def draw(self, context):
        """ 
        跟據 https://stackoverflow.com/a/65126811/20876404
        在 Menu 內的 Operator 才能從 F3 搜尋
        """
        layout = self.layout
        layout.operator('jby.load_opensfm_undistorted')
    

# cam = ZForwardCamera()
# R = mathutils.Quaternion((0.029876219948195382, 0.09597804823050295, -0.9478391790613576, 0.30248391093703103)).to_matrix()
# T = -(R @ mathutils.Vector((0.3402451508013547, -0.27393187356265014, 6.730133955505699)))
# ext_param = ExtrinsicParameter(R, T)
# cam.apply_extrinsic_param(ext_param)

# in_param = IntrinsicParameter(2320.667972955844 / 2560, 2560, 1440)
# cam.apply_intrinsic_param(in_param)

# cam.base_obj.name = '24.png.tif'

def file_import_menu_func(self, context):
    self.layout.menu(JBY_MT_SfM_Undistorted_Loader.bl_idname)

classes = [
    JBY_OT_OpenSfmLoader,
    JBY_MT_SfM_Undistorted_Loader
]

def register():
    for c in classes:
        bpy.utils.register_class(c)

    # File > Import
    bpy.types.TOPBAR_MT_file_import.append(file_import_menu_func)

def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)

    bpy.types.TOPBAR_MT_file_import.remove(file_import_menu_func)

if __name__ == "__main__":
    register()
