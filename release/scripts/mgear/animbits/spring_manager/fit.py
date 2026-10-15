"""Fit Bone Dynamics colliders and bone radii to geometry.

The math lives in :mod:`mgear.core.mesh` and :mod:`mgear.core.skin`; this
module turns selections into colliders and spring parameters.

Two ways to measure a mesh around a joint:

- ``skin``: the vertices whose dominant influence is the joint (the mesh
  must be skinned to the joints);
- ``raycast``: rays cast from the joint or bone outwards, for any mesh.

``auto`` uses ``skin`` when the mesh is skinned to the joints.
"""

import maya.api.OpenMaya as om2
from maya import cmds

import mgear
from mgear.core import mesh as mesh_utils
from mgear.core import node_remap
from mgear.core import skin
from mgear.core import utils

from . import colliders
from . import radius_profile

AUTO = "auto"
SKIN = "skin"
RAYCAST = "raycast"
METHODS = (AUTO, SKIN, RAYCAST)

RINGS = 5
RAYS = 12
SPHERE_RAYS = 26


class FitOptions(object):
    """Options of the fit tools.

    Attributes:
        method (str): :data:`AUTO`, :data:`SKIN` or :data:`RAYCAST`.
        padding (float): Radius multiplier.
        percentile (float): Radius percentile of the skin method, 0-100.
        min_radius (float): Smallest radius.
        end_spheres (bool): Fit Capsules adds a sphere at each chain end.
        profile (bool): Fit Bone Radius also fits the radius profile.
        smooth (int): Smoothing passes of the radius profile.
    """

    def __init__(
        self,
        method=AUTO,
        padding=1.0,
        percentile=75.0,
        min_radius=0.1,
        end_spheres=True,
        profile=True,
        smooth=radius_profile.SMOOTH,
    ):
        self.method = method
        self.padding = padding
        self.percentile = percentile
        self.min_radius = min_radius
        self.end_spheres = end_spheres
        self.profile = profile
        self.smooth = smooth

    def radius(self, value):
        """Return a measured radius with padding and minimum applied.

        Args:
            value (float): Measured radius, or None.

        Returns:
            float: The radius.
        """
        if value is None:
            return self.min_radius
        return max(self.min_radius, value * self.padding)


def _position(node):
    return tuple(cmds.xform(node, query=True, worldSpace=True, translation=True))


def chain_parts(joints):
    """Split selected joints (or controls) into segments and chain ends.

    A segment goes from a selected node to each selected node whose
    nearest selected ancestor it is. A chain end is a selected node with no
    selected descendant.

    Args:
        joints (list): Joint or control names.

    Returns:
        tuple: ``(segments, ends)``: ``[(start, end), ...]`` and
        ``[joint, ...]``, as long names in selection order.
    """
    joints = cmds.ls(joints, long=True) or []
    selected = set(joints)
    segments = []
    parents = set()
    for joint in joints:
        parent = joint.rpartition("|")[0]
        while parent and parent not in selected:
            parent = parent.rpartition("|")[0]
        if parent:
            segments.append((parent, joint))
            parents.add(parent)
    ends = [joint for joint in joints if joint not in parents]
    return segments, ends


