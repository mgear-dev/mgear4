"""mGear right-click dag menu.

Overrides Maya's viewport right-click menu for mGear controls and guides.
The menu is built from sections registered per context, so other tools can
add their own items::

    from functools import partial

    from mgear.core import dagmenu

    def build_my_tool(builder, ctx):
        builder.item("My Tool", partial(my_tool.run, ctx.node))

    dagmenu.register_section(
        "control", "my_tool", 650, build_my_tool,
        poll=lambda ctx: bool(ctx.space_attrs),
    )

Built-in sections use orders 100, 200, ..., 900, so the gaps are free for
other tools. Shifter components can add items for their own controls with a
``dagmenu.py`` file, see mgear.core.dagmenu.components.
"""

from functools import partial

from maya import cmds
from maya import mel

import mgear

from .builder import MenuBuilder
from .context import MenuContext
from .registry import Registry
from .sections import register_builtin_sections

OPTION_VAR = "mgear_dag_menu_OV"

REGISTRY = Registry()
register_builtin_sections(REGISTRY)


# =============================================================================
# public registration API
# =============================================================================


def register_context(name, detector, priority=0, prepare=None):
    """Register a kind of right-clicked node.

    On right-click, contexts are tested from the highest priority to the
    lowest and the first matching one builds the menu. When none matches,
    Maya's default menu is shown. The built-in contexts are "control"
    (priority 100) and "guide" (priority 90).

    Args:
        name (str): Context name.
        detector (callable): Called with a MenuContext, returns True when
            the right-clicked node belongs to this context.
        priority (int, optional): Test priority, highest first.
        prepare (callable, optional): Called with the MenuContext before the
            sections are built. i.e: to register sections on demand.

    Returns:
        Context: The registered context.
    """
    return REGISTRY.register_context(name, detector, priority, prepare)


def register_section(context, name, order, build, poll=None):
    """Register a group of menu items.

    Registering the same context and name again replaces the section.

    Args:
        context (str): Context showing the section. i.e: "control"
        name (str): Section name, unique in its context.
        order (int): Build order, lower first. Built-in sections use 100,
            200, ..., 900.
        build (callable): Called with a MenuBuilder and a MenuContext, adds
            the items.
        poll (callable, optional): Called with a MenuContext, the section is
            skipped when it returns False.

    Returns:
        Section: The registered section.
    """
    return REGISTRY.register_section(context, name, order, build, poll)


def unregister_section(context, name):
    """Remove a section.

    Args:
        context (str): Context name.
        name (str): Section name.
    """
    REGISTRY.unregister_section(context, name)


def build_menu(parent_menu, node, context=None):
    """Fill a menu with the sections of the node context.

    Args:
        parent_menu (str): Menu to fill.
        node (str): The right-clicked node.
        context (str, optional): Context to build. Defaults to the first
            registered context matching the node.

    Returns:
        str: The built context name, None when no context matches.
    """
    ctx = MenuContext(node)
    if context is None:
        context = REGISTRY.detect(ctx)
        if context is None:
            return None
    REGISTRY.build(MenuBuilder(parent_menu), ctx, context)
    return context


# =============================================================================
# Maya dag menu override
# =============================================================================


def get_option_var_state():
    """Gets dag menu option variable

    Maya's optionVar command installs a variable that is kept on Maya's
    settings so that you can use it on future sessions.

    Maya's optionVar are a quick and simple way to store a custom variable on
    Maya's settings but beware that they are kept even after mGear's uninstall
    so you will need to run the following commands.

    Returns:
        bool: Whether or not mGear's dag menu override is used

    Example:
        The following removes mgears dag menu optionVar

        .. code-block:: python

           from maya import cmds

           if cmds.optionVar(exists="mgear_dag_menu_OV"):
               cmds.optionVar(remove="mgear_dag_menu_OV")
    """
    if not cmds.optionVar(exists=OPTION_VAR):
        cmds.optionVar(intValue=(OPTION_VAR, 0))
    return cmds.optionVar(query=OPTION_VAR)


def install():
    """Installs dag menu option"""
    state = get_option_var_state()

    cmds.setParent(mgear.menu_id, menu=True)
    cmds.menuItem(divider=True)
    cmds.menuItem(
        "mgear_dagmenu_menuitem",
        label="mGear Viewport Menu ",
        command=run,
        checkBox=state,
    )

    run(state)


def mgear_dagmenu_callback(*args, **kwargs):  # @UnusedVariable
    """Triggers dag menu display

    If the first selected transform matches a registered context (an mGear
    control or guide by default), fill the menu with its sections. Else
    display Maya's standard right click dag menu.

    Args:
        *args: Parent Menu path name / Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        str: Menu object name/path that is passed to the function
    """
    parent_menu = args[0]

    # a bool second argument means mgear_dagmenu_toggle is turning the
    # override off and only needs the parent menu back
    if isinstance(args[1], bool):
        return parent_menu

    sel = cmds.ls(selection=True, long=True, type="transform")
    if sel:
        ctx = MenuContext(sel[0])
        context = REGISTRY.detect(ctx)
        if context:
            menu = parent_menu.replace('"', "")
            cmds.menu(menu, edit=True, deleteAllItems=True)
            REGISTRY.build(MenuBuilder(menu), ctx, context)
            return parent_menu

    mel.eval("buildObjectMenuItemsNow " + parent_menu)
    return parent_menu


def mgear_dagmenu_fill(parent_menu, current_control):
    """Fill the given menu with mGear's custom animation menu

    Args:
        parent_menu(str): Parent Menu path name
        current_control(str): current selected mGear control
    """
    build_menu(parent_menu, current_control, context="control")


def mgear_dagmenu_guide_fill(parent_menu, current_guide_locator):
    """Fill the given menu with mGear's custom guide menu

    Args:
        parent_menu(str): Parent Menu path name
        current_guide_locator(str): current selected mGear guide locator
    """
    build_menu(parent_menu, current_guide_locator, context="guide")


def mgear_dagmenu_toggle(state):
    """Set on or off the mgear dag menu override

    This function is responsible for turning ON or OFF mgear's right click
    menu override.

    Args:
        state (bool): Whether or not to override Maya's dag menu with mGear's
                      dag menu
    """
    # Maya's dag menu is a menu whose post command builds the items
    for maya_menu in cmds.lsUI(menus=True):
        menu_cmd = cmds.menu(maya_menu, query=True, postMenuCommand=True) or []

        # override Maya's dag menu
        if state and isinstance(menu_cmd, str):
            if "buildObjectMenuItemsNow" in menu_cmd:
                # Maya's dag menu post command has the parent menu in it
                parent_menu = menu_cmd.split(" ")[-1]
                cmds.menu(
                    maya_menu,
                    edit=True,
                    postMenuCommand=partial(mgear_dagmenu_callback, parent_menu),
                )

        # put back Maya's dag menu MEL command. The override is a partial of
        # mgear_dagmenu_callback, calling it with the state gives back the
        # original parent menu
        elif not state and isinstance(menu_cmd, partial):
            if "mgear_dagmenu_callback" in menu_cmd.func.__name__:
                parent_menu = menu_cmd(state)

                # don't edit any space or syntax here as this is what Maya
                # expects
                mel.eval(
                    "menu -edit -postMenuCommand "
                    '"buildObjectMenuItemsNow '
                    + parent_menu.replace('"', "")
                    + '"'
                    + maya_menu
                )


def run(*args, **kwargs):  # @UnusedVariable
    """Menu run execution

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.
    """
    state = args[0]
    cmds.optionVar(intValue=(OPTION_VAR, 1 if state else 0))
    mgear_dagmenu_toggle(state)
