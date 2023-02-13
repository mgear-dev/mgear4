import pymel.core as pm
from pymel.core import datatypes
from pymel.core import nodetypes


from mgear.core import attribute
from mgear.core import transform
from mgear.core import vector

PROXY_SUFFIX = "proxy"
PROXY_GRP = "proxy_grp"


def create_capsule(name, side, length, axis=[1, 0, 0]):
    """Create a Maya polygonal capsule with specified dimensions and return
    the transform node.

    Args:
        name (str): The name of the capsule transform node to be created.
        side (float): The radius of the capsule.
        length (float): The length of the capsule.
        axis (list, optional): The axis along which the capsule is aligned.
        Defaults to [1, 0, 0].

    Returns:
        pm.nodetypes.Transform: The transform node of the newly created capsule.

    """
    args = {
        "subdivisionsX": 16,
        "subdivisionsY": 1,
        "subdivisionsZ": 4,
        "roundCap": True,
        "createUVs": 0,
        "constructionHistory": True,
        "name": name,
        "radius": side,
        "height": length,
        "axis": axis,
    }
    trans, cap = pm.polyCylinder(**args)

    # hide build nodes from channelbox
    cap.isHistoricallyInteresting.set(False)
    trans.getShapes()[0].isHistoricallyInteresting.set(False)

    # add manipulation attrs
    r_att = attribute.addAttribute(
        trans,
        "side",
        "float",
        value=side,
        softMinValue=0.001,
        softMaxValue=100,
    )
    h_att = attribute.addAttribute(
        trans,
        "length",
        "float",
        value=length,
        softMinValue=0.001,
        softMaxValue=100,
    )

    # lock scale
    # attribute.lockAttribute(trans, attributes=["sx", "sy", "sz"])

    pm.connectAttr(r_att, cap.radius)
    pm.connectAttr(h_att, cap.height)

    return trans


def create_box(name, side, length, axis=[1, 0, 0]):
    """Create a Maya polygonal box with specified dimensions and return the
    transform node.

    Args:
        name (str): The name of the box transform node to be created.
        side (float): The size of each side of the box.
        length (float): The length of the box.
        axis (list, optional): The axis along which the box is aligned.
        Defaults to [1, 0, 0].

    Returns:
        pm.nodetypes.Transform: The transform node of the newly created box.

    """
    args = {
        "subdivisionsX": 1,
        "subdivisionsY": 1,
        "subdivisionsZ": 1,
        "subdivisionsDepth": 1,
        "subdivisionsHeight": 1,
        "subdivisionsWidth": 1,
        "createUVs": 0,
        "constructionHistory": True,
        "name": name,
        "depth": side * 2,
        "width": side * 2,
        "height": length,
        "axis": axis,
    }
    trans, box = pm.polyCube(**args)

    # hide build nodes from channelbox
    box.isHistoricallyInteresting.set(False)
    trans.getShapes()[0].isHistoricallyInteresting.set(False)

    # add manipulation attrs
    r_att = attribute.addAttribute(
        trans,
        "side",
        "float",
        value=side,
        softMinValue=0.001,
        softMaxValue=100,
    )
    h_att = attribute.addAttribute(
        trans,
        "length",
        "float",
        value=length,
        softMinValue=0.001,
        softMaxValue=100,
    )

    # lock scale
    # attribute.lockAttribute(trans, attributes=["sx", "sy", "sz"])

    pm.connectAttr(r_att, box.width)
    pm.connectAttr(r_att, box.depth)
    pm.connectAttr(h_att, box.height)

    return trans


