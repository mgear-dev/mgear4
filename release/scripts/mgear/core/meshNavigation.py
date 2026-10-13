"""Functions to help navigate the mesh topology"""

#############################################
# GLOBAL
#############################################
import mgear.pymaya as pm
import mgear.pymaya.datatypes as datatypes
from maya import OpenMaya as om
import maya.api.OpenMaya as om2
import itertools
import re
from . import utils
from . import mesh as mesh_utils
from maya import cmds


#############################################
# Vertex
#############################################

#NOTE: WIP function for further improvement in the eyerigger 2.1
def get_extreme_vertex_from_vtx_loop(vtx_list=None,
                                     side_range=False,
                                     z_up=False):
    """Get extreme vertices (up, low, in, out) from a vertex loop.

    Inspects a list of mesh vertex components (or mixed components that
    can be converted to vertices) and returns the extreme vertices along
    the lateral axis and the vertical axis.

    Args:
        vtx_list (list or None): List of mesh vertex components. If None,
            uses the current selection (flattened). Any edges/faces will
            be converted to vertices.
        side_range (bool): If True, use Z as the lateral axis. When
            `z_up` is False, this falls back to Y to match your logic.
        z_up (bool): If True, the up axis is Z; otherwise it is Y.

    Returns:
        tuple: (upPos, lowPos, inPos/outPos depending on side_range,
            input_list, vertex_list)

    """
    if not vtx_list:
        vtx_list = cmds.ls(sl=True, fl=True) or []

    verts = _as_vertices_unique(vtx_list)

    max_lat = None
    min_lat = None
    max_up = None
    min_up = None

    up_pos = None
    low_pos = None
    in_pos = None
    out_pos = None

    # Lateral axis: X(0) by default; Z(2) if side_range.
    axis_index = 2 if side_range else 0
    # Up axis: Z(2) if z_up else Y(1).
    up_axis = 2 if z_up else 1
    # Preserve your special case: if Y-up and side_range=True => lateral Y.
    if not z_up and axis_index == 2:
        axis_index = 1

    for v in verts:
        pos = cmds.pointPosition(v, w=True)
        lat = pos[axis_index]
        upv = pos[up_axis]

        if max_lat is None or lat > max_lat:
            max_lat = lat
            out_pos = v
        if min_lat is None or lat < min_lat:
            min_lat = lat
            in_pos = v
        if max_up is None or upv > max_up:
            max_up = upv
            up_pos = v
        if min_up is None or upv < min_up:
            min_up = upv
            low_pos = v

    if side_range:
        return (up_pos, low_pos, out_pos, in_pos, vtx_list, verts)
    else:
        return (up_pos, low_pos, in_pos, out_pos, vtx_list, verts)


def _as_vertices_unique(items):
    """Convert mixed components to a unique, ordered vertex list.

    Args:
        items (list): Mixed mesh components (verts/edges/faces) or strs.

    Returns:
        list: Unique, ordered list of vertex component strings.

    """
    flat = cmds.ls(items, fl=True) or []
    if not flat:
        return []

    verts_all = []
    for comp in flat:
        conv = cmds.polyListComponentConversion(comp, tv=True)
        if not conv:
            continue
        exp = cmds.ls(conv, fl=True) or []
        if exp:
            verts_all.extend(exp)

    seen = set()
    verts = []
    for v in verts_all:
        if v in seen:
            continue
        seen.add(v)
        verts.append(v)
    return verts


def getExtremeVertexFromLoop(edgeList=None, sideRange=False, z_up=False):
    """Get extreme vertex X and  Y

    min and max positions from edge loop

    Arguments:
        edgeList (list): Edge list
        sideRange (bool): If True will calculate the extreme position
            of Z instead of X
    Returns:
        list: upPos, lowPos, inPos, outPos, edgeList, vertexList

    """
    if not edgeList:
        edgeList = [x for x in pm.selected(fl=1)]
    vertexList = []
    for x in edgeList:
        cv = x.connectedVertices()
        for v in cv:
            if v not in vertexList:
                vertexList.append(v)
    maxX = None
    maxY = None

    minX = None
    minY = None

    upPos = None
    lowPos = None
    inPos = None
    outPos = None
    # index for X or Z
    if sideRange:
        axisIndex = 2
    else:
        axisIndex = 0

    if z_up:
        up_axis = 2
    else:
        up_axis = 1
        if axisIndex == 2:
            axisIndex = 1
    for x in vertexList:
        pos = x.getPosition(space="world")
        if maxX is None or pos[axisIndex] > maxX:
            maxX = pos[axisIndex]
            outPos = x
        if maxY is None or pos[up_axis] > maxY:
            maxY = pos[up_axis]
            upPos = x
        if minX is None or pos[axisIndex] < minX:
            minX = pos[axisIndex]
            inPos = x
        if minY is None or pos[up_axis] < minY:
            minY = pos[up_axis]
            lowPos = x
    if sideRange:
        return upPos, lowPos, outPos, inPos, edgeList, vertexList
    else:
        return upPos, lowPos, inPos, outPos, edgeList, vertexList


