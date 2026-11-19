"""
這個 Module 定義了 ExtrinsicParameter, IntrinsicParameter, ZForwardCamera

Importer 使用順序：
1. 從檔案 parse 出相機參數並存在 ExtrinsicParameter, IntrinsicParameter 中
2. 建立 ZForwardCamera 並應用參數
3. (Optional) 載圖片後 -> set_bg_image
"""

import bpy
import mathutils
import math

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
    The focal length is the distance between camera center and image plane normalized by `max(img_width, img_height)`.
    """
    img_width: int
    """
    The width of the source image
    """
    img_height: int
    """
    The height of the source image
    """
    shiftX: float
    """
    Move the image plane right relative to the camera's optical axis.
    The length is normalized by `max(img_width, img_height)`.
    """
    shiftY: float
    """
    Move the image plane up relative to the camera's optical axis.
    The length is normalized by `max(img_width, img_height)`.
    """
    
    def __init__(self, flen_normalized: float, img_width: int, img_height: int, shiftX: float = 0, shiftY: float = 0):
        self.flen_normalized = flen_normalized
        self.img_width = img_width
        self.img_height = img_height
        self.shiftX = shiftX
        self.shiftY = shiftY

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

    def delete(self):
        """ 將自己清除 """
        if self.has_arrows():
            bpy.data.objects.remove(self.__base_obj)

        camera_data = self.__camera_obj.data
        bpy.data.objects.remove(self.__camera_obj)
        bpy.data.cameras.remove(camera_data)

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
        res_width = bpy.context.scene.render.resolution_x
        res_height = bpy.context.scene.render.resolution_y
        res_aspect = res_width / res_height

        img_aspect = param.img_width / param.img_height
        flen = param.flen_normalized * max(param.img_width, param.img_height)

        # 如果 Render Resolution 比輸入的影像還寬，則將影像垂直縮放可以避免寬超出去
        if res_aspect > img_aspect:
            # Fit Vertical -> 成像平面的高固定為 sensor_height
            self.__camera_obj.data.sensor_fit = 'VERTICAL'
            
            # 固定成像平面的高度，然後按比例將 focal length 縮放為 f'
            # f : img_height = f' : sensor_height
            # f' = f * sensor_height / img_height
            self.__camera_obj.data.lens = flen * self.__camera_obj.data.sensor_height / param.img_height
        else:
            # Fit Horizontal -> 成像平面的寬固定為 sensor_width
            self.__camera_obj.data.sensor_fit = 'HORIZONTAL'
            
            # 固定成像平面的寬度，然後按比例將 focal length 縮放為 f'
            # f : img_width = f' : sensor_width
            # f' = f * sensor_width / img_width
            self.__camera_obj.data.lens = flen * self.__camera_obj.data.sensor_width / param.img_width

        # Blender 的 shift_x, shift_y 在 VERTICAL FIT 下以 sensor height normalized
        # 在 HORIZONTAL FIT 下以 sensor width normalized
        if (param.img_width >= param.img_height and self.__camera_obj.data.sensor_fit == 'HORIZONTAL') \
            or (param.img_width <= param.img_height and self.__camera_obj.data.sensor_fit == 'VERTICAL'):
            # 在這情況下 param.shiftX/Y 都是以和 blender shift_x/y 同樣方向進行 normalized
            self.__camera_obj.data.shift_x = param.shiftX
            self.__camera_obj.data.shift_y = param.shiftY
        
        elif self.__camera_obj.data.sensor_fit == 'HORIZONTAL':
            # param.shiftX/Y 以垂直方向 normalized，而 blender shift_x/y 以水平方向 normalized
            # 要讓 param.shiftX/Y 換方向 normalized
            self.__camera_obj.data.shift_x = param.shiftX * param.img_height / param.img_width
            self.__camera_obj.data.shift_y = param.shiftY * param.img_height / param.img_width

        else: # self.__camera_obj.data.sensor_fit == 'VERTICAL'
            # param.shiftX/Y 以水平方向 normalized，而 blender shift_x/y 以垂直方向 normalized
            # 要讓 param.shiftX/Y 換方向 normalized
            self.__camera_obj.data.shift_x = param.shiftX * param.img_width / param.img_height
            self.__camera_obj.data.shift_y = param.shiftY * param.img_width / param.img_height


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
