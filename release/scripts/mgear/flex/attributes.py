
""" flex.attributes

A simple module listing all attributes classifications inside Maya or a
simplified verison of long attributes in maya

:module: flex.attributes
"""

BLENDSHAPE_TARGET = "{}.inputTarget[0].inputTargetGroup[{}].inputTargetItem"

COMPONENT_DISPLAY_ATTRIBUTES = ["displayColors",
                                "displayColorChannel",
                                "materialBlend"]

OBJECT_DISPLAY_ATTRIBUTES = ["visibility",
                             "template",
                             "lodVisibility",
                             "displayHWEnvironment",
                             "ignoreHwShader",
                             "hideOnPlayback"]

RENDER_STATS_ATTRIBUTES = ["castsShadows",
                           "receiveShadows",
                           "holdOut",
                           "motionBlur",
                           "primaryVisibility",
                           "smoothShading",
                           "visibleInReflections",
                           "visibleInRefractions",
                           "doubleSided",
                           "opposite",
                           "geometryAntialiasingOverride",
                           "antialiasingLevel",
                           "shadingSamplesOverride",
                           "shadingSamples",
                           "maxShadingSamples"]
