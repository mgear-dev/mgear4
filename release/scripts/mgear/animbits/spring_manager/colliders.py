"""Bone Dynamics colliders: shared collision objects assigned to springs.

A collider is a ``mgearSpring`` network of kind ``collider`` owning:

- ``<name>_drv``: a group under :data:`GROUP`, constrained to the driver
  (a joint or control) so the rig hierarchy is never changed;
- ``<name>``: the collider transform under it, holding the plug-in shape
  (``sphereColliderNode``, ``capsuleColliderNode`` or
  ``infinitePlaneColliderNode``). Its local matrix is the offset from the
  driver, free to edit.

Mesh colliders use a mesh instead: a reduced proxy following the source
mesh (owned by the collider), or the source mesh itself.

Colliders are assigned to springs with :func:`registry.assign`; the Bone
Dynamics backend wires them into its nodes.
"""

import json

import maya.api.OpenMaya as om2
from maya import cmds

import mgear
from mgear.core import attribute
from mgear.core import mesh as mesh_utils
from mgear.core import node_remap
from mgear.core import string
from mgear.core import utils

from . import constants
from . import registry

BACKEND = constants.BONE_DYNAMICS_BACKEND
GROUP = "spring_colliders_grp"

SPHERE = "sphere"
CAPSULE = "capsule"
PLANE = "plane"
MESH = "mesh"
TYPES = (SPHERE, CAPSULE, PLANE, MESH)
SHAPE_TYPES = {
    SPHERE: "sphereColliderNode",
    CAPSULE: "capsuleColliderNode",
    PLANE: "infinitePlaneColliderNode",
}
# collider type: shape dimension attributes
DIMENSIONS = {
    SPHERE: ("radius",),
    CAPSULE: ("height", "radiusA", "radiusB"),
    PLANE: (),
    MESH: (),
}

TYPE_ATTR = "colliderType"
DRIVER_ATTR = "driver"
TRANSFORM_ATTR = "collider"
SOURCE_ATTR = "sourceMesh"
PROXY_ATTR = "proxySettings"

# default percentage of faces removed from mesh collider proxies
PROXY_REDUCE = 50.0
# faces above which mesh collision gets slow
FACE_WARNING = 2000
DISPLAY_COLOR = 17  # yellow, as the plug-in collider tools


def _plug(node, attr):
    return "{}.{}".format(node, attr)


def _unique(name):
    if not cmds.objExists(name):
        return name
    index = 1
    while cmds.objExists("{}{}".format(name, index)):
        index += 1
    return "{}{}".format(name, index)


def _group():
    """Return the colliders group, created when missing."""
    if cmds.objExists(GROUP):
        return GROUP
    return cmds.createNode("transform", name=GROUP)


def _ensure_plugin():
    from .backends import get_backend

    if not get_backend(BACKEND).is_available():
        raise RuntimeError("boneDynamicsNode plug-in is not available")


# -----------------------------------------------------------------------------
# Queries
# -----------------------------------------------------------------------------


def list_colliders():
    """Return the collider networks of the scene.

    Returns:
        list: Network node names, sorted.
    """
    return sorted(registry.list_shared(constants.KIND_COLLIDER, BACKEND))


def collider_type(network):
    """Return the type of a collider: sphere, capsule, plane or mesh."""
    return attribute.get_string_attr(network, TYPE_ATTR)


def collider_transform(network):
    """Return the collider transform (the mesh for mesh colliders)."""
    nodes = attribute.get_message_inputs(network, TRANSFORM_ATTR)
    return nodes[0] if nodes else None


def collider_shape(network):
    """Return the collider shape: plug-in shape or mesh shape."""
    transform = collider_transform(network)
    if not transform:
        return None
    shapes = cmds.listRelatives(
        transform, shapes=True, noIntermediate=True, fullPath=True
    )
    return shapes[0] if shapes else None


def driver(network):
    """Return the driver of a collider, or None."""
    nodes = attribute.get_message_inputs(network, DRIVER_ATTR)
    return nodes[0] if nodes else None


def source_mesh(network):
    """Return the source mesh of a mesh collider, or None."""
    nodes = attribute.get_message_inputs(network, SOURCE_ATTR)
    return nodes[0] if nodes else None


def label(network):
    """Return the display name of a collider: its transform short name."""
    transform = collider_transform(network)
    return node_remap.leaf_name(transform) if transform else network


