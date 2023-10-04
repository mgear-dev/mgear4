import unittest


class TestAttr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        import os
        from maya import standalone
        standalone.initialize()

        from maya import cmds
        cls.cmds = cmds

        mpath = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if mpath not in sys.path:
            sys.path.append(mpath)

        import pymaya
        cls.pm = pymaya

    def setUp(self):
        self.cmds.file(new=True, f=True)

    def test_init(self):
        test_node_name = self.cmds.createNode("transform", n="test")
        v = self.pm.PyAttr(f"{test_node_name}.v")
        self.assertIsNotNone(v)
        self.assertEqual(v.name(), "test.visibility")

        plug = v.plug()
        self.assertIsNotNone(plug)
        self.assertEqual(plug.partialName(False, False, False, False, False, True), "visibility")
        self.assertEqual(plug.partialName(False, False, False, False, False, False), "v")

    def test_connect(self):
        test1_node_name = self.cmds.createNode("transform", n="test1")
        test2_node_name = self.cmds.createNode("transform", n="test2")
        t1 = self.pm.PyAttr(f"{test1_node_name}.tx")
        t2 = self.pm.PyAttr(f"{test2_node_name}.tx")
        self.assertIsNone(self.cmds.listConnections(f"{test1_node_name}.tx"))
        t1.connect(t2)
        self.assertIsNotNone(self.cmds.listConnections(f"{test1_node_name}.tx"))
        t1.disconnect(t2)
        self.assertIsNone(self.cmds.listConnections(f"{test1_node_name}.tx"))
        t1 >> t2
        self.assertIsNotNone(self.cmds.listConnections(f"{test1_node_name}.tx"))
        t1 // t2
        self.assertIsNone(self.cmds.listConnections(f"{test1_node_name}.tx"))

    def test_delete(self):
        test1_node_name = self.cmds.createNode("transform", n="test1")
        self.cmds.addAttr(test1_node_name, ln="test_attr_x", at="float")
        self.assertTrue(self.cmds.objExists(f"{test1_node_name}.test_attr_x"))
        tattr = self.pm.PyAttr(f"{test1_node_name}.test_attr_x")
        tattr.delete()
        self.assertFalse(self.cmds.objExists(f"{test1_node_name}.test_attr_x"))

    def test_partial_name(self):
        child_name = self.cmds.createNode("transform", n="child")
        parent_name = self.cmds.createNode("transform", n="parent")
        child = self.pm.PyNode(child_name)
        self.cmds.parent(child_name, parent_name)
        self.assertEqual(child.v.name(), f"{child_name}.visibility")
        self.cmds.duplicate(parent_name)
        self.assertNotEqual(child.v.name(), f"{child_name}.visibility")
        self.assertEqual(child.v.name(), f"{parent_name}|{child_name}.visibility")

    def test_array_compound(self):
        sp = self.cmds.polySphere()[0]
        sps = self.cmds.listRelatives(sp, s=1)[0]
        vrts = self.pm.PyAttr(f"{sps}.vrts")
        self.assertEqual(vrts[0].name(), f"{sps}.vrts[0]")
        self.assertIsNotNone(vrts[0].vrtx)
        self.assertIsNotNone(vrts[0].vrty)
        self.assertIsNotNone(vrts[0].vrtz)
        self.assertIsNotNone(vrts[0].attr("vrtz"))
        self.assertEqual(vrts[0].vrtz.name(), f"{sps}.vrts[0].vrtz")
