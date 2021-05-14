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
MTypeId mgear_percentageToU::id(0x0011FEC8);

// Define the Node's attribute specifiers

MObject mgear_percentageToU::curve;
MObject mgear_percentageToU::normalizedU;
MObject mgear_percentageToU::percentage;
MObject mgear_percentageToU::steps;
MObject mgear_percentageToU::u;

mgear_percentageToU::mgear_percentageToU() {} // constructor
mgear_percentageToU::~mgear_percentageToU() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_percentageToU::SchedulingType mgear_percentageToU::schedulingType() const
{
	return kParallel;
}

// CREATOR ======================================
void* mgear_percentageToU::creator()
{
   return new mgear_percentageToU();
}

// INIT =========================================
MStatus mgear_percentageToU::initialize()
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

	percentage = nAttr.create( "percentage", "p", MFnNumericData::kFloat, 0 );
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( percentage );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    steps = nAttr.create("steps", "s", MFnNumericData::kShort, 40);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( steps );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Outputs
    u = nAttr.create("u", "u", MFnNumericData::kFloat, .5, 0);
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setReadable(true);
    nAttr.setKeyable(false);
    stat = addAttribute( u );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    // Connections
    stat = attributeAffects ( curve, u );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( steps, u );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( percentage, u );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( normalizedU, u );
		if (!stat) {stat.perror("attributeAffects"); return stat;}


   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_percentageToU::compute(const MPlug& plug, MDataBlock& data)
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
	double in_percentage = (double)data.inputValue( percentage ).asFloat() * .01;
	const unsigned in_steps = data.inputValue( steps ).asShort();

	// Process
	// Get length
	MVectorArray u_subpos(in_steps);
	MPoint pt;
	MDoubleArray u_list(in_steps);
	for(unsigned i = 0 ; i < in_steps ; i++ ){
		u_list[i] = normalizedUToU(i /(in_steps - 1.0), crv.numCVs());

		crv.getPointAtParam(u_list[i], pt, MSpace::kWorld);
		u_subpos[i] = MVector(pt);
	}


	double t_length = 0;
	MDoubleArray dist(in_steps);
	MVector v;
	for (unsigned i = 0; i < in_steps ; i++){
		if (i>0){
			v = u_subpos[i] - u_subpos[i-1];
			t_length += v.length();
			dist[i] = t_length;
		}
	}

	MDoubleArray u_perc(in_steps);
	for (unsigned i = 0; i < in_steps ; i++){
		u_perc[i] = dist[i] / t_length;
	}

	double out_u = 0.0;

	// Get closest indices
	unsigned index = findClosestInArray(in_percentage, u_perc);
	if (index != (unsigned)-1) {
		unsigned indexA, indexB;
		if (in_percentage <= u_perc[index]){
			indexA = abs(int(index));
			indexB = index;
			if ( indexA > indexB){
				indexA = indexB;
				indexB = indexA+1;
			}
		}
		else {
			indexA = index;
			indexB = index + 1;
		}

		// blend value
		double blend = set01range(in_percentage, u_perc[indexA], u_perc[indexB]);

		out_u = linearInterpolate(u_list[indexA], u_list[indexB], blend);

		if (in_normU)
			out_u = uToNormalizedU(out_u, crv.numCVs());
	}

	// Ouput
	MDataHandle h = data.outputValue( u );
	h.setDouble( out_u );
	data.setClean( plug );

	return MS::kSuccess;
}

