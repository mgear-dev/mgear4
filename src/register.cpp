/*

MGEAR is under the terms of the MIT License

Copyright (c) 2016 Jeremie Passerin, Miquel Campos

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Author:     Jeremie Passerin      geerem@hotmail.com  www.jeremiepasserin.com
Author:     Miquel Campos         hello@miquel-campos.com  www.miquel-campos.com
Date:       2016 / 10 / 10

*/
/////////////////////////////////////////////////
// INCLUDE
/////////////////////////////////////////////////

#include "mgear_solvers.h"

#include <maya/MFnPlugin.h>

/////////////////////////////////////////////////
// LOAD / UNLOAD
/////////////////////////////////////////////////
// INIT =========================================
PLUGIN_EXPORT MStatus initializePlugin( MObject obj )
{
	MStatus status;
	MFnPlugin plugin( obj, "Jeremie Passerin, Miquel Campos, Jascha Wohlkinger", "2.2.0", "Any");

	status = plugin.registerNode( "mgear_curveCns", mgear_curveCns::id, mgear_curveCns::creator, mgear_curveCns::initialize, MPxNode::kDeformerNode );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_rollSplineKine", mgear_rollSplineKine::id, mgear_rollSplineKine::creator, mgear_rollSplineKine::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_slideCurve2", mgear_slideCurve2::id, mgear_slideCurve2::creator, mgear_slideCurve2::initialize, MPxNode::kDeformerNode );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_squashStretch2", mgear_squashStretch2::id, mgear_squashStretch2::creator, mgear_squashStretch2::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_ikfk2Bone", mgear_ikfk2Bone::id, mgear_ikfk2Bone::creator, mgear_ikfk2Bone::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_inverseRotOrder", mgear_inverseRotOrder::id, mgear_inverseRotOrder::creator, mgear_inverseRotOrder::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_mulMatrix", mgear_mulMatrix::id, mgear_mulMatrix::creator, mgear_mulMatrix::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_intMatrix", mgear_intMatrix::id, mgear_intMatrix::creator, mgear_intMatrix::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_percentageToU", mgear_percentageToU::id, mgear_percentageToU::creator, mgear_percentageToU::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_spinePointAt", mgear_spinePointAt::id, mgear_spinePointAt::creator, mgear_spinePointAt::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode( "mgear_uToPercentage", mgear_uToPercentage::id, mgear_uToPercentage::creator, mgear_uToPercentage::initialize );
		if (!status) {status.perror("registerNode() failed."); return status;}

	status = plugin.registerNode("mgear_springNode", mgear_springNode::id, mgear_springNode::creator, mgear_springNode::initialize);
		if (!status) { status.perror("registerNode() failed."); return status; }

	status = plugin.registerNode("mgear_linearInterpolate3DvectorNode", mgear_linearInterpolate3DvectorNode::id, mgear_linearInterpolate3DvectorNode::creator, mgear_linearInterpolate3DvectorNode::initialize);
		if (!status) { status.perror("registerNode() failed."); return status; }

	status = plugin.registerNode("mgear_add10scalarNode", mgear_add10scalarNode::id, mgear_add10scalarNode::creator, mgear_add10scalarNode::initialize);
		if (!status) { status.perror("registerNode() failed."); return status; }

	status = plugin.registerNode("mgear_rayCastPosition", mgear_rayCastPosition::id, mgear_rayCastPosition::creator, mgear_rayCastPosition::initialize);
		if (!status) { status.perror("registerNode() failed."); return status; }

	status = plugin.registerNode("mgear_trigonometryAngle", mgear_trigonometryAngle::id, mgear_trigonometryAngle::creator, mgear_trigonometryAngle::initialize);
		if (!status) { status.perror("registerNode() failed."); return status; }

	status = plugin.registerNode("mgear_vertexPosition", mgear_vertexPosition::id, mgear_vertexPosition::creator, mgear_vertexPosition::initialize);
		if (!status) { status.perror("registerNode() failed."); return status; }

	status = plugin.registerNode("mgear_matrixConstraint", mgear_matrixConstraint::id, mgear_matrixConstraint::creator, mgear_matrixConstraint::initialize);
		if (!status) { status.perror("registerNode() failed."); return status; }

	return status;
}

// UNINIT =======================================
PLUGIN_EXPORT MStatus uninitializePlugin( MObject obj)
{
	MStatus status;
	MFnPlugin plugin( obj );

	status = plugin.deregisterNode( mgear_curveCns::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_slideCurve2::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_rollSplineKine::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_squashStretch2::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_ikfk2Bone::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_inverseRotOrder::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_mulMatrix::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_intMatrix::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_percentageToU::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_spinePointAt::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode( mgear_uToPercentage::id );
		if (!status) {status.perror("deregisterNode() failed."); return status;}
	status = plugin.deregisterNode(mgear_springNode::id);
		if (!status) { status.perror("deregisterNode() failed."); return status; }
	status = plugin.deregisterNode(mgear_linearInterpolate3DvectorNode::id);
		if (!status) { status.perror("deregisterNode() failed."); return status; }
	status = plugin.deregisterNode(mgear_add10scalarNode::id);
		if (!status) { status.perror("deregisterNode() failed."); return status; }
	status = plugin.deregisterNode(mgear_rayCastPosition::id);
		if (!status) { status.perror("deregisterNode() failed."); return status; }
	status = plugin.deregisterNode(mgear_trigonometryAngle::id);
		if (!status) { status.perror("deregisterNode() failed."); return status; }
	status = plugin.deregisterNode(mgear_vertexPosition::id);
		if (!status) { status.perror("deregisterNode() failed."); return status; }
	status = plugin.deregisterNode(mgear_matrixConstraint::id);
		if (!status) { status.perror("deregisterNode() failed."); return status; }


	return MS::kSuccess;
}