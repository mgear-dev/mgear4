import maya.cmds as cmds
import pymel.core as pm
import maya.mel
import os
import sys

from mgear.core import string


# FBX SDK section
MGEAR_FBX_SDK_PATH = "MGEAR_FBX_SDK_PATH"
FBX_SDK = False

if os.environ.get(MGEAR_FBX_SDK_PATH, ""):
    sys.path.append(os.environ.get(MGEAR_FBX_SDK_PATH, ""))

try:
    import fbx
    import FbxCommon
except ImportError:
    pm.displayWarning(
        "FBX SDK not available. Some mGear's "
        "FBX functionality will be limited. "
        "Please set the env var MGEAR_FBX_SDK_PATH "
        "to your FBX SDK installation"
    )
else:
    pm.displayInfo("mGear has found the FBX SDK.")
    FBX_SDK = True


"""
Thanks to Randall Hess https://gist.github.com/Meatplowz for the FBX_class
and Thanks to Rigging dojo for hosting the fantastic article about FBX SDK
https://www.riggingdojo.com/2017/04/04/guest-post-fbx-file-solutions-python-fbx-sdk/

This is a helper FBX class useful in accessing and modifying the FBX Scene
Documentation for the FBX SDK
http://help.autodesk.com/view/FBX/2015/ENU/?guid=__cpp_ref_index_html
Examples:
# instantiate the class, as seen below with a path to an FBX file
fbx_file = FBX_Class(r'c:/my_path/character.fbx')
#get all of the scene nodes
all_fbx_nodes = fbx_file.file.scene_nodes()
# remove namespaces from all of the nodes
fbx_file.remove_namespace()
# get the display layer objects
display_layer_nodes = fbx_file.get_type_nodes( u'DisplayLayer' )
geometry_nodes = fbx_file.get_class_nodes( fbx_file.FbxGeometry.ClassId )
# save the file that was given
fbx_file.save_scene()
# cleanly close the fbx scene.
# YOU SHOULD ALWAYS CLOSE WHEN FINISHED WITH THE FILE
fbx_file.close()


fbx_file = FBX_Class(r'd:/my_path/test.fbx')
fbx_file.remove_namespace()
node = fbx_file.get_node_by_name('head')
node_property = fbx_file.get_property(node, 'no_export')
node_property_value = fbx_file.get_property_value( node, 'no_export')
remove_property = fbx_file.remove_node_property(node, 'no_anim_export')
remove_property = fbx_file.remove_node_property(node, 'no_export')
remove_node = fbx_file.remove_nodes_by_names('hair_a_01')
save_file = fbx_file.save(filename=r'd:/temp.fbx')
fbx_file.close()

"""


