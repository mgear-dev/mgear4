"""
FBX Batch

Is used to handle tasks that used to be performed by the FBX API.
As the FBX API was an extra module that needed to be downloaded and installed,
it was decided that it would be more beneficial to the user to utilise
Maya Batch to perform the same tasks on the exported FBX file.

Process
-------
1. Shift FBX Exporter, exports the "master" fbx. This will be exported directly from
   the active scene, and should not impact the users scene data in any way.
2. Depending on what options/partitions where active, a variaty of batch tasks will be
   initialised, and perform alterations on the master fbx, and then generate a new FBX
   before ending the batch task.

Tasks / Conditions
------------------
- Removing namespaces
- Clean up any lingering DAG nodes that are not needed
- Partition Skeleton + Geometry

"""
import sys, os

import maya.cmds as cmds
import maya.api.OpenMaya as om

from mgear.core import pyFBX as pfbx


def perform_fbx_condition(remove_namespace, scene_clean, master_fbx_path, root_joint, root_geos, skinning=True, blendshapes=True, partitions=True):
    """
     [X] Import FBX Master
     [X] Remove Namespace
     [X] Scene Clean
     [X] Skinning
     [X] Blendshapes
     [ ] Save out master maya scene, to perform Partitions
    """
    print("-----------------------")
    print(" perform fbx condition")
    print(f"  remove namespace:{remove_namespace}")
    print(f"  clean scene:{scene_clean}")
    print(f"  fbx path : {master_fbx_path}")
    print("-----------------------")

    log_file = "logs.txt"

    # Import fbx into scene
    _import_fbx(master_fbx_path)

    # formats the output location from the master fbx path.
    output_dir = os.path.dirname(master_fbx_path)
    fbx_file = os.path.basename(master_fbx_path)
    conditioned_file = fbx_file.split(".")[0] + "_conditioned.ma"
    
    print(f"  Output location: {output_dir}")
    print(f"  FBX file: {fbx_file}")
    print(f"  Conditioned file: {conditioned_file}")

    # Removes all namespaces from any DG or DAG object.
    if remove_namespace:
        print("Removing Namespace..")
        _clean_namespaces()

        # updates root joint name if namespace is found
        root_joint = root_joint.split(":")[-1]
        for i in range(len(root_geos)):
            root_geos[i] = root_geos[i].split(":")[-1]

    if scene_clean:
        print("Clean Scene..")
        # Move the root_joint and root_geos to the scene root
        _parent_to_root(root_joint)
        for r_geo in root_geos:
            _parent_to_root(r_geo)

        # Remove all redundant DAG Nodes.
        _cleanup_stale_dag_hierarchies([root_joint] + root_geos)
    
    if not skinning:
        print("Removing Skinning..")
        # Remove skinning from geometry
        _delete_bind_poses()

    if not blendshapes:
        # Remove blendshapes from geometry
        print("Removing Blendshapes..")
        _delete_blendshapes()

    if partitions:
        print("Getting Scene ready for Partition creation..")
        # Save out conditioned file, as this will be used by other partition processes
        cmds.file( rename=conditioned_file)
        cmds.file( save=True, force=True, type="mayaAscii")

        # Trigger partitions
        # TODO: Check partitions
        #   [ ] If only master partition, perform fbx export
        #   [ ] If Multiple partitions...

        # Delete temporary conditioned .ma file
        cmds.file( new=True, force=True)
        if os.path.exists(conditioned_file):
            os.remove(conditioned_file)
        else:
            print("  Cleaned up conditional file")
    else:
        # Partitions deactivated, updates master fbx file.
        print("Partitions deactivated - Save out master fbx.. ")
        print(  "Path: {}".format(master_fbx_path))
        cmds.select( clear=True )
        cmds.select([root_joint] + root_geos)
        pfbx.FBXExport(f=master_fbx_path, s=True)


def _delete_blendshapes():
    """
    Deletes all blendshape objects in the scene.
    """
    blendshape_mobjs = find_dg_nodes_by_type(om.MFn.kBlendShape)
    
    dg_mod = om.MDGModifier()
    for mobj in blendshape_mobjs:
        print("   - {}".format(om.MFnDependencyNode(mobj).name()))
        dg_mod.deleteNode(mobj)

    dg_mod.doIt()


def find_geometry_dag_objects(parent_object_name):
    selection_list = om.MSelectionList()

    try:
        # Add the parent object to the selection list
        selection_list.add(parent_object_name)

        # Get the MDagPath of the parent object
        parent_dag_path = om.MDagPath()
        parent_dag_path = selection_list.getDagPath(0)

        # Iterate through child objects
        child_count = parent_dag_path.childCount()
        geometry_objects = []

        for i in range(child_count):
            child_obj = parent_dag_path.child(i)
            child_dag_node = om.MFnDagNode(child_obj)
            child_dag_path = child_dag_node.getPath()

            # Check if the child is a geometry node
            if (child_dag_path.hasFn(om.MFn.kMesh) or child_dag_path.hasFn(om.MFn.kNurbsSurface)) and child_dag_path.hasFn(om.MFn.kTransform):
                geometry_objects.append(child_dag_path.fullPathName())

            # Recursive call to find geometry objects under the child
            geometry_objects.extend(find_geometry_dag_objects(child_dag_path.fullPathName()))

        return geometry_objects

    except Exception as e:
        print(f"Error: {e}")
        return []


