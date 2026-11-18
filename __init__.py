import bpy
from .importers.opensfm_importer import JBY_OT_OpenSfmImporter

#########################################
#region Menu
#########################################

importer_classes = [
    JBY_OT_OpenSfmImporter
]

class JBY_MT_SfM_Undistorted_Loader(bpy.types.Menu):
    bl_idname = "JBY_MT_SfM_Undistorted_Loader"
    bl_label = "SfM Undistorted Loader"

    def draw(self, context):
        """ 
        跟據 https://stackoverflow.com/a/65126811/20876404
        在 Menu 內的 Operator 才能從 F3 搜尋
        """
        layout = self.layout
        for importer in importer_classes:
            layout.operator(importer.bl_idname)
    

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

#########################################
#region Register
#########################################

classes = [
    JBY_MT_SfM_Undistorted_Loader
]
classes += importer_classes

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
