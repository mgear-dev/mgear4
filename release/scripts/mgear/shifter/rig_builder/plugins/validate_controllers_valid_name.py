import pyblish.api
import pymel.core as pm


# actions
class SelectWrongNames(pyblish.api.Action):
    """Select the wrong names on the controllers grp from a given list"""

    label = "Select objects without _ctl suffix"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        """select"""
        pm.select(plugin.wrongNames)


class RemoveFromSet(pyblish.api.Action):
    """Remove the object in wrong names list from the controllers grp"""

    label = "Remove from Set"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        """add _ctl to controllers grp"""
        # self.log.info("remove")
        # self.log.info("Finding failed instances..")
        # errored_instances = act._get_errored_instances_from_context(context)
        # instances = pyblish.api.instances_by_plugin(errored_instances, plugin)
        for x in plugin.wrongNames:
            plugin.controllersGrp.remove(x)


class Rename(pyblish.api.Action):
    """Rename the controllers with wrong suffix"""

    label = "Rename objects with _ctl suffix"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "wrench"  # Icon from Awesome Icon

    def process(self, context, plugin):
        """add _ctl to controllers grp"""
        for x in plugin.wrongNames:
            pm.rename(x, x.name() + "_ctl")


class validateControllersValidName(pyblish.api.Validator):
    """Validate if all the controllers in controllers_grp set
    have correct suffix_ctl

    This plugin have 3 actions for wrong named object on the controllers_grp set

        -Select objects without _ctl suffix
        -Remove from Set
        -Rename objects with _ctl suffix

    """

    families = ["rig"]
    actions = [RemoveFromSet, Rename, SelectWrongNames]
    optional = True
    label = "Validator - Controllers Valid Name"

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
    def getWrongNames(self, instance):
        """Return the wrong names on the controllers grp set"""
        oSet = self.getControllersGrp(instance)
        self.wrongNames = []
        for ctl in oSet.members(flatten=True):
            if ctl.name().endswith("_ctl") or ctl.name().endswith("_grp"):
                continue
            else:
                self.wrongNames.append(ctl)

        return self.wrongNames

    def process(self, instance):
        """Process all the nodes in the instance"""
        check = True
        wn = self.getWrongNames(instance)
        if wn:
            check = False

        assert (
            check
        ), "The objects: {} are in controllers_grp, but have wrong control name".format(
            wn
        )
