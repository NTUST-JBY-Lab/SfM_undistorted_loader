import bpy
from bpy.props import *
from bpy_extras.io_utils import ImportHelper
import mathutils
import json
import os

from .base import CommonImporterProperty
from ..camera import *

class JBY_OT_OpenSfmImporter(bpy.types.Operator, ImportHelper, CommonImporterProperty):
    """ Load the cameras from OpenSfm reconstruction.json """
    bl_idname = "jby.load_opensfm_undistorted"
    bl_label = "OpenSfM Undistorted (.json)"
    bl_options = {'REGISTER', 'UNDO'}

    # property for ImportHelper
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'}) #type: ignore
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore

    def execute(self, context):
        # Parse Json
        with open(self.filepath, encoding='utf8') as fp:
            try:
                recons = json.load(fp)
            except json.JSONDecodeError:
                self.report({'ERROR'}, "Invalid JSON")
                return {'CANCELLED'}

        # Create Collection
        collection = bpy.data.collections.new("OpenSfM Undistorted")
        bpy.context.scene.collection.children.link(collection)

        # for each camera parse its intrinsic & extrinsic parameter
        # then apply parameter to the ZForwardCamera
        for recon in recons:
            for shot_id, shot in recon['shots'].items():
                camera = ZForwardCamera(add_arrows=self.add_arrows)
                camera.rename(shot_id)

                # intrinsic
                camera_model = recon['cameras'][shot['camera']]
                if camera_model['projection_type'] != 'perspective' or camera_model['k1'] != 0 or camera_model['k2'] != 0:
                    self.report({'WARNING'}, f"SHOT: {shot_id} is distorted")
                camera.apply_intrinsic_param(IntrinsicParameter(camera_model['focal'], camera_model['width'], camera_model['height']))

                # extrinsic
                axis_angle_vec = mathutils.Vector(shot['rotation'])
                angle = axis_angle_vec.length
                axis_vec = axis_angle_vec / angle
                R = mathutils.Matrix.Rotation(angle, 3, axis_vec)
                T = mathutils.Vector(shot['translation'])
                camera.apply_extrinsic_param(ExtrinsicParameter(R, T))

                # load image
                if self.add_background:
                    img = bpy.data.images.load(os.path.join(os.path.dirname(self.filepath), "images", shot_id))
                    camera.set_bg_image(img)

                camera.move_to_collection(collection)
        return {'FINISHED'}
