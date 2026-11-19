"""
RealityScan 如果選擇以 RealityScan XMPs with Image List 格式匯出 Registration 結果，
則會匯出一個 .imagelist 記錄所有相機，並為每個相機匯出一個 XMP 記錄相機參數

XMP 格式類似如下（RealityScan 2.1.1）：
```
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xcr:Version="4" xcr:ExportCoordinateSystemType="0" xcr:PosePrior="locked"
       xcr:Coordinates="absolute" xcr:DistortionModel="perspective" xcr:DistortionCoeficients="0 0 0 0 0 0"
       xcr:FocalLength35mm="24.4164600892414" xcr:Skew="0" xcr:AspectRatio="1"
       xcr:PrincipalPointU="0.000867625185919697" xcr:PrincipalPointV="0.0022310361923649"
       xcr:CalibrationPrior="exact" xcr:CalibrationGroup="-1" xcr:DistortionGroup="-1"
       xcr:InTexturing="1" xcr:InMeshing="1" xcr:latitude="179.993539916949430N"
       xcr:longitude="127.338989004636773W" xcr:version="2.2.0.0" xcr:altitude="642359440/10000"
       xmlns:xcr="http://www.capturingreality.com/ns/xcr/1.1#">
      <xcr:Rotation>0.734046384405981 0.679083509835349 -0.00463596917688166 -0.0505993412574241 0.0478844755006662 -0.99757044045538 -0.677211645059963 0.732497551992994 0.069510604366889</xcr:Rotation>
      <xcr:Position>-47.3106150384215 -62.0164679689369 4.80535589996725</xcr:Position>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
```

XMP 中比較重要的資訊有：
- xcr:ExportCoordinateSystemType -> 0: Grid Plane
- xcr:FocalLength35mm -> 35mm equivalent focal length。當 sensor 大小為 width 36mm 時，等效的 focal length (mm)
- xcr:AspectRatio -> pixel aspect ratio
- xcr:PrincipalPointU -> normalized by longer dimension
- xcr:PrincipalPointV -> normalized by longer dimension
- xcr:Rotation -> Rw2c
- xcr:Position -> Tc2w

Note: 
  PrincipalPoint U/V 為 Principal Point 在圖片上的位置，其中圖片中心為 (0, 0)，向右為 +X ，向下為 +Y 。
  PrincipalPointU 在右邊（ > 0 ）時，成像平面要向左移（ shiftX < 0 ），所以 xcr:PrincipalPointU 正比於 -shiftX。
  PrincipalPointV 在下面（ > 0 ）時，成像平面要向上移（ shiftY > 0 ），所以 xcr:PrincipalPointV 正比於 shiftY。


參考：[RealityCapture XMP Camera Math](https://dev.epicgames.com/community/learning/knowledge-base/vzwB/realityscan-realitycapture-xmp-camera-math)
"""
import bpy
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
from pathlib import Path
import mathutils
import xml.etree.ElementTree as ET

from .base import CommonImporterProperty
from ..camera import *

XMP_NAMESPACE = "http://www.capturingreality.com/ns/xcr/1.1#"


def _xmp_attribute(description, name):
    """
    RealityScan XMP 的自訂屬性以完整命名空間儲存在 rdf:Description。
    先用 Clark notation "{namespace}name" 查找，若 XMP 未綁定命名空間則退回無前綴名稱。
    """
    value = description.attrib.get(f"{{{XMP_NAMESPACE}}}{name}")
    if value is None:
        value = description.attrib.get(name)
    return value


def _xmp_child_text(description, name):
    """
    xcr:Rotation 與 xcr:Position 是 rdf:Description 的子節點，而非屬性。
    優先尋找完整命名空間；找不到時再嘗試無前綴節點名稱，以提高格式相容性。
    """
    element = description.find(f"{{{XMP_NAMESPACE}}}{name}")
    if element is None:
        element = description.find(name)
    return element.text if element is not None and element.text else None


