Shifter Component Development
=============================

This guide explains how to write your own Shifter components: the guide the
rigger places, the settings window, and the code that builds the rig. Each
section has snippets you can copy. The last part walks through
``eyelid_01``, a component that uses the newer features: an engine shared
with a tool, guide validation, and mesh data mirrored with the guide.

.. contents::
    :local:
    :depth: 2


What a component is
-------------------

A component is a Python package with two parts:

* **The guide** (``guide.py``): the locators, blades and curves the rigger
  places, and the settings stored on the guide root.
* **The build** (``__init__.py``): the code that reads the guide and creates
  the controls, operators and joints of that part of the rig.

Shifter finds components in:

* ``mgear/shifter_classic_components/`` (shipped with mGear);
* ``mgear/shifter_epic_components/`` (shipped with mGear);
* every folder listed in the ``MGEAR_SHIFTER_COMPONENT_PATH`` environment
  variable (your studio or project components).

A component folder holds:

==================  ========================================================
File                Purpose
==================  ========================================================
``__init__.py``     ``Component`` class: builds the rig. Required.
``guide.py``        ``Guide`` class: draws and reads the guide. Settings
                    window classes. Required.
``settingsUI.py``   Settings tab compiled from a Qt Designer ``.ui`` file.
                    Optional, the tab can also be built in code.
``icon.jpg``        Icon in the component list. Optional.
``dagmenu.py``      Right-click menu items for the component controls.
                    Optional, see `Right-click menu`_.
==================  ========================================================

The folder name is the component type, for example ``control_01``. Keep the
``_01`` version suffix: when a component changes in a way that breaks
existing guides, add ``_02`` instead of changing ``_01``.


A minimal component
-------------------

This component places one control and one joint between a root and a tip
locator. Save both files in a folder named ``simple_ctl_01`` inside a
folder of ``MGEAR_SHIFTER_COMPONENT_PATH``.

``guide.py``:

.. code-block:: python

    """Guide Simple Control 01 module"""

    from mgear.shifter.component import guide
    from mgear.core import transform
    from mgear.core import pyqt
    from mgear.vendor.Qt import QtCore

    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
    from maya.app.general.mayaMixin import MayaQDockWidget

    AUTHOR = "Your Name"
    URL = ""
    EMAIL = ""
    VERSION = [1, 0, 0]
    TYPE = "simple_ctl_01"
    NAME = "simple"
    DESCRIPTION = "One control between a root and a tip locator"


    class Guide(guide.ComponentGuide):
        """Component Guide Class"""

        compType = TYPE
        compName = NAME
        description = DESCRIPTION

        author = AUTHOR
        url = URL
        email = EMAIL
        version = VERSION

        def postInit(self):
            """Names of the guide transforms to save."""
            self.save_transform = ["root", "tip"]

        def addObjects(self):
            """Draw the guide."""
            self.root = self.addRoot()
            position = transform.getOffsetPosition(self.root, [0, 1, 0])
            self.tip = self.addLoc("tip", self.root, position)
            self.dispcrv = self.addDispCurve("crv", [self.root, self.tip])

        def addParameters(self):
            """Settings stored on the guide root."""
            self.pCtlSize = self.addParam("ctlSize", "double", 1.0, 0.01, None)
            self.pUseIndex = self.addParam("useIndex", "bool", False)
            self.pParentJointIndex = self.addParam(
                "parentJointIndex", "long", -1, None, None
            )


    class componentSettings(MayaQWidgetDockableMixin, guide.componentMainSettings):
        """Settings window, with only the common tabs."""

        def __init__(self, parent=None):
            self.toolName = TYPE
            pyqt.deleteInstances(self, MayaQDockWidget)
            super(componentSettings, self).__init__(parent=parent)
            self.setup_componentSettingWindow()
            self.create_componentControls()
            self.populate_componentControls()
            self.create_componentLayout()
            self.create_componentConnections()

        def setup_componentSettingWindow(self):
            self.mayaMainWindow = pyqt.maya_main_window()
            self.setObjectName(self.toolName)
            self.setWindowFlags(QtCore.Qt.Window)
            self.setWindowTitle(TYPE)
            self.resize(280, 350)

        def create_componentControls(self):
            return

        def populate_componentControls(self):
            return

        def create_componentLayout(self):
            from mgear.vendor.Qt import QtWidgets

            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(self.tabs)
            layout.addWidget(self.close_button)
            self.setLayout(layout)

        def create_componentConnections(self):
            return

        def dockCloseEventTriggered(self):
            pyqt.deleteInstances(self, MayaQDockWidget)

