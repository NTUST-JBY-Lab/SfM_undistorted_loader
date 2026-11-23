"""
這個 Module 定義了 ExtrinsicParameter, IntrinsicParameter, ZForwardCamera

Importer 該做的工作如下：
1. 從檔案 parse 出相機參數並存在 ExtrinsicParameter, IntrinsicParameter 中
2. 建立 ZForwardCamera 並應用參數
3. 將原圖片路徑寫入 ZForwardCamera 的 Prop.img_path 屬性，以確保 Exporter 可以找到原圖片
4. (Optional) 載圖片後 -> set_bg_image

Exporter 該做的工作如下：
1. CommonExporterProperty.gather_camera_to_export() -> 取得要匯出的相機列表
2. 提取每個相機的 ExtrinsicParameter, IntrinsicParameter 並匯出到檔案
3. CommonExporterProperty.export_image_of_camera() -> 匯出相機的圖片
"""

import bpy
import mathutils
import math
from enum import StrEnum
from pathlib import Path
import re

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
    Horizontal displacement of the image plane relative to the camera's optical axis.
    The length is normalized by `img_width`.
    Positive values move the image plane to the right.
    """
    shiftY: float
    """
    Vertical displacement of the image plane relative to the camera's optical axis.
    The length is normalized by `img_height`.
    Positive values move the image plane upward.
    """
    pixel_aspect_ratio: float
    """
    The aspect ratio of the pixel
    """
    
    def __init__(self, flen_normalized: float, img_width: int, img_height: int, shiftX: float = 0, shiftY: float = 0, pixel_aspect_ratio: float = 1):
        self.flen_normalized = flen_normalized
        self.img_width = img_width
        self.img_height = img_height
        self.shiftX = shiftX
        self.shiftY = shiftY
        self.pixel_aspect_ratio = pixel_aspect_ratio

class ZForwardCamera:
    __base_obj: bpy.types.Object
    __camera_obj: bpy.types.Object

    class Prop(StrEnum):
        hasArrow = "__sfm_undistorted_loader__hasArrow"
        flen_normalized = "__sfm_undistorted_loader__flen_normalized"
        img_width = "__sfm_undistorted_loader__img_width"
        img_height = "__sfm_undistorted_loader__img_height"
        img_path = "__sfm_undistorted_loader__img_path"
        shiftX = "__sfm_undistorted_loader__shiftX"
        shiftY = "__sfm_undistorted_loader__shiftY"
        pixel_aspect_ratio = "__sfm_undistorted_loader__pixel_aspect_ratio"
    
    def __init__(self, *, add_arrows: bool=False, camera_obj: bpy.types.Object=None):
        """
        ZForwardCamera is a class that represents a camera with a Z-forward coordinate system.
        
        由於 Blender 預設的相機座標系為 -Z 朝前，而 Computer Vision 中通常使用 Z 朝前的座標系。
        所以這個類別用來將 Z 朝前的相機參數轉換成 Blender 的相機參數。

        :param add_arrows: 是否要為相機多加一個箭頭作為父物件，輔助顯示相機的區域座標系
        :param camera_obj: 
            如果已經有相機物件，則沿用這個物件作為相機。

            當 `camera_obj` 不為 None 時， `base_obj` 的處理如下：
            1. 如果 `add_arrows` 為 `True` -> 增加一個箭頭作為 `camera_obj` 的父物件， `base_obj` 為該箭頭物件。
            2. 否則如果 `camera_obj` 的 "hasArrow" 屬性為 `True` -> 沿用 `camera_obj` 的父物件作為 `base_obj`
            3. 否則 -> `base_obj` 為 `camera_obj` 本身
        
        :raises ValueError: 如果 `camera_obj` 不是相機物件，則會拋出 `ValueError`
        """
        create_new_camera = camera_obj is None

        if create_new_camera:
            bpy.ops.object.camera_add(enter_editmode=False, align='VIEW', location=(0, 0, 0), rotation=(math.pi, 0, 0), scale=(1, 1, 1))
            self.__camera_obj = bpy.context.object
        else:
            if camera_obj.type != 'CAMERA':
                raise ValueError("camera_obj must be a camera object")
            self.__camera_obj = camera_obj

        # 如果要加箭頭，則建立一個箭頭物件作為相機的父物件
        if add_arrows:
            bpy.ops.object.empty_add(type='ARROWS', align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
            self.__base_obj = bpy.context.object
            # 將 camera object 的 parent 替換為 base object
            self.__base_obj.parent = self.__camera_obj.parent
            self.__camera_obj.parent = self.__base_obj
            self.__camera_obj[self.Prop.hasArrow] = True

            # 如果不是新建立的相機物件，則將相機物件的 transform 移到 base object 上
            if not create_new_camera:
                self.__camera_obj.lock_rotation[:] = [False, False, False]
                self.__camera_obj.lock_location[:] = [False, False, False]
                self.__camera_obj.lock_scale[:] = [False, False, False]

                self.__base_obj.matrix_world = self.__camera_obj.matrix_world @ mathutils.Matrix.Rotation(math.pi, 4, (1, 0, 0))
                self.__camera_obj.matrix_basis = mathutils.Matrix.Rotation(math.pi, 4, (1, 0, 0))

            # Lock Editing
            self.__camera_obj.use_camera_lock_parent = True
            self.__camera_obj.lock_rotation[:] = [True, True, True]
            self.__camera_obj.lock_location[:] = [True, True, True]
        # 如果相機物件已經有箭頭父物件，則沿用該父物件作為 base object
        elif self.Prop.hasArrow in self.__camera_obj and self.__camera_obj[self.Prop.hasArrow]:
            self.__base_obj = self.__camera_obj.parent
        # 如果相機物件沒有箭頭父物件，則 base object 就是相機物件本身
        else:
            self.__base_obj = self.__camera_obj
            self.__camera_obj[self.Prop.hasArrow] = False

        if create_new_camera:
            self.rename('Z Forward Camera')

    ######################################################################################
    # region Property
    ######################################################################################
    def get_property(self, prop: 'ZForwardCamera.Prop'):
        """ 取得相機物件的自訂屬性 """
        return self.__camera_obj[prop] if prop in self.__camera_obj else None

    def set_property(self, prop: 'ZForwardCamera.Prop', value):
        """ 設定相機物件的自訂屬性 """
        self.__camera_obj[prop] = value

    def get_save_img_name(self) -> str:
        """ The name to use when exporting the image. """
        img_path = self.get_property(ZForwardCamera.Prop.img_path)

        if img_path:
            return Path(img_path).name
        else:
            # Use the camera object name as a fallback, replacing invalid characters with underscores
            return re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', self.__camera_obj.name) + '.png'

    def has_arrows(self) -> bool:
        """ 是否有箭頭父物件 """
        return self.__camera_obj[self.Prop.hasArrow]

    def get_camera_obj(self) -> bpy.types.Object:
        """ 取得相機物件 """
        return self.__camera_obj

    def get_base_obj(self) -> bpy.types.Object:
        """ 取得箭頭父物件（如果 has_arrows 為 True，否則為相機物件） """
        return self.__base_obj

    def remove_arrow(self):
        """ 移除箭頭父物件，並將相機物件的 parent 設為原本箭頭父物件的 parent """
        if self.has_arrows():
            # unlock
            self.__camera_obj.lock_location[:] = [False, False, False]
            self.__camera_obj.lock_rotation[:] = [False, False, False]
            self.__camera_obj.lock_scale[:] = [False, False, False]

            # set camera transform to keep the same world transform
            old_world_matrix = self.__camera_obj.matrix_world.copy()

            # change parent
            self.__camera_obj.parent = self.__base_obj.parent
            self.__camera_obj.matrix_world = old_world_matrix

            # remove arrow
            bpy.data.objects.remove(self.__base_obj)
            self.__camera_obj[self.Prop.hasArrow] = False
            self.__base_obj = self.__camera_obj

    ######################################################################################
    # region Edit
    ######################################################################################
    def delete(self):
        """ 清除相機物件及箭頭父物件 """
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
        # move base obj
        cs = self.__base_obj.users_collection
        for c in cs:
            c.objects.unlink(self.__base_obj)
        collection.objects.link(self.__base_obj)

        # move camera obj
        if self.has_arrows():
            cs = self.__camera_obj.users_collection
            for c in cs:
                c.objects.unlink(self.__camera_obj)
            collection.objects.link(self.__camera_obj)

    ######################################################################################
    # region Camera Parameter
    ######################################################################################
    def extract_extrinsic_param(self) -> ExtrinsicParameter:
        """ 提取相機的外參 （World to Camera Transform） """
        if self.has_arrows():
            cam_to_world = self.__base_obj.matrix_world
        else:
            cam_to_world = self.__camera_obj.matrix_world @ mathutils.Matrix.Rotation(math.pi, 4, (1, 0, 0))
        world_to_cam = cam_to_world.inverted()

        R = world_to_cam.to_3x3()
        T = world_to_cam.to_translation()

        return ExtrinsicParameter(R, T)

    def apply_extrinsic_param(self, param: ExtrinsicParameter):
        if self.has_arrows():
            self.__base_obj.matrix_world = param.get_cam_to_world_matrix()
        else:
            self.__base_obj.matrix_world = param.get_cam_to_world_matrix() @ mathutils.Matrix.Rotation(math.pi, 4, (1, 0, 0))

    def cache_intrinsic_param(self, param: IntrinsicParameter):
        """
        將內參快取到相機物件的自訂屬性中。
        方便 Exporter 取得，以及避免 resolution 修改而導致讀入的內參和 Blender 中的不一致。
        """
        self.__camera_obj[self.Prop.flen_normalized] = param.flen_normalized
        self.__camera_obj[self.Prop.img_width] = param.img_width
        self.__camera_obj[self.Prop.img_height] = param.img_height
        self.__camera_obj[self.Prop.shiftX] = param.shiftX
        self.__camera_obj[self.Prop.shiftY] = param.shiftY
        self.__camera_obj[self.Prop.pixel_aspect_ratio] = param.pixel_aspect_ratio

    def extract_intrinsic_param(self, use_cache: bool = True) -> IntrinsicParameter:
        """
        從相機物件中提取內參，若 use_cache 為 True，則會先嘗試從相機物件的自訂屬性中讀取內參。

        :param use_cache: 
            是否使用快取。

            - 若為 True，則會從相機物件的自訂屬性中讀取內參。
            - 若為 False，則會直接從相機物件中提取內參。

        :return intrinsic: 提取到的內參
        """
        if use_cache:
            try:
                flen_normalized = self.__camera_obj[self.Prop.flen_normalized]
                img_width = self.__camera_obj[self.Prop.img_width]
                img_height = self.__camera_obj[self.Prop.img_height]
                shiftX = self.__camera_obj[self.Prop.shiftX]
                shiftY = self.__camera_obj[self.Prop.shiftY]
                pixel_aspect_ratio = self.__camera_obj[self.Prop.pixel_aspect_ratio]
                
                return IntrinsicParameter(flen_normalized, img_width, img_height, shiftX, shiftY, pixel_aspect_ratio)
            except KeyError:
                pass

        ################################################################
        # 從相機物件中提取內參
        ################################################################
        # 畫面大小 = Render Resolution
        img_width = bpy.context.scene.render.resolution_x
        img_height = bpy.context.scene.render.resolution_y

        # 如果相機的 sensor_fit 不是 AUTO，則使用相機的 sensor_fit，否則根據畫面大小決定 sensor_fit
        if self.__camera_obj.data.sensor_fit != 'AUTO':
            sensor_fit = self.__camera_obj.data.sensor_fit  
        else:
            sensor_fit = ('HORIZONTAL' if img_width >= img_height else 'VERTICAL')

        # 依據 sensor_fit 推出 sensor_width 與 sensor_height
        if sensor_fit == 'VERTICAL':
            sensor_height = self.__camera_obj.data.sensor_height
            sensor_width = sensor_height * img_width / img_height
        else:
            sensor_width = self.__camera_obj.data.sensor_width
            sensor_height = sensor_width * img_height / img_width

        # flen_normalized = f / max(img_width, img_height)
        flen_normalized = self.__camera_obj.data.lens / max(sensor_width, sensor_height)

        # 這是 apply_intrinsic_param 的反推公式，將 blender 的 shift_x/y 轉換成自己定義的 shiftX/Y
        # shiftX = self.__camera_obj.data.shift_x * shift_base_unit / (img_width * pixel_to_mm_scale)
        # shiftY = self.__camera_obj.data.shift_y * shift_base_unit / (img_height * pixel_to_mm_scale)
        pixel_to_mm_scale = (sensor_height / img_height) if sensor_fit == 'VERTICAL' else (sensor_width / img_width)
        shift_base_unit = sensor_height if sensor_fit == 'VERTICAL' else sensor_width
        shiftX = self.__camera_obj.data.shift_x * shift_base_unit / (img_width * pixel_to_mm_scale)
        shiftY = self.__camera_obj.data.shift_y * shift_base_unit / (img_height * pixel_to_mm_scale)

        # pixel_aspect_ratio
        pixel_aspect_ratio = bpy.context.scene.render.pixel_aspect_x / bpy.context.scene.render.pixel_aspect_y

        return IntrinsicParameter(flen_normalized, img_width, img_height, shiftX, shiftY, pixel_aspect_ratio)
        
    def apply_intrinsic_param(self, param: IntrinsicParameter):
        # record
        self.cache_intrinsic_param(param)

        if param.pixel_aspect_ratio != 1:
            print("Pixel aspect ration != 1 is not supported, the visualization willl be incorrect")

        ##################################################################################
        # Img Size & Focal Length
        ##################################################################################
        res_width = bpy.context.scene.render.resolution_x
        res_height = bpy.context.scene.render.resolution_y
        res_aspect = res_width / res_height

        img_aspect = param.img_width / param.img_height
        flen_pixel = param.flen_normalized * max(param.img_width, param.img_height)

        # 如果 Render Resolution 比輸入的影像還寬，則將影像垂直縮放可以避免寬超出去
        if res_aspect > img_aspect:
            # Fit Vertical -> 成像平面的高固定為 sensor_height
            self.__camera_obj.data.sensor_fit = 'VERTICAL'
            
            # 固定成像平面的高度，然後按比例將 focal length 縮放為 f'
            # f : img_height = f' : sensor_height
            # f' = f * sensor_height / img_height
            sensor_height = self.__camera_obj.data.sensor_height
            pixel_to_mm_scale = sensor_height / param.img_height
            self.__camera_obj.data.lens = flen_pixel * pixel_to_mm_scale

            shift_base_unit = sensor_height
        else:
            # Fit Horizontal -> 成像平面的寬固定為 sensor_width
            self.__camera_obj.data.sensor_fit = 'HORIZONTAL'
            
            # 固定成像平面的寬度，然後按比例將 focal length 縮放為 f'
            # f : img_width = f' : sensor_width
            # f' = f * sensor_width / img_width
            sensor_width = self.__camera_obj.data.sensor_width
            pixel_to_mm_scale = sensor_width / param.img_width
            self.__camera_obj.data.lens = flen_pixel * pixel_to_mm_scale

            shift_base_unit = sensor_width

        ##################################################################################
        # Shift
        ##################################################################################
        # Blender 的 shift_x 及 shift_y 會依據不同 Fit 方式而用不同方式正規化
        # VERTICAL Fit -> 將 shift mm 除以 sensor height
        # HORIZONTAL Fit -> 將 shift mm 除以 sensor width
        self.__camera_obj.data.shift_x = param.shiftX * param.img_width * pixel_to_mm_scale / shift_base_unit
        self.__camera_obj.data.shift_y = param.shiftY * param.img_height * pixel_to_mm_scale / shift_base_unit


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
