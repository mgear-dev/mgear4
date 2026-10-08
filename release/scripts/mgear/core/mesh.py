"""Functions to create mesh topology"""

#############################################
# GLOBAL
#############################################

import math

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import mgear.pymaya as pm
from mgear.core import node_remap
from mgear.core import utils


def is_selected_object_mesh(obj=None):
    """
    Check if the currently selected object's transform has a mesh shape.

    Returns:
        bool: True if the transform's shape is a mesh, False otherwise.

    Args:
        obj (str or PyNode, optional): Object to check if is mesh

    """
    if not obj:
        # Get the current selection
        selection = pm.selected()

        if not selection:
            raise ValueError("No object is selected.")

        # Get the first item in the selection
        obj = selection[0]
    else:
        if isinstance(obj, str):
            obj = pm.PyNode(obj)

    # Check if the selected object is a transform and has a shape
    if obj.nodeType() == "transform" and obj.getShape():
        # Check if the shape of the selected object is a mesh
        is_mesh = isinstance(obj.getShape(), pm.nodetypes.Mesh)
        return is_mesh
    else:
        return False


def create_square_polygon(
    side_length=1.0, alignment="Y", name=None, position=(0, 0, 0)
):
    """
    Creates a square polygon face with its normal aligned along a specified
    world axis and positions it at a given 3D location.

    Args:
        side_length (float, optional): The length of each side of the square.
            Defaults to 1.0.
        alignment (str, optional): The world axis ('X', 'Y', 'Z') along which
            the square's normal will be aligned. Defaults to 'Y'.
        name (str, optional): The name of the new polygon object. If None,
            Maya will assign a default name.
        position (tuple, optional): The 3D position (x, y, z) where the square
            will be placed. Defaults to (0, 0, 0).

    Returns:
        str: The full name of the newly created polygon object.
    """
    half_length = side_length * 0.5
    points = om2.MPointArray()

    # Adjust vertex definitions based on alignment to ensure correct normal direction
    if alignment.upper() == "X":
        # Normal along X-axis
        base_points = [
            om2.MPoint(0, half_length, half_length),
            om2.MPoint(0, -half_length, half_length),
            om2.MPoint(0, -half_length, -half_length),
            om2.MPoint(0, half_length, -half_length),
        ]
    elif alignment.upper() == "Y":
        # Normal along Y-axis
        base_points = [
            om2.MPoint(-half_length, 0, half_length),
            om2.MPoint(half_length, 0, half_length),
            om2.MPoint(half_length, 0, -half_length),
            om2.MPoint(-half_length, 0, -half_length),
        ]
    else:  # Z alignment
        # Normal along Z-axis
        base_points = [
            om2.MPoint(-half_length, half_length, 0),
            om2.MPoint(half_length, half_length, 0),
            om2.MPoint(half_length, -half_length, 0),
            om2.MPoint(-half_length, -half_length, 0),
        ]

    # Apply position offset and append to MPointArray
    for pt in base_points:
        pt.x += position[0]
        pt.y += position[1]
        pt.z += position[2]
        points.append(pt)

    # Create mesh
    mesh_fn = om2.MFnMesh()
    mesh_fn.create(points, [4], [0, 1, 2, 3])

    # Get the transform node of the created mesh
    new_mesh_name = mesh_fn.fullPathName()
    transform_node = cmds.listRelatives(new_mesh_name, parent=True)[0]

    # Rename if name is provided
    if name:
        transform_node = cmds.rename(transform_node, name)

    # Apply default shader (lambert1) to the new object
    # Directly use the initialShadingGroup which is the default for lambert1
    shading_group = "initialShadingGroup"
    cmds.sets(transform_node, edit=True, forceElement=shading_group)

    transform_node = pm.PyNode(transform_node)
    return transform_node