def _delete_bind_poses():
    """
    Removes all skin clusters and bind poses nodes from the scene.
    """
    bind_poses_mobjs = find_dg_nodes_by_type(om.MFn.kDagPose)
    skin_cluster = find_dg_nodes_by_type(om.MFn.kSkinClusterFilter)

    dg_mod = om.MDGModifier()
    for mobj in bind_poses_mobjs + skin_cluster:
        print("   - {}".format(om.MFnDependencyNode(mobj).name()))
        dg_mod.deleteNode(mobj)

    dg_mod.doIt()


def find_dg_nodes_by_type(node_type):
    """
    returns a list of MObjects, that match the node type
    """
    dagpose_nodes = []

    # Create an iterator to traverse all dependency nodes
    dep_iter = om.MItDependencyNodes()

    while not dep_iter.isDone():
        current_node = dep_iter.thisNode()

        # Check if the node is a DAG Pose node
        if current_node.hasFn(node_type):
            dagpose_nodes.append(current_node)

        dep_iter.next()

    return dagpose_nodes

def _cleanup_stale_dag_hierarchies(ignore_objects):
    """
    Deletes any dag objects that are not geo or skeleton roots, under the scene root.
    """
    IGNORED_OBJECTS = ['|persp', '|top', '|front', '|side']
    obj_names = _get_dag_objects_under_scene_root()
    
    for i_o in IGNORED_OBJECTS:
        obj_names.remove(i_o)
    
    for i_o in ignore_objects:
        pipped_io = "|"+i_o
        try:
            obj_names.remove(pipped_io)
        except:
            print("  skipped {}".format(pipped_io))

    # Delete left over object hierarchies
    dag_mod = om.MDagModifier()

    for name in obj_names:
        temp_sel = om.MSelectionList()
        temp_sel.add(name)

        if temp_sel.length() != 1:
                continue

        dag_path = temp_sel.getDagPath(0)
        dag_node = om.MFnDagNode(dag_path)
        dag_mod.deleteNode(dag_node.object())
        dag_mod.doIt()


def _parent_to_root(name):
    """
    As Maya's parent command can cause failures if you try and parent the object to 
    the same object it is already parented to. We check the parent, and only if it
    it not the world do we reparent the object.
    """
    temp_sel = om.MSelectionList()
    temp_sel.add(name)

    if temp_sel.length() != 1:
            return

    dag_path = temp_sel.getDagPath(0)
    dag_node = om.MFnDagNode(dag_path)
    parent_obj = dag_node.parent(0)
    parent_name = om.MFnDependencyNode(parent_obj).name()

    if parent_name == "world":
        return

    cmds.parent( name, world=True )

    temp_sel.clear()
    print("  Moved {} to scene root.".format(name))


def _get_dag_objects_under_scene_root():
    """
    Gets a list of all dag objects that direct children of the scene root.
    """
    # Create an MItDag iterator starting from the root of the scene
    dag_iter = om.MItDag(om.MItDag.kDepthFirst, om.MFn.kInvalid)

    dag_objects = []

    while not dag_iter.isDone():
        current_dag_path = dag_iter.getPath()

        # Check if the current DAG path is under the scene root
        if current_dag_path.length() == 1:
            dag_objects.append(current_dag_path.fullPathName())

        # Move to the next DAG object
        dag_iter.next()

    return dag_objects


def _clean_namespaces():
    """
    Gets all available namespaces in scene.
    Checks each for objects that have it assigned.
    Removes the namespace from the object.
    """
    namespaces = _get_scene_namespaces()
    for namespace in namespaces:
        print("  - {}".format(namespace))
        child_namespaces = om.MNamespace.getNamespaces(namespace, True)

        for chld_ns in child_namespaces:
            m_objs = om.MNamespace.getNamespaceObjects(chld_ns)
            for m_obj in m_objs:
                _remove_namespace(m_obj)

        m_objs = om.MNamespace.getNamespaceObjects(namespace)
        for m_obj in m_objs:
            _remove_namespace(m_obj)


def _remove_namespace(mobj):
    """
    Removes the namesspace that is currently assigned to the asset
    """
    dg = om.MFnDependencyNode(mobj)
    name = dg.name()
    dg.setName(name[len(dg.namespace):])


def _get_scene_namespaces():
    """
    Gets all namespaces in the scene.
    """
    IGNORED_NAMESPACES = [":UI", ":shared", ":root"]
    spaces = om.MNamespace.getNamespaces()
    for ignored in IGNORED_NAMESPACES:
        if ignored in spaces:
            spaces.remove(ignored)
    return spaces 


def _import_fbx(file_path):
    try:
        # Import FBX file
        name = cmds.file(file_path, i=True, type="FBX", ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, namespace=":")

        print("FBX file imported successfully.")
        return name

    except Exception as e:
        print("Error importing FBX file:", e)
        return
