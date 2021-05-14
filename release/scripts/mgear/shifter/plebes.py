import os
import re
import json
from glob import glob
import pymel.core as pm
try:
    from mgear.shifter import io
    from mgear.shifter import guide_manager
except:
    pm.warning("Failed to load Plebes as mGear was not found")


class Plebes():
    """Quickly rig various character generator plebes with mGear
    """

    def __init__(self):
        self.template_menu_entries = {}
        self.template = {}

    def template_change(self, menu):
        """Update the Template, when a new one is selected from the menu
        """
        self.set_template(self.template_menu_entries.get(menu.getValue()))

    def gui(self):
        """GUI for Plebes
        """
        if pm.window('plebesDialog', exists=True):
            pm.deleteUI('plebesDialog')
        win = pm.window(
            'plebesDialog',
            title='Rig Plebe',
            sizeable=False
        )
        win.setHeight(475)
        win.setWidth(300)

        layout = pm.frameLayout(
            height=475,
            width=300,
            marginHeight=10,
            marginWidth=10,
            labelVisible=False
        )

        template_label = pm.text(label='Choose a Character Template:')
        self.template_menu = pm.optionMenu(
            'template_menu',
            alwaysCallChangeCommand=True
        )
        self.template_menu.changeCommand(
            pm.Callback(
                self.template_change,
                self.template_menu
            )
        )

        self.help = pm.scrollField(
            editable=False,
            wordWrap=True,
            height=200,
            text=" "
        )

        self.populate_template_menu(self.template_menu)

        import_fbx_btn = pm.button(label='Import FBX')
        import_fbx_btn.setCommand(self.import_fbx)
        import_fbx_btn.setAnnotation(
            "Import the FBX of your skinned character."
        )

        fbx_naming_btn = pm.button(label='Fix FBX Naming')
        fbx_naming_btn.setCommand(self.fix_fbx_naming)
        fbx_naming_btn.setAnnotation(
            "Replaces FBXASCxxx  with '_' in node names from imported FBX \n"
            "files. This is needed when the FBX uses characters that are \n"
            "not supported in Maya."
        )

        pm.separator(style='in')

        get_guides_btn = pm.button(label='Import Guides')
        get_guides_btn.setCommand(self.import_guides)
        get_guides_btn.setAnnotation(
            "Import a mGear biped guide template."
        )

        align_guides_btn = pm.button(label='Align Guides')
        align_guides_btn.setCommand(self.align_guides)
        align_guides_btn.setAnnotation(
            "Position the guides to match your character.\n\n"
            "Note! You will need to adjust some of the guides manually (e.g. "
            "the heel position and inner and outer foot)."
        )

        rig_btn = pm.button(label='Build Rig')
        rig_btn.setCommand(self.rig)
        rig_btn.setAnnotation(
            "Builds the mGear rig based on the guides."
        )

        attach_btn = pm.button(label='Attach Plebe to Rig')
        attach_btn.setCommand(self.attach_to_rig)
        attach_btn.setAnnotation(
            "Constrain the characters joints to the mGear rig."
        )

        win.show()

    def populate_template_menu(self, template_menu):
        """Populate the template menu from PLEBE_TEMPLATES_DIR environment
        """
        template_paths = []
        if os.getenv('PLEBE_TEMPLATES_DIR'):
            template_paths = os.getenv('PLEBE_TEMPLATES_DIR').split(':')
        template_paths.append(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                'plebes_templates'
            )
        )
        for template_path in template_paths:
            template_pattern = os.path.join(template_path, '*.json')
            for filename in sorted(glob(template_pattern)):
                template_name = os.path.basename(filename).\
                    replace('.json', '').replace('_', ' ').title()
                self.template_menu_entries[template_name] = filename
                pm.menuItem(
                    'templateMenuItem_{name}'.format(name=template_name),
                    label=template_name,
                    parent=template_menu,
                    command=pm.Callback(self.set_template, filename)
                )
        self.set_template(
            self.template_menu_entries.get(
                template_menu.getValue()))

    def import_fbx(self, nothing):
        """Import a FBX
        """
        fbx_filter = "FBX (*.fbx)"
        fbx = pm.fileDialog2(
            fileFilter=fbx_filter,
            caption='Import FBX',
            okCaption='Import',
            fileMode=1
        )
        if fbx:
            pm.displayInfo("Importing: {fbx}".format(fbx=fbx))
            pm.importFile(fbx[0])

    def fix_fbx_naming(self, nothing):
        """Fixes naming of imported FBX's that use unsopperted characters
        """
        nodes = []
        for node in pm.ls('*FBXASC*', long=True):
            new_name = re.sub(r'FBXASC[0-9][0-9][0-9]', '_', node.name())
            pm.displayInfo("Renaming '{old_name}' to '{new_name}'".format(
                old_name=node.name(),
                new_name=new_name
            ))
            node.rename(new_name)
            nodes.append(node)
        if len(nodes) < 1:
            pm.displayInfo(
                "No node names with FBXASCxxx found. Nothing to do.")

    def clear_transforms(self, input_node):
        """Clears out keys, locks and limits on trans, rot, scale and vis
        """
        # TODO! Do I need to unset Segment Scale Compensate on the joints?
        node = pm.PyNode(input_node)
        node.translateX.unlock()
        node.translateY.unlock()
        node.translateZ.unlock()
        node.rotateX.unlock()
        node.rotateY.unlock()
        node.rotateZ.unlock()
        node.scaleX.unlock()
        node.scaleY.unlock()
        node.scaleZ.unlock()
        node.visibility.unlock()
        node.translateX.disconnect()
        node.translateY.disconnect()
        node.translateZ.disconnect()
        node.rotateX.disconnect()
        node.rotateY.disconnect()
        node.rotateZ.disconnect()
        node.scaleX.disconnect()
        node.scaleY.disconnect()
        node.scaleZ.disconnect()
        node.visibility.disconnect()
        node.minTransLimitEnable.set(False, False, False)
        node.maxTransLimitEnable.set(False, False, False)
        node.minRotLimitEnable.set(False, False, False)
        node.maxRotLimitEnable.set(False, False, False)
        node.minScaleLimitEnable.set(False, False, False)
        node.maxScaleLimitEnable.set(False, False, False)

    def check_for_guides(self):
        """Check if the mGear guides are in the scene
        """
        if pm.objExists('guide'):
            return True
        else:
            return False

    def import_guides(self, what):
        """Import mGear's Biped Template guides
        """
        if pm.objExists('guide'):
            pm.warning("There is already a guide in the scene. Skipping!")
        else:
            io.import_sample_template("biped.sgt")

    def rig(self, nothing):
        """Build the mGear rig from guides
        """
        # Sanity check
        if len(pm.ls('rig', assemblies=True)) > 0:
            pm.warning("The character has already been rigged. "
                       "You can delete the rig and re-build it if you need to")
            return False

        pm.select(pm.PyNode('guide'), replace=True)
        guide_manager.build_from_selection()

    def set_template(self, template):
        """
        Set which template to use
        """
        pm.displayInfo('Setting template to: {template}'.format(
            template=template
        ))
        with open(template) as json_file:
            self.template = json.load(json_file)
        self.help.setText(self.template.get('help'))

    def get_target(self, search_guide):
        """Get's the joint matching the guide
        """
        for pairs in self.template.get('guides'):
            for guide, target in pairs.items():
                if guide == search_guide:
                    return pm.PyNode(target)

    def get_joint(self, search_joint):
        """Get's the joint matching the guide
        """
        for pairs in self.template.get('joints'):
            for joint, target in pairs.items():
                if joint == search_joint:
                    return pm.PyNode(target)

    def align_guides(self, nothing):
        """Align the mGear guide to character based on the selected template
        """
        # Sanity checking
        if not pm.objExists('guide'):
            pm.warning("You need to import guides first")
            return False
        if not pm.objExists(self.template.get('root')):
            pm.warning("Unable to find '{character}' in scene! ".format(
                character=self.template.get('root')
            ), "Check that you have the correct template selected")
            return False
        warnings = False

        # Scale the guides
        factor = 16.741  # Height of guide head
        head_pos = self.get_target(
            'neck_C0_head').getTranslation(space='world')
        scale = head_pos.y / factor
        pm.PyNode('guide').setScale(pm.datatypes.Vector(scale, scale, scale))

        # Match guides to joints based on template
        for pairs in self.template.get('guides'):
            for guide, target in pairs.items():
                g = pm.PyNode(guide)
                if target == 'PARENT_OFFSET':
                    # Offset by the same amount the parent is from it's parent
                    gparent = g.getParent()
                    parent = self.get_target(gparent)
                    ggrandparent = gparent.getParent()
                    grandparent = self.get_target(ggrandparent)
                    parent_pos = parent.getTranslation(space='world')
                    grandparent_pos = grandparent.getTranslation(space='world')
                    offset = parent_pos - grandparent_pos + parent_pos
                    g.setTranslation(
                        offset,
                        space='world'
                    )
                elif isinstance(target, list):
                    # Average position between targets
                    pos = pm.datatypes.Vector((0.0, 0.0, 0.0))
                    for t in target:
                        pos = pm.PyNode(t).getTranslation(space='world') + pos
                    g.setTranslation(
                        pos / len(target),
                        space='world'
                    )
                else:
                    try:
                        t = pm.PyNode(target)
                        g.setTranslation(
                            t.getTranslation(space='world'),
                            space='world'
                        )
                    except:
                        warnings = True
                        pm.warning(
                            "Target '{target}' not found in scene. "
                            "Unable to align the '{guide}' guide".format(
                                target=target,
                                guide=guide
                            )
                        )

        # Adjust the setgings on the guides
        try:
            for pairs in self.template.get('settings'):
                for guide, settings in pairs.items():
                    for setting in settings:
                        for attribute, value in setting.items():
                            try:
                                pm.PyNode(guide).attr(attribute).set(value)
                            except:
                                warnings = True
                                pm.warning("Unable to set attribute '{attr}' "
                                           "on guide '{guide}' to '{value}'"
                                           "".format(
                                               attr=attribute,
                                               guide=guide,
                                               value=value
                                           ))
        except:
            pm.displayInfo("No guide settings defined in template")
        pm.displayInfo("Remember to align heels and direction of blades."
                       "Not everything can be automated.")
        if warnings:
            pm.warning("Some guides failed to align correctly. "
                       "See the script editor for details!")

    def attach_to_rig(self, nothing):
        """Attach the plebe to the mGear rig
        """
        # Sanity checking
        if not pm.objExists(self.template.get('root')):
            pm.warning("Unable to find '{character}' in scene! ".format(
                character=self.template.get('root')
            ), "Check that you have the correct template selected")
            return False
        warnings = False

        for pairs in self.template.get('joints'):
            for source, target in pairs.items():
                if not pm.objExists(target.get('joint')):
                    warnings = True
                    pm.warning("Joint '{joint}' not found, so it won't be "
                               "connected to the rig.".format(
                                   joint=target.get('joint')
                               )
                               )
                    continue
                self.clear_transforms(target.get('joint'))
                if target.get('constrain')[0] == "1" and target.get('constrain')[1] == "1":
                    pm.parentConstraint(
                        source,
                        target.get('joint'),
                        maintainOffset=True,
                        decompRotationToChild=True
                    )
                elif target.get('constrain')[0] == "1":
                    pm.pointConstraint(
                        source,
                        target.get('joint'),
                        maintainOffset=True
                    )
                elif target.get('constrain')[1] == "1":
                    pm.orientConstraint(
                        source,
                        target.get('joint'),
                        maintainOffset=True
                    )
                if target.get('constrain')[2] == "1":
                    pm.scaleConstraint(
                        source,
                        target.get('joint'),
                        maintainOffset=True
                    )
        pm.displayInfo("Done attaching the character to the rig")
        if warnings:
            pm.warning("Some joints failed to attach to the rig. "
                       "See the script editor for details!")


def plebes_gui():
    """Open the Plebes interface
    """
    plebes = Plebes()
    plebes.gui()
