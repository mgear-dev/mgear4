.. _file-drop:

File Drop
#########

With mGear file drop enabled, dropping an mGear file from the file explorer onto Maya imports it with the right tool, instead of Maya's default import.

Turn it on from **mGear > Utilities > Enable mGear file drop**. The setting is saved with your Maya preferences.

Each dropped file is one undo step (except a guide build), and a file that can't be imported shows a warning instead of an error. Files mGear doesn't know, and plain ``.json`` files, go to Maya's default import. Extensions are not case sensitive. When several files are dropped at once, Maya imports them one at a time.

Supported Files
===============

.. list-table::
    :header-rows: 1
    :widths: 15 25 60

    * - Extension
      - File
      - What a drop does
    * - ``.sgt``
      - Shifter guide template
      - Asks to **Import** the guide or **Build** the rig from it. With a component root or locator of a guide selected, also offers to add the template, or some of its components, under that element, with or without snapping (see :ref:`guide-import-options`).
    * - ``.gSkinPack``
      - Skin pack
      - Imports the skin files of the pack. Opens the remap dialog for missing objects or joints.
    * - ``.gSkin`` ``.jSkin``
      - Skin weights
      - Imports the skin. Opens the remap dialog for missing objects or joints.
    * - ``.rbf``
      - RBF Manager setups
      - Imports the RBF setups.
    * - ``.wts``
      - Wire to Skinning configuration
      - Imports the wires on the selected mesh, or on the mesh stored in the file.
    * - ``.gst``
      - Gimmick joints (see :ref:`gimmick-joints`)
      - Rebuilds the blended and support joints.
    * - ``.lat``
      - Lattice IO (see :ref:`lattice-io`)
      - Rebuilds the lattices, replacing the ones with the same names, with the deformer order stored in the file.
    * - ``.shw``
      - Shrink Wrap IO (see :ref:`shrinkwrap-io`)
      - Rebuilds the shrink wraps, replacing the ones with the same names.
    * - ``.pxw``
      - Proximity Wrap IO (see :ref:`proximitywrap-io`)
      - Rebuilds the proximity wraps, replacing the ones with the same names. Warns when the skinned meshes are not at their bind pose, because the drivers are bound at the current pose.
    * - ``.cwc``
      - Channel Wrangler configuration
      - Applies the channel moves and proxies.
    * - ``.cmc``
      - Channel Master configuration
      - Creates the Channel Master node and opens Channel Master on it. When a node of the same name exists, asks to **Replace** its configuration, **Add Tabs** to it, or create a **New Node**.
    * - ``.pkr``
      - Anim Picker
      - Creates the picker node and opens the Anim Picker. When the scene has namespaces, asks which one the picker drives.
    * - ``.sbk``
      - Bookmarks
      - Opens the Bookmarks window (**Animbits > Bookmarks**) and loads the file. When there are bookmarks already, asks to **Replace** or **Append** them.

Adding Your Own Files
=====================

Studio tools can handle their own file types with ``register_drop_handler``. The handler is a function called with the file path, or a ``"module:function"`` string that is imported only when such a file is dropped. Registering an extension mGear already handles replaces the mGear handler. A handler can return ``False`` to let Maya import the file.

.. code-block:: python

    from mgear.core import dragdrop

    # Imported on the first drop of a .cfx file
    dragdrop.register_drop_handler(".cfx", "studio.cfx_tool:import_file", "CFX setup")

    # Or a function
    def import_notes(path):
        print("Notes:", open(path).read())

    dragdrop.register_drop_handler(".notes", import_notes, "Notes", undo=False)

    # The registered handlers
    dragdrop.get_drop_handlers()

Run the registration from a startup script (i.e. ``userSetup.py``) so it is ready before the first drop.