class JBY_OT_RealityScanImporter(bpy.types.Operator, ImportHelper, CommonImporterProperty):
    """ Load the cameras from RealityScan XMPs with Image List """
    bl_idname = "jby.load_realityscan_undistorted"
    bl_label = "RealityScan XMPs with Image List (.imagelist)"
    bl_options = {'REGISTER', 'UNDO'}

    # property for ImportHelper
    filename_ext = ".imagelist"
    filter_glob: StringProperty(default="*.imagelist", options={'HIDDEN'}) #type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore

    ignore_ExportCoordinateSystemType: BoolProperty(
        name="Ignore Export Coordinate System Type",
        description=
        """
        是否要忽略 ExportCoordinateSystemType ，並強行匯入使用任意座標系記錄的 XMP。
        \n\n預設情況下，只有在從 RealityScan 匯出時 Coordinate System 選擇 Grid Plane 才會進行匯入。
        """,
        default=False,
    ) # type: ignore

    def execute(self, context):
        # Read .imagelist
        try:
            with open(self.filepath, encoding='UTF-16') as fp:
                img_list = fp.readlines()
        except (UnicodeDecodeError, OSError):
            try:
                with open(self.filepath, encoding='utf-8-sig') as fp:
                    img_list = fp.readlines()
            except (UnicodeDecodeError, OSError) as error:
                self.report({'ERROR'}, f"Cannot read image list: {error}")
                return {'CANCELLED'}

        # Create Collection
        collection = bpy.data.collections.new("RealityScan Undistorted")
        bpy.context.scene.collection.children.link(collection)

        # For each image
        for img_path in img_list:
          img_path = Path(img_path.strip().strip('"'))
          if not img_path.is_absolute():
              img_path = Path(self.filepath).parent / img_path
          xmp_path = img_path.with_suffix('.xmp')
          
          try:
              xmp_tree = ET.parse(str(xmp_path))
          except (ET.ParseError, OSError) as error:
              self.report({'ERROR'}, f"Cannot read XMP for {img_path.name}: {error}")
              continue

          xmp_root = xmp_tree.getroot()
          description = xmp_root.find('.//{http://www.w3.org/1999/02/22-rdf-syntax-ns#}Description')
          if description is None:
              description = xmp_root.find('.//rdf:Description', {
                  'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
              })
          if description is None:
              self.report({'ERROR'}, f"No XMP camera description in {xmp_path.name}")
              continue

          # 檢查是否為 Grid Plane Coordinate System
          if not self.ignore_ExportCoordinateSystemType:
              if _xmp_attribute(description, 'ExportCoordinateSystemType') != '0':
                  self.report({'ERROR'}, f"SHOT: {img_path.name} ExportCoordinateSystemType is not Grid Plane")
                  continue

          # Create Camera
          camera = ZForwardCamera(add_arrows=self.add_arrows)
          camera.rename(img_path.name)

          try:
              # Load image first so intrinsic parameters use the actual source resolution.
              blender_img = bpy.data.images.load(str(img_path))
              img_width, img_height = blender_img.size
              print(f"{img_path} is loaded")

              # Intrinsic #################################################################
              focal_35mm = float(_xmp_attribute(description, 'FocalLength35mm'))
              aspect_ratio = float(_xmp_attribute(description, 'AspectRatio'))
              shift_x = -float(_xmp_attribute(description, 'PrincipalPointU')) * max(img_width, img_height) / img_width
              shift_y = float(_xmp_attribute(description, 'PrincipalPointV')) * max(img_width, img_height) / img_height

              if aspect_ratio != 1.0:
                  self.report({'WARNING'}, f"SHOT: {img_path.name} aspect ratio != 1")

              # 先對 focal_35mm 縮放到 image 的 pixel 尺度，再除以最長邊做正規化
              flen_normalized = focal_35mm * (img_width / 36.0) / max(img_width, img_height)
              camera.apply_intrinsic_param(
                  IntrinsicParameter(
                      flen_normalized,
                      img_width,
                      img_height,
                      shift_x,
                      shift_y
                  )
              )

              # Extrinsic #################################################################
              rotation_text = _xmp_child_text(description, 'Rotation')
              position_text = _xmp_child_text(description, 'Position')
              if not rotation_text or not position_text:
                  raise ValueError("Missing Rotation or Position")

              rotation_values = [float(value) for value in rotation_text.split()]
              position_values = [float(value) for value in position_text.split()]
              if len(rotation_values) != 9 or len(position_values) != 3:
                  raise ValueError("Invalid Rotation or Position")

              R_w2c = mathutils.Matrix((
                  tuple(rotation_values[0:3]),
                  tuple(rotation_values[3:6]),
                  tuple(rotation_values[6:9])
              ))
              T_c2w = mathutils.Vector(tuple(position_values))

              # ExtrinsicParameter stores world-to-camera values.
              T_w2c = (-1 * R_w2c) @ T_c2w
              camera.apply_extrinsic_param(ExtrinsicParameter(R_w2c, T_w2c))

              distortion_model = _xmp_attribute(description, 'DistortionModel')
              distortion = _xmp_attribute(description, 'DistortionCoeficients')
              if distortion_model and distortion_model.lower() != 'perspective':
                  self.report({'WARNING'}, f"SHOT: {img_path.name} is distorted")
              elif distortion:
                  try:
                      if any(float(value) != 0.0 for value in distortion.split()):
                          self.report({'WARNING'}, f"SHOT: {img_path.name} is distorted")
                  except ValueError:
                      pass

              # Background #######################################################################
              if self.add_background:
                  camera.set_bg_image(blender_img)
              else:
                  bpy.data.images.remove(blender_img)

              camera.move_to_collection(collection)
          except (OSError, RuntimeError, ValueError, TypeError) as error:
              self.report({'ERROR'}, f"Cannot load camera {img_path.name}: {error}")
              camera.delete()
        return {'FINISHED'}
