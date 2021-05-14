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
MTypeId mgear_ikfk2Bone::id(0x0011FEC3);

// Define the Node's attribute specifiers

MObject mgear_ikfk2Bone::blend;

MObject mgear_ikfk2Bone::lengthA;
MObject mgear_ikfk2Bone::lengthB;
MObject mgear_ikfk2Bone::negate;
MObject mgear_ikfk2Bone::scaleA;
MObject mgear_ikfk2Bone::scaleB;
MObject mgear_ikfk2Bone::roll;
MObject mgear_ikfk2Bone::maxstretch;
MObject mgear_ikfk2Bone::slide;
MObject mgear_ikfk2Bone::softness;
MObject mgear_ikfk2Bone::reverse;

MObject mgear_ikfk2Bone::root;
MObject mgear_ikfk2Bone::ikref;
MObject mgear_ikfk2Bone::upv;
MObject mgear_ikfk2Bone::fk0;
MObject mgear_ikfk2Bone::fk1;
MObject mgear_ikfk2Bone::fk2;

MObject mgear_ikfk2Bone::inAparent;
MObject mgear_ikfk2Bone::inBparent;
MObject mgear_ikfk2Bone::inCenterparent;
MObject mgear_ikfk2Bone::inEffparent;

MObject mgear_ikfk2Bone::outA;
MObject mgear_ikfk2Bone::outB;
MObject mgear_ikfk2Bone::outCenter;
MObject mgear_ikfk2Bone::outEff;

mgear_ikfk2Bone::mgear_ikfk2Bone() {} // constructor
mgear_ikfk2Bone::~mgear_ikfk2Bone() {} // destructor

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

// CREATOR ======================================
mgear_ikfk2Bone::SchedulingType mgear_ikfk2Bone::schedulingType() const
{
	return kParallel;
}

void* mgear_ikfk2Bone::creator()
{
   return new mgear_ikfk2Bone();
}

