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
MTypeId mgear_squashStretch2::id(0x0011FECC);

// Define the Node's attribute specifiers

MObject mgear_squashStretch2::global_scale;
MObject mgear_squashStretch2::global_scalex;
MObject mgear_squashStretch2::global_scaley;
MObject mgear_squashStretch2::global_scalez;

MObject mgear_squashStretch2::blend;
MObject mgear_squashStretch2::driver;
MObject mgear_squashStretch2::driver_min;
MObject mgear_squashStretch2::driver_ctr;
MObject mgear_squashStretch2::driver_max;

MObject mgear_squashStretch2::axis;
MObject mgear_squashStretch2::squash;
MObject mgear_squashStretch2::stretch;

MObject mgear_squashStretch2::output;

mgear_squashStretch2::mgear_squashStretch2() {} // constructor
mgear_squashStretch2::~mgear_squashStretch2() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_squashStretch2::SchedulingType mgear_squashStretch2::schedulingType() const
{
	return kParallel;
}

// CREATOR ======================================
void* mgear_squashStretch2::creator()
{
   return new mgear_squashStretch2();
}

// INIT =========================================
MStatus mgear_squashStretch2::initialize()
{
	MFnNumericAttribute nAttr;
	MFnEnumAttribute eAttr;
	MStatus stat;

    // Inputs
    global_scale = nAttr.createPoint("global_scale", "gs" );
    global_scalex = nAttr.child(0);
    global_scaley = nAttr.child(1);
    global_scalez = nAttr.child(2);
    nAttr.setWritable(true);
    nAttr.setStorable(true);
    nAttr.setReadable(true);
    nAttr.setKeyable(false);
    stat = addAttribute( global_scale );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// Sliders
	blend = nAttr.create("blend", "b", MFnNumericData::kFloat, 1);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(0);
    stat = addAttribute( blend );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	driver = nAttr.create("driver", "d", MFnNumericData::kFloat, 3);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( driver );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	driver_min = nAttr.create("driver_min", "dmin", MFnNumericData::kFloat, 1);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( driver_min );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	driver_ctr = nAttr.create("driver_ctr", "dctr", MFnNumericData::kFloat, 3);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( driver_ctr );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	driver_max = nAttr.create("driver_max", "dmax", MFnNumericData::kFloat, 6);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( driver_max );
		if (!stat) {stat.perror("addAttribute"); return stat;}

    axis = eAttr.create( "axis", "a", 0 );
    eAttr.addField("x", 0);
    eAttr.addField("y", 1);
    eAttr.addField("z", 2);
    eAttr.setWritable(true);
    eAttr.setStorable(true);
    eAttr.setReadable(true);
    eAttr.setKeyable(false);
    addAttribute( axis );

	squash = nAttr.create("squash", "sq", MFnNumericData::kFloat, .5);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(-1);
    stat = addAttribute( squash );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	stretch = nAttr.create("stretch", "st", MFnNumericData::kFloat, -.5);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(-1);
    stat = addAttribute( stretch );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// Outputs
	output = nAttr.createPoint("output", "out" );
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setReadable(true);
    addAttribute( output );

	// Connections
    stat = attributeAffects ( global_scale, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( blend, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( driver, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( driver_min, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( driver_ctr, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( driver_max, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( axis, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( squash, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects ( stretch, output );
		if (!stat) {stat.perror("attributeAffects"); return stat;}


   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_squashStretch2::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus returnStatus;
	// Error check
    if (plug != output)
        return MS::kUnknownParameter;

	// Inputs
    MVector gscale = data.inputValue( global_scale ).asFloatVector();
	double sx = gscale.x;
	double sy = gscale.y;
	double sz = gscale.z;

	// Sliders
	double in_blend = (double)data.inputValue( blend ).asFloat();
	double in_driver = (double)data.inputValue( driver ).asFloat();
	double in_dmin = (double)data.inputValue( driver_min ).asFloat();
	double in_dctr = (double)data.inputValue( driver_ctr ).asFloat();
	double in_dmax = (double)data.inputValue( driver_max ).asFloat();
	int in_axis = data.inputValue( axis ).asShort();
	double in_sq = (double)data.inputValue( squash ).asFloat();
	double in_st = (double)data.inputValue( stretch ).asFloat();

	// Process
    in_st *= clamp(std::max(in_driver - in_dctr, 0.0) / std::max(in_dmax - in_dctr, 0.0001), 0.0, 1.0);
    in_sq *= clamp(std::max(in_dctr - in_driver, 0.0) / std::max(in_dctr - in_dmin, 0.0001), 0.0, 1.0);

    if (in_axis != 0)
        sx *= std::max( 0.0, 1.0 + in_sq + in_st );

    if (in_axis != 1)
        sy *= std::max( 0.0, 1.0 + in_sq + in_st );

    if (in_axis != 2)
        sz *= std::max( 0.0, 1.0 + in_sq + in_st );

    MVector scl = MVector(sx, sy, sz);
    scl = linearInterpolate(gscale, scl, in_blend);

	double clamp_value = 0.0001;

	double scl_x = std::max(scl.x, clamp_value);
	double scl_y = std::max(scl.y, clamp_value);
	double scl_z = std::max(scl.z, clamp_value);

	// Output
	MDataHandle h = data.outputValue(output);
	h.set3Float((float)scl_x, (float)scl_y, (float)scl_z);
	data.setClean(plug);

	return MS::kSuccess;
}