def collider_from_node(node):
    """Return the collider network owning a node, or None.

    Args:
        node (str): The network, the collider transform, its shape or its
            driver group.

    Returns:
        str: The collider network, or None.
    """
    if not node or not cmds.objExists(node):
        return None
    # the shape of a mesh used as is is not connected: try its transform
    for candidate in [node] + (cmds.listRelatives(node, parent=True) or []):
        networks = (
            [candidate]
            if cmds.nodeType(candidate) == "network"
            else cmds.listConnections(
                candidate + ".message",
                source=False,
                destination=True,
                type="network",
            )
            or []
        )
        for network in networks:
            if registry.node_kind(network) == constants.KIND_COLLIDER:
                return network
    return None


def get_dimensions(network):
    """Return the dimensions of a collider.

    Returns:
        dict: ``{attr: value}``, empty for planes and meshes.
    """
    shape = collider_shape(network)
    return {
        attr: cmds.getAttr(_plug(shape, attr))
        for attr in DIMENSIONS.get(collider_type(network), ())
    }


def set_dimensions(network, dimensions):
    """Set the dimensions of a collider. Unknown keys are ignored.

    Args:
        network (str): Collider network.
        dimensions (dict): ``{attr: value}``.
    """
    shape = collider_shape(network)
    for attr in DIMENSIONS.get(collider_type(network), ()):
        if attr in dimensions:
            cmds.setAttr(_plug(shape, attr), dimensions[attr])


def get_offset(network):
    """Return the collider matrix relative to its driver group.

    Returns:
        list: 16 floats.
    """
    return cmds.xform(
        collider_transform(network), query=True, objectSpace=True, matrix=True
    )


def set_offset(network, matrix):
    """Set the collider matrix relative to its driver group.

    Args:
        network (str): Collider network.
        matrix (list): 16 floats.
    """
    cmds.xform(collider_transform(network), objectSpace=True, matrix=list(matrix))


def get_world_matrix(network):
    """Return the collider world matrix (16 floats)."""
    return cmds.xform(
        collider_transform(network), query=True, worldSpace=True, matrix=True
    )


def set_world_matrix(network, matrix):
    """Place a collider in world space, keeping its driver.

    Args:
        network (str): Collider network.
        matrix (list): 16 floats.
    """
    cmds.xform(collider_transform(network), worldSpace=True, matrix=list(matrix))


# -----------------------------------------------------------------------------
# Creation
# -----------------------------------------------------------------------------


def _create_network(name, kind_type, transform, driver_node=None, extra=None):
    values = {TYPE_ATTR: kind_type}
    values.update(extra or {})
    network = registry.create_network(
        name + "_net", BACKEND, [], None, values, kind=constants.KIND_COLLIDER
    )
    for attr, source in (
        (TRANSFORM_ATTR, transform),
        (DRIVER_ATTR, driver_node),
    ):
        cmds.addAttr(network, longName=attr, attributeType="message")
        if source:
            cmds.connectAttr(source + ".message", _plug(network, attr))
    return network


def create(kind_type, driver_node=None, name=None, dimensions=None, matrix=None):
    """Create a sphere, capsule or plane collider.

    A sphere or capsule driven by the sim joint of a Bone Dynamics spring
    also sets the volume of that bone, see
    :meth:`BoneDynamicsBackend.link_collider`.

    Args:
        kind_type (str): :data:`SPHERE`, :data:`CAPSULE` or :data:`PLANE`.
        driver_node (str, optional): Joint or control the collider follows,
            and is placed at. World space when None.
        name (str, optional): Collider name, ``<driver>_<type>Col`` by
            default. Made unique.
        dimensions (dict, optional): Shape dimensions, see
            :data:`DIMENSIONS`.
        matrix (list, optional): World matrix, the driver's when None.

    Returns:
        str: The collider network.
    """
    if kind_type not in SHAPE_TYPES:
        raise ValueError("Unknown collider type: {}".format(kind_type))
    _ensure_plugin()
    base = name or "{}_{}Col".format(
        node_remap.flat_name(driver_node) if driver_node else "world", kind_type
    )
    base = _unique(base)
    with utils.undo_chunk("springManagerCreateCollider"):
        # created first: shared by every collider, never one's member
        parent = _group()
        with utils.capture_created_nodes() as created:
            group = cmds.createNode("transform", name=base + "_drv", parent=parent)
            if driver_node:
                cmds.xform(
                    group,
                    worldSpace=True,
                    matrix=cmds.xform(
                        driver_node, query=True, worldSpace=True, matrix=True
                    ),
                )
                cmds.parentConstraint(driver_node, group, maintainOffset=True)
            transform = cmds.createNode("transform", name=base, parent=group)
            shape = cmds.createNode(
                SHAPE_TYPES[kind_type], name=base + "Shape", parent=transform
            )
            cmds.setAttr(shape + ".overrideEnabled", True)
            cmds.setAttr(shape + ".overrideColor", DISPLAY_COLOR)
        transform = cmds.ls(transform, long=True)[0]
        network = _create_network(base, kind_type, transform, driver_node)
        registry.add_members(network, created)
        if dimensions:
            set_dimensions(network, dimensions)
        if matrix:
            set_world_matrix(network, matrix)
        # on a spring's own joint: the bone collides with the same volume
        from .backends import get_backend

        get_backend(BACKEND).link_collider(network)
    return network


