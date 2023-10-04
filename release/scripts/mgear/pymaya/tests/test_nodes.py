import unittest


class TestNode(unittest.TestCase):
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
        node_name = self.cmds.createNode("transform", n="test")
        node = self.pm.PyNode(node_name)
        self.assertIsNotNone(node)
        with self.assertRaises(self.pm.MayaNodeError):
            self.pm.PyNode("no_such_node")

        self.assertEqual(node_name, node.name())

    def test_holding_object(self):
        node_name = self.cmds.createNode("transform", n="test")
        node = self.pm.PyNode(node_name)
        new_name = self.cmds.rename(node_name, "test2")
        self.assertEqual(new_name, node.name())

    def test_partial_name(self):
        child_name = self.cmds.createNode("transform", n="child")
        parent_name = self.cmds.createNode("transform", n="parent")
        child = self.pm.PyNode(child_name)
        parent = self.pm.PyNode(parent_name)

        self.assertEqual(child_name, child.name())
        self.assertEqual(parent_name, parent.name())

        self.cmds.parent(child_name, parent_name)
        self.assertEqual(child_name, child.name())
        self.assertEqual(parent_name, parent.name())

        self.cmds.duplicate(parent_name)
        self.assertNotEqual(child_name, child.name())
        self.assertEqual(f"{parent_name}|{child_name}", child.name())

    def test_dag_or_dg(self):
        sphere_dag_name, sphere_name = self.cmds.polySphere()
        sphere_dag = self.pm.PyNode(sphere_dag_name)
        sphere = self.pm.PyNode(sphere_name)

        self.assertTrue(sphere_dag.isDag())
        self.assertFalse(sphere.isDag())
        self.assertIsNotNone(sphere_dag.dg())
        self.assertIsNotNone(sphere.dg())
        self.assertIsNotNone(sphere_dag.dag())
        self.assertIsNone(sphere.dag())

    def test_eq(self):
        child_name = self.cmds.createNode("transform", n="child")
        parent_name = self.cmds.createNode("transform", n="parent")
        child = self.pm.PyNode(child_name)
        parent = self.pm.PyNode(parent_name)
        self.cmds.parent(child_name, parent_name)

        a = self.pm.PyNode(child_name)
        b = self.pm.PyNode(f"|{parent_name}|{child_name}")

        self.assertEqual(child, a)
        self.assertEqual(child, b)
        self.assertNotEqual(child, parent)
        self.assertTrue(b in [child, parent])

    def test_attr(self):
        child_name = self.cmds.createNode("transform", n="test")
        node = self.pm.PyNode("test")
        self.assertIsNotNone(node.attr("v"))
        self.assertIsNotNone(node.v)
        with self.assertRaises(self.pm.MayaAttributeError):
            node.attr("testtest")
