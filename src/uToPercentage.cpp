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
MTypeId mgear_uToPercentage::id(0x0011FECD);

// Define the Node's attribute specifiers

MObject mgear_uToPercentage::curve;
MObject mgear_uToPercentage::normalizedU;
MObject mgear_uToPercentage::u;
MObject mgear_uToPercentage::steps;
MObject mgear_uToPercentage::percentage;

mgear_uToPercentage::mgear_uToPercentage() {} // constructor
mgear_uToPercentage::~mgear_uToPercentage() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_uToPercentage::SchedulingType mgear_uToPercentage::schedulingType() const
{
	return kParallel;
}

// CREATOR ======================================
void* mgear_uToPercentage::creator()
{
   return new mgear_uToPercentage();
}

// INIT =========================================
MStatus mgear_uToPercentage::initialize()
{
	MFnTypedAttribute tAttr;
	MFnNumericAttribute nAttr;
	MStatus stat;

    // Curve
    curve = tAttr.create("curve", "crv", MFnData::kNurbsCurve);
    stat = addAttribute( curve );
		if (!stat) {stat.perror("addAttribute"); return stat;}


   // Sliders
    normalizedU = nAttr.create("normalizedU", "n", MFnNumericData::kBoolean, false);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( normalizedU );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    u = nAttr.create("u", "u", MFnNumericData::kFloat, .5, 0);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( u );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    steps = nAttr.create("steps", "s", MFnNumericData::kShort, 40);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( steps );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Outputs
	percentage = nAttr.create( "percentage", "p", MFnNumericData::kFloat, 0 );
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setReadable(true);
    nAttr.setKeyable(false);
    stat = addAttribute( percentage );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Connections
    stat = attributeAffects ( curve, percentage );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( steps, percentage );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( u, percentage );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( normalizedU, percentage );
		if (!stat) {stat.perror("attributeAffects"); return stat;}



   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_uToPercentage::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus returnStatus;
	// Error check
    if (plug != percentage)
        return MS::kUnknownParameter;

	// Curve
   MObject crvObj = data.inputValue( curve ).asNurbsCurve();

	MFnNurbsCurve crv(crvObj);

	// Sliders
	bool in_normU = data.inputValue( normalizedU ).asBool();
	double in_u = (double)data.inputValue( u ).asFloat();
	unsigned in_steps = data.inputValue( steps ).asShort();

	// Process
	if (in_normU)
		in_u = normalizedUToU(in_u, crv.numCVs());

	// Get length
	MVectorArray u_subpos(in_steps);
	MVectorArray t_subpos(in_steps);
	MPoint pt;
	double step;
	for (unsigned i = 0; i < in_steps ; i++){

		step = i * in_u / (in_steps - 1.0);
		crv.getPointAtParam(step, pt, MSpace::kWorld);
		u_subpos[i] = MVector(pt);

        step = i/(in_steps - 1.0);
		crv.getPointAtParam(step, pt, MSpace::kWorld);
		t_subpos[i] = MVector(pt);

	}

	double u_length = 0;
	double t_length = 0;
	MVector v;
	for (unsigned i = 0; i < in_steps ; i++){
		if (i>0){
			v = u_subpos[i] - u_subpos[i-1];
			u_length += v.length();
			v = t_subpos[i] - t_subpos[i-1];
			t_length += v.length();
		}
	}

	double out_perc = (u_length / t_length) * 100;

	// Output
    MDataHandle h = data.outputValue( percentage );
    h.setDouble( out_perc );
    data.setClean( plug );

	return MS::kSuccess;
}