class FBX_Class(object):
    def __init__(self, filename):
        """
        FBX Scene Object
        """
        self.filename = filename
        self.scene = None
        self.sdk_manager = None
        self.sdk_manager, self.scene = FbxCommon.InitializeSdkObjects()
        FbxCommon.LoadScene(self.sdk_manager, self.scene, filename)

        self.root_node = self.scene.GetRootNode()
        self.scene_nodes = self.get_scene_nodes()

    def close(self):
        """
        You need to run this to close the FBX scene safely
        """
        # destroy objects created by the sdk
        self.sdk_manager.Destroy()

    def __get_scene_nodes_recursive(self, node):
        """
        Rescursive method to get all scene nodes
        this should be private, called by get_scene_nodes()
        """
        self.scene_nodes.append(node)
        for i in range(node.GetChildCount()):
            self.__get_scene_nodes_recursive(node.GetChild(i))

    def __cast_property_type(self, fbx_property):
        """
        Cast a property to type to properly get the value
        """
        casted_property = None

        unsupported_types = [
            fbx.eFbxUndefined,
            fbx.eFbxChar,
            fbx.eFbxUChar,
            fbx.eFbxShort,
            fbx.eFbxUShort,
            fbx.eFbxUInt,
            fbx.eFbxLongLong,
            fbx.eFbxHalfFloat,
            fbx.eFbxDouble4x4,
            fbx.eFbxEnum,
            fbx.eFbxTime,
            fbx.eFbxReference,
            fbx.eFbxBlob,
            fbx.eFbxDistance,
            fbx.eFbxDateTime,
            fbx.eFbxTypeCount,
        ]

        # property is not supported or mapped yet
        property_type = fbx_property.GetPropertyDataType().GetType()
        if property_type in unsupported_types:
            return None

        if property_type == fbx.eFbxBool:
            casted_property = fbx.FbxPropertyBool1(fbx_property)
        elif property_type == fbx.eFbxDouble:
            casted_property = fbx.FbxPropertyDouble1(fbx_property)
        elif property_type == fbx.eFbxDouble2:
            casted_property = fbx.FbxPropertyDouble2(fbx_property)
        elif property_type == fbx.eFbxDouble3:
            casted_property = fbx.FbxPropertyDouble3(fbx_property)
        elif property_type == fbx.eFbxDouble4:
            casted_property = fbx.FbxPropertyDouble4(fbx_property)
        elif property_type == fbx.eFbxInt:
            casted_property = fbx.FbxPropertyInteger1(fbx_property)
        elif property_type == fbx.eFbxFloat:
            casted_property = fbx.FbxPropertyFloat1(fbx_property)
        elif property_type == fbx.eFbxString:
            casted_property = fbx.FbxPropertyString(fbx_property)
        else:
            raise ValueError(
                "Unknown property type: {0} {1}".format(
                    property.GetPropertyDataType().GetName(), property_type
                )
            )

        return casted_property

    def get_scene_nodes(self):
        """
        Get all nodes in the fbx scene
        """
        self.scene_nodes = []
        for i in range(self.root_node.GetChildCount()):
            self.__get_scene_nodes_recursive(self.root_node.GetChild(i))
        return self.scene_nodes

    def get_type_nodes(self, type):
        """
        Get nodes from the scene with the given type

        display_layer_nodes = fbx_file.get_type_nodes( u'DisplayLayer' )
        """
        nodes = []
        num_objects = self.scene.RootProperty.GetSrcObjectCount()
        for i in range(0, num_objects):
            node = self.scene.RootProperty.GetSrcObject(i)
            if node:
                if node.GetTypeName() == type:
                    nodes.append(node)
        return nodes

    def get_class_nodes(self, class_id):
        """
        Get nodes in the scene with the given classid

        geometry_nodes = fbx_file.get_class_nodes( fbx.FbxGeometry.ClassId )
        """
        nodes = []
        num_objects = self.scene.RootProperty.GetSrcObjectCount(
            fbx.FbxCriteria.ObjectType(class_id)
        )
        for index in range(0, num_objects):
            node = self.scene.RootProperty.GetSrcObject(
                fbx.FbxCriteria.ObjectType(class_id), index
            )
            if node:
                nodes.append(node)
        return nodes

    def get_property(self, node, property_string):
        """
        Gets a property from an Fbx node

        export_property = fbx_file.get_property(node, 'no_export')
        """
        fbx_property = node.FindProperty(property_string)
        return fbx_property

    def get_property_value(self, node, property_string):
        """
        Gets the property value from an Fbx node

        property_value = fbx_file.get_property_value(node, 'no_export')
        """
        fbx_property = node.FindProperty(property_string)
        if fbx_property.IsValid():
            # cast to correct property type so you can get
            casted_property = self.__cast_property_type(fbx_property)
            if casted_property:
                return casted_property.Get()
        return None

    def get_node_by_name(self, name):
        """
        Get the fbx node by name
        """
        self.get_scene_nodes()
        # right now this is only getting the first one found
        node = [node for node in self.scene_nodes if node.GetName() == name]
        if node:
            return node[0]
        return None

    def remove_namespace(self):
        """
        Remove all namespaces from all nodes

        This is not an ideal method but
        """
        self.get_scene_nodes()
        for node in self.scene_nodes:
            orig_name = node.GetName()
            split_by_colon = orig_name.split(":")
            if len(split_by_colon) > 1:
                new_name = split_by_colon[-1:][0]
                node.SetName(new_name)
        return True

    def remove_node_property(self, node, property_string):
        """
        Remove a property from an Fbx node

        remove_property = fbx_file.remove_property(node, 'UDP3DSMAX')
        """
        node_property = self.get_property(node, property_string)
        if node_property.IsValid():
            node_property.DestroyRecursively()
            return True
        return False

    def remove_nodes_by_names(self, names):
        """
        Remove nodes from the fbx file from a list of names

        names = ['object1','shape2','joint3']
        remove_nodes = fbx_file.remove_nodes_by_names(names)
        """

        if names is None or len(names) == 0:
            return True

        self.get_scene_nodes()
        remove_nodes = [
            node for node in self.scene_nodes if node.GetName() in names
        ]
        for node in remove_nodes:
            disconnect_node = self.scene.DisconnectSrcObject(node)
            remove_node = self.scene.RemoveNode(node)
        self.get_scene_nodes()
        return True

    def save(self, filename=None):
        """
        Save the current fbx scene as the incoming filename .fbx
        """
        # save as a different filename
        if filename:
            FbxCommon.SaveScene(self.sdk_manager, self.scene, filename)
        else:
            FbxCommon.SaveScene(self.sdk_manager, self.scene, self.filename)
        self.close()


