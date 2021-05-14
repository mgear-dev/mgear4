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
MTypeId mgear_inverseRotOrder::id(0x0011FEC5);

// Define the Node's attribute specifiers

MObject mgear_inverseRotOrder::rotOrder;
MObject mgear_inverseRotOrder::output;

mgear_inverseRotOrder::mgear_inverseRotOrder() {} // constructor
mgear_inverseRotOrder::~mgear_inverseRotOrder() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_inverseRotOrder::SchedulingType mgear_inverseRotOrder::schedulingType() const
{
	return kParallel;
}

// CREATOR ======================================
void* mgear_inverseRotOrder::creator()
{
   return new mgear_inverseRotOrder();
}

// INIT =========================================
MStatus mgear_inverseRotOrder::initialize()
{
   MFnNumericAttribute nAttr;
   MFnEnumAttribute eAttr;
   MStatus stat;

    // Inputs
    rotOrder = eAttr.create( "rotOrder", "ro", 0 );
    eAttr.addField("xyz", 0);
    eAttr.addField("yzx", 1);
    eAttr.addField("zxy", 2);
    eAttr.addField("xzy", 3);
    eAttr.addField("yxz", 4);
    eAttr.addField("zyx", 5);
    eAttr.setWritable(true);
    eAttr.setStorable(true);
    eAttr.setReadable(true);
    eAttr.setKeyable(true);
	stat = addAttribute( rotOrder );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Outputs
	output = nAttr.create( "output", "out", MFnNumericData::kShort, 0 );
	nAttr.setWritable(false);
	nAttr.setStorable(true);
    nAttr.setReadable(true);
	nAttr.setKeyable(false);
	stat = addAttribute( output );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Connections
	stat = attributeAffects( rotOrder, output );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_inverseRotOrder::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus returnStatus;

	if( plug != output )
		return MS::kUnknownParameter;

	// Input
	int ro  = data.inputValue( rotOrder ).asShort();
	int inv_ro [6] = {5, 3, 4, 1, 2, 0};

	// Output
	MDataHandle h_output = data.outputValue( output );
	h_output.setShort(inv_ro[ro]);
	data.setClean(plug);

	return MS::kSuccess;
}