def add_to_grp(proxy_objs):
    """Add a list of proxy objects to the appropriate rig proxy set and rig
    groups.

    If the first proxy object in the list has a parent transform with an
    "is_rig" attribute, the proxy
    objects will be added to a proxy set specific to that rig. Otherwise,
    the proxy objects will be
    added to a generic "rig_proxy_grp" set.

    Args:
        proxy_objs (list of pm.nodetypes.Transform): A list of proxy objects
            to add to the rig proxy set.

    Returns:
        None

    """
    if proxy_objs and proxy_objs[0].getParent(-1).hasAttr("is_rig"):
        model = proxy_objs[0].getParent(-1)
        name = "{}_{}".format(model.name(), PROXY_GRP)
    else:
        model = None
        name = "rig_{}".format(PROXY_GRP)

    # Check if the set already exists
    if pm.objExists(name):
        # The set already exists, get a reference to it
        pxy_set = pm.PyNode(name)
    else:
        # The set does not exist, create it
        pxy_set = pm.sets(empty=True, name=name)
        if model:
            groupIdx = attribute.get_next_available_index(model.rigGroups)
            pm.connectAttr(pxy_set.message, model.rigGroups[groupIdx])
            masterSet = model.rigGroups.listConnections()[0]
            masterSet.add(pxy_set)

    # Add the objects to the set
    for o in proxy_objs:
        pxy_set.add(o)


def collect_proxy_data(proxy):
    """Collect the data of a single proxy object.

    Args:
        proxy (pymel.core.PyNode): The proxy object.

    Returns:
        dict: The data of the proxy object, including its translation,
        rotation, scale, shape, length, side, and parent.
    """
    if proxy.hasAttr("isProxy"):
        data = {}
        data["t"] = proxy.translate.get().get()
        data["r"] = proxy.rotate.get().get()
        data["s"] = proxy.scale.get().get()
        data["shape"] = proxy.proxy_shape.get()
        data["length"] = proxy.length.get()
        data["side"] = proxy.side.get()
        data["parent"] = proxy.getParent().name()

        return data


def collect_config_data(proxies):
    """Collect the data of multiple proxy objects.

    Args:
        proxies (list[pymel.core.PyNode]): The list of proxy objects.

    Returns:
        dict: The data of the proxy objects, including their order and the
        data for each individual proxy.
    """
    config_data = {}
    config_data["proxy_order"] = []
    for p in proxies:
        data = collect_proxy_data(p)
        if data:
            p_name = p.name()
            config_data["proxy_order"].append(p_name)
            config_data[p_name] = data
    return config_data


def collect_selected_proxy_data():
    """Collect the data of the selected proxy objects.

    Returns:
        dict: The data of the selected proxy objects, including their order
        and the data for each individual proxy.
    """
    return collect_config_data(pm.selected())


def create_proxy(
    parent,
    side,
    length,
    m=datatypes.Matrix(),
    shape="capsule",
    replace=False,
    used_index=[],
):
    """Create a geo proxy for a given parent transform with specified dimensions and return the proxy node.

    Args:
        parent (pm.nodetypes.Transform): The parent transform to attach the rig proxy to.
        side (float): The size or radius of the rig proxy.
        length (float): The length of the rig proxy.
        m (pm.datatypes.Matrix, optional): The initial transformation matrix of the rig proxy. Defaults to pm.datatypes.Matrix().
        shape (str, optional): The shape of the rig proxy, either "capsule" or "box". Defaults to "capsule".
        replace (bool, optional): Whether to replace an existing proxy at the same index or create a new index. Defaults to False.
        used_index (list of int, optional): A list of existing proxy indices that are already in use. Defaults to [].

    Returns:
        pm.nodetypes.Transform: The newly created or updated rig proxy.

    """
    if parent.hasAttr("isProxy"):
        return
    index = 0

    while True:
        name = "{}_{:02d}_{}".format(parent.name(), index, PROXY_SUFFIX)
        if not pm.objExists(name):
            # Object does not exist, create it
            if shape == "capsule":
                proxy = create_capsule(name, side, length)
                proxy_shape = "capsule"
            else:
                proxy = create_box(name, side, length)
                proxy_shape = "box"
            pm.parent(proxy, parent)
            proxy.setMatrix(m, worldSpace=True)
            attribute.addAttribute(proxy, "isProxy", "bool", keyable=False)
            attribute.addAttribute(
                proxy, "proxy_shape", "string", value=proxy_shape
            )
            return proxy, index
        else:
            # Object exists, check if it is parented to the given parent
            existing_object = pm.PyNode(name)
            if existing_object.getParent() == parent:
                # Object is already parented to the given parent
                if replace and index not in used_index:
                    pm.delete(existing_object)
                    continue
                else:
                    index += 1
            else:
                # Object is not parented to the given parent, parent it
                pm.parent(existing_object, parent)
                return existing_object, index