# FBX wrapper section

# NOTE: pymel can use MEL commands directly
# for example:
#     pm.mel.FBXExport(f=path, s=True)
#
# But we will use this wrapper to ensure it will work if we remove pymel
# from mGear


# check if we have loaded the necessary plugins
if not pm.pluginInfo("fbxmaya", q=True, loaded=True):
    try:
        pm.loadPlugin("fbxmaya")
    except RuntimeError:
        pm.displayError("You need the fbxmaya.mll plugin!")


def _py_fbx(mel_cmd, *args, **kwargs):

    arg_string = ""
    kwargs_string = ""
    for a in args:
        if not isinstance(a, str):
            a = str(a)
        arg_string += " {}".format(a)

    for ka in kwargs.items():
        if ka[0] != "q":
            if isinstance(ka[1], str):
                argu = string.normalize_path('"{}"'.format(ka[1]))
            else:
                argu = ka[1]
            kwargs_string += " -{} {}".format(ka[0], argu)
        else:
            kwargs_string += " -q"

    mel_format_cmd = "{}{}{};".format(mel_cmd, kwargs_string, arg_string)

    return maya.mel.eval(mel_format_cmd)


def FBXImport(*args, **kwargs):
    return _py_fbx("FBXImport", *args, **kwargs)


def FBXExport(*args, **kwargs):
    return _py_fbx("FBXExport", *args, **kwargs)


def FBXResetImport(*args, **kwargs):
    return _py_fbx("FBXResetImport", *args, **kwargs)


def FBXResetExport(*args, **kwargs):
    return _py_fbx("FBXResetExport", *args, **kwargs)


def FBXImportOCMerge(*args, **kwargs):
    return _py_fbx("FBXImportOCMerge", *args, **kwargs)


def FBXPushSettings(*args, **kwargs):
    return _py_fbx("FBXPushSettings", *args, **kwargs)


def FBXPopSettings(*args, **kwargs):
    return _py_fbx("FBXPopSettings", *args, **kwargs)


def FBXLoadImportPresetFile(*args, **kwargs):
    return _py_fbx("FBXLoadImportPresetFile", *args, **kwargs)


def FBXLoadExportPresetFile(*args, **kwargs):
    return _py_fbx("FBXLoadExportPresetFile", *args, **kwargs)


def FBXLoadMBImportPresetFile(*args, **kwargs):
    return _py_fbx("FBXLoadMBImportPresetFile", *args, **kwargs)


def FBXLoadMBExportPresetFile(*args, **kwargs):
    return _py_fbx("FBXLoadMBExportPresetFile", *args, **kwargs)


def FBXImportShowUI(*args, **kwargs):
    return _py_fbx("FBXImportShowUI", *args, **kwargs)


def FBXImportGenerateLog(*args, **kwargs):
    return _py_fbx("FBXImportGenerateLog", *args, **kwargs)


def FBXImportMode(*args, **kwargs):
    return _py_fbx("FBXImportMode", *args, **kwargs)


def FBXImportMergeBackNullPivots(*args, **kwargs):
    return _py_fbx("FBXImportMergeBackNullPivots", *args, **kwargs)


