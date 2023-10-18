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
        import pymaya.geometry
        cls.pm = pymaya
        cls.pgeo = pymaya.geometry

    def setUp(self):
        self.cmds.file(new=True, f=True)

    def test_init(self):
        self.cmds.polySphere()
        self.assertIsNotNone(self.pgeo.BindGeometry("pSphere1.vtx[0]"))
        self.assertIsNotNone(self.pgeo.BindGeometry("pSphereShape1.vtx[0]"))
        self.assertIsNotNone(self.pgeo.BindGeometry("pSphereShape1.vtx[0:10]"))
        self.assertIsNotNone(self.pgeo.BindGeometry("pSphere1.f[1]"))
        self.assertIsNotNone(self.pgeo.BindGeometry("pSphereShape1.f[0:10]"))
        self.assertIsNone(self.pgeo.BindGeometry("pSphere1"))
        self.assertIsNone(self.pgeo.BindGeometry("pSphereShape1"))

        self.assertTrue(isinstance(self.pm.PyNode("pSphereShape1.vtx[0]"), self.pm.MeshVertex))
        self.assertTrue(isinstance(self.pm.PyNode("pSphereShape1.f[0]"), self.pm.MeshFace))