def getConcentricVertexLoop(loop, nbLoops):
    """Get concentric vertex loops

    Arguments:
        loop (list): Vertex loop list
        nbLoops (int): Number of loops to search

    Returns:
        list: the loop list

    """
    loopList = []
    allLoops = []
    for x in loop:
        allLoops.append(x)
    loopList.append(loop)

    for x in range(nbLoops):
        tempLoopList = []
        for v in loop:
            connected = v.connectedVertices()
            for cv in connected:
                if cv not in loop:
                    if cv not in allLoops:
                        allLoops.append(cv)
                        tempLoopList.append(cv)
        loop = []
        for c in tempLoopList:
            loop.append(c)

        loopList.append(tempLoopList)

    return loopList


def getVertexRowsFromLoops(loopList):
    """Get vertex rows from edge loops

    Arguments:
        loopList (list): Edge loop list

    Returns:
        list: vertex rows

    """
    rows = []
    for x in loopList[0]:
        rows.append([x])

    loopListLength = len(loopList) - 1

    for i in range(loopListLength):
        for e, r in enumerate(rows):
            cvs = r[-1].connectedVertices()
            # little trick to force the expansion in 2 directions
            cvs2 = False
            if len(r) > 2:
                cvs2 = r[-2].connectedVertices()

            if cvs2:
                for cv in cvs2:
                    if cv in loopList[i + 1]:
                        rows[e].append(cv)
                        continue
            for cv in cvs:
                if cv in loopList[i + 1]:
                    rows[e].append(cv)
                    continue
    return rows


#################################################
# EDGE LOOPS and ROWS
#################################################


def edgeRangeInLoopFromMid(edgeList, midPos, endA, endB):
    """Return a range of edges in the same loop from a mid position

    Arguments:
        edgeList (list): selection edge loop
        midPos (vertex): mid vertex
        endA (vertex): endA vertex
        endB (vertex): endB vertex

    Returns:
        list: loop range

    """
    extremeEdges = []

    scanPoint = [midPos]

    scannedPoints = []
    indexcheck = []
    midEdges = []
    count = 0
    stop = False
    while True:
        oldScanPoint = []
        for sp in scanPoint:
            ce = sp.connectedEdges()
            oldScanPoint.append(sp)
            scannedPoints.append(sp)
            for e in ce:
                if e in edgeList:
                    if e not in midEdges:
                        midEdges.append(e)
                    cv = e.connectedVertices()
                    for v in cv:
                        if (
                            v.index() in [endA.index(), endB.index()]
                            and e not in extremeEdges
                        ):
                            # extra check to ensure that the 2 edges
                            # selected are not attach to the same vertex
                            if v.index() not in indexcheck:
                                extremeEdges.append(e)
                                indexcheck.append(v.index())
                                if len(extremeEdges) == 2:
                                    stop = True
        # regenerate the new list for recursive scan
        scanPoint = []
        for sp in oldScanPoint:
            ce = sp.connectedEdges()
            for e in ce:
                if e in edgeList:
                    cv = e.connectedVertices()
                    for v in cv:
                        if v not in scanPoint and v not in scannedPoints:
                            if v.index() not in [endA.index(), endB.index()]:
                                scanPoint.append(v)

        if stop:
            break
        count += 1
        if count > 50:
            break
    # loopRange = set(midEdges + extremeEdges)
    loopRange = midEdges + extremeEdges
    return loopRange


