"""Facial rig engine shared by the facial rigger tools and Shifter components.

Each rig has three layers:

* a settings schema (``<rig>_schema``), the single list of its settings;
* a geometry solver (``<rig>_solver``), reading the mesh and loops without
  creating nodes;
* a builder (``_<rig>_build``), creating the rig in phases that line up with
  the Shifter build steps. It creates controls, joints and named nodes
  through a :class:`backend.BaseBackend`, so the facial rigger tool and a
  Shifter component can build the same rig.
"""
