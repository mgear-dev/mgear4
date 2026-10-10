Viewport Menu
=============

The mGear Viewport Menu replaces Maya's right-click menu when an mGear control or a Shifter guide is selected. Turn it on or off with the **mGear Viewport Menu** checkbox in the mGear menu. The items it shows for animators are described in :doc:`quickStart`.

This page is for TDs and pipeline developers who want to add their own items to the menu, from a tool, a custom step, a ``userSetup.py`` or a Shifter component.

.. contents::
   :local:
   :depth: 2


How the menu is built
---------------------

On right-click, the menu goes through three steps:

1. **Context.** The first selected transform is tested against the registered contexts, from the highest priority to the lowest. The first context whose detector returns ``True`` builds the menu. If no context matches, Maya's default menu is shown.
2. **Prepare.** The context's optional ``prepare`` function runs. The built-in ``"control"`` context uses it to load the items of Shifter components.
3. **Sections.** The context's sections are built in ascending order. A section whose ``poll`` function returns ``False`` is skipped. A divider is added between sections automatically.

Built-in contexts:

========== ======== ==================================================
Context    Priority Detects
========== ======== ==================================================
control    100      mGear rig controls (``isCtl`` attribute)
guide      90       Shifter guide nodes (``rig_name`` or ``isGearGuide`` attribute)
========== ======== ==================================================

Built-in sections use orders in steps of 100, so the gaps are free for your own sections.

===== ======================= ===== =======================
Order Control section         Order Guide section
===== ======================= ===== =======================
100   select_host             100   settings
200   ikfk_switch             200   build
300   select_children         300   duplicate
400   reset                   400   guide_manager
500   mirror_flip             500   export
600   rotate_order            600   update
700   spaces                  700   xray
800   select_all_keyframe
900   xray
1000+ Shifter component items
===== ======================= ===== =======================


Adding a section
----------------

A section is a function that adds items to the menu. It receives a ``builder``, to add the items, and a ``ctx``, with the right-clicked node and its rig data.

.. code-block:: python

    from functools import partial

    from mgear.core import dagmenu


    def print_control(control):
        print(control)


    def build(builder, ctx):
        builder.item("Print Control", partial(print_control, ctx.node))


    dagmenu.register_section("control", "print_control", 650, build)

This adds **Print Control** between the Rotate Order switch (600) and the Parent spaces (700).

* Registering the same context and name again replaces the section, so reloading your tool doesn't duplicate items.
* ``dagmenu.unregister_section("control", "print_control")`` removes it. This also works on built-in sections, i.e. ``dagmenu.unregister_section("control", "xray")``.
* If a section raises an error, the error is logged and the rest of the menu is still built.

Use a ``poll`` function to show the section only for some controls:

.. code-block:: python

    dagmenu.register_section(
        "control",
        "space_tools",
        750,
        build_space_tools,
        poll=lambda ctx: bool(ctx.space_attrs),
    )


Menu commands
-------------

Bind the command arguments with ``functools.partial``. Commands are called without arguments; the check state that Maya sends to menu commands is dropped.

Keep the build function light: it runs on every right-click. Query heavy data in the command, when the item is clicked, not when the menu is built.


The builder
-----------

``builder.item(label, command=None, image=None, **kwargs)``
    Adds a menu item. Extra keyword arguments are passed to ``cmds.menuItem``, i.e. ``radioButton=True``.

``builder.divider()``
    Adds a divider before the next item. A menu never starts or ends with a divider, and never has two in a row.

``builder.submenu(label, image=None, radio=False)``
    Context manager that adds a submenu and gives its builder. With ``radio=True`` its items are grouped as radio buttons.

.. code-block:: python

    def build(builder, ctx):
        with builder.submenu("My Tools") as sub:
            sub.item("Tool A", partial(tool_a, ctx.node))
            sub.divider()
            sub.item("Tool B", partial(tool_b, ctx.node))


Icons
-----

``builder.item`` and ``builder.submenu`` take an ``image`` argument. It accepts the same values as the ``image`` flag of ``cmds.menuItem``: an icon file name found in Maya's icon paths, or the full path of an image file (``.png`` or ``.svg``).

