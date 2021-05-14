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
MTypeId mgear_trigonometryAngle::id(0x0011FEEC);

// Define the Node's attribute specifiers

MObject mgear_trigonometryAngle::trigoOperation;
MObject mgear_trigonometryAngle::angle;
MObject mgear_trigonometryAngle::output;

mgear_trigonometryAngle::mgear_trigonometryAngle() {} // constructor
mgear_trigonometryAngle::~mgear_trigonometryAngle() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_trigonometryAngle::SchedulingType mgear_trigonometryAngle::schedulingType() const
{
	return kParallel;
}

// CREATOR ======================================
void* mgear_trigonometryAngle::creator()
{
   return new mgear_trigonometryAngle();
}

// INIT =========================================
MStatus mgear_trigonometryAngle::initialize()
{
   MFnNumericAttribute nAttr;
   MFnEnumAttribute eAttr;
   MStatus stat;
   MFnUnitAttribute uAttr;

    // Inputs
    trigoOperation = eAttr.create( "operation", "op", 0 );
    eAttr.addField("sine", 0);
    eAttr.addField("cosine", 1);
    eAttr.setWritable(true);
    eAttr.setStorable(true);
    eAttr.setReadable(true);
    eAttr.setKeyable(true);
	stat = addAttribute( trigoOperation );
		if (!stat) {stat.perror("addAttribute"); return stat;}


	MAngle angle_default( 0.0, MAngle::kDegrees );
	angle = uAttr.create("angle", "angle", angle_default);
	uAttr.setKeyable(true);
	addAttribute(angle);

    // Outputs
	// MAngle output( (double)0.0, MAngle::kDegrees );
	// nAttr.create("output", "output", output);
	output = nAttr.create("output", "output", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	// nAttr.setStorable(true);
    nAttr.setReadable(true);
	nAttr.setKeyable(false);
	stat = addAttribute( output );
		if (!stat) {stat.perror("addAttribute"); return stat;}


    // Connections
	stat = attributeAffects( trigoOperation, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	attributeAffects(angle, output);

   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_trigonometryAngle::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus returnStatus;

	if( plug != output )
		return MS::kUnknownParameter;

	// Input
	short   in_trigoOperation = data.inputValue( trigoOperation ).asShort();
	MAngle in_angle = data.inputValue(angle, &returnStatus).asAngle();


	double val;
	if (in_trigoOperation == 0)

		val = sin(in_angle.asRadians());
	else
		val = cos(in_angle.asRadians());

	// Output
	MDataHandle h_output = data.outputValue( output );
	h_output.setDouble(val);
	data.setClean(plug);

	return MS::kSuccess;
}

