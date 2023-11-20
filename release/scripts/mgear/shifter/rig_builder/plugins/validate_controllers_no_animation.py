import pyblish.api
import pymel.core as pm


# actions
class DeleteAnimation(pyblish.api.Action):
    """Delete animation from animated controls"""

    label = "Delete Animation"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        """select"""
        for ctl in plugin.animatedCtl:
            pm.delete(ctl, channels=True)
            for attr in ctl.listAttr(ud=True):
                pm.cutKey(attr, cl=True)


class RenameAsNoCtl(pyblish.api.Action):
    """Rename the controllers with wrong suffix"""

    label = "Rename objects with _NoCtl suffix"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        """add _ctl to controllers grp"""
        for x in plugin.animatedCtl:
            pm.rename(x, x.name().replace("_ctl", "_NoCtl"))


class SelectAnimatedCtl(pyblish.api.Action):
    """Select animated controls"""

    label = "Select Animated Ctl"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        """select"""
        pm.select(plugin.animatedCtl)


class validateControllersNoAnimation(pyblish.api.Validator):
    """Validate if all the controllers have clean channels witout animation"""

    families = ["rig"]
    actions = [SelectAnimatedCtl, DeleteAnimation, RenameAsNoCtl]
    optional = True
    label = "Validator - Controllers No Animation"

    @classmethod
    def getControllersGrp(self, instance):
        """return the controllers grp"""
        node = pm.PyNode(instance)
        sets = node.listConnections(type="objectSet")

        self.controllersGrp = False
        for oSet in sets:
            if "controllers_grp" in oSet.name().lower():
                self.controllersGrp = oSet

        return self.controllersGrp

    @classmethod
    def getAnimatedCtl(self, instance):
        """Return the wrong names on the controllers grp set"""
        # check = True
        oSet = self.getControllersGrp(instance)
        self.animatedCtl = []
        for ctl in oSet.members():
            if ctl.listConnections(type="animCurve"):
                self.log.warning("{} have animation".format(ctl.name()))
                self.animatedCtl.append(ctl)

        return self.animatedCtl

    def process(self, instance):
        """Process all the nodes in the instance"""
        check = True
        anim = self.getAnimatedCtl(instance)
        if anim:
            check = False

        assert check, "The Controls: {} should not have animation".format(anim)