class _Measure(object):
    """Mesh measures around joints, with the method resolved once.

    Args:
        mesh (str): Mesh transform.
        joints (list): Joint long names.
        options (FitOptions): Options.
    """

    def __init__(self, mesh, joints, options):
        self.mesh = mesh
        self.options = options
        self.vertices = {}
        self.points = []
        method = options.method
        if method in (AUTO, SKIN):
            self.vertices = skin.get_dominant_influence_vertices(mesh, joints)
            if not any(self.vertices.values()):
                if method == SKIN:
                    mgear.log(
                        "{} is not skinned to the joints, ray casting".format(
                            node_remap.leaf_name(mesh)
                        ),
                        mgear.sev_warning,
                    )
                self.vertices = {}
        if self.vertices:
            fn = mesh_utils.get_mesh_fn(mesh)
            self.points = [
                (point.x, point.y, point.z) for point in fn.getPoints(om2.MSpace.kWorld)
            ]

    def joint_points(self, joint):
        """Return the world points of the vertices dominated by a joint."""
        return [self.points[index] for index in self.vertices.get(joint, ())]

    def capsule_radii(self, start, start_position, end_position):
        """Return the (start, end) radii of the mesh around a segment.

        Args:
            start (str): Start joint, whose vertices are measured.
            start_position (tuple): World start.
            end_position (tuple): World end.

        Returns:
            tuple: ``(start radius, end radius)``, None without mesh.
        """
        points = self.joint_points(start)
        if points:
            return mesh_utils.fit_capsule_to_points(
                points, start_position, end_position, self.options.percentile
            )
        radii = [
            radius
            for radius in mesh_utils.measure_radius_along_segment(
                self.mesh, start_position, end_position, RINGS, RAYS
            )
            if radius is not None
        ]
        if not radii:
            return None, None
        return radii[0], radii[-1]

    def sphere(self, joint):
        """Return the (centre, radius) of the mesh around a joint."""
        points = self.joint_points(joint)
        if points:
            return mesh_utils.fit_sphere_to_points(points, self.options.percentile)
        position = _position(joint)
        return position, mesh_utils.measure_radius_around_point(
            self.mesh, position, SPHERE_RAYS
        )


def capsule_matrix(start, end):
    """Return the world matrix of a capsule collider between two points.

    The capsule shape lies along its local Y axis, centred: Y points from
    ``start`` to ``end``, so ``radiusA`` (+Y) is the end radius.

    Args:
        start (tuple): World start.
        end (tuple): World end.

    Returns:
        list: 16 floats.
    """
    start = om2.MVector(*start)
    axis = om2.MVector(*end) - start
    y = axis.normal()
    helper = om2.MVector(1, 0, 0) if abs(y.x) < 0.9 else om2.MVector(0, 0, 1)
    z = (helper ^ y).normal()
    x = (y ^ z).normal()
    center = start + axis * 0.5
    return [
        x.x, x.y, x.z, 0.0,
        y.x, y.y, y.z, 0.0,
        z.x, z.y, z.z, 0.0,
        center.x, center.y, center.z, 1.0,
    ]  # fmt: skip


def fit_capsules(mesh, joints, options=None):
    """Create capsule colliders fitted to a mesh along selected joints.

    Each segment gets a capsule driven by its start node. With
    ``options.end_spheres``, each chain end gets a sphere driven by the end
    node. The last bone of a spring always gets a capsule to its tip
    instead. Controls are measured by ray casting: they are not skin
    influences. On the sim joints of a Bone Dynamics spring, each collider
    also sets the volume of its bone.

    Args:
        mesh (str): Mesh transform.
        joints (list): Joints or controls, in any order.
        options (FitOptions, optional): Options.

    Returns:
        list: The created collider networks.
    """
    options = options or FitOptions()
    segments, ends = chain_parts(joints)
    measure = _Measure(mesh, cmds.ls(joints, long=True), options)
    created = []
    with utils.undo_chunk("springManagerFitCapsules"):
        for start, end in segments:
            created.append(_fit_capsule(measure, start, end, options))
        for joint in ends:
            # the last bone of a spring goes on to its tip joint: a capsule
            # matches the bone volume, a sphere would only cover its root
            tip = _spring_tip(joint)
            if tip:
                created.append(_fit_capsule(measure, joint, tip, options))
            elif options.end_spheres:
                created.append(_fit_sphere_at(measure, joint, options))
    return [network for network in created if network]


def _spring_tip(joint):
    """Return the tip joint after the last bone of a spring, or None.

    Args:
        joint (str): Selected joint, possibly a spring sim joint.

    Returns:
        str: The joint the bone's boneDynamicsNode aims at, when ``joint``
        is a simulated bone.
    """
    from .backends import bone_dynamics
    from .backends import get_backend

    node = get_backend(bone_dynamics.BACKEND).bone_node(joint)
    if not node:
        return None
    ends = cmds.listConnections(node + ".endTranslate", source=True, destination=False)
    return cmds.ls(ends[0], long=True)[0] if ends else None