def create_square_polygon_with_reference(
    side_length=1.0, alignment="Y", name=None, reference_matrix=None
):
    """
    Creates a square polygon face with its normal aligned and positioned
    according to the transformation matrix of a reference object and applies
    the default shader. The alignment is corrected to ensure the polygon
    aligns with the Y-axis as intended.

    Args:
        side_length (float, optional): The length of each side of the square.
            Defaults to 1.0.
        alignment (str, optional): The axis ('X', 'Y', 'Z') along which the
            square's normal will be aligned based on the reference object.
            Defaults to 'Y'.
        name (str, optional): The name of the new polygon object. If None,
            Maya will assign a default name.
        reference_matrix (matrix, optional): The matrix used for alignment and
            positioning.

    Returns:
        pm.nt.Transform: The PyNode transform of the newly created polygon object.
    """
    if reference_matrix is None:
        pm.displayWarning("Reference matrix is not specified. Aborting.")
        return None

    # # Retrieve the world matrix from the reference object
    # reference_matrix = reference_object.getMatrix(worldSpace=True)
    ref_matrix_mfn = om2.MTransformationMatrix(om2.MMatrix(reference_matrix))

    half_length = side_length / 2.0
    points = om2.MPointArray()

    # Adjust base points for square polygon to ensure proper alignment with the Y-axis
    vectors = [
        (-half_length, 0, half_length),  # Top-Left
        (half_length, 0, half_length),  # Top-Right
        (half_length, 0, -half_length),  # Bottom-Right
        (-half_length, 0, -half_length),  # Bottom-Left
    ]

    for vec in vectors:
        point = om2.MPoint(vec) * ref_matrix_mfn.asMatrix()
        points.append(point)

    # Create mesh
    mesh_fn = om2.MFnMesh()
    mesh_fn.create(points, [4], [0, 1, 2, 3])

    # Get the transform node of the created mesh and apply the default shader
    new_mesh_transform = pm.listRelatives(
        pm.PyNode(mesh_fn.fullPathName()), parent=True
    )[0]
    if name:
        new_mesh_transform = new_mesh_transform.rename(name)

    # Apply default shader (lambert1) to the new object
    pm.sets(
        "initialShadingGroup",
        edit=True,
        forceElement=new_mesh_transform.name(),
    )

    return new_mesh_transform


#############################################
# FITTING
#############################################
# The pure Python helpers work on sequences of (x, y, z) tuples, so they run
# without a scene and can move to C++ later. The ray-cast helpers use OM2.


def percentile(values, q):
    """Return a percentile of values, linearly interpolated.

    Args:
        values (list): Numbers.
        q (float): Percentile, 0 to 100.

    Returns:
        float: The percentile, or None for no values.
    """
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * max(0.0, min(100.0, q)) / 100.0
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length(a):
    return math.sqrt(_dot(a, a))


def fit_sphere_to_points(points, q=75.0):
    """Fit a sphere to points, ignoring outliers.

    The centre is the per-axis median, the radius the ``q`` percentile of
    the distances to it.

    Args:
        points (list): (x, y, z) points.
        q (float, optional): Radius percentile, 0 to 100.

    Returns:
        tuple: ``((x, y, z) centre, radius)``, or ``(None, None)`` without
        points.
    """
    if not points:
        return None, None
    center = tuple(
        percentile([point[axis] for point in points], 50.0) for axis in range(3)
    )
    radius = percentile([_length(_sub(point, center)) for point in points], q)
    return center, radius


def fit_capsule_to_points(points, start, end, q=75.0, slab=0.25):
    """Return the capsule radii of points around a segment.

    Each point is projected on the segment. The radius at each end is the
    ``q`` percentile of the radial distances of the points in the slab
    near that end, ``slab`` being a fraction of the segment length. An
    empty slab uses every point.

    Args:
        points (list): (x, y, z) points.
        start (tuple): Segment start.
        end (tuple): Segment end.
        q (float, optional): Radius percentile, 0 to 100.
        slab (float, optional): End slab size, 0 to 0.5 of the length.

    Returns:
        tuple: ``(start radius, end radius)``, ``(None, None)`` without
        points or for a zero length segment.
    """
    axis = _sub(end, start)
    length_sq = _dot(axis, axis)
    if not points or length_sq < 1e-12:
        return None, None
    near_start = []
    near_end = []
    radial = []
    for point in points:
        offset = _sub(point, start)
        ratio = _dot(offset, axis) / length_sq
        distance = _length(
            _sub(offset, (axis[0] * ratio, axis[1] * ratio, axis[2] * ratio))
        )
        radial.append(distance)
        if ratio <= slab:
            near_start.append(distance)
        if ratio >= 1.0 - slab:
            near_end.append(distance)
    return (
        percentile(near_start or radial, q),
        percentile(near_end or radial, q),
    )


def sphere_directions(count):
    """Return directions evenly spread on a sphere (Fibonacci lattice).

    Args:
        count (int): Number of directions.

    Returns:
        list: Normalized (x, y, z) directions.
    """
    golden = math.pi * (3.0 - math.sqrt(5.0))
    directions = []
    for index in range(count):
        y = 1.0 - 2.0 * (index + 0.5) / count
        ring = math.sqrt(max(0.0, 1.0 - y * y))
        angle = golden * index
        directions.append((ring * math.cos(angle), y, ring * math.sin(angle)))
    return directions


def get_mesh_fn(mesh):
    """Return the OM2 function set of a mesh.

    Args:
        mesh (str): Mesh transform or shape.

    Returns:
        om2.MFnMesh: The function set, on the mesh shape.
    """
    dag_path = utils.get_dag_path(mesh)
    if dag_path.apiType() != om2.MFn.kMesh:
        dag_path.extendToShape()
    return om2.MFnMesh(dag_path)