def edgeLoopBetweenVertices(startPos, endPos):
    """Computes edge loop between two vertices.

    Arguments:
        startPos (vertex): Start of edge loop
        endPos (vertex): End of edge loop

    Returns:
        Edge loop, if one exists. Otherwise None.

    """

    oldSelection = pm.selected()
    mesh = startPos.node()
    edgeLoops = []
    for startEdge in startPos.connectedEdges():
        for endEdge in endPos.connectedEdges():
            testEdgeLoop = pm.polySelect(
                mesh, edgeLoopPath=[startEdge.index(), endEdge.index()]
            )
            if testEdgeLoop:
                edgeLoops.append(pm.selected())
    pm.select(oldSelection, r=1)
    if edgeLoops:
        edgeLoops.sort(key=len)
        return edgeLoops[0]
    return None


#################################################
# Bounding box info
#################################################


def bboxCenter(obj, radius=False):
    """Get bounding box center of mesh object

    Arguments:
        obj (dagNode): mesh object
        radius (bool): If True return a list the center + the radius

    Returns:
        list of float: the bounding box center in world space

    >>> center = mnav.bboxCenter(source, radius=False)

    """
    bbx = obj.getBoundingBox(invisible=True, space="world")
    center = [(bbx[0][x] + bbx[1][x]) / 2.0 for x in range(3)]
    if radius:
        r = abs((bbx[0][0] - bbx[1][0]) / 2)
        return center, r
    return datatypes.Vector(center)


def bBoxData(obj=None, yZero=False, *args):
    """Get bounding box data of a mesh object

    Arguments:
        obj (dagNode): Mesh object
        yZero (bool): If True, sets the Y axis value to 0 in world space
        args:

    Returns:
        list: center, radio, bounding box full data

    """
    volCenter = False

    if not obj:
        obj = pm.selected()[0]
    shapes = pm.listRelatives(obj, ad=True, s=True)
    if shapes:
        bb = pm.polyEvaluate(shapes, b=True)
        volCenter = [(axis[0] + axis[1]) / 2 for axis in bb]
        if yZero:
            volCenter[1] = bb[1][0]
        radio = max([bb[0][1] - bb[0][0], bb[2][1] - bb[2][0]]) / 1.7

    return volCenter, radio, bb


#################################################
# CLOSEST LOCATIONS
#################################################


def getClosestPolygonFromTransform(geo, loc):
    """Get closest polygon from transform

    Arguments:
        geo (dagNode): Mesh object
        loc (matrix): location transform

    Returns:
        Closest Polygon

    """
    if isinstance(
        loc, (pm.nodetypes.Transform, pm.nodetypes.Joint, pm.nodetypes.Locator)
    ):
        pos = loc.getTranslation(space="world")
    else:
        pos = datatypes.Vector(loc[0], loc[1], loc[2])

    nodeDagPath = om.MObject()
    try:
        selectionList = om.MSelectionList()
        selectionList.add(geo.name())
        nodeDagPath = om.MDagPath()
        selectionList.getDagPath(0, nodeDagPath)
    except Exception as e:
        raise RuntimeError(
            "om.MDagPath() failed " "on {}. \n {}".format(geo.name(), e)
        )

    mfnMesh = om.MFnMesh(nodeDagPath)

    pointA = om.MPoint(pos.x, pos.y, pos.z)
    pointB = om.MPoint()
    space = om.MSpace.kWorld

    util = om.MScriptUtil()
    util.createFromInt(0)
    idPointer = util.asIntPtr()

    mfnMesh.getClosestPoint(pointA, pointB, space, idPointer)
    idx = om.MScriptUtil(idPointer).asInt()

    return geo.f[idx], pos


def getClosestVertexFromTransform(geo, loc):
    """Get closest vertex from transform

    Arguments:
        geo (dagNode or str): Mesh object
        loc (matrix): location transform

    Returns:
        Closest Vertex

    >>> v = mn.getClosestVertexFromTransform(geometry, joint)

    """
    geo = utils.as_pynode(geo)
    polygon, pos = getClosestPolygonFromTransform(geo, loc)

    faceVerts = [geo.vtx[i] for i in polygon.getVertices()]
    closestVert = None
    minLength = None
    for v in faceVerts:
        thisLength = (pos - v.getPosition(space="world")).length()
        if minLength is None or thisLength < minLength:
            minLength = thisLength
            closestVert = v
    return closestVert


