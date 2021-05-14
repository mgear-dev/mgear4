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
MTypeId mgear_intMatrix::id(0x0011FEC4);

// Define the Node's attribute specifiers
MObject mgear_intMatrix::blend;

MObject mgear_intMatrix::matrixA; 
MObject mgear_intMatrix::matrixB; 
MObject mgear_intMatrix::output; 

mgear_intMatrix::mgear_intMatrix() {} // constructor
mgear_intMatrix::~mgear_intMatrix() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////
mgear_intMatrix::SchedulingType mgear_intMatrix::schedulingType() const
{
	return kParallel;
}
// CREATOR ======================================
void* mgear_intMatrix::creator()
{
   return new mgear_intMatrix();
}

// INIT =========================================
MStatus mgear_intMatrix::initialize()
{
  MFnNumericAttribute nAttr;		
  MFnMatrixAttribute mAttr;
	MStatus stat;

	// ATTRIBUTES
   blend = nAttr.create( "blend", "b", MFnNumericData::kFloat, 0.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
   nAttr.setMin(0);
   nAttr.setMax(1);
	stat = addAttribute( blend );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// INPUTS
	matrixA = mAttr.create( "matrixA", "mA" );
	mAttr.setStorable(true);
	mAttr.setKeyable(true);
	mAttr.setConnectable(true);
	stat = addAttribute( matrixA );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	matrixB = mAttr.create( "matrixB", "mB" );
	mAttr.setStorable(true);
	mAttr.setKeyable(true);
	mAttr.setConnectable(true);
	stat = addAttribute( matrixB );
		if (!stat) {stat.perror("addAttribute"); return stat;}
		
	// OUTPUTS
	output = mAttr.create( "output", "out" );
	mAttr.setStorable(false);
	mAttr.setKeyable(false);
	mAttr.setConnectable(true);
	stat = addAttribute( output );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// CONNECTIONS
	stat = attributeAffects( matrixA, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( matrixB, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( blend, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_intMatrix::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus returnStatus;

	if( plug != output )
		return MS::kUnknownParameter;

	// Input
	MMatrix mA = data.inputValue( matrixA ).asMatrix();
	MMatrix mB = data.inputValue( matrixB ).asMatrix();

	MTransformationMatrix mAm= MTransformationMatrix(mA);
	MTransformationMatrix mBm = MTransformationMatrix(mB);

	// SLIDERS
	double in_blend = (double)data.inputValue( blend ).asFloat();

	MTransformationMatrix mCm = interpolateTransform(mAm, mBm, in_blend);

	MMatrix mC = mCm.asMatrix();
	//MMatrix mC = (mA * in_blend) +( (1 - in_blend) * mB);
	// double i = mC.matrix[0][0];
	

	

	// Output
	MDataHandle h;
	h = data.outputValue( output );
	h.setMMatrix( mC );
	data.setClean(plug);

	return MS::kSuccess;
}