def _fit_capsule(measure, start, end, options):
    """Create a capsule collider fitted between two nodes, driven by start.

    Args:
        measure (_Measure): Mesh measures.
        start (str): Start node, the driver.
        end (str): End node.
        options (FitOptions): Options.

    Returns:
        str: The collider network.
    """
    start_position = _position(start)
    end_position = _position(end)
    start_radius, end_radius = measure.capsule_radii(
        start, start_position, end_position
    )
    if start_radius is None:
        mgear.log(
            "{}: no mesh around the segment, minimum radius used".format(
                node_remap.leaf_name(start)
            ),
            mgear.sev_warning,
        )
    height = om2.MVector(*end_position) - om2.MVector(*start_position)
    return colliders.create(
        colliders.CAPSULE,
        start,
        "{}_capsuleCol".format(node_remap.short_name(start)),
        {
            "height": height.length(),
            "radiusA": options.radius(end_radius),
            "radiusB": options.radius(start_radius),
        },
        capsule_matrix(start_position, end_position),
    )


def _fit_sphere_at(measure, joint, options):
    center, radius = measure.sphere(joint)
    if radius is None:
        mgear.log(
            "{}: no mesh around the joint, sphere skipped".format(
                node_remap.leaf_name(joint)
            ),
            mgear.sev_warning,
        )
        return None
    matrix = cmds.xform(joint, query=True, worldSpace=True, matrix=True)
    matrix[12:15] = center
    return colliders.create(
        colliders.SPHERE,
        joint,
        "{}_sphereCol".format(node_remap.short_name(joint)),
        {"radius": options.radius(radius)},
        matrix,
    )


def fit_sphere(mesh=None, joint=None, vertices=None, options=None):
    """Create a sphere collider fitted to vertices, or to a mesh at a joint.

    Args:
        mesh (str, optional): Mesh transform, with ``joint``.
        joint (str, optional): Driver joint. With ``vertices`` and no
            joint, the dominant influence of the vertices drives the sphere
            when the mesh is skinned.
        vertices (list, optional): Vertex components.
        options (FitOptions, optional): Options.

    Returns:
        str: The collider network, or None.
    """
    options = options or FitOptions()
    with utils.undo_chunk("springManagerFitSphere"):
        if vertices:
            vertices = cmds.ls(
                cmds.polyListComponentConversion(vertices, toVertex=True),
                flatten=True,
            )
            flat = cmds.xform(vertices, query=True, worldSpace=True, translation=True)
            points = list(zip(flat[0::3], flat[1::3], flat[2::3]))
            center, radius = mesh_utils.fit_sphere_to_points(points, options.percentile)
            if joint is None:
                joint = _dominant_joint(vertices)
            matrix = om2.MTransformationMatrix()
            matrix.setTranslation(om2.MVector(*center), om2.MSpace.kWorld)
            return colliders.create(
                colliders.SPHERE,
                joint,
                None,
                {"radius": options.radius(radius)},
                list(matrix.asMatrix()),
            )
        if not (mesh and joint):
            raise ValueError("Select vertices, or a joint and a mesh")
        measure = _Measure(mesh, cmds.ls(joint, long=True), options)
        return _fit_sphere_at(measure, cmds.ls(joint, long=True)[0], options)


def fit_spheres(mesh, joints, options=None):
    """Create a sphere collider fitted to a mesh at each joint or control.

    Args:
        mesh (str): Mesh transform.
        joints (list): Joints or controls, each the driver of its sphere.
        options (FitOptions, optional): Options.

    Returns:
        list: The created collider networks (joints without mesh around
        them are skipped with a warning).
    """
    options = options or FitOptions()
    joints = cmds.ls(joints, long=True)
    measure = _Measure(mesh, joints, options)
    with utils.undo_chunk("springManagerFitSpheres"):
        created = [_fit_sphere_at(measure, joint, options) for joint in joints]
    return [network for network in created if network]


def _dominant_joint(vertices):
    """Return the influence weighting most of the vertices, or None."""
    mesh = vertices[0].split(".")[0]
    indices = {int(vertex.split("[")[-1][:-1]) for vertex in vertices}
    counts = {
        influence: len(members)
        for influence, members in skin.get_dominant_influence_vertices(
            mesh, threshold=0.0, vertices=sorted(indices)
        ).items()
    }
    best = max(counts, key=counts.get) if counts else None
    return best if best and counts[best] else None