def getClosestNVerticesFromTransform(geo, loc, count=32):
    """Get the N closest vertices to a transform position.

    Uses a flood-fill from the closest polygon to efficiently
    gather nearby vertices sorted by distance.

    Args:
        geo (dagNode or str): Mesh object.
        loc (matrix): Location transform or position.
        count (int, optional): Number of vertices to return.

    Returns:
        list: Of vertex PyNodes sorted by distance to loc.
    """
    geo = utils.as_pynode(geo)
    polygon, pos = getClosestPolygonFromTransform(geo, loc)

    seed_verts = set(polygon.getVertices())
    visited = set(seed_verts)
    frontier = list(seed_verts)
    collected = []

    for vtx_id in frontier:
        v = geo.vtx[vtx_id]
        d = (pos - v.getPosition(space="world")).length()
        collected.append((d, vtx_id, v))

    while len(collected) < count and frontier:
        next_frontier = []
        for vtx_id in frontier:
            v = geo.vtx[vtx_id]
            for neighbor in v.connectedVertices():
                n_id = neighbor.index()
                if n_id not in visited:
                    visited.add(n_id)
                    next_frontier.append(n_id)
                    d = (pos - neighbor.getPosition(space="world")).length()
                    collected.append((d, n_id, neighbor))
        frontier = next_frontier

    collected.sort(key=lambda x: x[0])
    return [item[2] for item in collected[:count]]


def find_mirror_edge(obj, edgeIndx):
    """Return the mirror edge of an edge

    Args:
        obj (PyNode or str): Mesh object to get the mirror edge
        edge (int): Index of the edge to find the mirror

    Returns:
        PyNode: Mirror edge as a pynode
    """
    obj = utils.as_pynode(obj)

    edge = pm.PyNode(obj.name() + ".e[{}]".format(str(edgeIndx)))
    v1 = edge.getPoint(0, space="world")
    v2 = edge.getPoint(1, space="world")

    # mirror vectors in X axis
    mv1 = [v1[0] * -1, v1[1], v1[2]]
    mv2 = [v2[0] * -1, v2[1], v2[2]]

    vtx1 = getClosestVertexFromTransform(obj.getShape(), mv1)
    vtx2 = getClosestVertexFromTransform(obj.getShape(), mv2)
    for ee in vtx1.connectedEdges():
        if ee in vtx2.connectedEdges():
            return ee


def get_closes_edge_index(sourceGeo, targetGeo, edgeIndx):
    """Get the closes edge index from 2 diferent object.

    In some situation even with same topology and vertez index order. The edge
    index may change.

    Args:
        sourceGeo (str): Name of the source object
        targetGeo (str): Name of the target object
        edgeIndx (int): Edge Index

    Returns:
        PyNode: Description
    """
    edge = pm.PyNode("{}.e[{}]".format(sourceGeo, str(edgeIndx)))

    verts = edge.connectedVertices()

    closes_v = []
    for v in verts:
        vv = getClosestVertexFromTransform(
            targetGeo, v.getPosition(space="world")
        )
        closes_v.append(vv)

    v1_edges = closes_v[0].connectedEdges()
    v2_edges = closes_v[1].connectedEdges()
    for e in v1_edges:
        if e in v2_edges:
            return e.index()


def get_selected_mesh():
    """Get the selected mesh dag path.

    Returns:
        seleted mesh: selected mesh dag path

    Raises:
        ValueError: Non selected object

    """
    selection = om.MSelectionList()
    om.MGlobal.getActiveSelectionList(selection)

    if selection.length() == 0:
        raise ValueError("No object selected. Please select a polygon mesh.")

    mesh_dag_path = om.MDagPath()
    selection.getDagPath(0, mesh_dag_path)

    if mesh_dag_path.apiType() == om.MFn.kTransform:
        child_count = mesh_dag_path.childCount()
        for i in range(child_count):
            child = mesh_dag_path.child(i)
            if child.hasFn(om.MFn.kMesh):
                mesh_dag_path.push(child)
                break

    return mesh_dag_path


