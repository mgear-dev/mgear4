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
MTypeId mgear_rayCastPosition::id(0x0011FEFF);

// Define the Node's attribute specifiers

MObject mgear_rayCastPosition::meshInput;
MObject mgear_rayCastPosition::raySource;
MObject mgear_rayCastPosition::rayDirection;
MObject mgear_rayCastPosition::output;

mgear_rayCastPosition::mgear_rayCastPosition() {} // constructor
mgear_rayCastPosition::~mgear_rayCastPosition() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_rayCastPosition::SchedulingType mgear_rayCastPosition::schedulingType() const
{
	return kParallel;
}

// CREATOR ======================================
void* mgear_rayCastPosition::creator()
{
   return new mgear_rayCastPosition();
}

// INIT =========================================
MStatus mgear_rayCastPosition::initialize()
{
  MFnNumericAttribute nAttr;
  MFnTypedAttribute meshAttr;
  MFnMatrixAttribute mAttr;
  MStatus stat;


	// INPUTS
	meshInput = meshAttr.create("meshInput", "meshIn", MFnData::kMesh);
	// mAttr.setStorable(true);
	// mAttr.setKeyable(true);
	// mAttr.setConnectable(true);
	stat = addAttribute( meshInput );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	raySource = mAttr.create( "raySource", "rSrc" );
	mAttr.setStorable(true);
	mAttr.setKeyable(true);
	mAttr.setConnectable(true);
	stat = addAttribute( raySource );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	rayDirection = mAttr.create( "rayDirection", "rDir" );
	mAttr.setStorable(true);
	mAttr.setKeyable(true);
	mAttr.setConnectable(true);
	stat = addAttribute( rayDirection );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// OUTPUTS
	output = mAttr.create( "output", "out" );
	mAttr.setStorable(false);
	mAttr.setKeyable(false);
	mAttr.setConnectable(true);
	stat = addAttribute( output );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// CONNECTIONS
	stat = attributeAffects( meshInput, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( raySource, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( rayDirection, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_rayCastPosition::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus returnStatus;
	MStatus status;

	if( plug != output )
		return MS::kUnknownParameter;

	// Input
	MDataHandle hMeshInput = data.inputValue(meshInput, &status);
	MObject oMesh = hMeshInput.asMesh();
	MMatrix mRS = data.inputValue( raySource ).asMatrix();
	MMatrix mRD = data.inputValue( rayDirection ).asMatrix();

	MFnMesh fnMesh( oMesh, &status );
	MTransformationMatrix mRSt= MTransformationMatrix(mRS);
	MTransformationMatrix mRDt = MTransformationMatrix(mRD);

	MFloatVector vRS = mRSt.getTranslation(MSpace::kWorld);
	MFloatVector vRD = mRDt.getTranslation(MSpace::kWorld);
	double ax = vRD.x - vRS.x;
	double ay = vRD.y - vRS.y;
	double az = vRD.z - vRS.z;
	MFloatVector vRDn(ax, ay, az);
	double oriLength = vRDn.length();
	vRDn.normalize();




	//Do the stuff
	MFloatPoint hitPoint;
	int faceIdx = -1;
	float  maxParam = 9999;
	float  tolerance = 0.000001;

	bool hit = fnMesh.closestIntersection(
                            vRS,
                            vRDn,
                            NULL,
							NULL,
                            false,
                            MSpace::kWorld,
                            maxParam,
                            false,
							NULL,
                            hitPoint,
							NULL,
                            &faceIdx,
							NULL,
							NULL,
							NULL,
                            tolerance
                            );

	MTransformationMatrix result;

	if (hit)
	{
		//Check contact max position
		//MFloatVector newVec;
		double bx = hitPoint.x - vRS.x;
		double by = hitPoint.y - vRS.y;
		double bz = hitPoint.z - vRS.z;
		MFloatVector newVec(bx, by, bz);
		//newVec.x = hitPoint.x - vRS.x;
		//newVec.y = hitPoint.y - vRS.y;
		//newVec.z = hitPoint.z - vRS.z;
		double newLength = newVec.length();



		if (newLength > oriLength)
		{
			result = mRDt;
		}
		else
		{
			result.setTranslation(hitPoint, MSpace::kWorld);
		}

	}
	else
	{
		result = mRDt;
	}

	MMatrix mC = result.asMatrix();

	// Output
	MDataHandle h;
	h = data.outputValue( output );
	h.setMMatrix(mC);
	data.setClean(plug);

	return MS::kSuccess;
}