def fit_bone_radius(backend, springs, mesh, options=None):
    """Set the bone radius of springs from a mesh around their bones.

    Each simulated bone is measured by ray casting, ring by ring. A
    straight line fitted through the measures, from the root (ratio 0) to
    the tip (ratio 1), gives the Root Radius and the Tip Radius. Bone As
    Capsule is turned on. With ``options.profile``, the radius profile is
    fitted too: one factor per joint, so the radii follow the measures
    smoothed along each root-to-leaf path.

    Args:
        backend (BoneDynamicsBackend): The Bone Dynamics backend.
        springs (list): :class:`registry.Spring` records.
        mesh (str): Mesh transform.
        options (FitOptions, optional): Options (padding, minimum radius,
            profile and smoothing).

    Returns:
        dict: ``{spring: (root radius, tip radius)}`` for the fitted springs.
    """
    from .backends import bone_dynamics

    options = options or FitOptions()
    result = {}
    with utils.undo_chunk("springManagerFitBoneRadius"):
        for spring in springs:
            sections = backend.profile_sections(spring)
            samples = [_section_samples(mesh, section) for section in sections]
            line_samples = [
                (
                    (section.ratio + section.end_ratio) * 0.5,
                    mesh_utils.percentile([radius for _, radius in points], 50),
                )
                for section, points in zip(sections, samples)
                if points
            ]
            if not line_samples:
                mgear.log(
                    "{}: no mesh around the bones, skipped".format(spring.label),
                    mgear.sev_warning,
                )
                continue
            root, tip = (options.radius(value) for value in _line_fit(line_samples))
            backend.set_params(
                [spring],
                {
                    bone_dynamics.RADIUS: root,
                    bone_dynamics.TIP_RADIUS: tip,
                    bone_dynamics.BONE_CAPSULE: True,
                },
            )
            if options.profile:
                backend.set_radius_profile(
                    [spring], _profile_items(sections, samples, root, tip, options)
                )
            result[spring] = (root, tip)
    return result


def _section_samples(mesh, section):
    """Return the measured radii along a section, at their chain ratios.

    Args:
        mesh (str): Mesh transform.
        section (ProfileSection): The section.

    Returns:
        list: ``(ratio, radius)`` pairs, rings without hits left out.
    """
    radii = mesh_utils.measure_radius_along_segment(
        mesh, _position(section.bone), _position(section.end), RINGS, RAYS
    )
    return [
        (
            section.ratio + (section.end_ratio - section.ratio) * (index + 0.5) / RINGS,
            radius,
        )
        for index, radius in enumerate(radii)
        if radius is not None
    ]


def _profile_items(sections, samples, root, tip, options):
    """Return the radius profile fitted to the measures of a spring.

    Args:
        sections (list): ``ProfileSection`` items of the spring.
        samples (list): Per section, ``(ratio, radius)`` measures.
        root (float): Fitted Root Radius.
        tip (float): Fitted Tip Radius.
        options (FitOptions): Padding, minimum radius and smoothing.

    Returns:
        list: ``(joint, ratio, factor)`` per joint, factor 1 for joints
        without measures.
    """
    chain_sections = [section.chain() for section in sections]
    radii = radius_profile.joint_radii(chain_sections, samples, options.smooth)
    return [
        (
            joint,
            ratio,
            (
                radius_profile.factor(
                    options.radius(radii[joint]),
                    radius_profile.gradient(root, tip, ratio),
                )
                if joint in radii
                else 1.0
            ),
        )
        for joint, ratio in radius_profile.chain_joints(chain_sections)
    ]


def _line_fit(samples):
    """Return the values at 0 and 1 of the least-squares line of samples.

    Args:
        samples (list): ``(ratio, value)`` pairs.

    Returns:
        tuple: ``(value at 0, value at 1)``. One sample gives a flat line.
    """
    count = len(samples)
    mean_x = sum(x for x, _ in samples) / count
    mean_y = sum(y for _, y in samples) / count
    spread = sum((x - mean_x) ** 2 for x, _ in samples)
    if count < 2 or spread < 1e-9:
        return mean_y, mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in samples) / spread
    start = mean_y - slope * mean_x
    return start, start + slope