def create_mesh(mesh, proxy=True, reduce_percent=None, name=None):
    """Create a mesh collider (experimental).

    Args:
        mesh (str): Source mesh transform.
        proxy (bool, optional): Collide with a reduced, soft-edged copy
            following the mesh, instead of the mesh itself.
        reduce_percent (float, optional): Proxy faces removed, percent,
            :data:`PROXY_REDUCE` when None.
        name (str, optional): Collider name, ``<mesh>_meshCol`` by default.

    Returns:
        str: The collider network.
    """
    _ensure_plugin()
    base = _unique(name or "{}_meshCol".format(node_remap.flat_name(mesh)))
    if reduce_percent is None:
        reduce_percent = PROXY_REDUCE
    settings = {"proxy": proxy, "reduce_percent": reduce_percent}
    with utils.undo_chunk("springManagerCreateMeshCollider"):
        created = []
        transform = mesh
        if proxy:
            transform = mesh_utils.create_collision_proxy(
                mesh, reduce_percent=reduce_percent, name=base
            )
            transform = cmds.parent(transform, _group())[0]
            cmds.setAttr(transform + ".visibility", False)
            created = [transform] + (cmds.listRelatives(transform, shapes=True) or [])
        transform = cmds.ls(transform, long=True)[0]
        network = _create_network(
            base,
            MESH,
            transform,
            extra={PROXY_ATTR: json.dumps(settings)},
        )
        cmds.addAttr(network, longName=SOURCE_ATTR, attributeType="message")
        cmds.connectAttr(mesh + ".message", _plug(network, SOURCE_ATTR))
        registry.add_members(network, created)
    faces = cmds.polyEvaluate(transform, face=True)
    if faces > FACE_WARNING:
        mgear.log(
            "{}: {} faces, mesh collision gets slow above {}. Use a proxy "
            "or reduce it more.".format(
                node_remap.leaf_name(transform), faces, FACE_WARNING
            ),
            mgear.sev_warning,
        )
    return network


def proxy_settings(network):
    """Return the mesh proxy settings of a mesh collider.

    Returns:
        dict: ``proxy`` (bool) and ``reduce_percent``, empty for other types.
    """
    value = attribute.get_string_attr(network, PROXY_ATTR)
    return json.loads(value) if value else {}


def delete(networks):
    """Delete colliders, unassigning them from every spring first.

    Bones whose volume a collider set go back to the spring gradient.

    Args:
        networks (list): Collider networks.
    """
    from .backends import get_backend

    backend = get_backend(BACKEND)
    with utils.undo_chunk("springManagerDeleteCollider"):
        for network in networks:
            if cmds.objExists(network):
                backend.unlink_collider(network)
                registry.delete_shared(network)


# -----------------------------------------------------------------------------
# Presets
# -----------------------------------------------------------------------------


def _name_prefix(namespace):
    """Return the collider name prefix of a namespace (``chr:`` > ``chr_``)."""
    namespace = (namespace or "").rstrip(":")
    return namespace.replace(":", "_") + "_" if namespace else ""


def to_preset(network):
    """Return the preset ``colliders`` entry of a collider.

    Names are stored without namespace: the namespace of the driver (or
    source mesh) is stripped from the collider name prefix.

    Args:
        network (str): Collider network.

    Returns:
        dict: ``name``, ``type``, ``driver``, ``offset``, ``dimensions``
        and, for mesh colliders, ``mesh`` (``source``, ``proxy``,
        ``reduce_percent``).
    """
    kind_type = collider_type(network)
    driver_node = driver(network)
    reference = driver_node or source_mesh(network)
    name = label(network)
    prefix = _name_prefix(node_remap.get_namespace(reference)) if reference else ""
    if prefix and name.startswith(prefix):
        name = name[len(prefix) :]
    entry = {
        "name": name,
        "type": kind_type,
        "driver": node_remap.short_name(driver_node) if driver_node else None,
        "offset": get_offset(network) if kind_type != MESH else None,
        "dimensions": get_dimensions(network),
    }
    if kind_type == MESH:
        settings = proxy_settings(network)
        entry["mesh"] = {
            "source": node_remap.short_name(source_mesh(network)),
            "proxy": settings.get("proxy", True),
            "reduce_percent": settings.get("reduce_percent", PROXY_REDUCE),
        }
    return entry