def create_proxy_to_children(joints=None, side=None):
    """Create one proxy geo aiming to each child of the joint

    Args:
        joints (list, optional): list of joints
        side (float, optional): default side

    Returns:
        list: list of pyNode proxy gemetries
    """

    joints = get_list_or_selection(joints)
    proxies = []
    used_index = []

    for j in joints:
        children = [
            child for child in j.getChildren() if not child.hasAttr("isProxy")
        ]

        if children:
            pos = transform.getTranslation(j)
            blade = vector.Blade(j.getMatrix(worldSpace=True))
            normal = blade.z
            for child in children:
                lookat_ref = child
                lookat = transform.getTranslation(child)

                t = transform.getTransformLookingAt(
                    pos, lookat, normal, axis="xy"
                )

                mid_pos = vector.linearlyInterpolate(pos, lookat)
                t = transform.setMatrixPosition(t, mid_pos)
                length = vector.getDistance2(j, lookat_ref)
                if not side:
                    side = length * 0.3
                pxy, idx = create_proxy(
                    j, side, length, m=t, used_index=used_index
                )
                used_index.append(idx)
                if pxy:
                    proxies.append(pxy)
        else:
            pm.displayWarning("{}: has not children".format(j.name()))
    add_to_grp(proxies)
    return proxies


def create_proxy_to_next(joints=None, side=None, tip=True):
    """Create proxy geo aiming to the next joint position

    Args:
        joints (list, optional): list of joints
        side (float, optional): default side
        tip (bool, optional): if true will create the proxy for the tip joint

    Returns:
        list: list of pyNode proxy gemetries
    """
    proxies = []
    joints = get_list_or_selection(joints)
    nb_joints = len(joints)

    for i, j in enumerate(joints):
        pos = transform.getTranslation(j)
        blade = vector.Blade(j.getMatrix(worldSpace=True))
        normal = blade.z
        if i < nb_joints - 1:
            lookat_ref = joints[i + 1]
            lookat = transform.getTranslation(lookat_ref)

            t = transform.getTransformLookingAt(pos, lookat, normal, axis="xy")

            mid_pos = vector.linearlyInterpolate(pos, lookat)
            t = transform.setMatrixPosition(t, mid_pos)
            length = vector.getDistance2(j, lookat_ref)
            if not side:
                side = length * 0.3
            pxy, idx = create_proxy(j, side, length, m=t)
            if pxy:
                proxies.append(pxy)

        elif tip:
            # create the proxy for the tip joint
            if nb_joints >= 2:
                lookat_ref = joints[i - 1]
            elif j.getParent():
                lookat_ref = j.getParent()
            else:
                pm.displayWarning(
                    "Selected single joint without parent, can't build proxy."
                )
                return

            pos = j.getTranslation(space="world")
            lookat = lookat_ref.getTranslation(space="world")
            v = pos - lookat
            v2 = v + pos
            mid_pos = vector.linearlyInterpolate(pos, v2)

            t = transform.getTransformLookingAt(lookat, pos, normal, axis="xy")
            t = transform.setMatrixPosition(t, mid_pos)
            length = vector.getDistance2(j, lookat_ref)
            if not side:
                side = length * 0.3
            pxy, idx = create_proxy(j, side, length, m=t)
            if pxy:
                proxies.append(pxy)
    add_to_grp(proxies)
    return proxies


