import pymel.core as pm
from pymel.core import datatypes
from pymel.core import nodetypes


from mgear.core import attribute
from mgear.core import transform
from mgear.core import vector

PROXY_SUFFIX = "proxy"
PROXY_GRP = "proxy_grp"


def create_capsule(name, side, length, axis=[1, 0, 0]):
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
    return
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
    data = {}

    return


def add_meta_data(proxy):
    joint = proxy.getParent(proxy)
    # add proxy_data attr if doesn 't exist
    return


def get_proxy_name(parent, idx):
    name = "{}_{}_{}".format(parent.name(), str(idx).zfill(2), PROXY_SUFFIX)
    return name


def create_proxy(
    parent,
    side,
    length,
    m=datatypes.Matrix(),
    shape="capsule",
    replace=True,
    used_index=[],
):
    if parent.hasAttr("isProxy"):
        return
    index = 0

    while True:
        name = "{}_{:02d}_{}".format(parent.name(), index, PROXY_SUFFIX)
        if not pm.objExists(name):
            # Object does not exist, create it
            if shape == "capsule":
                proxy = create_capsule(name, side, length)
            else:
                proxy = create_box(name, side, length)
            pm.parent(proxy, parent)
            proxy.setMatrix(m, worldSpace=True)
            attribute.addAttribute(proxy, "isProxy", "bool", keyable=False)
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
    return [o for o in objs if not o.hasAttr("isProxy")]


def get_list_or_selection(joints=None):
    if not joints:
        return filter_out_proxy(pm.selected())

    if isinstance(joints, str):
        joints = filter_out_proxy([pm.PyNode(joints)])
    if not isinstance(joints, list):
        joints = filter_out_proxy(list(joints))
    return joints