.. code-block:: python

    def build(builder, ctx):
        # Maya icon
        builder.item(
            "Key Control",
            partial(cmds.setKeyframe, ctx.node),
            image="setKeyframe.png",
        )
        # mGear icon
        builder.item(
            "My Reset",
            partial(my_reset, ctx.node),
            image="mgear_refresh-cw.svg",
        )
        # custom icon, by full path
        builder.item(
            "My Tool",
            partial(my_tool, ctx.node),
            image="D:/studio/icons/my_tool.svg",
        )
        with builder.submenu("My Tools", image="mgear_list.svg") as sub:
            sub.item("Tool A", partial(tool_a, ctx.node))

Where to find icons:

* **Maya icons**: browse them in **Windows > General Editors > Resource Browser**, or list them with ``cmds.resourceManager(nameFilter="*key*")``. Use the name as shown, i.e. ``"setKeyframe.png"``.
* **mGear icons**: the files in the mGear ``icons`` folder, i.e. ``"mgear_x.svg"``, ``"mgear_sliders.svg"``. The mGear module adds this folder to Maya's icon paths.
* **Custom icons**: use the full file path, or add your icon folder to Maya's icon paths and use the file name only. Add the folder with an ``icons:`` line in your own Maya module file (``.mod``), or with the ``XBMLANGPATH`` environment variable in ``Maya.env``.

Prefer ``.svg`` icons, they stay sharp at any display scaling. An icon that can't be found shows no image, the item still works.


The context
-----------

``ctx`` gives the right-clicked node and the data the built-in sections use. Each value is queried the first time it's used and then cached for that right-click.

================== ==========================================================
Attribute          Value
================== ==========================================================
``node``           The right-clicked node (full path)
``selection``      The selected nodes
``ui_host``        The control holding the IK/FK and space switch attributes
``ikfk_attrs``     ``(attribute, suffix)`` IK/FK blend and switch attributes
``space_attrs``    ``(node, attribute)`` space switch enum attributes
``child_controls`` Controls below the selected controls, and the node
``all_controls``   All the controls of the rig
``rig_root``       The rig top node
``comp_type``      The Shifter component type of the control, i.e. ``arm_2jnt_01``
================== ==========================================================


Adding a context
----------------

Register a context to show an mGear menu on other kinds of nodes:

.. code-block:: python

    from maya import cmds

    from mgear.core import dagmenu


    def is_joint(ctx):
        return cmds.nodeType(ctx.node) == "joint"


    dagmenu.register_context("joint", is_joint, priority=10)
    dagmenu.register_section("joint", "joint_tools", 100, build_joint_tools)

``register_context`` also accepts a ``prepare`` function, called with the context before the sections are built, i.e. to register sections on demand.


Shifter component items
-----------------------

A Shifter component can add items for its own controls with a ``dagmenu.py`` file in its folder, next to its ``__init__.py``. This works for built-in components and for custom components found through ``MGEAR_SHIFTER_COMPONENT_PATH``.

.. code-block:: python

    # my_component_01/dagmenu.py
    from functools import partial


    def match_pose(control):
        print("match", control)


    def build(builder, ctx):
        builder.item("Match Pose", partial(match_pose, ctx.node))


    def register(registry):
        registry.register_section("match_pose", build)

* The file is imported the first time a control of that component type is right-clicked, and only once per session. The component ``__init__.py`` is not imported.
* ``registry.register_section(name, build, order=1000, poll=None)`` adds the section to the ``"control"`` context. It only shows for the controls of that component type, after the built-in sections.
* Use absolute imports in ``dagmenu.py``, it is not imported as part of the component package.
* Rigs built with mGear 5.4.0 or later store the component type on each control in the ``ctl_comp_type`` attribute. Older rigs find it from the guide data stored in the rig.


Where to register
-----------------

Register your sections once per Maya session, after mGear is loaded. For example, from a ``userSetup.py``:

.. code-block:: python

    from maya import cmds

    cmds.evalDeferred("import my_studio.dagmenu_items")

where ``my_studio/dagmenu_items.py`` calls ``dagmenu.register_section`` at import. The menu module itself is light to import: it doesn't load Shifter.


API reference
-------------

See :doc:`mgear/mgear.core.dagmenu`.