``__init__.py``:

.. code-block:: python

    """Component Simple Control 01 module"""

    from mgear.shifter import component
    from mgear.core import attribute
    from mgear.core import primitive
    from mgear.core import transform


    class Component(component.Main):
        """Shifter component Class"""

        def addObjects(self):
            """Create the objects of the component."""
            t = transform.getTransformLookingAt(
                self.guide.pos["root"],
                self.guide.pos["tip"],
                self.y_axis,
                "yx",
                self.negate,
            )
            self.npo = primitive.addTransform(self.root, self.getName("npo"), t)
            self.ctl = self.addCtl(
                self.npo,
                "ctl",
                t,
                self.color_fk,
                "cube",
                w=self.settings["ctlSize"] * self.size,
                h=self.settings["ctlSize"] * self.size,
                d=self.settings["ctlSize"] * self.size,
                tp=self.parentCtlTag,
            )
            attribute.setKeyableAttributes(self.ctl, self.tr_params)
            self.jnt_pos.append(
                {"obj": self.ctl, "name": "0", "newActiveJnt": "parent_relative_jnt"}
            )

        def setRelation(self):
            """Rig objects children components attach to."""
            self.relatives["root"] = self.ctl
            self.relatives["tip"] = self.ctl
            self.controlRelatives["root"] = self.ctl
            self.controlRelatives["tip"] = self.ctl
            self.jointRelatives["root"] = 0
            self.jointRelatives["tip"] = 0

Open the Shifter guide manager. The component is listed with the others; draw
it, place the locators and build.


The guide (``guide.py``)
------------------------

Guide class attributes
^^^^^^^^^^^^^^^^^^^^^^

==================  ========================================================
Attribute           Meaning
==================  ========================================================
``compType``        Component type, the folder name.
``compName``        Default component name, e.g. ``arm`` for ``arm_L0``.
``description``     Shown in the component list.
``connectors``      Extra connector names, see `Connectors`_.
``compatible``      Other component types the guide can be swapped with.
==================  ========================================================

Guide objects
^^^^^^^^^^^^^

``postInit`` declares what the guide saves. ``addObjects`` draws it. The
names in ``save_transform`` must match the names you draw.

.. code-block:: python

    def postInit(self):
        self.save_transform = ["root", "#_loc"]
        self.save_blade = ["blade"]
        # between 1 and unlimited "#_loc" locators
        self.addMinMax("#_loc", 1, -1)

    def addObjects(self):
        self.root = self.addRoot()
        self.locs = self.addLocMulti("#_loc", self.root)
        self.blade = self.addBlade("blade", self.root, self.locs[0])
        centers = [self.root] + self.locs
        self.dispcrv = self.addDispCurve("crv", centers)

============================================  =================================
Method                                        Draws
============================================  =================================
``addRoot()``                                 The component root. Every
                                              setting is written on it as an
                                              attribute.
``addLoc(name, parent, position)``            A locator.
``addLocMulti("#_loc", parent)``              A chain of numbered locators.
                                              With ``addMinMax``, the guide
                                              asks how many when drawn.
``addBlade(name, parentPos, parentDir)``      A blade: an orientation, with
                                              roll offset and scale.
``addDispCurve(name, centers, degree=1)``     A display curve, for the eye
                                              only. It isn't read back.
============================================  =================================

``postDraw`` runs after the guide is drawn, for extra display only.

Guide settings
^^^^^^^^^^^^^^

``addParameters`` declares the settings. Each one becomes an attribute on the
guide root, saved with the guide and readable in the build as
``self.settings[name]``.