def _ray_distances(fn, origin, directions, accel):
    """Return the distances of the first hits of rays from a point.

    Args:
        fn (om2.MFnMesh): The mesh.
        origin (tuple): World ray origin.
        directions (list): Normalized (x, y, z) directions.
        accel (om2.MMeshIsectAccelParams): From ``autoUniformGridParams``.

    Returns:
        list: Hit distances, rays without hit skipped.
    """
    source = om2.MFloatPoint(*origin)
    distances = []
    for direction in directions:
        hit = fn.closestIntersection(
            source,
            om2.MFloatVector(*direction),
            om2.MSpace.kWorld,
            1e6,
            False,
            accelParams=accel,
        )
        if hit and hit[2] != -1:
            distances.append(hit[1])
    return distances


def measure_radius_around_point(mesh, point, rays=26):
    """Return the median distance from a point inside a mesh to its surface.

    Args:
        mesh (str): Mesh transform or shape.
        point (tuple): World (x, y, z) point.
        rays (int, optional): Number of rays, spread on a sphere.

    Returns:
        float: Median hit distance, or None without hits.
    """
    fn = get_mesh_fn(mesh)
    distances = _ray_distances(
        fn, point, sphere_directions(rays), fn.autoUniformGridParams()
    )
    return percentile(distances, 50.0) if distances else None


def measure_radius_along_segment(mesh, start, end, rings=5, rays=8):
    """Return the mesh radius around a segment, ring by ring.

    Rays are cast from points along the segment, outwards and at right
    angles to it.

    Args:
        mesh (str): Mesh transform or shape.
        start (tuple): World segment start.
        end (tuple): World segment end.
        rings (int, optional): Number of rings, spread along the segment.
        rays (int, optional): Rays per ring.

    Returns:
        list: Median hit distance per ring, None for rings without hits.
    """
    start = om2.MVector(*start)
    axis = om2.MVector(*end) - start
    if axis.length() < 1e-6:
        return [None] * rings
    normal = axis.normal()
    helper = om2.MVector(0, 1, 0)
    if abs(normal * helper) > 0.9:
        helper = om2.MVector(1, 0, 0)
    side = (normal ^ helper).normal()
    up = side ^ normal
    directions = []
    for index in range(rays):
        angle = 2.0 * math.pi * index / rays
        direction = side * math.cos(angle) + up * math.sin(angle)
        directions.append((direction.x, direction.y, direction.z))
    fn = get_mesh_fn(mesh)
    accel = fn.autoUniformGridParams()
    radii = []
    for index in range(rings):
        center = start + axis * ((index + 0.5) / rings)
        distances = _ray_distances(
            fn, (center.x, center.y, center.z), directions, accel
        )
        radii.append(percentile(distances, 50.0) if distances else None)
    return radii


def create_collision_proxy(
    mesh, reduce_percent=50.0, soft_edges=True, follow=True, name=None
):
    """Create a light copy of a mesh for collisions.

    The copy is reduced, its edges softened and its history deleted. With
    ``follow`` it follows the mesh through a proximity wrap. The source
    mesh is not changed.

    Args:
        mesh (str): Source mesh transform.
        reduce_percent (float, optional): Percentage of faces removed,
            0 keeps them all.
        soft_edges (bool, optional): Soften every edge.
        follow (bool, optional): Follow the source mesh deformation.
        name (str, optional): Proxy name, ``<mesh>_colProxy`` by default.

    Returns:
        str: The proxy transform.
    """
    from mgear.core import deformer

    proxy = cmds.duplicate(
        mesh, name=name or node_remap.short_name(mesh) + "_colProxy"
    )[0]
    intermediates = [
        shape
        for shape in cmds.listRelatives(proxy, shapes=True, fullPath=True) or []
        if cmds.getAttr(shape + ".intermediateObject")
    ]
    if intermediates:
        cmds.delete(intermediates)
    if reduce_percent > 0:
        cmds.polyReduce(
            proxy,
            version=1,
            percentage=reduce_percent,
            keepQuadsWeight=1.0,
            constructionHistory=False,
        )
    if soft_edges:
        cmds.polySoftEdge(proxy, angle=180, constructionHistory=False)
    cmds.delete(proxy, constructionHistory=True)
    if follow:
        deformer.create_proximity_wrap(proxy, mesh)
    return proxy


def get_lowest_point(nodes, axis=1):
    """Return the lowest world coordinate of objects or components.

    Objects use their world bounding box, components (vertices, edges,
    faces) the positions of their vertices.

    Args:
        nodes (list): Objects and/or components.
        axis (int, optional): 0, 1 or 2 for X, Y or Z.

    Returns:
        float: The lowest coordinate, or None for no nodes.
    """
    nodes = cmds.ls(nodes) or []
    components = [node for node in nodes if "." in node]
    values = [
        cmds.exactWorldBoundingBox(node)[axis] for node in nodes if "." not in node
    ]
    if components:
        vertices = cmds.polyListComponentConversion(components, toVertex=True)
        positions = cmds.xform(
            vertices or components, query=True, worldSpace=True, translation=True
        )
        values.extend(positions[axis::3])
    return min(values) if values else None