def preset_name(entry, namespace=""):
    """Return the scene name of a preset collider in a namespace.

    Args:
        entry (dict): Preset ``colliders`` entry.
        namespace (str, optional): Target namespace.

    Returns:
        str: The collider name.
    """
    return _name_prefix(namespace) + entry["name"]


def from_preset(entry, namespace="", existing=None):
    """Create or update a collider from a preset entry.

    A collider of the same name is updated (dimensions and offset), not
    duplicated. Entries whose driver or source mesh is missing are skipped
    with a warning.

    Args:
        entry (dict): Preset ``colliders`` entry.
        namespace (str, optional): Namespace of the driver and mesh.
        existing (dict, optional): ``{name: network}`` of the scene
            colliders, read from the scene when None.

    Returns:
        str: The collider network, or None when skipped.
    """
    if existing is None:
        existing = {label(network): network for network in list_colliders()}
    name = preset_name(entry, namespace)
    kind_type = entry.get("type")
    network = existing.get(name)
    if kind_type == MESH:
        if network:
            return network
        mesh_entry = entry.get("mesh") or {}
        source = node_remap.add_namespace(mesh_entry.get("source") or "", namespace)
        if not mesh_entry.get("source") or not cmds.objExists(source):
            mgear.log(
                "Collider {}: mesh {} not found, skipped".format(name, source),
                mgear.sev_warning,
            )
            return None
        return create_mesh(
            source,
            mesh_entry.get("proxy", True),
            mesh_entry.get("reduce_percent", PROXY_REDUCE),
            name,
        )
    if kind_type not in SHAPE_TYPES:
        mgear.log(
            "Collider {}: unknown type {}, skipped".format(name, kind_type),
            mgear.sev_warning,
        )
        return None
    driver_node = None
    if entry.get("driver"):
        driver_node = node_remap.add_namespace(entry["driver"], namespace)
        if not cmds.objExists(driver_node):
            mgear.log(
                "Collider {}: driver {} not found, skipped".format(name, driver_node),
                mgear.sev_warning,
            )
            return None
    if not network:
        network = create(kind_type, driver_node, name)
    set_dimensions(network, entry.get("dimensions") or {})
    if entry.get("offset"):
        set_offset(network, entry["offset"])
    return network


# -----------------------------------------------------------------------------
# Mirror
# -----------------------------------------------------------------------------

# mirror across the world YZ plane, keeping a right-handed matrix
_MIRROR = om2.MMatrix(
    [-1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
)


def _mirror_name(node):
    namespace, _, short = node_remap.leaf_name(node).rpartition(":")
    mirrored = string.convertRLName(short)
    return "{}:{}".format(namespace, mirrored) if namespace else mirrored


def mirror(networks):
    """Mirror colliders to the other side, by name.

    The counterpart is updated when it exists, created otherwise, and
    assigned to the counterparts of the source springs. Mesh colliders and
    colliders without a mirrored name or driver are skipped.

    Args:
        networks (list): Collider networks.

    Returns:
        list: The mirrored collider networks.
    """
    existing = {label(network): network for network in list_colliders()}
    mirrored = []
    with utils.undo_chunk("springManagerMirrorColliders"):
        for network in networks:
            kind_type = collider_type(network)
            name = label(network)
            target_name = _mirror_name(name)
            source_driver = driver(network)
            target_driver = _mirror_name(source_driver) if source_driver else None
            if kind_type == MESH:
                mgear.log("{}: mesh colliders are not mirrored".format(name))
                continue
            if target_name == name or (
                target_driver and not cmds.objExists(target_driver)
            ):
                mgear.log(
                    "{}: no mirrored name or driver, skipped".format(name),
                    mgear.sev_warning,
                )
                continue
            world = om2.MMatrix(get_world_matrix(network))
            matrix = list(_MIRROR * world * _MIRROR)
            target = existing.get(target_name)
            if target:
                set_dimensions(target, get_dimensions(network))
                set_world_matrix(target, matrix)
            else:
                target = create(
                    kind_type,
                    target_driver,
                    target_name,
                    get_dimensions(network),
                    matrix,
                )
            springs = []
            for spring in registry.assigned_springs(network):
                settings = spring.settings_node
                counterpart = (
                    registry.spring_from_node(_mirror_name(settings))
                    if settings
                    else None
                )
                if counterpart and counterpart != spring:
                    springs.append(counterpart)
            registry.assign(target, springs)
            mirrored.append(target)
    return mirrored