.. code-block:: python

    def addParameters(self):
        self.pMode = self.addEnumParam("mode", ["FK", "IK"], 0)
        self.pDivisions = self.addParam("divisions", "long", 4, 1, 64)
        self.pBlend = self.addParam("blend", "double", 0.5, 0, 1)
        self.pMesh = self.addParam("mesh", "string", "")
        self.pIkRefArray = self.addParam("ikrefarray", "string", "")
        self.pUseIndex = self.addParam("useIndex", "bool", False)
        self.pParentJointIndex = self.addParam(
            "parentJointIndex", "long", -1, None, None
        )

* Types are ``"bool"``, ``"long"``, ``"double"`` and ``"string"``; enums use
  ``addEnumParam`` and store the index.
* ``useIndex`` and ``parentJointIndex`` are read by the joint step of every
  component (they choose the parent component joint by index). Declare them.
* A comma separated guide name list (like ``ikrefarray``) is the usual way
  to reference other guide elements, for example spaces.

.. note::
    Adding a setting to an existing component makes guides saved before it
    "not up to date" until they are updated. Prefer a new component version
    for big changes.

Reading the guide in the build
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

=========================  ===================================================
In the component           Holds
=========================  ===================================================
``self.guide.pos[name]``   World position of a guide transform (Vector).
``self.guide.tra[name]``   World matrix of a guide transform.
``self.guide.apos``        Positions of the ``#`` locators, in order.
``self.guide.atra``        Matrices of the ``#`` locators.
``self.guide.blades``      Blades by name, with ``.x``, ``.y``, ``.z`` axes.
``self.settings``          Setting values, by name.
=========================  ===================================================

Mirroring the guide
^^^^^^^^^^^^^^^^^^^

*Duplicate Symmetrical* calls ``symmetrize()`` on the copy. The base class
mirrors every transform and blade, and renames L/R in string settings. If a
setting holds data that must be mirrored another way, override it. The
eyelid mirrors mesh vertex indices:

.. code-block:: python

    def symmetrize(self):
        if not super(Guide, self).symmetrize():
            return False  # center components don't mirror
        value = self.values["vertexLoop"]
        if value:
            mirrored, missing = meshNavigation.mirror_component_string(value)
            if missing:
                mgear.log(
                    "{}: no mirror for {}".format(self.fullName, missing),
                    mgear.sev_warning,
                )
            else:
                self.setParamDefValue("vertexLoop", mirrored)
        return True

Validating the guide
^^^^^^^^^^^^^^^^^^^^

A component that needs data the guide only references (a mesh, a vertex
loop, another node) can check it before anything is built. Override
``validate()`` and return the problems as messages:

.. code-block:: python

    def validate(self):
        """Check the component can build.

        Returns:
            list: Problem messages, empty when the component can build.
        """
        problems = []
        mesh = self.values["mesh"]
        if not mesh:
            problems.append("Set the mesh in the component settings")
        elif not cmds.objExists(mesh):
            problems.append("The mesh {} doesn't exist".format(mesh))
        return problems

How the build uses it:

* It runs at the start of the build, after the pre custom steps, so data a
  pre step imports (geometry, for example) already exists. It runs for
  builds from the scene guide and from template files.
* With the guide option **Stop build on validation fail** on (default), each
  problem is logged as an error, named after the component, and the build
  stops before creating anything.
* With the option off, problems are logged as warnings, those components are
  skipped and the rest of the rig is built.

Write messages the rigger can act on: what's wrong and where to fix it. No
tracebacks: keep ``raise`` for real bugs.

``validate()`` is also a good place to compute data the build needs, and
keep it on the guide, so the build doesn't do the work twice. Initialize the
member in ``postInit``:

.. code-block:: python

    def postInit(self):
        self.save_transform = ["root", "aim"]
        self.geometry = None  # set by validate, read by the build

The settings window
-------------------

The settings window class is ``componentSettings`` in ``guide.py``. The base
class (``guide.componentMainSettings``) gives the common tabs (name, side,
index, connector, joints, colors). Add your own tab in
``populate_componentControls``.

Each widget writes its value to the guide root attribute. The base class has
helpers for the usual widgets:

=========================================  ==================================
Helper                                     Use
=========================================  ==================================
``populateCheck(widget, attr)``            Set a check box from the guide.
``updateCheck(widget, attr)``              Check box changed.
``updateSpinBox(widget, attr)``            Spin box changed.
``updateComboBox(widget, attr)``           Combo box changed (enum index).
``updateLineEdit(widget, attr)``           Line edit changed (cleans the
                                           text to a valid name).
``addItem2listWidget(widget, attr)``       Add the selected guides to a
                                           name list setting.
``removeSelectedFromListWidget(...)``      Remove from a name list setting.
=========================================  ==================================

.. code-block:: python

    def populate_componentControls(self):
        self.tabs.insertTab(1, self.settingsTab, "Component Settings")
        self.settingsTab.divisions_spinBox.setValue(
            self.root.attr("divisions").get()
        )

    def create_componentConnections(self):
        self.settingsTab.divisions_spinBox.valueChanged.connect(
            partial(
                self.updateSpinBox,
                self.settingsTab.divisions_spinBox,
                "divisions",
            )
        )

A tab from a settings list
^^^^^^^^^^^^^^^^^^^^^^^^^^

For components with many settings, describe them once with
``mgear.core.settings_schema`` and let ``mgear.core.settings_form`` build the
tab. The same list can define the guide parameters, so they never drift
apart. This is how ``eyelid_01`` does it:

.. code-block:: python

    from mgear.core import settings_form
    from mgear.core.settings_schema import Param

    SCHEMA = [
        Param("mesh", "string", "", label="Mesh", kind="mesh",
              tooltip="Mesh the component reads"),
        Param("divisions", "long", 4, minimum=1, maximum=64,
              label="Divisions", tooltip="Number of controls"),
        Param("doSkin", "bool", False, label="Autoskin",
              tooltip="Skin the joints at the end of the build"),
    ]

    class Guide(guide.ComponentGuide):
        def addParameters(self):
            for param in SCHEMA:
                self.addParam(param.key, param.value_type, param.default,
                              param.minimum, param.maximum)

    class componentSettings(...):
        def populate_componentControls(self):
            self.form = settings_form.SettingsForm(SCHEMA)
            self.tabs.insertTab(1, self.form, "Component Settings")
            self.form.set_settings(
                {param.key: self.root.attr(param.key).get() for param in SCHEMA}
            )

        def create_componentConnections(self):
            self.form.valueChanged.connect(
                lambda key, value: self.root.attr(key).set(value)
            )

String settings with a ``kind`` (``mesh``, ``node``, ``set``, ``edges``,
``vertices``, ``vertex``) get a "<<" button that fills them from the
selection. ``set_visibility_rule(rule, keys)`` shows and hides rows from
other settings.

The build (``__init__.py``)
---------------------------

The ``Component`` class derives from ``mgear.shifter.component.Main``. The
rig builds every component step by step: all components run step 1, then all
run step 2, and so on. So a component can use, in a later step, what its
parent created in an earlier one.

======  ============  =========================================================
Step    Name          Methods you override
======  ============  =========================================================
00      Objects       ``addObjects`` (transforms, controls, joint list),
                      ``setRelation``
01      Properties    ``addAttributes`` (animation and setup attributes)
02      Operators     ``addOperators`` (constraints, solvers, node networks)
03      Connect       ``addConnection`` (extra connectors), the connector
                      method, ``postConnect``
04      Joints        Usually nothing: the joints listed in ``jnt_pos`` are
                      created
05      Finalize      ``finalize`` (call ``super`` first)
======  ============  =========================================================

Useful members
^^^^^^^^^^^^^^

=============================  ================================================
Member                         Holds
=============================  ================================================
``self.settings``              Guide setting values.
``self.options``               Rig (guide) options, e.g. ``joint_rig``.
``self.size``                  Guide size, multiply control shapes by it.
``self.color_fk / color_ik``   Component colors (index or RGB).
``self.side``                  ``"L"``, ``"R"`` or ``"C"``.
``self.negate``                True on the right side.
``self.n_factor``              -1 on the right side, else 1.
``self.root``                  Component root transform.
``self.parentCtlTag``          Controller tag parent of the first control.
``self.getName(name)``         Full node name, e.g. ``arm_L0_fk0_npo``.
``self.t_params`` and co.      Channel lists for ``setKeyableAttributes``:
                               ``t_params``, ``r_params``, ``s_params``,
                               ``tr_params``, ``rs_params``,
                               ``local_params``.