def get_mesh_dag_path(node):
    """Get the mesh dag path from a given node.

    Args:
        node (str or PyNode): The name of the node or the PyNode itself

    Returns:
        mesh_dag_path: The dag path to the mesh

    Raises:
        ValueError: If the node does not exist or is not a mesh
    """
    # Ensure node is a PyNode
    if isinstance(node, str):
        try:
            node = pm.PyNode(node)
        except pm.MayaNodeError:
            raise ValueError("No such node: {}".format(node))

    selection_list = om.MSelectionList()
    selection_list.add(str(node))

    mesh_dag_path = om.MDagPath()

    selection_list.getDagPath(0, mesh_dag_path)
    if mesh_dag_path.apiType() == om.MFn.kTransform:
        child_count = mesh_dag_path.childCount()
        for i in range(child_count):
            child = mesh_dag_path.child(i)
            if child.apiType() == om.MFn.kMesh:
                mesh_dag_path.push(child)
                break
    elif mesh_dag_path.apiType() != om.MFn.kMesh:
        raise ValueError("Node is not a mesh: {}".format(node))

    return mesh_dag_path


def get_edge_center(mesh_dag_path, edge_indices):
    """Summary

    Args:
        mesh_dag_path (dag paht): mesh dag path
        edge_indices (TYPE): edge index tuple

    Returns:
        vector: position

    Usage example:
        mesh_dag_path = get_selected_mesh()
        edge_indices = [40, 60]  # Replace with your desired edge indices
        center_position = get_edge_center(mesh_dag_path, edge_indices)
    """
    mesh_fn = om.MFnMesh(mesh_dag_path)
    edge_iter = om.MItMeshEdge(mesh_dag_path)

    point_sum = om.MVector()
    point_count = 0

    for edge_index in edge_indices:
        prev_index = om.MScriptUtil().asIntPtr()
        edge_iter.setIndex(edge_index, prev_index)
        vertex_indices = [edge_iter.index(0), edge_iter.index(1)]
        for vertex_index in vertex_indices:
            point = om.MPoint()
            mesh_fn.getPoint(vertex_index, point, om.MSpace.kWorld)
            point_sum += om.MVector(
                point
            )  # Convert MPoint to MVector before adding
            point_count += 1

    return om.MPoint(point_sum / point_count)  # Convert MVector back to MPoint


#############################################
# Ordered loops by index (OM2)
#############################################

_COMPONENT_KINDS = {"e": "edge", "vtx": "vertex"}
_KIND_TOKENS = {kind: token for token, kind in _COMPONENT_KINDS.items()}
_COMPONENT_RE = re.compile(
    r"^(?P<node>[^\.\s]+)\.(?P<kind>e|vtx)\[(?P<range>[\d:]+)\]$"
)


def parse_component_string(text):
    """Parse a mesh component string into the mesh, kind and indices.

    Accepts comma or space separated components with Maya ranges, as stored
    by the facial riggers, e.g. ``"head.e[10],head.e[12:14]"``.

    Args:
        text (str): Component string.

    Returns:
        tuple: (mesh, kind, indices). kind is "edge" or "vertex" and indices
            is a sorted list of unique ints. (None, None, []) if text is
            empty.

    Raises:
        ValueError: If the components are not edges or vertices, mix kinds
            or belong to more than one mesh.
    """
    items = [item for item in re.split(r"[,\s]+", text or "") if item]
    if not items:
        return None, None, []
    mesh = None
    kind = None
    indices = set()
    for item in items:
        match = _COMPONENT_RE.match(item)
        if not match:
            raise ValueError("Not an edge or vertex component: {}".format(item))
        item_mesh = match.group("node")
        item_kind = _COMPONENT_KINDS[match.group("kind")]
        if mesh is None:
            mesh = item_mesh
            kind = item_kind
        elif item_mesh != mesh:
            raise ValueError("Components from more than one mesh: {}".format(text))
        elif item_kind != kind:
            raise ValueError("Mixed edges and vertices: {}".format(text))
        bounds = [int(value) for value in match.group("range").split(":")]
        indices.update(range(bounds[0], bounds[-1] + 1))
    return mesh, kind, sorted(indices)


def format_component_string(mesh, kind, indices):
    """Format a mesh, kind and indices as a compact component string.

    Args:
        mesh (str): Mesh name.
        kind (str): "edge" or "vertex".
        indices (list): Component indices.

    Returns:
        str: Comma separated components with ranges, e.g.
            ``"head.e[10:12],head.e[20]"``.
    """
    token = _KIND_TOKENS[kind]
    items = []
    ordered = enumerate(sorted(set(indices)))
    # consecutive indices share the same index - position difference
    for _, run in itertools.groupby(ordered, lambda pair: pair[1] - pair[0]):
        run = [index for _, index in run]
        if len(run) == 1:
            items.append("{}.{}[{}]".format(mesh, token, run[0]))
        else:
            items.append("{}.{}[{}:{}]".format(mesh, token, run[0], run[-1]))
    return ",".join(items)