def create_proxy_centered(joints=None, side=None):
    """Create proxy geo centered in the joint position

    Args:
        joints (list, optional): list of joints
        side (float, optional): default side

    Returns:
        list: list of pyNode proxy gemetries
    """
    proxies = []
    joints = get_list_or_selection(joints)
    nb_joints = len(joints)

    if nb_joints == 1:
        # just create an center proxy using the joint side as reference
        if joints[0].type() == "joint":
            side = joints[0].radius.get()
        else:
            side = 1
        t = joints[0].getMatrix(worldSpace=True)
        pxy, idx = create_proxy(joints[0], side, 0.1, m=t)
        if pxy:
            proxies.append(pxy)

    elif nb_joints >= 2:
        for i, j in enumerate(joints):
            pos = transform.getTranslation(j)
            t = j.getMatrix(worldSpace=True)

            if i < nb_joints - 1:
                lookat_ref = joints[i + 1]
                lookat = transform.getTranslation(lookat_ref)

            if i == 0:
                mid_pos = vector.linearlyInterpolate(pos, lookat, blend=0.25)
                t = transform.setMatrixPosition(t, mid_pos)
                length = vector.getDistance2(j, lookat_ref) / 2
                if not side:
                    side = length * 0.3
            elif i == nb_joints - 1:
                lookat_back_ref = joints[i - 1]
                lookat_back = transform.getTranslation(lookat_back_ref)
                mid_pos = vector.linearlyInterpolate(
                    pos, lookat_back, blend=0.25
                )
                t = transform.setMatrixPosition(t, mid_pos)
                length = vector.getDistance2(j, lookat_back_ref) / 2
            else:
                lookat_back_ref = joints[i - 1]
                lookat_back = transform.getTranslation(lookat_back_ref)
                mid_pos_A = vector.linearlyInterpolate(pos, lookat)
                mid_pos_B = vector.linearlyInterpolate(pos, lookat_back)
                mid_pos = vector.linearlyInterpolate(mid_pos_A, mid_pos_B)
                t = transform.setMatrixPosition(t, mid_pos)
                length = vector.getDistance(lookat_back, lookat) / 2

            pxy, idx = create_proxy(j, side, length, m=t)
            if pxy:
                proxies.append(pxy)
    add_to_grp(proxies)
    return proxies


def combine_proxy_geo():
    # combines all the proxy geometry and the skinning
    # by defaul we just parent the proxy geos
    # this function will add the skinning and combine all
    return


def filter_out_proxy(objs):
    """Return a list of Maya nodes without the "isProxy" attribute.

    Args:
        objs (list of pm.nodetypes.Transform): A list of Maya nodes to filter.

    Returns:
        list of pm.nodetypes.Transform: A filtered list of Maya nodes without
        the "isProxy" attribute.

    """
    return [o for o in objs if not o.hasAttr("isProxy")]


def get_list_or_selection(joints=None):
    """Return a list of Maya joints based on user input or current selection.

    If `joints` is None, return the currently selected joints without the
        "isProxy" attribute.
    If `joints` is a string, treat it as the name of a single joint and return
        it without the "isProxy" attribute.
    If `joints` is a list of strings, treat each string as the name of a single
        joint and return them without the "isProxy" attribute.
    If `joints` is a list of Maya joint nodes, return them without the
        "isProxy" attribute.

    Args:
        joints (None, str, list of str, list of pm.nodetypes.Joint, optional):
            The input specifying which joints to return. Defaults to None.

    Returns:
        list of pm.nodetypes.Joint: A list of Maya joint nodes without the
            "isProxy" attribute.

    """
    if not joints:
        return filter_out_proxy(pm.selected())

    if isinstance(joints, str):
        joints = filter_out_proxy([pm.PyNode(joints)])
    if not isinstance(joints, list):
        joints = filter_out_proxy(list(joints))
    return joints