=============================  ================================================

Controls
^^^^^^^^

Create controls with ``self.addCtl``. It names them with the rig naming rule,
reuses the shape the rigger stored on the guide, sets the color, the
controller tag, the mirror configuration and the control group.

.. code-block:: python

    self.fk_ctl = self.addCtl(
        self.fk_npo,            # parent
        "fk0_ctl",              # description, "_ctl" is added by the rule
        t,                      # world matrix
        self.color_fk,
        "cube",                 # default shape
        w=self.size, h=self.size, d=self.size,
        tp=self.parentCtlTag,   # controller tag parent
        mirrorConf=[0, 0, 0, 0, 1, 1, 0, 0, 0],  # invert ry, rz on mirror
        guide_loc_ref="root",   # guide element this control matches
    )
    attribute.setKeyableAttributes(self.fk_ctl, self.tr_params)

Name all other nodes with ``self.getName("description")``, so they follow
the component name, side and index.

Attributes
^^^^^^^^^^

.. code-block:: python

    def addAttributes(self):
        # on the UI host, for animators
        self.blend_att = self.addAnimParam(
            "blend", "Fk/Ik Blend", "double", 0, 0, 1
        )
        self.ref_att = self.addAnimEnumParam(
            "ikref", "Ik Ref", 0, ["world", "body"]
        )
        # on the setup root, for riggers
        self.roll_att = self.addSetupParam(
            "roll", "Roll", "double", 0, -180, 180
        )

Animation attributes go on the component UI host: the guide element set in
the ``ui_host`` setting, or the global control when it's empty. Their name
starts with the component name, for example ``arm_L0_blend``, so components
sharing a host don't clash (``exactName=True`` keeps the name as given).

Operators
^^^^^^^^^

``addOperators`` connects what ``addObjects`` created: constraints,
``mgear.core.applyop`` solvers, node networks. Don't create rig transforms
here, so the hierarchy is complete before the operators run.

Joints
^^^^^^

List the joints in ``addObjects`` with ``self.jnt_pos``. The joint step
creates them, in order, each driven by its object. Add each joint as a dict
of the ``addJoint`` keyword arguments:

.. code-block:: python

    self.jnt_pos.append(
        {
            "obj": self.fk_ctl,
            "name": "fk0",
            "newActiveJnt": "parent_relative_jnt",
            "UniScale": False,
            "leaf_joint": self.settings["leafJoints"],
            "guide_relative": "root",
        }
    )

Arguments:

=====================  =======================================================
Key                    Meaning
=====================  =======================================================
``obj``                Driver transform: the joint follows it (matrix
                       constraint). A ``Matrix`` instead places a joint that
                       isn't driven.
``name``               Description, solved with the rig joint naming rule,
                       e.g. ``"fk0"`` gives ``arm_L0_fk0_jnt``. Custom joint
                       names set in the guide win.
``newActiveJnt``       Parent joint, one of:
                       ``"parent_relative_jnt"`` (the joint of the parent
                       component under the guide parent locator),
                       ``"component_jnt_org"`` (the rig joint group),
                       an int (the joint at that index of this component),
                       a ``jointRelatives`` name (that joint of this
                       component), a joint node, or ``None`` (default: the
                       previous joint, to make chains).
``UniScale``           Uniform scale: the three scale axes follow the
                       driver Z scale. The ``force_uniScale`` rig option
                       turns it on for all joints. Default False.
``segComp``            Segment scale compensate on the joint. The
                       ``force_SSC`` rig option turns it on for all joints.
                       Default False.
``rot_off``            ``[x, y, z]`` rotation offset in degrees. Defaults to
                       the component *Joint Rotation Offset* settings.
``neutral_rot``        True (default): the rotation goes in the joint orient
                       and the rotate channels are zero at rest. False: the
                       rotation goes in the rotate channels.