def components_from_selection(kind="edge"):
    """Get the selected mesh components as a component string.

    Selected components are converted to the requested kind.

    Args:
        kind (str): "edge" or "vertex".

    Returns:
        str: Component string, or "" if nothing usable is selected.
    """
    flag = {"edge": "toEdge", "vertex": "toVertex"}[kind]
    selection = cmds.ls(selection=True, flatten=True) or []
    components = [item for item in selection if "." in item]
    if not components:
        return ""
    converted = cmds.ls(
        cmds.polyListComponentConversion(components, **{flag: True}),
        flatten=True,
    )
    mesh = None
    indices = []
    for item in converted:
        item_node, rest = item.split(".", 1)
        mesh = mesh or item_node
        indices.append(int(rest[rest.index("[") + 1 : -1]))
    if mesh is None:
        return ""
    return format_component_string(mesh, kind, indices)


def _vertex_neighbours(mesh, indices):
    """Get the connected vertices of each vertex.

    Args:
        mesh (str): Mesh name.
        indices (iterable): Vertex indices.

    Returns:
        dict: {vertex: set of connected vertices}
    """
    iterator = om2.MItMeshVertex(mesh_utils.get_mesh_fn(mesh).dagPath())
    neighbours = {}
    for index in indices:
        iterator.setIndex(index)
        neighbours[index] = set(iterator.getConnectedVertices())
    return neighbours


def _walk_adjacency(adjacency):
    """Walk an adjacency map of max degree 2 into an ordered path.

    Args:
        adjacency (dict): {vertex: set of linked vertices}

    Returns:
        tuple: (ordered vertices, is_closed)

    Raises:
        ValueError: If the vertices are not one connected chain or cycle.
    """
    if any(not linked for linked in adjacency.values()):
        raise ValueError("The components are not connected")
    ends = sorted(v for v, linked in adjacency.items() if len(linked) == 1)
    is_closed = not ends
    if not is_closed and len(ends) != 2:
        raise ValueError(
            "The components are not one connected loop or path "
            "(path ends: {})".format(ends)
        )
    start = min(adjacency) if is_closed else ends[0]
    ordered = [start]
    previous = None
    current = start
    while True:
        following = [v for v in sorted(adjacency[current]) if v != previous]
        if not following or following[0] == start:
            break
        previous, current = current, following[0]
        ordered.append(current)
    if len(ordered) != len(adjacency):
        raise ValueError("The components are not connected")
    return ordered, is_closed


def get_ordered_loop_from_edges(mesh, edge_indices):
    """Get the ordered vertices of an edge loop or open edge path.

    Args:
        mesh (str): Mesh name.
        edge_indices (list): Edge indices.

    Returns:
        tuple: (ordered vertex indices, is_closed)

    Raises:
        ValueError: If the edges branch or are not connected.
    """
    mesh_fn = mesh_utils.get_mesh_fn(mesh)
    adjacency = {}
    for edge in edge_indices:
        a, b = mesh_fn.getEdgeVertices(edge)
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    branching = sorted(v for v, linked in adjacency.items() if len(linked) > 2)
    if branching:
        raise ValueError("The edges branch at vertices {}".format(branching))
    return _walk_adjacency(adjacency)


def get_ordered_loop_from_vertices(mesh, vertex_indices):
    """Get the ordered vertices of a vertex loop or open vertex path.

    Mesh edges joining two selected vertices link them. Chords (edges whose
    two vertices both have more than two links, like the diagonal of a
    triangulated corner) are removed.

    Args:
        mesh (str): Mesh name.
        vertex_indices (list): Vertex indices.

    Returns:
        tuple: (ordered vertex indices, is_closed)

    Raises:
        ValueError: If the vertices are ambiguous or not connected.
    """
    selected = set(vertex_indices)
    neighbours = _vertex_neighbours(mesh, selected)
    adjacency = {v: neighbours[v] & selected for v in selected}
    for v in sorted(adjacency):
        for linked in sorted(adjacency[v]):
            if len(adjacency[v]) > 2 and len(adjacency[linked]) > 2:
                adjacency[v].discard(linked)
                adjacency[linked].discard(v)
    ambiguous = sorted(v for v, linked in adjacency.items() if len(linked) > 2)
    if ambiguous:
        raise ValueError(
            "The vertex loop is ambiguous at vertices {}. Use an edge "
            "loop instead".format(ambiguous)
        )
    return _walk_adjacency(adjacency)


