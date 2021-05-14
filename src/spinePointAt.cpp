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

/////////////////////////////////////////////////
// GLOBAL
/////////////////////////////////////////////////
MTypeId mgear_spinePointAt::id(0x0011FECB);

// Define the Node's attribute specifiers

MObject mgear_spinePointAt::rotA;
MObject mgear_spinePointAt::rotAx;
MObject mgear_spinePointAt::rotAy;
MObject mgear_spinePointAt::rotAz;
MObject mgear_spinePointAt::rotB;
MObject mgear_spinePointAt::rotBx;
MObject mgear_spinePointAt::rotBy;
MObject mgear_spinePointAt::rotBz;
MObject mgear_spinePointAt::axe;
MObject mgear_spinePointAt::blend;
MObject mgear_spinePointAt::pointAt;

mgear_spinePointAt::mgear_spinePointAt() {} // constructor
mgear_spinePointAt::~mgear_spinePointAt() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_spinePointAt::SchedulingType mgear_spinePointAt::schedulingType() const
{
    return kParallel;
}

// CREATOR ======================================
void* mgear_spinePointAt::creator()
{
   return new mgear_spinePointAt();
}

// INIT =========================================
MStatus mgear_spinePointAt::initialize()
{
   MFnNumericAttribute nAttr;
   MFnEnumAttribute eAttr;
   MStatus stat;

    // Inputs
    rotA = nAttr.createPoint("rotA", "ra" );
    rotAx = nAttr.child(0);
    rotAy = nAttr.child(1);
    rotAz = nAttr.child(2);
    nAttr.setWritable(true);
    nAttr.setStorable(true);
    nAttr.setReadable(true);
    nAttr.setKeyable(false);
    stat = addAttribute( rotA );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    rotB = nAttr.createPoint("rotB", "rb" );
    rotBx = nAttr.child(0);
    rotBy = nAttr.child(1);
    rotBz = nAttr.child(2);
    nAttr.setWritable(true);
    nAttr.setStorable(true);
    nAttr.setReadable(true);
    nAttr.setKeyable(false);
    stat = addAttribute( rotB );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    axe = eAttr.create( "axe", "a", 2 );
    eAttr.addField("X", 0);
    eAttr.addField("Y", 1);
    eAttr.addField("Z", 2);
    eAttr.addField("-X", 3);
    eAttr.addField("-Y", 4);
    eAttr.addField("-Z", 5);
    eAttr.setWritable(true);
    eAttr.setStorable(true);
    eAttr.setReadable(true);
    eAttr.setKeyable(false);
    stat = addAttribute( axe );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    blend = nAttr.create( "blend", "b", MFnNumericData::kFloat, 0.5 );
    nAttr.setWritable(true);
    nAttr.setStorable(true);
    nAttr.setReadable(true);
    nAttr.setKeyable(true);
    nAttr.setMin(0);
    nAttr.setMax(1);
    stat = addAttribute( blend );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Outputs
	pointAt = nAttr.createPoint("pointAt", "pa" );
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setReadable(true);
    stat = addAttribute( pointAt );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Connections
    stat = attributeAffects ( rotA, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( rotAx, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( rotAy, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( rotAz, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( rotB, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( rotBx, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( rotBy, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( rotBz, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( axe, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( blend, pointAt );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_spinePointAt::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus returnStatus;

	if( plug != pointAt )
		return MS::kUnknownParameter;

	MString sx, sy, sz, sw;

    // Get inputs
	MDataHandle h;
	MVector v;
    h = data.inputValue( rotA );
	v = h.asFloatVector();
    double rAx = v.x;
    double rAy = v.y;
    double rAz = v.z;

    h = data.inputValue( rotB );
	v = h.asFloatVector();
    double rBx = v.x;
    double rBy = v.y;
    double rBz = v.z;

	h = data.inputValue( axe );
    int axe = h.asShort();

	h = data.inputValue( blend );
    double in_blend = (double)h.asFloat();

    // Process
    // There is no such thing as siTransformation in Maya,
    // so what we really need to compute this +/-360 roll is the global rotation of the object
    // We then need to convert this eulerRotation to Quaternion
    // Maybe it would be faster to use the MEulerRotation class, but anyway, this code can do it
    MQuaternion qA = e2q(rAx, rAy, rAz);
    MQuaternion qB = e2q(rBx, rBy, rBz);

    MQuaternion qC = slerp2(qA, qB, in_blend);

	MVector vOut;
	switch ( axe )
	{
		case 0:
			vOut = MVector(1,0,0);
			break;
		case 1:
			vOut = MVector(0,1,0);
			break;
		case 2:
			vOut = MVector(0,0,1);
			break;
		case 3:
			vOut = MVector(-1,0,0);
			break;
		case 4:
			vOut = MVector(0,-1,0);
			break;
		case 5:
			vOut = MVector(0,0,-1);
			break;
	}

    vOut = vOut.rotateBy(qC);
    float x = (float)vOut.x;
    float y = (float)vOut.y;
    float z = (float)vOut.z;

    // Output
    h = data.outputValue( pointAt );
	h.set3Float( x, y, z );

	// This doesn't work
    // h.setMVector( vOut );
    // h.set3Double( vOut );

    data.setClean( plug );

	return MS::kSuccess;
}

