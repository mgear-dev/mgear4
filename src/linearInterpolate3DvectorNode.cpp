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


#include "mgear_solvers.h"

MTypeId		mgear_linearInterpolate3DvectorNode::id(0x0011FEC6);

//Static variables

MObject		mgear_linearInterpolate3DvectorNode::vecA;
MObject		mgear_linearInterpolate3DvectorNode::vecAx;
MObject		mgear_linearInterpolate3DvectorNode::vecAy;
MObject		mgear_linearInterpolate3DvectorNode::vecAz;

MObject		mgear_linearInterpolate3DvectorNode::vecB;
MObject		mgear_linearInterpolate3DvectorNode::vecBx;
MObject		mgear_linearInterpolate3DvectorNode::vecBy;
MObject		mgear_linearInterpolate3DvectorNode::vecBz;

MObject		mgear_linearInterpolate3DvectorNode::blend;

MObject		mgear_linearInterpolate3DvectorNode::outVec;
//MObject		mgear_linearInterpolate3DvectorNode::outVecX;
//MObject		mgear_linearInterpolate3DvectorNode::outVecY;
//MObject		mgear_linearInterpolate3DvectorNode::outVecZ;





mgear_linearInterpolate3DvectorNode::mgear_linearInterpolate3DvectorNode(){}

mgear_linearInterpolate3DvectorNode::~mgear_linearInterpolate3DvectorNode(){}

mgear_linearInterpolate3DvectorNode::SchedulingType mgear_linearInterpolate3DvectorNode::schedulingType() const
{
	return kParallel;
}

void* mgear_linearInterpolate3DvectorNode::creator()
{
	return new mgear_linearInterpolate3DvectorNode();
}


/// INIT
MStatus mgear_linearInterpolate3DvectorNode::initialize()
{
	MStatus status;
	MFnNumericAttribute nAttr;
	//Inputs
	vecA = nAttr.createPoint("vectorA", "vectorA");
	vecAx = nAttr.child(0);
	vecAy = nAttr.child(1);
	vecAz = nAttr.child(2);
	nAttr.setKeyable(true);
	nAttr.setStorable(false);
	addAttribute(vecA);


	vecB = nAttr.createPoint("vectorB", "vectorB");
	vecBx = nAttr.child(0);
	vecBy = nAttr.child(1);
	vecBz = nAttr.child(2);
	nAttr.setKeyable(true);
	nAttr.setStorable(false);
	addAttribute(vecB);


	blend = nAttr.create("blend", "blend", MFnNumericData::kFloat, 0.0);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(0);
	nAttr.setMax(1);
	addAttribute(blend);


	// ouput
	outVec = nAttr.createPoint("outVector", "outVector");
	nAttr.setWritable(false);
	nAttr.setStorable(false);
	nAttr.setReadable(true);
	addAttribute(outVec);

	// connections
	attributeAffects(vecA, outVec);
	attributeAffects(vecAx, outVec);
	attributeAffects(vecAy, outVec);
	attributeAffects(vecAz, outVec);
	attributeAffects(vecB, outVec);
	attributeAffects(vecBx, outVec);
	attributeAffects(vecBy, outVec);
	attributeAffects(vecBz, outVec);
	attributeAffects(blend, outVec);

	return MS::kSuccess;
}

// COMPUTE

MStatus mgear_linearInterpolate3DvectorNode::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus status;

	if (plug != outVec)
	{
		return MS::kUnknownParameter;
	}


	// inputs

	MDataHandle h;
	MVector v;
	h = data.inputValue(vecA);
	v = h.asFloatVector();
	float vecAx = v.x;
	float vecAy = v.y;
	float vecAz = v.z;

	h = data.inputValue(vecB);
	v = h.asFloatVector();
	float vecBx = v.x;
	float vecBy = v.y;
	float vecBz = v.z;

	//h = data.inputValue( blend );
	//double in_blend = (double)h.asFloat();
	float in_blend = (float)data.inputValue(blend, &status).asFloat();

	// Compute
	float vecCx = (vecBx * in_blend) + ((1.0 - in_blend) * vecAx);
	float vecCy = (vecBy * in_blend) + ((1.0 - in_blend) * vecAy);
	float vecCz = (vecBz * in_blend) + ((1.0 - in_blend) * vecAz);

	// Output
	MDataHandle hOut = data.outputValue(outVec, &status);
	hOut.set3Float(vecCx, vecCy, vecCz);
	//h.setClean();
	data.setClean(plug);

	return MS::kSuccess;
}
