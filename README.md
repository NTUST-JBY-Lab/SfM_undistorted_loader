# What's this extension for?

This extension allows you to import and export camera parameters and undistorted images from various photogrammetry software. It provides a convenient way to visualize camera poses and image alignment within Blender, making it easier to inspect and understand photogrammetry results during your workflow.

> ⚠️ Only undistorted camera models and images are supported.

> ⚠️ Currently, we assume fx == fy, i.e., a pixel aspect ratio of 1.

# Supported format

## 📥 Supported format that can be imported:

| Software | Format | Note |
| --- | --- | --- |
| OpenSfM | reconstruction.json | Following OpenSfM's convention, images are assumed to be stored in the images folder next to reconstruction.json.
| RealityScan | XMPs with Image List | It's suggested to set "Coordinate System" to "Grid Plane" when exporting the registration. 
| LTBC ([mvs-texturing](https://github.com/nmoehrle/mvs-texturing)) | Scene Folder |

## 📤 Supported format that can be exported:

| Software | Format | Note |
| --- | --- | --- |
| LTBC ([mvs-texturing](https://github.com/nmoehrle/mvs-texturing)) | Scene Folder |


# How to pack the project?

- Build (pack into zip)

```
blender --command extension build
```
