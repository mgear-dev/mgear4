"""Backend interface of the facial rig builders.

A builder creates controls, deform joints and named nodes only through a
backend. The facial rigger tool and the Shifter components each implement
one, so both build the same rig with their own naming, sets, control
creation and joint handling.
"""


class BaseBackend(object):
    """Interface the facial rig builders build through.

    Joints are registered while building and created later, by the backend
    (a Shifter component creates them in its joint step). Only use
    :meth:`deform_joint` after the joints exist.
    """

    @property
    def root(self):
        """dagNode: Root transform of the rig."""
        raise NotImplementedError

    @property
    def setup_root(self):
        """dagNode: Hidden transform for curves and other setup nodes."""
        raise NotImplementedError

    def name(self, name, idx=None):
        """Get the full name of a rig node.

        Args:
            name (str): Short name, e.g. "upBlink_ctl".
            idx (int, optional): Index of the node.

        Returns:
            str: The full node name.
        """
        raise NotImplementedError

    def add_transform(self, parent, name, m, idx=None):
        """Create a transform.

        Args:
            parent (dagNode): Parent.
            name (str): Short name.
            m (Matrix): World matrix.
            idx (int, optional): Index of the node.

        Returns:
            dagNode: The transform.
        """
        raise NotImplementedError

    def add_curve(self, parent, name, points):
        """Create a cubic nurbs curve.

        Args:
            parent (dagNode): Parent.
            name (str): Short name.
            points (list): World points.

        Returns:
            dagNode: The curve transform.
        """
        raise NotImplementedError

    def add_ctl(
        self,
        parent,
        name,
        m,
        shape,
        role,
        keyable,
        w=1.0,
        d=None,
        ro=None,
        po=None,
        tag_parent=None,
        mirror_conf=None,
    ):
        """Create an animation control.

        Args:
            parent (dagNode): Parent.
            name (str): Short name, without the control suffix.
            m (Matrix): World matrix.
            shape (str): Icon shape.
            role (str): "main" or "secondary" control, for the color.
            keyable (list): Keyable attributes.
            w (float, optional): Shape width.
            d (float, optional): Shape depth, the width when None.
            ro (Vector, optional): Shape rotation offset.
            po (Vector, optional): Shape position offset.
            tag_parent (dagNode, optional): Parent controller tag.
            mirror_conf (list, optional): Mirror pose flags, inverting tx ty
                tz rx ry rz sx sy sz. None inverts nothing.

        Returns:
            dagNode: The control.
        """
        raise NotImplementedError

    def add_deform_joint(self, driver, name, idx=None):
        """Register a deform joint following a driver transform.

        Args:
            driver (dagNode): Transform the joint follows.
            name (str): Short joint name.
            idx (int, optional): Index of the joint.

        Returns:
            object: Handle of the joint, for :meth:`deform_joint`.
        """
        raise NotImplementedError

    def deform_joint(self, handle):
        """Get a deform joint once the joints exist.

        Args:
            handle (object): Handle from :meth:`add_deform_joint`.

        Returns:
            str: The joint.
        """
        raise NotImplementedError

    def head_joint(self):
        """Get the joint the rig is skinned against.

        Returns:
            str: The joint, or None.
        """
        raise NotImplementedError

    def finalize(self):
        """Finish the build, e.g. parent the rig."""
        raise NotImplementedError