def FBXImportConvertDeformingNullsToJoint(*args, **kwargs):
    return _py_fbx("FBXImportConvertDeformingNullsToJoint", *args, **kwargs)


def FBXImportHardEdges(*args, **kwargs):
    return _py_fbx("FBXImportHardEdges", *args, **kwargs)


def FBXImportUnlockNormals(*args, **kwargs):
    return _py_fbx("FBXImportUnlockNormals", *args, **kwargs)


def FBXImportProtectDrivenKeys(*args, **kwargs):
    return _py_fbx("FBXImportProtectDrivenKeys", *args, **kwargs)


def FBXImportMergeAnimationLayers(*args, **kwargs):
    return _py_fbx("FBXImportMergeAnimationLayers", *args, **kwargs)


def FBXImportResamplingRateSource(*args, **kwargs):
    return _py_fbx("FBXImportResamplingRateSource", *args, **kwargs)


def FBXImportSetMayaFrameRate(*args, **kwargs):
    return _py_fbx("FBXImportSetMayaFrameRate", *args, **kwargs)


def FBXImportQuaternion(*args, **kwargs):
    return _py_fbx("FBXImportQuaternion", *args, **kwargs)


def FBXImportSetLockedAttribute(*args, **kwargs):
    return _py_fbx("FBXImportSetLockedAttribute", *args, **kwargs)


def FBXImportSetTake(*args, **kwargs):
    return _py_fbx("FBXImportSetTake", *args, **kwargs)


def FBXImportAxisConversionEnable(*args, **kwargs):
    return _py_fbx("FBXImportAxisConversionEnable", *args, **kwargs)


def FBXImportScaleFactor(*args, **kwargs):
    return _py_fbx("FBXImportScaleFactor", *args, **kwargs)


def FBXImportUpAxis(*args, **kwargs):
    return _py_fbx("FBXImportUpAxis", *args, **kwargs)


def FBXImportAutoAxisEnable(*args, **kwargs):
    return _py_fbx("FBXImportAutoAxisEnable", *args, **kwargs)


def FBXImportForcedFileAxis(*args, **kwargs):
    return _py_fbx("FBXImportForcedFileAxis", *args, **kwargs)


def FBXImportCacheFile(*args, **kwargs):
    return _py_fbx("FBXImportCacheFile", *args, **kwargs)


def FBXImportSkins(*args, **kwargs):
    return _py_fbx("FBXImportSkins", *args, **kwargs)


def FBXImportShapes(*args, **kwargs):
    return _py_fbx("FBXImportShapes", *args, **kwargs)


def FBXImportCameras(*args, **kwargs):
    return _py_fbx("FBXImportCameras", *args, **kwargs)


def FBXImportLights(*args, **kwargs):
    return _py_fbx("FBXImportLights", *args, **kwargs)


def FBXImportAudio(*args, **kwargs):
    return _py_fbx("FBXImportAudio", *args, **kwargs)


def FBXImportFillTimeline(*args, **kwargs):
    return _py_fbx("FBXImportFillTimeline", *args, **kwargs)


def FBXImportConstraints(*args, **kwargs):
    return _py_fbx("FBXImportConstraints", *args, **kwargs)


def FBXImportSkeletonDefinitionsAs(*args, **kwargs):
    return _py_fbx("FBXImportSkeletonDefinitionsAs", *args, **kwargs)


def FBXExportShowUI(*args, **kwargs):
    return _py_fbx("FBXExportShowUI", *args, **kwargs)


def FBXExportGenerateLog(*args, **kwargs):
    return _py_fbx("FBXExportGenerateLog", *args, **kwargs)


def FBXExportFileVersion(*args, **kwargs):
    return _py_fbx("FBXExportFileVersion", *args, **kwargs)


def FBXExportApplyConstantKeyReducer(*args, **kwargs):
    return _py_fbx("FBXExportApplyConstantKeyReducer", *args, **kwargs)


def FBXExportQuaternion(*args, **kwargs):
    return _py_fbx("FBXExportQuaternion", *args, **kwargs)


def FBXExportSkins(*args, **kwargs):
    return _py_fbx("FBXExportSkins", *args, **kwargs)