// INIT =========================================
MStatus mgear_ikfk2Bone::initialize()
{
   MFnNumericAttribute nAttr;
   MFnMatrixAttribute mAttr;
   MStatus	 stat;

   // ATTRIBUTES
   blend = nAttr.create( "blend", "b", MFnNumericData::kFloat, 0.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
   nAttr.setMin(0);
   nAttr.setMax(1);
	stat = addAttribute( blend );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   lengthA = nAttr.create( "lengthA", "lA", MFnNumericData::kFloat, 0.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( lengthA );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   lengthB = nAttr.create( "lengthB", "lB", MFnNumericData::kFloat, 0.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( lengthB );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   negate = nAttr.create( "negate", "n", MFnNumericData::kBoolean, false );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( negate );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   scaleA = nAttr.create( "scaleA", "sA", MFnNumericData::kFloat, 1.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( scaleA );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   scaleB = nAttr.create( "scaleB", "sB", MFnNumericData::kFloat, 1.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( scaleB );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   roll = nAttr.create( "roll", "r", MFnNumericData::kFloat, 0.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( roll );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   maxstretch = nAttr.create( "maxstretch", "ms", MFnNumericData::kFloat, 1.5 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( maxstretch );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   slide = nAttr.create( "slide", "sl", MFnNumericData::kFloat, 0.5 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( slide );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   softness = nAttr.create( "softness", "so", MFnNumericData::kFloat, 0.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( softness );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   reverse = nAttr.create( "reverse", "re", MFnNumericData::kFloat, 0.0 );
   nAttr.setStorable(true);
   nAttr.setKeyable(true);
	stat = addAttribute( reverse );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   // INPUTS
   root = mAttr.create( "root", "root" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( root );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   ikref = mAttr.create( "ikref", "ikref" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( ikref );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   upv = mAttr.create( "upv", "upv" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( upv );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   fk0 = mAttr.create( "fk0", "fk0" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( fk0 );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   fk1 = mAttr.create( "fk1", "fk1" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( fk1 );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   fk2 = mAttr.create( "fk2", "fk2" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( fk2 );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   inAparent = mAttr.create( "inAparent", "inAparent" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( inAparent );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   inBparent = mAttr.create( "inBparent", "inBparent" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( inBparent );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   inCenterparent = mAttr.create( "inCenterparent", "inCenterparent" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( inCenterparent );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   inEffparent = mAttr.create( "inEffparent", "inEffparent" );
   mAttr.setStorable(true);
   mAttr.setKeyable(true);
   mAttr.setConnectable(true);
	stat = addAttribute( inEffparent );
		if (!stat) {stat.perror("addAttribute"); return stat;}

   // OUTPUTS
	outA = mAttr.create( "outA", "outA" );
	mAttr.setStorable(false);
	mAttr.setKeyable(false);
	mAttr.setConnectable(true);
	stat = addAttribute( outA );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	outB = mAttr.create( "outB", "outB" );
	mAttr.setStorable(false);
	mAttr.setKeyable(false);
	mAttr.setConnectable(true);
	stat = addAttribute( outB );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	outCenter = mAttr.create( "outCenter", "outCenter" );
	mAttr.setStorable(false);
	mAttr.setKeyable(false);
	mAttr.setConnectable(true);
	stat = addAttribute( outCenter );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	outEff = mAttr.create( "outEff", "outEff" );
	mAttr.setStorable(false);
	mAttr.setKeyable(false);
	mAttr.setConnectable(true);
	stat = addAttribute( outEff );
		if (!stat) {stat.perror("addAttribute"); return stat;}

	// Attributes Affects
	stat = attributeAffects( blend, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthA, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthB, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( negate, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleA, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleB, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( roll, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( maxstretch, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( slide, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( softness, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( reverse, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( root, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( ikref, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( upv, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk0, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk1, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk2, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inAparent, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inBparent, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inCenterparent, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inEffparent, outA );
		if (!stat) { stat.perror("attributeAffects"); return stat;}


	stat = attributeAffects( blend, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthA, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthB, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( negate, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleA, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleB, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( roll, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( maxstretch, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( slide, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( softness, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( reverse, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( root, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( ikref, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( upv, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk0, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk1, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk2, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inAparent, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inBparent, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inCenterparent, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inEffparent, outB );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

	stat = attributeAffects( blend, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthA, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthB, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( negate, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleA, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleB, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( roll, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( maxstretch, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( slide, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( softness, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( reverse, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( root, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( ikref, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( upv, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk0, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk1, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk2, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inAparent, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inBparent, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inCenterparent, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inEffparent, outCenter );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

	stat = attributeAffects( blend, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthA, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( lengthB, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( negate, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleA, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( scaleB, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( roll, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( maxstretch, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( slide, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( softness, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( reverse, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( root, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( ikref, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( upv, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk0, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk1, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( fk2, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inAparent, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inBparent, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inCenterparent, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}
	stat = attributeAffects( inEffparent, outEff );
		if (!stat) { stat.perror("attributeAffects"); return stat;}

   return MS::kSuccess;
}
// COMPUTE ======================================
MStatus mgear_ikfk2Bone::compute(const MPlug& plug, MDataBlock& data)
{
   MStatus returnStatus;

	// INPUT MATRICES
	MMatrix in_root = data.inputValue( root, &returnStatus ).asMatrix();
	MMatrix in_ikref = data.inputValue( ikref, &returnStatus ).asMatrix();
	MMatrix in_upv = data.inputValue( upv, &returnStatus ).asMatrix();
	MMatrix in_fk0 = data.inputValue( fk0, &returnStatus ).asMatrix();
	MMatrix in_fk1 = data.inputValue( fk1, &returnStatus ).asMatrix();
	MMatrix in_fk2 = data.inputValue( fk2, &returnStatus ).asMatrix();

	MMatrix in_aParent = data.inputValue( inAparent, &returnStatus ).asMatrix();
	MMatrix in_bParent = data.inputValue( inBparent, &returnStatus ).asMatrix();
	MMatrix in_centerParent = data.inputValue( inCenterparent, &returnStatus ).asMatrix();
	MMatrix in_effParent = data.inputValue( inEffparent, &returnStatus ).asMatrix();

	// SLIDERS
	double in_blend = (double)data.inputValue( blend ).asFloat();

	// setup the base IK parameters
	s_GetIKTransform ikparams;

	ikparams.root = in_root;
	ikparams.eff = in_ikref;
	ikparams.upv = in_upv;

	ikparams.lengthA = (double)data.inputValue( lengthA ).asFloat();
	ikparams.lengthB = (double)data.inputValue( lengthB ).asFloat();
	ikparams.negate = data.inputValue( negate ).asBool();
	ikparams.roll = degrees2radians((double)data.inputValue( roll ).asFloat());
	ikparams.scaleA = (double)data.inputValue( scaleA ).asFloat();
	ikparams.scaleB = (double)data.inputValue( scaleB ).asFloat();
	ikparams.maxstretch = (double)data.inputValue( maxstretch ).asFloat();
	ikparams.softness = (double)data.inputValue( softness ).asFloat();
	ikparams.slide = (double)data.inputValue( slide ).asFloat();
	ikparams.reverse = (double)data.inputValue( reverse ).asFloat();

	// setup the base FK parameters
	s_GetFKTransform fkparams;

	fkparams.root = in_root;
	fkparams.bone1 = in_fk0;
	fkparams.bone2 = in_fk1;
	fkparams.eff = in_fk2;

	fkparams.lengthA = ikparams.lengthA;
	fkparams.lengthB = ikparams.lengthB;
	fkparams.negate = ikparams.negate;

	MStringArray outNameArray;
	plug.name().split('.', outNameArray);
	MString outName = outNameArray[outNameArray.length() - 1];

	MTransformationMatrix result;
	if(in_blend == 0.0)
		result = getFKTransform(fkparams, outName);
	else if(in_blend == 1.0)
		result = getIKTransform(ikparams, outName);
	else{
		// here is where the blending happens!
        MTransformationMatrix ikbone1 = getIKTransform(ikparams, "outA");
        MTransformationMatrix ikbone2 = getIKTransform(ikparams, "outB");
        MTransformationMatrix ikeff = getIKTransform(ikparams, "outEff");

        MTransformationMatrix fkbone1 = getFKTransform(fkparams, "outA");
        MTransformationMatrix fkbone2 = getFKTransform(fkparams, "outB");
        MTransformationMatrix fkeff = getFKTransform(fkparams, "outEff");

        // remove scale to avoid shearing issue
        // This is not necessary in Softimage because the scaling hierarchy is not computed the same way.
		double noScale[3] = {1,1,1};
		ikbone1.setScale(noScale, MSpace::kWorld);
		ikbone2.setScale(noScale, MSpace::kWorld);
		ikeff.setScale(noScale, MSpace::kWorld);
		fkbone1.setScale(noScale, MSpace::kWorld);
		fkbone2.setScale(noScale, MSpace::kWorld);
		fkeff.setScale(noScale, MSpace::kWorld);

        // map the secondary transforms from global to local
        ikeff = mapWorldPoseToObjectSpace(ikbone2, ikeff);
        fkeff = mapWorldPoseToObjectSpace(fkbone2, fkeff);
        ikbone2 = mapWorldPoseToObjectSpace(ikbone1, ikbone2);
        fkbone2 = mapWorldPoseToObjectSpace(fkbone1, fkbone2);

        // now blend them!
		fkparams.bone1 = interpolateTransform(fkbone1, ikbone1, in_blend);
		fkparams.bone2 = interpolateTransform(fkbone2, ikbone2, in_blend);
		fkparams.eff = interpolateTransform(fkeff, ikeff, in_blend);


        // now map the local transform back to global!
		fkparams.bone2 = mapObjectPoseToWorldSpace(fkparams.bone1, fkparams.bone2);
        fkparams.eff = mapObjectPoseToWorldSpace(fkparams.bone2, fkparams.eff);

        // calculate the result based on that
        result = getFKTransform(fkparams, outName);
	}

    // Output
	MDataHandle h;
    if (plug == outA){
        h = data.outputValue( outA );
        h.setMMatrix( result.asMatrix() * in_aParent.inverse() );

        data.setClean( plug );
	}
    else if (plug == outB){
        h = data.outputValue( outB );
        h.setMMatrix( result.asMatrix() *  in_bParent.inverse() );
        data.setClean( plug );
	}
    else if (plug == outCenter){
        h = data.outputValue( outCenter );
        h.setMMatrix( result.asMatrix() * in_centerParent.inverse() );

        data.setClean( plug );
	}
    else if (plug == outEff){
        h = data.outputValue( outEff );
        h.setMMatrix( result.asMatrix() * in_effParent.inverse() );

        data.setClean( plug );
	}
    else
        return MStatus::kUnknownParameter;

   return MS::kSuccess;
}

MTransformationMatrix mgear_ikfk2Bone::getIKTransform(s_GetIKTransform data, MString name){

    // prepare all variables
	MTransformationMatrix result;
	MVector bonePos, rootPos, effPos, upvPos, rootEff, xAxis, yAxis, zAxis, rollAxis;

    rootPos = data.root.getTranslation(MSpace::kWorld);
    effPos = data.eff.getTranslation(MSpace::kWorld);
    upvPos = data.upv.getTranslation(MSpace::kWorld);
    rootEff = effPos - rootPos;
    rollAxis = rootEff.normal();

    double rootEffDistance = rootEff.length();

    // init the scaling
	double scale[3];
	data.root.getScale(scale, MSpace::kWorld);
	double global_scale = scale[0];

	result.setScale(scale, MSpace::kWorld);

    // Distance with MaxStretch ---------------------
    double restLength = (data.lengthA * data.scaleA + data.lengthB * data.scaleB) * global_scale;
    double distance = rootEffDistance;
    double distance2 = distance;
    if (distance > (restLength * data.maxstretch))
        distance = restLength * data.maxstretch;

    // Adapt Softness value to chain length --------
    data.softness = data.softness * restLength * .1;

    // Stretch and softness ------------------------
    // We use the real distance from root to controler to calculate the softness
    // This way we have softness working even when there is no stretch
    double stretch = std::max(1.0, distance / restLength);
    double da = restLength - data.softness;
    if ((data.softness > 0) && (distance2 > da)){
        double newlen = data.softness*(1.0 - exp(-(distance2 -da)/data.softness)) + da;
        stretch = distance / newlen;
	}

    data.lengthA = data.lengthA * stretch * data.scaleA * global_scale;
    data.lengthB = data.lengthB * stretch * data.scaleB * global_scale;

    // Reverse -------------------------------------
    double d = distance / (data.lengthA + data.lengthB);

	double reverse_scale;
    if (data.reverse < 0.5)
        reverse_scale = 1-(data.reverse*2 * (1-d));
    else
        reverse_scale = 1-((1-data.reverse)*2 * (1-d));

    data.lengthA *= reverse_scale;
    data.lengthB *= reverse_scale;

    bool invert = data.reverse > 0.5;

    // Slide ---------------------------------------
	double slide_add;
    if (data.slide < .5)
        slide_add = (data.lengthA * (data.slide * 2)) - (data.lengthA);
    else
        slide_add = (data.lengthB * (data.slide * 2)) - (data.lengthB);

    data.lengthA += slide_add;
    data.lengthB -= slide_add;

    // calculate the angle inside the triangle!
    double angleA = 0;
    double angleB = 0;

    // check if the divider is not null otherwise the result is nan
    // and the output disapear from xsi, that breaks constraints
    if ((rootEffDistance < data.lengthA + data.lengthB) && (rootEffDistance > abs(data.lengthA - data.lengthB) + 1E-6)){

        // use the law of cosine for lengthA
        double a = data.lengthA;
        double b = rootEffDistance;
        double c = data.lengthB;

        angleA = acos(std::min(1.0, (a * a + b * b - c * c ) / ( 2 * a * b)));

        // use the law of cosine for lengthB
        a = data.lengthB;
        b = data.lengthA;
        c = rootEffDistance;
        angleB = acos(std::min(1.0, (a * a + b * b - c * c ) / ( 2 * a * b)));

        // invert the angles if need be
        if (invert){
            angleA = -angleA;
            angleB = -angleB;
		}
	}

    // start with the X and Z axis
    xAxis = rootEff;
    xAxis.normalize();
    yAxis = linearInterpolate(rootPos, effPos, .5);
    yAxis = upvPos - yAxis;
    yAxis.normalize();
    yAxis = rotateVectorAlongAxis(yAxis, rollAxis, data.roll);
    zAxis = xAxis ^ yAxis;
    zAxis.normalize();
    yAxis = zAxis ^ xAxis;
    yAxis.normalize();

    // switch depending on our mode
    if (name == "outA"){

        // check if we need to rotate the bone
        if (angleA != 0.0)
            xAxis = rotateVectorAlongAxis(xAxis, zAxis, -angleA);

        if (data.negate)
            xAxis *= -1;
        // cross the yAxis and normalize
        yAxis = zAxis ^ xAxis;
        yAxis.normalize();

        // output the rotation
        MQuaternion q = getQuaternionFromAxes(xAxis,yAxis,zAxis);
        result.setRotationQuaternion(q.x, q.y, q.z, q.w);

        // set the scaling + the position
		double s[3] = {data.lengthA, global_scale, global_scale};
		result.setScale(s, MSpace::kWorld);
        result.setTranslation(rootPos, MSpace::kWorld);
	}
    else if (name == "outB"){

        // check if we need to rotate the bone
        if (angleA != 0.0)
            xAxis = rotateVectorAlongAxis(xAxis, zAxis, -angleA);

        // calculate the position of the elbow!
        bonePos = xAxis * data.lengthA;
        bonePos += rootPos;

        // check if we need to rotate the bone
        if (angleB != 0.0)
            xAxis = rotateVectorAlongAxis(xAxis, zAxis, -(angleB - PI));

        if (data.negate)
            xAxis *= -1;

        // cross the yAxis and normalize
        yAxis = zAxis ^ xAxis;
        yAxis.normalize();

        // output the rotation
        MQuaternion q = getQuaternionFromAxes(xAxis,yAxis,zAxis);
        result.setRotationQuaternion(q.x, q.y, q.z, q.w);

        // set the scaling + the position
		double s[3] = {data.lengthB, global_scale, global_scale};
		result.setScale(s, MSpace::kWorld);
        result.setTranslation(bonePos, MSpace::kWorld);
	}
    else if (name == "outCenter"){

        // check if we need to rotate the bone
        if (angleA != 0.0)
            xAxis = rotateVectorAlongAxis(xAxis, zAxis, -angleA);

        // calculate the position of the elbow!
        bonePos = xAxis * data.lengthA;
        bonePos += rootPos;

        // check if we need to rotate the bone
        if (angleB != 0.0){
            if (invert){
                angleB += PI * 2;
			}
            xAxis = rotateVectorAlongAxis(xAxis, zAxis, -(angleB *.5 - PI*.5));
		}


        // cross the yAxis and normalize
        // yAxis.Sub(upvPos,bonePos); // this was flipping the centerN when the elbow/upv was aligned to root/eff
        zAxis = xAxis ^ yAxis;
        zAxis.normalize();

        if (data.negate)
            xAxis *= -1;

        yAxis = zAxis ^ xAxis;
        yAxis.normalize();

        // output the rotation
        MQuaternion q = getQuaternionFromAxes(xAxis,yAxis,zAxis);
        result.setRotationQuaternion(q.x, q.y, q.z, q.w);

        // set the scaling + the position
        // result.SetSclX(stretch * data["root.GetSclX());

        result.setTranslation(bonePos, MSpace::kWorld);
	}

    else if (name == "outEff"){

        // check if we need to rotate the bone
        effPos = rootPos;
        if (angleA != 0.0)
            xAxis = rotateVectorAlongAxis(xAxis, zAxis, -angleA);

        // calculate the position of the elbow!
        bonePos = xAxis * data.lengthA;
        effPos += bonePos;

        // check if we need to rotate the bone
        if (angleB != 0.0)
            xAxis = rotateVectorAlongAxis(xAxis, zAxis, -(angleB - PI));

        // calculate the position of the effector!
        bonePos = xAxis * data.lengthB;
        effPos += bonePos;

        // output the rotation
        result = data.eff;
        result.setTranslation(effPos, MSpace::kWorld);
	}

    return result;
}

MTransformationMatrix mgear_ikfk2Bone::getFKTransform(s_GetFKTransform data, MString name){

	// prepare all variables
	MTransformationMatrix result;

	MVector xAxis, yAxis, zAxis;

	if (name == "outA"){
		result = data.bone1;
		xAxis = data.bone2.getTranslation(MSpace::kWorld) - data.bone1.getTranslation(MSpace::kWorld);

		double scale[3] = {xAxis.length(), 1.0, 1.0};
		result.setScale(scale, MSpace::kWorld);

		if (data.negate)
			xAxis *= -1;

		// cross the yAxis and normalize
		xAxis.normalize();

		zAxis = MVector(0,0,1);
		zAxis = zAxis.rotateBy(data.bone1.rotation());
		yAxis = zAxis ^ xAxis;

		// rotation
		MQuaternion q = getQuaternionFromAxes(xAxis,yAxis,zAxis);
		result.setRotationQuaternion(q.x, q.y, q.z, q.w);
	}
	else if (name == "outB"){

		result = data.bone2;
		xAxis = data.eff.getTranslation(MSpace::kWorld) - data.bone2.getTranslation(MSpace::kWorld);

		double scale[3] = {xAxis.length(), 1.0, 1.0};
		result.setScale(scale, MSpace::kWorld);

		if (data.negate)
			xAxis *= -1;

		// cross the yAxis and normalize
		xAxis.normalize();
		yAxis = MVector(0,1,0);
		yAxis = yAxis.rotateBy(data.bone2.rotation());
		zAxis = xAxis ^ yAxis;
		zAxis.normalize();
		yAxis = zAxis ^ xAxis;
		yAxis.normalize();

		// rotation
		MQuaternion q = getQuaternionFromAxes(xAxis,yAxis,zAxis);
		result.setRotationQuaternion(q.x, q.y, q.z, q.w);
	}
	else if (name == "outCenter"){


        // Only +/-180 degree with this one but we don't get the shear issue anymore
        MTransformationMatrix t = mapWorldPoseToObjectSpace(data.bone1, data.bone2);
		MEulerRotation er = t.eulerRotation();
        er *= .5;
        MQuaternion q = er.asQuaternion();
        t.setRotationQuaternion(q.x, q.y, q.z, q.w);
        t = mapObjectPoseToWorldSpace(data.bone1, t);
        q = t.rotation();

        result.setRotationQuaternion(q.x, q.y, q.z, q.w);

		// rotation
		result.setTranslation(data.bone2.getTranslation(MSpace::kWorld), MSpace::kWorld);
	}
	else if (name == "outEff")
		result = data.eff;

	return result;
}


