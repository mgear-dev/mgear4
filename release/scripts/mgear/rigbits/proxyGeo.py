import pymel.core as pm


def add_meta_data():
    # adds meta data attrs in joint
    # str to store dic
    # tranlation array
    # rotation array
    # heigh
    # radius
    return


def create_capsule():
    a = pm.polyCylinder()
    pm.polyCylinder(a, q=True, axis=True)
    # add manipulation attrs
    # heigh
    # radius

    # lock scale


def create_box():
    return


def get_joint_childs(joint):
    # get current joint firs degree childs
    return


def combine_proxy_geo():
    # combines all the proxy geometry and the skinning
    # by defaul we just parent the proxy geos
    # this function will add the skinning and combine all
    return


def calculate_volume_to_next():
    # calculate volume position to  next joint
    return


def calculate_volume_to_previous_next():
    # calculate volume position between the previous and next joint t0
    # 50% distance to each part
    return