def FBXExportShapes(*args, **kwargs):
    return _py_fbx("FBXExportShapes", *args, **kwargs)


def FBXExportShapeAttributes(*args, **kwargs):
    return _py_fbx("FBXExportShapeAttributes", *args, **kwargs)


def FBXExportShapeAttributeValues(*args, **kwargs):
    return _py_fbx("FBXExportShapeAttributeValues", *args, **kwargs)


def FBXExportCameras(*args, **kwargs):
    return _py_fbx("FBXExportCameras", *args, **kwargs)


def FBXExportLights(*args, **kwargs):
    return _py_fbx("FBXExportLights", *args, **kwargs)


def FBXExportAudio(*args, **kwargs):
    return _py_fbx("FBXExportAudio", *args, **kwargs)


def FBXExportInstances(*args, **kwargs):
    return _py_fbx("FBXExportInstances", *args, **kwargs)


def FBXExportReferencedContainersContent(*args, **kwargs):
    return _py_fbx("FBXExportReferencedContainersContent", *args, **kwargs)


def FBXExportReferencedAssetsContent(*args, **kwargs):
    return _py_fbx("FBXExportReferencedAssetsContent", *args, **kwargs)


def FBXExportBakeComplexStart(*args, **kwargs):
    return _py_fbx("FBXExportBakeComplexStart", *args, **kwargs)


def FBXExportBakeComplexEnd(*args, **kwargs):
    return _py_fbx("FBXExportBakeComplexEnd", *args, **kwargs)


def FBXExportBakeComplexStep(*args, **kwargs):
    return _py_fbx("FBXExportBakeComplexStep", *args, **kwargs)


def FBXExportEmbeddedTextures(*args, **kwargs):
    return _py_fbx("FBXExportEmbeddedTextures", *args, **kwargs)


def FBXExportConvert2Tif(*args, **kwargs):
    return _py_fbx("FBXExportConvert2Tif", *args, **kwargs)


def FBXExportInAscii(*args, **kwargs):
    return _py_fbx("FBXExportInAscii", *args, **kwargs)


def FBXExportBakeComplexAnimation(*args, **kwargs):
    return _py_fbx("FBXExportBakeComplexAnimation", *args, **kwargs)


def FBXExportBakeResampleAnimation(*args, **kwargs):
    return _py_fbx("FBXExportBakeResampleAnimation", *args, **kwargs)


def FBXExportUseSceneName(*args, **kwargs):
    return _py_fbx("FBXExportUseSceneName", *args, **kwargs)


def FBXExportAnimationOnly(*args, **kwargs):
    return _py_fbx("FBXExportAnimationOnly", *args, **kwargs)


def FBXExportSplitAnimationIntoTakes(*args, **kwargs):
    return _py_fbx("FBXExportSplitAnimationIntoTakes", *args, **kwargs)


def FBXExportDeleteOriginalTakeOnSplitAnimation(*args, **kwargs):
    return _py_fbx(
        "FBXExportDeleteOriginalTakeOnSplitAnimation", *args, **kwargs
    )


def FBXExportHardEdges(*args, **kwargs):
    return _py_fbx("FBXExportHardEdges", *args, **kwargs)


def FBXExportTangents(*args, **kwargs):
    return _py_fbx("FBXExportTangents", *args, **kwargs)


def FBXExportSmoothMesh(*args, **kwargs):
    return _py_fbx("FBXExportSmoothMesh", *args, **kwargs)


def FBXExportSmoothingGroups(*args, **kwargs):
    return _py_fbx("FBXExportSmoothingGroups", *args, **kwargs)


def FBXExportFinestSubdivLevel(*args, **kwargs):
    return _py_fbx("FBXExportFinestSubdivLevel", *args, **kwargs)


def FBXExportInputConnections(*args, **kwargs):
    return _py_fbx("FBXExportInputConnections", *args, **kwargs)


def FBXExportIncludeChildren(*args, **kwargs):
    return _py_fbx("FBXExportIncludeChildren", *args, **kwargs)


def FBXExportConstraints(*args, **kwargs):
    return _py_fbx("FBXExportConstraints", *args, **kwargs)