def get_ordered_loop(mesh, indices, kind="edge"):
    """Get the ordered vertices of an edge or vertex loop or path.

    Args:
        mesh (str): Mesh name.
        indices (list): Edge or vertex indices.
        kind (str): "edge" or "vertex".

    Returns:
        tuple: (ordered vertex indices, is_closed)
    """
    if kind == "vertex":
        return get_ordered_loop_from_vertices(mesh, indices)
    return get_ordered_loop_from_edges(mesh, indices)


def split_loop_at_vertices(ordered, is_closed, vertex_a, vertex_b):
    """Split an ordered loop into the two paths running from a to b.

    Args:
        ordered (list): Ordered loop vertices.
        is_closed (bool): True if the loop is closed.
        vertex_a (int): Start vertex.
        vertex_b (int): End vertex.

    Returns:
        tuple: (path, other_path). Both run from a to b and include them.
            For an open loop other_path is empty.
    """
    index_a = ordered.index(vertex_a)
    index_b = ordered.index(vertex_b)
    if not is_closed:
        if index_a <= index_b:
            return ordered[index_a : index_b + 1], []
        return ordered[index_b : index_a + 1][::-1], []
    rotated = ordered[index_a:] + ordered[:index_a]
    index_b = rotated.index(vertex_b)
    return rotated[: index_b + 1], [rotated[0]] + rotated[index_b:][::-1]


def order_path_from(ordered, start):
    """Order an open path so it starts at the given end vertex.

    Args:
        ordered (list): Ordered path vertices.
        start (int): One of the two path ends.

    Returns:
        list: The path starting at start.

    Raises:
        ValueError: If start is not a path end.
    """
    if ordered and ordered[0] == start:
        return list(ordered)
    if ordered and ordered[-1] == start:
        return list(reversed(ordered))
    raise ValueError("Vertex {} is not an end of the path".format(start))


def get_vertex_world_positions(mesh, indices):
    """Get the world positions of vertices.

    Args:
        mesh (str): Mesh name.
        indices (list): Vertex indices.

    Returns:
        list: (x, y, z) tuples in the indices order.
    """
    mesh_fn = mesh_utils.get_mesh_fn(mesh)
    points = [mesh_fn.getPoint(i, om2.MSpace.kWorld) for i in indices]
    return [(point.x, point.y, point.z) for point in points]


def get_average_vertex_normal(mesh, indices):
    """Get the normalized average world normal of vertices.

    Args:
        mesh (str): Mesh name.
        indices (list): Vertex indices.

    Returns:
        tuple: (x, y, z) unit vector.
    """
    mesh_fn = mesh_utils.get_mesh_fn(mesh)
    total = om2.MVector()
    for index in indices:
        total += mesh_fn.getVertexNormal(index, False, om2.MSpace.kWorld)
    total.normalize()
    return (total.x, total.y, total.z)


def get_mirror_vertex_indices(mesh, indices, axis="x", tolerance=0.001):
    """Get the vertices at the mirrored position of each vertex.

    Args:
        mesh (str): Mesh name.
        indices (list): Vertex indices.
        axis (str): Mirror axis, "x", "y" or "z".
        tolerance (float): Max distance to the mirrored position.

    Returns:
        list: Mirror vertex index per vertex, None where there is none.
    """
    axis_index = "xyz".index(axis)
    mesh_fn = mesh_utils.get_mesh_fn(mesh)
    dag_path = mesh_fn.dagPath()
    intersector = om2.MMeshIntersector()
    intersector.create(dag_path.node(), dag_path.inclusiveMatrix())
    found = {}
    for index in set(indices):
        target = mesh_fn.getPoint(index, om2.MSpace.kWorld)
        target[axis_index] *= -1
        face = intersector.getClosestPoint(target).face
        best = None
        best_distance = tolerance
        for vertex in mesh_fn.getPolygonVertices(face):
            point = mesh_fn.getPoint(vertex, om2.MSpace.kWorld)
            distance = point.distanceTo(target)
            if distance <= best_distance:
                best = vertex
                best_distance = distance
        found[index] = best
    return [found[index] for index in indices]


