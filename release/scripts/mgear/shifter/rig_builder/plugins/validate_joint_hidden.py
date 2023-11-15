import pyblish.api
import pymel.core as pm

# from pyblish_shifter.actions import RepairAction


class validateJointHidden(pyblish.api.Validator):
    """Test Validate Rig information"""

    families = ["rig"]
    # actions = [RepairAction]
    optional = True
    label = "Validator - Joints Hidden"

    def process(self, instance):
        """Process all the nodes in the instance"""
        check = True
        node = pm.PyNode(instance)
        if node.attr("jnt_vis").get():
            check = False

        assert check, " {} joint visible active. Please hide the joints".format(
            instance
        )

    @classmethod
    def repair(cls, instance):
        """Check is rig checkbox"""
        node = pm.PyNode(instance)

        node.attr("jnt_vis").set(False)
