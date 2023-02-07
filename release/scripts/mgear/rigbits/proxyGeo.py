import pymel.core as pm
from pymel.core import datatypes
from pymel.core import nodetypes


from mgear.core import attribute
from mgear.core import transform
from mgear.core import vector

PROXY_SUFFIX = "_proxy"


def create_capsule(name, radius, height, axis=[1, 0, 0]):
    args = {
        "subdivisionsX": 16,
        "subdivisionsY": 1,
        "subdivisionsZ": 4,
        "roundCap": True,
        "createUVs": 0,
        "constructionHistory": True,
        "name": name,
        "radius": radius,
        "height": height,
        "axis": axis,
    }
    trans, cap = pm.polyCylinder(**args)

    # hide build nodes from channelbox
    cap.isHistoricallyInteresting.set(False)
    trans.getShapes()[0].isHistoricallyInteresting.set(False)

    # add manipulation attrs
    r_att = attribute.addAttribute(
        trans,
        "radius",
        "float",
        value=radius,
        softMinValue=0.001,
        softMaxValue=100,
    )
    h_att = attribute.addAttribute(
        trans,
        "height",
        "float",
        value=height,
        softMinValue=0.001,
        softMaxValue=100,
    )

    # lock scale
    # attribute.lockAttribute(trans, attributes=["sx", "sy", "sz"])

    pm.connectAttr(r_att, cap.radius)
    pm.connectAttr(h_att, cap.height)

    return trans


def create_box():
    return


def add_meta_data():
    # adds meta data attrs in joint
    # str to store dic
    # tranlation array
    # rotation array
    # heigh
    # radius
    return


def create_proxy(
    parent, radius, height, m=datatypes.Matrix(), shape="capsule"
):
    name = parent.name() + PROXY_SUFFIX
    if shape == "capsule":
        proxy = create_capsule(name, radius, height)
    else:
        return
    pm.parent(proxy, parent)
    proxy.setMatrix(m, worldSpace=True)
    return proxy


def create_proxy_to_children(joints=None, radius=None):

    joints = get_list_or_selection(joints)
    proxies = []

    for j in joints:
        children = j.getChildren()
        if children:
            pos = transform.getTranslation(j)
            blade = vector.Blade(j.getMatrix(worldSpace=True))
            normal = blade.z
            for child in children:
                # child = children[0]
                lookat_ref = child
                lookat = transform.getTranslation(child)

                t = transform.getTransformLookingAt(
                    pos, lookat, normal, axis="xy"
                )

                mid_pos = vector.linearlyInterpolate(pos, lookat)
                t = transform.setMatrixPosition(t, mid_pos)
                length = vector.getDistance2(j, lookat_ref)
                if not radius:
                    radius = length * 0.3
                pxy = create_proxy(j, radius, length, m=t)
                proxies.append(pxy)
        else:
            pm.displayWarning("{}: has not children".format(j.name()))

    return proxies


def create_proxy_to_next(joints=None, radius=None):
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
            if not radius:
                radius = length * 0.3
            pxy = create_proxy(j, radius, length, m=t)
            proxies.append(pxy)

        else:
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
            if not radius:
                radius = length * 0.3
            pxy = create_proxy(j, radius, length, m=t)
            proxies.append(pxy)

    return proxies


def create_proxy_centered(joints=None, radius=None):
    proxies = []
    joints = get_list_or_selection(joints)
    nb_joints = len(joints)

    if nb_joints == 1:
        # just create an center proxy using the joint radius as reference
        radius = joints[0].radius.get()
        t = joints[0].getMatrix(worldSpace=True)
        pxy = create_proxy(joints[0], radius, 1, m=t)
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
                if not radius:
                    radius = length * 0.3
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

            # radius = length * 0.3
            pxy = create_proxy(j, radius, length, m=t)
            proxies.append(pxy)

    return proxies


def combine_proxy_geo():
    # combines all the proxy geometry and the skinning
    # by defaul we just parent the proxy geos
    # this function will add the skinning and combine all
    return


def get_list_or_selection(joints=None):
    if not joints:
        return pm.selected()
    if isinstance(joints, str):
        joints = [pm.PyNode(joints)]
    if not isinstance(joints, list):
        joints = list(joints)
    return joints
