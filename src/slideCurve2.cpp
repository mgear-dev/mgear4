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
MTypeId mgear_slideCurve2::id(0x0011FECA);

MObject mgear_slideCurve2::master_crv;
MObject mgear_slideCurve2::master_mat;

MObject mgear_slideCurve2::slave_length;
MObject mgear_slideCurve2::master_length;
MObject mgear_slideCurve2::position;
MObject mgear_slideCurve2::maxstretch;
MObject mgear_slideCurve2::maxsquash;
MObject mgear_slideCurve2::softness;

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_slideCurve2::SchedulingType mgear_slideCurve2::schedulingType() const
{
	return kParallel;
}

// CREATOR ======================================
void* mgear_slideCurve2::creator() { return new mgear_slideCurve2; }

// INIT =========================================
MStatus mgear_slideCurve2::initialize()
{
	MFnTypedAttribute tAttr;
	MFnMatrixAttribute mAttr;
	MFnNumericAttribute nAttr;
	MStatus stat;

	// INPUTS MESH

    master_crv = tAttr.create("master_crv", "mcrv", MFnData::kNurbsCurve);
    stat = addAttribute( master_crv );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	master_mat = mAttr.create( "master_mat", "mmat" );
	mAttr.setStorable(true);
    mAttr.setReadable(false);
	stat = addAttribute( master_mat );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// SLIDERS
	slave_length = nAttr.create("slave_length", "sl", MFnNumericData::kFloat, 1);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( slave_length );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	master_length = nAttr.create("master_length", "ml", MFnNumericData::kFloat, 1);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
    stat = addAttribute( master_length );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	position = nAttr.create("position", "p", MFnNumericData::kFloat, 0.0);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(0);
	nAttr.setMax(1);
    stat = addAttribute( position );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	maxstretch = nAttr.create("maxstretch", "mst", MFnNumericData::kFloat, 1.5);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(1);
    stat = addAttribute( maxstretch );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	maxsquash = nAttr.create("maxsquash", "msq", MFnNumericData::kFloat, .5);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(0);
	nAttr.setMax(1);
    stat = addAttribute( maxsquash );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	softness = nAttr.create("softness", "s", MFnNumericData::kFloat, 0.5);
	nAttr.setStorable(true);
	nAttr.setKeyable(true);
	nAttr.setMin(0);
	nAttr.setMax(1);
    stat = addAttribute( softness );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// CONNECTIONS
	stat = attributeAffects( master_crv, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( master_mat, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

	stat = attributeAffects( master_length, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( slave_length, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( position, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( maxstretch, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( maxsquash, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( softness, outputGeom );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

    return MS::kSuccess;
}

// COMPUTE ======================================
MStatus mgear_slideCurve2::deform( MDataBlock& data, MItGeometry& iter, const MMatrix &mat, unsigned int /* mIndex */ )
{
    MStatus returnStatus;

    // Inputs ---------------------------------------------------------
    // Input NurbsCurve
	// Curve
    MObject crvObj = data.inputValue( master_crv ).asNurbsCurve();
	MFnNurbsCurve crv(crvObj);
    MMatrix m = data.inputValue(master_mat).asMatrix();

    // Input Sliders
    double in_sl = (double)data.inputValue(slave_length).asFloat();
    double in_ml = (double)data.inputValue(master_length).asFloat();
    double in_position = (double)data.inputValue(position).asFloat();
    double in_maxstretch = (double)data.inputValue(maxstretch).asFloat();
	double in_maxsquash = (double)data.inputValue(maxsquash).asFloat();
    double in_softness = (double)data.inputValue(softness).asFloat();

    // Init -----------------------------------------------------------
    double mstCrvLength = crv.length();

    int slvPointCount = iter.exactCount(); // Can we use .count() ?
    int mstPointCount = crv.numCVs();

    // Stretch --------------------------------------------------------
	double expo = 1;
    if ((mstCrvLength > in_ml) && (in_maxstretch > 1)){
        if (in_softness != 0){
            double stretch = (mstCrvLength - in_ml) / (in_sl * in_maxstretch);
            expo = 1 - exp(-(stretch) / in_softness);
		}

        double ext = std::min(in_sl * (in_maxstretch - 1) * expo, mstCrvLength - in_ml);

        in_sl += ext;
	}
    else if ((mstCrvLength < in_ml) && (in_maxsquash < 1)){
        if (in_softness != 0){
            double squash = (in_ml - mstCrvLength) / (in_sl * in_maxsquash);
            expo = 1 - exp(-(squash) / in_softness);
		}

        double ext = std::min(in_sl * (1 - in_maxsquash) * expo, in_ml - mstCrvLength);

        in_sl -= ext;
	}

    // Position --------------------------------------------------------
    double size = in_sl / mstCrvLength;
    double sizeLeft = 1 - size;

    double start = in_position * sizeLeft;
    double end = start + size;

	double tStart, tEnd;
	crv.getKnotDomain(tStart, tEnd);

    // Process --------------------------------------------------------
    double step = (end - start) / (slvPointCount - 1.0);
    MPoint pt;
	MVector tan;
    while (! iter.isDone()){
        double perc = start + (iter.index() * step);

        double u = crv.findParamFromLength(perc * mstCrvLength);

        if ((0 <= perc) && (perc <= 1))
            crv.getPointAtParam(u, pt, MSpace::kWorld);
        else{
			double overPerc;
            if (perc < 0){
                overPerc = perc;
                crv.getPointAtParam(0, pt, MSpace::kWorld);
                tan = crv.tangent(0);
			}
            else{
                overPerc = perc - 1;
                crv.getPointAtParam(mstPointCount-3.0, pt, MSpace::kWorld);
                tan = crv.tangent(mstPointCount-3.0);

            tan.normalize();
            tan *= mstCrvLength * overPerc;

            pt += tan;
			}
		}

        pt *= mat.inverse();
        pt *= m;
        iter.setPosition(pt);
        iter.next();
	}

    return MS::kSuccess;
}