def get_mirror_edge_indices(mesh, indices, axis="x", tolerance=0.001):
    """Get the edges at the mirrored position of each edge.

    Args:
        mesh (str): Mesh name.
        indices (list): Edge indices.
        axis (str): Mirror axis, "x", "y" or "z".
        tolerance (float): Max distance to the mirrored vertex positions.

    Returns:
        list: Mirror edge index per edge, None where there is none.
    """
    mesh_fn = mesh_utils.get_mesh_fn(mesh)
    edge_vertices = [mesh_fn.getEdgeVertices(edge) for edge in indices]
    flat = [v for pair in edge_vertices for v in pair]
    mirrored = get_mirror_vertex_indices(mesh, flat, axis, tolerance)
    iterator = om2.MItMeshVertex(mesh_fn.dagPath())

    def edges_of(vertex):
        iterator.setIndex(vertex)
        return set(iterator.getConnectedEdges())

    mirrors = []
    for i in range(len(indices)):
        a, b = mirrored[2 * i], mirrored[2 * i + 1]
        common = edges_of(a) & edges_of(b) if None not in (a, b) else set()
        mirrors.append(min(common) if common else None)
    return mirrors


def get_nearest_seed_map(mesh, seed_indices, count):
    """Get the ring and nearest seed of the vertices around seed vertices.

    Grows rings out from the seeds through the mesh edges. Each new vertex
    takes the seed of its closest neighbour in the previous ring.

    Args:
        mesh (str): Mesh name.
        seed_indices (list): Seed vertex indices.
        count (int): Number of rings after the seeds.

    Returns:
        dict: {vertex: (ring, seed)} for the seeds and their rings.
    """
    mesh_fn = mesh_utils.get_mesh_fn(mesh)
    iterator = om2.MItMeshVertex(mesh_fn.dagPath())
    points = {}

    def point(index):
        if index not in points:
            points[index] = mesh_fn.getPoint(index, om2.MSpace.kWorld)
        return points[index]

    seed_map = {seed: (0, seed) for seed in seed_indices}
    frontier = sorted(seed_map)
    for ring in range(1, count + 1):
        found = {}
        for vertex in frontier:
            iterator.setIndex(vertex)
            seed = seed_map[vertex][1]
            for linked in iterator.getConnectedVertices():
                if linked in seed_map:
                    continue
                distance = point(linked).distanceTo(point(vertex))
                if linked not in found or distance < found[linked][0]:
                    found[linked] = (distance, seed)
        for vertex, (_, seed) in found.items():
            seed_map[vertex] = (ring, seed)
        frontier = sorted(found)
        if not frontier:
            break
    return seed_map


def get_concentric_vertex_rings(mesh, seed_indices, count):
    """Get rings of vertices growing out from seed vertices.

    Ring 0 is the seeds. Each next ring holds the not yet visited vertices
    connected by an edge to the previous ring.

    Args:
        mesh (str): Mesh name.
        seed_indices (list): Seed vertex indices.
        count (int): Number of rings after the seeds.

    Returns:
        list: count + 1 lists of vertex indices.
    """
    rings = [[] for _ in range(count + 1)]
    for vertex, (ring, _) in sorted(
        get_nearest_seed_map(mesh, seed_indices, count).items()
    ):
        rings[ring].append(vertex)
    return rings


def mirror_component_string(text, axis="x", tolerance=0.001):
    """Mirror the edges or vertices of a component string.

    Args:
        text (str): Component string, see :func:`parse_component_string`.
        axis (str): Mirror axis, "x", "y" or "z".
        tolerance (float): Max distance to the mirrored positions.

    Returns:
        tuple: (mirrored string, list of indices without a mirror). The
            string is unchanged when some indices have no mirror.
    """
    mesh, kind, indices = parse_component_string(text)
    if not indices:
        return text, []
    if kind == "edge":
        mirrored = get_mirror_edge_indices(mesh, indices, axis, tolerance)
    else:
        mirrored = get_mirror_vertex_indices(mesh, indices, axis, tolerance)
    missing = [index for index, mirror in zip(indices, mirrored) if mirror is None]
    if missing:
        return text, missing
    return format_component_string(mesh, kind, mirrored), []