``leaf_joint``         Adds a ``leaf_<joint>`` child joint that takes the
                       scale (and shear), so the joint itself keeps a clean
                       scale; meant for game engines. Ignored with
                       ``UniScale``.
``guide_relative``     Guide element the joint comes from, stored on the
                       joint (``guide_relative`` attribute) for guide tools.
``preBind_relative``   Node connected to the joint by message
                       (``preBind_relative``), to use as skin prebind
                       reference.
``data_contracts``     String stored on the joint (``data_contracts``
                       attribute), for pipeline metadata.
``vanilla_nodes``      True: drive the joint with Maya nodes instead of the
                       mGear matrix constraint. Kept for old rigs.
``gearMulMatrix``      With ``vanilla_nodes``: use the mGear multiply matrix
                       node instead of Maya's.
=====================  =======================================================

* The joints are in ``self.jointList`` after the joint step, in the
  ``jnt_pos`` order.
* When the rig builds with **joints off** (``options["joint_rig"]``), Shifter
  makes the joints under their drivers. Only set ``newActiveJnt`` when joints
  are on.
* With the *Connect to existing joints* rig option, a joint with the same
  name that already exists in the scene is reused.

.. note::
    Older components add joints as lists: ``[obj, name, newActiveJnt,
    UniScale, gearMulMatrix]``. The list form is kept for compatibility with
    existing components; use the dict form in new code.

Relations
^^^^^^^^^

``setRelation`` tells child components what to attach to. The keys are the
guide element names a child guide can be parented under.

=====================  =======================================================
Dict                   Meaning
=====================  =======================================================
``relatives``          Rig transform a child component is parented to.
``controlRelatives``   Control used as controller tag parent for children.
``jointRelatives``     Index in ``jointList`` of the joint children use as
                       parent joint.
``aliasRelatives``     Readable names for spaces (``ikref`` lists).
=====================  =======================================================

Connectors
^^^^^^^^^^

The connector is how the component root attaches to its parent. ``standard``
parents the root under the parent relative. Add your own in
``addConnection``:

.. code-block:: python

    def addConnection(self):
        self.connections["orient_parent"] = self.connect_orient_parent

    def connect_orient_parent(self):
        # step 03: self.parent (rig transform) and self.parent_comp
        # (parent component) are set
        self.parent.addChild(self.root)
        pm.orientConstraint(self.parent, self.root, maintainOffset=True)

Then list it in the guide: ``connectors = ["orient_parent"]``.

Built-in connections you can reuse: ``connect_standard``,
``connect_standardWithSimpleIkRef``, ``connect_orientCns``,
``connect_positionCns``, ``connect_pointCns``, ``connectRef`` (spaces).

.. tip::
    Name a connector after a component type, for example ``eye_01``: when the
    guide is drawn under that component, the connector is picked
    automatically.

``postConnect`` runs after every component of the step is connected, for
work that needs the final parenting (for example following a parent
component control).

Subclassing a component
-----------------------

A component can extend another one: same guide and build, plus your
changes. Import the base component with ``importComponent`` and
``importComponentGuide``. They find a component type wherever it is
installed (mGear or ``MGEAR_SHIFTER_COMPONENT_PATH``), so the base can be a
studio component too.

``guide.py`` of ``control_ext_01``, a ``control_01`` with an extra setting:

.. code-block:: python

    from mgear.shifter import importComponentGuide

    base = importComponentGuide("control_01")

    AUTHOR = "Your Name"
    URL = ""
    EMAIL = ""
    VERSION = [1, 0, 0]
    TYPE = "control_ext_01"
    NAME = "ctlExt"
    DESCRIPTION = "control_01 with an extra animation attribute"


    class Guide(base.Guide):
        """Component Guide Class"""

        compType = TYPE
        compName = NAME
        description = DESCRIPTION

        author = AUTHOR
        url = URL
        email = EMAIL
        version = VERSION

        def addParameters(self):
            """The control_01 settings, plus ours."""
            super(Guide, self).addParameters()
            self.pExtra = self.addParam("addExtra", "bool", True)


    class componentSettings(base.componentSettings):
        """The control_01 settings window, for this component type."""

        def __init__(self, parent=None):
            super(componentSettings, self).__init__(parent)
            self.toolName = TYPE
            self.setObjectName(TYPE)
            self.setWindowTitle(TYPE)

