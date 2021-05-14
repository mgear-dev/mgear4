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
MTypeId		mgear_add10scalarNode::id(0x0011FEC0);

//Static variables

MObject		mgear_add10scalarNode::aOutValue;
MObject		mgear_add10scalarNode::aInValue0;
MObject 	mgear_add10scalarNode::aInValue1;
MObject 	mgear_add10scalarNode::aInValue2;
MObject 	mgear_add10scalarNode::aInValue3;
MObject 	mgear_add10scalarNode::aInValue4;
MObject 	mgear_add10scalarNode::aInValue5;
MObject 	mgear_add10scalarNode::aInValue6;
MObject 	mgear_add10scalarNode::aInValue7;
MObject 	mgear_add10scalarNode::aInValue8;
MObject 	mgear_add10scalarNode::aInValue9;



mgear_add10scalarNode::mgear_add10scalarNode()
{
}

mgear_add10scalarNode::~mgear_add10scalarNode()
{
}

mgear_add10scalarNode::SchedulingType mgear_add10scalarNode::schedulingType() const
{
	return kParallel;
}

void* mgear_add10scalarNode::creator()
{
	return new mgear_add10scalarNode();
}


/// INIT
MStatus mgear_add10scalarNode::initialize()
{
	MStatus status;
	MFnNumericAttribute nAttr;

	aOutValue = nAttr.create("outValue", "outValue", MFnNumericData::kFloat);
	nAttr.setWritable(false); // es un attribute de salida por eso bloqueamos que se pueda meter una conexion como input
	nAttr.setStorable(false); // lo mismo
	addAttribute(aOutValue);

	aInValue0 = nAttr.create("inValue0", "inValue0", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue0);
	attributeAffects(aInValue0, aOutValue);

	aInValue1 = nAttr.create("inValue1", "inValue1", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue1);
	attributeAffects(aInValue1, aOutValue);

	aInValue2 = nAttr.create("inValue2", "inValue2", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue2);
	attributeAffects(aInValue2, aOutValue);

	aInValue3 = nAttr.create("inValue3", "inValue3", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue3);
	attributeAffects(aInValue3, aOutValue);

	aInValue4 = nAttr.create("inValue4", "inValue4", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue4);
	attributeAffects(aInValue4, aOutValue);

	aInValue5 = nAttr.create("inValue5", "inValue5", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue5);
	attributeAffects(aInValue5, aOutValue);

	aInValue6 = nAttr.create("inValue6", "inValue6", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue6);
	attributeAffects(aInValue6, aOutValue);

	aInValue7 = nAttr.create("inValue7", "inValue7", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue7);
	attributeAffects(aInValue7, aOutValue);

	aInValue8 = nAttr.create("inValue8", "inValue8", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue8);
	attributeAffects(aInValue8, aOutValue);

	aInValue9 = nAttr.create("inValue9", "inValue9", MFnNumericData::kFloat);
	nAttr.setKeyable(true);
	addAttribute(aInValue9);
	attributeAffects(aInValue9, aOutValue);



	return MS::kSuccess;
}

// COMPUTE

MStatus mgear_add10scalarNode::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus status;

	if (plug != aOutValue)
	{
		return MS::kUnknownParameter;
	}

	// preparing the values from the attributes
	float inputValue0 = data.inputValue(aInValue0, &status).asFloat();
	float inputValue1 = data.inputValue(aInValue1, &status).asFloat();
	float inputValue2 = data.inputValue(aInValue2, &status).asFloat();
	float inputValue3 = data.inputValue(aInValue3, &status).asFloat();
	float inputValue4 = data.inputValue(aInValue4, &status).asFloat();
	float inputValue5 = data.inputValue(aInValue5, &status).asFloat();
	float inputValue6 = data.inputValue(aInValue6, &status).asFloat();
	float inputValue7 = data.inputValue(aInValue7, &status).asFloat();
	float inputValue8 = data.inputValue(aInValue8, &status).asFloat();
	float inputValue9 = data.inputValue(aInValue9, &status).asFloat();



	// making the calculation

	float output = inputValue0 + inputValue1 + inputValue2 + inputValue3 + inputValue4 + inputValue5 + inputValue6 + inputValue7 + inputValue8 + inputValue9;

	MDataHandle hOutput = data.outputValue(aOutValue, &status);      //lower "h" for indicate that the variable is a handle
	McheckStatusAndReturnIt(status); // mirar este statment en la documentacion de Maya
	hOutput.setFloat(output);
	hOutput.setClean();
	data.setClean(plug); // Esta linea es un ejemplo. hace lo mismo que la anteriro ya que el pointer apunta
			// a la mis memoria. pero trabajar con handles es mas rapido que con el plug directamente.

	return MS::kSuccess;
}