def FBXExportSkeletonDefinitions(*args, **kwargs):
    return _py_fbx("FBXExportSkeletonDefinitions", *args, **kwargs)


def FBXExportCacheFile(*args, **kwargs):
    return _py_fbx("FBXExportCacheFile", *args, **kwargs)


def FBXExportQuickSelectSetAsCache(*args, **kwargs):
    return _py_fbx("FBXExportQuickSelectSetAsCache", *args, **kwargs)


def FBXExportTriangulate(*args, **kwargs):
    return _py_fbx("FBXExportTriangulate", *args, **kwargs)


def FBXExportColladaTriangulate(*args, **kwargs):
    return _py_fbx("FBXExportColladaTriangulate", *args, **kwargs)


def FBXExportColladaSingleMatrix(*args, **kwargs):
    return _py_fbx("FBXExportColladaSingleMatrix", *args, **kwargs)


def FBXExportColladaFrameRate(*args, **kwargs):
    return _py_fbx("FBXExportColladaFrameRate", *args, **kwargs)


def FBXResamplingRate(*args, **kwargs):
    return _py_fbx("FBXResamplingRate", *args, **kwargs)


def FBXRead(*args, **kwargs):
    return _py_fbx("FBXRead", *args, **kwargs)


def FBXClose(*args, **kwargs):
    return _py_fbx("FBXClose", *args, **kwargs)


def FBXGetTakeCount(*args, **kwargs):
    return _py_fbx("FBXGetTakeCount", *args, **kwargs)


def FBXGetTakeIndex(*args, **kwargs):
    return _py_fbx("FBXGetTakeIndex", *args, **kwargs)


def FBXGetTakeName(*args, **kwargs):
    return _py_fbx("FBXGetTakeName", *args, **kwargs)


def FBXGetTakeComment(*args, **kwargs):
    return _py_fbx("FBXGetTakeComment", *args, **kwargs)


def FBXGetTakeLocalTimeSpan(*args, **kwargs):
    return _py_fbx("FBXGetTakeLocalTimeSpan", *args, **kwargs)


def FBXGetTakeReferenceTimeSpan(*args, **kwargs):
    return _py_fbx("FBXGetTakeReferenceTimeSpan", *args, **kwargs)


def FBXImportConvertUnitString(*args, **kwargs):
    return _py_fbx("FBXImportConvertUnitString", *args, **kwargs)


def FBXExportConvertUnitString(*args, **kwargs):
    return _py_fbx("FBXExportConvertUnitString", *args, **kwargs)


def FBXExportAxisConversionMethod(*args, **kwargs):
    return _py_fbx("FBXExportAxisConversionMethod", *args, **kwargs)


def FBXExportUpAxis(*args, **kwargs):
    return _py_fbx("FBXExportUpAxis", *args, **kwargs)


def FBXExportScaleFactor(*args, **kwargs):
    return _py_fbx("FBXExportScaleFactor", *args, **kwargs)


def FBXProperties(*args, **kwargs):
    return _py_fbx("FBXProperties", *args, **kwargs)


def FBXProperty(*args, **kwargs):
    pm.displayWarning("This command is not yet supported in the wrapper")
    return


def FBXExportUseTmpFilePeripheral(*args, **kwargs):
    return _py_fbx("FBXExportUseTmpFilePeripheral", *args, **kwargs)


def FBXUICallBack(*args, **kwargs):
    return _py_fbx("FBXUICallBack", *args, **kwargs)


def FBXUIShowOptions(*args, **kwargs):
    return _py_fbx("FBXUIShowOptions", *args, **kwargs)


# SNIPPETS
# docs https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2023/ENU/Maya-DataExchange/files/GUID-F48E3B78-3E56-4869-9914-CE0FAB6E3116-htm.html

# query and format all fbxmaya commands

"""
import pymel.core as pm
cds = pm.pluginInfo( 'fbxmaya.mll', query=True, command=True )


final_str = ""
for c in cds:
    fun = r'''

def {0}(*args, **kwargs):
    return _py_fbx("{0}", *args, **kwargs)
'''.format(c)
    final_str += fun
print(final_str)
"""