``__init__.py``:

.. code-block:: python

    from mgear.shifter import importComponent

    base = importComponent("control_01")


    class Component(base.Component):
        """control_01 with an extra animation attribute."""

        def addAttributes(self):
            """The control_01 attributes, plus ours."""
            super(Component, self).addAttributes()
            if self.settings["addExtra"]:
                self.extra_att = self.addAnimParam(
                    "extra", "Extra", "double", 0, 0, 1
                )

Things to know:

* Set ``compType`` and the other guide class attributes again: they are the
  identity of the new component.
* Call ``super`` in the methods you override, unless you replace the base
  behavior on purpose.
* New settings appear on the guide; to edit them in the settings window, add
  your own tab (see `The settings window`_).
* A subclass depends on the base component's code. When the base changes
  version (``control_02``), the subclass keeps using the version it imports.

Rules of thumb
--------------

* Create nodes in ``addObjects``, connect them in ``addOperators``.
* Name everything with ``addCtl`` or ``getName``; never hard-code names.
* Scale control shapes with ``self.size``.
* For mirrored behavior, build the right side from mirrored matrices
  (``transform.getSymmetricalTransform``) and keep ``mirrorConf`` at zeros;
  for controls that don't mirror, set the inverted channels in
  ``mirrorConf``.
* Check missing data in ``Guide.validate``, not by raising in the build.
* Never open UI during a build: builds also run in mayapy. Use
  ``pyqt.can_show_ui()`` if a component must decide.
* Put reusable logic in ``mgear.core``, not in the component, so tools and
  other components can use it. See the eyelid case below.


Right-click menu
----------------

A ``dagmenu.py`` file next to ``__init__.py`` adds items to the viewport
right-click menu of the component controls:

.. code-block:: python

    from functools import partial

    from maya import cmds


    def reset_offsets(nodes):
        for node in nodes:
            cmds.setAttr(node + ".offset", 0)


    def build(builder, ctx):
        builder.item("Reset Offsets", partial(reset_offsets, ctx.selection))


    def register(registry):
        registry.register_section("reset_offsets", build)

The file is imported the first time a control of the component is
right-clicked, and its items only show for that component's controls.


Case study: ``eyelid_01``
-------------------------

``eyelid_01`` builds the Eye Rigger 3.0 eyelid rig. It shows how to share a
rig between a standalone tool and a component, and how a component can rely
on data the guide only points to (a mesh loop).

Shared engine
^^^^^^^^^^^^^

The rig lives in ``mgear.core.facial``, not in the component:

* ``eyelid_schema``: the settings list (keys, defaults, tooltips, file IO).
* ``eyelid_solver.solve(settings, eye_center, aim, side)``: reads the mesh
  loop and returns the geometry (ordered lids, corners, frames). It creates
  nothing.
* ``EyelidBuilder``: creates the rig in phases, through a *backend* that
  creates controls, names and joints.

The Eye Rigger tool passes a ``ToolBackend`` (its own naming, sets and
joints). The component passes ``mgear.shifter.component.facial_backend.
ComponentBackend``, which maps the same calls to ``getName``, ``addCtl`` and
``jnt_pos``. The builder phases run in the Shifter steps:

.. code-block:: python

    class Component(component.Main):
        def addObjects(self):
            self.follow_eye = self._uses_eye_connector()
            settings = guide.eyelid_settings(self.settings, self.follow_eye)
            geometry = self.guide.geometry  # solved by Guide.validate
            self.backend = ComponentBackend(self)
            self.builder = EyelidBuilder(settings, geometry, self.backend)
            self.builder.build_objects()

        def addAttributes(self):
            self.builder.build_attributes()

        def addOperators(self):
            self.builder.build_operators()

        def postConnect(self):
            source = (
                self.parent_comp.relatives["root"]
                if self.follow_eye
                else self.builder.aim_ctl
            )
            self.builder.connect_tracking(source, add_center_joint=not self.follow_eye)

        def finalize(self):
            super(Component, self).finalize()
            if self.options["joint_rig"] and self.options.get(
                "autoskin", True
            ):
                self.builder.build_skin()

