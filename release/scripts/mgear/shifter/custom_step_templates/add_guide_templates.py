"""Add Guide Templates custom step template.

Template for adding guide templates, whole or in part, under elements of
the guide being built. Works for scene builds and serialized builds.
"""

TEMPLATE = r'''import os

import mgear.shifter.custom_step as cstp


class CustomShifterStep(cstp.customShifterMainStep):
    """Add guide templates to the guide being built.

    Use it as a PRE custom step. Each operation adds a guide template
    (.sgt), or some of its components, under an element of the guide,
    like a component root or a locator, with an optional snap.

    The templates are merged into the guide when the build runs, the same
    way for a guide in the scene and for a serialized guide (Rig Builder,
    Build from File). The scene guide is never changed, so rebuilding
    doesn't add copies, and the guide stored on the rig is the original
    guide. The added components get the next free index, like an Add
    import, and their UI host and space references are not updated.
    """

    def setup(self):
        """Set up the custom step name and the operations."""
        self.name = "{stepName}"

        # One dict per operation:
        #   path: template file, absolute or relative to this step file
        #   target: guide element to add the template under
        #   partial: component names to add, with their children.
        #            None adds the whole template
        #   snap: move the added components so the first root sits on
        #         the target
        self.operations = [
            {{
                "path": "hand_L.sgt",
                "target": "arm_L0_wrist",
                "partial": None,
                "snap": True,
            }},
            {{
                "path": "hand_R.sgt",
                "target": "arm_R0_wrist",
                "partial": None,
                "snap": True,
            }},
            # Partial: only the tail of the template, with all its children
            {{
                "path": "trex.sgt",
                "target": "spine_C0_root",
                "partial": ["tail_C0"],
                "snap": True,
            }},
        ]

    def run(self):
        """Register the operations on the build.

        Returns:
            None
        """
        step_dir = os.path.dirname(__file__)
        for operation in self.operations:
            path = os.path.join(step_dir, operation["path"])
            if not os.path.isfile(path):
                # An error log stops the build
                self.log(
                    "Guide template not found: {{}}".format(path),
                    level="error",
                )
            added = self.add_guide_template(
                operation["target"],
                path=path,
                partial=operation.get("partial"),
                snap=operation.get("snap", False),
            )
            if added:
                self.log(
                    "{{}} added under {{}}".format(
                        os.path.basename(path), operation["target"]
                    )
                )
        return'''