A component autoskin is a starting point: the final skin is usually exported
and imported again by a custom step. The guide option **Autoskin**
(``autoskin``, on by default) turns every component autoskin off at once,
whatever its type. Components with an autoskin check it with ``options.get``, so guides
saved before the option keep skinning.

Guide locators instead of settings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The guide has a root (eye center) and an ``aim`` locator. Instead of
settings, they give the eye center, the eye direction and the distance of
the controls in front of the lid. The component side gives the side. Tilted
and side facing eyes need no extra setting, and *Duplicate Symmetrical*
mirrors the locators for free.

Mesh data in the guide
^^^^^^^^^^^^^^^^^^^^^^

The eyelid loop is a component string setting, for example
``"head.vtx[120:139]"``:

* the settings tab fills it from the selected vertices;
* ``symmetrize`` mirrors the indices on the mesh;
* ``validate`` solves the eyelid, so a missing loop or mesh is reported
  before the build, and keeps the geometry for the build.

The mesh must exist when the rig builds: import it in a pre custom step.

Eye connector
^^^^^^^^^^^^^

The connectors ``eye_01`` and ``MCS_eye_01`` are named after the eye
components, so they are picked when the eyelid guide is drawn under an eye.
The connector parents the eyelids under the eye's ``look`` relative (it
doesn't spin with the aim) and ``postConnect`` follows the eye's ``root``
relative (the aimed control).


Testing components
------------------

New components ship with tests. They run in ``mayapy`` with pytest (see the
``tests`` folder of the mGear repository):

.. code-block:: bash

    mayapy -m pytest tests/test_mgear/test_shifter -v

A component test draws a guide, builds it and checks the result:

.. code-block:: python

    def test_build(rig_plugins, setup_path):
        from maya import cmds

        import mgear.pymaya as pm
        from mgear import shifter
        from mgear.shifter import guide

        cmds.file(new=True, force=True)
        guide.Rig().drawNewComponent(None, "simple_ctl_01", showUI=False)
        root = pm.PyNode("simple_C0_root")
        # side and index
        guide.Rig().updateProperties(root, "simple", "L", 0)
        cmds.setAttr("simple_L0_root.ctlSize", 2.0)

        cmds.select("guide")
        shifter.Rig().buildFromSelection()

        assert cmds.objExists("simple_L0_ctl")
        assert cmds.objExists("simple_L0_0_jnt")

Fixtures from ``tests/conftest.py``:

* ``rig_plugins`` loads the mGear solvers, or skips the test.
* ``count_calls(owner, name, record)`` records calls, for example the build
  log: ``count_calls(mgear, "log", lambda args, kwargs: args[0])``.
* ``eye_face`` gives a symmetric face mesh with eyelid loops, used by the
  eyelid tests.

Things to know:

* ``drawNewComponent(None, ...)`` with nothing selected starts a **new**
  guide. To add a second component to the same guide, pass the ``guide``
  node, or a guide locator, as the parent.
* The guide root and the rig root have the same name; use long names to
  tell them apart.
* *Duplicate Symmetrical* in a test: ``guide.Rig().duplicate(root, True)``.
* The settings window can't be shown in mayapy, but it can be created and
  driven: select the guide root, create ``componentSettings()`` and set its
  widgets.
* A Shifter build in a mayapy script needs a GUI ``QApplication`` created
  before ``maya.standalone.initialize()``.


Checklist
---------

* ``guide.py``: ``Guide`` with ``postInit``, ``addObjects``,
  ``addParameters`` (with ``useIndex`` and ``parentJointIndex``) and a
  ``componentSettings`` window.
* ``__init__.py``: ``Component`` with ``addObjects`` (controls through
  ``addCtl``, joints in ``jnt_pos`` as dicts), ``setRelation`` for every
  saved transform, and operators in ``addOperators``.
* ``validate()`` for any data the guide only references.
* ``symmetrize()`` if a setting must mirror in a special way.
* Tests that build the component and check values, not only that nodes
  exist.
