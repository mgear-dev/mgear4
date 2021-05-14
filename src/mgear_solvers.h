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
#ifndef _rigSolvers
#define _rigSolvers

#define McheckErr(stat,msg)         \
    if ( MS::kSuccess != stat ) {   \
                std::cerr << msg;                \
                return MS::kFailure;        \
        }

#define McheckStatusAndReturn(_status, _retVal)    \
{                                         \
   MStatus _maya_status = (_status);               \
   if ( MStatus::kSuccess != _maya_status )        \
   {                                      \
      std::cerr << "\nAPI error detected in " << __FILE__  \
          <<   " at line " << __LINE__ << std::endl;    \
      _maya_status.perror ( "" );                  \
      return (_retVal);                      \
   }                                      \
}

#define McheckStatusAndReturnIt(_status)        \
   McheckStatusAndReturn((_status), (_status))

/////////////////////////////////////////////////
// INCLUDE
/////////////////////////////////////////////////

#include <iostream>
#include <algorithm>
#include <cmath>

#include <maya/MGlobal.h>
#include <maya/MPxNode.h>
#include <maya/MPxDeformerNode.h>
#include <maya/MFnDependencyNode.h>


#include <maya/MPlug.h>
#include <maya/MDataBlock.h>
#include <maya/MDataHandle.h>

#include <maya/MFnTypedAttribute.h>
#include <maya/MFnNumericAttribute.h>
#include <maya/MFnMatrixAttribute.h>
#include <maya/MFnEnumAttribute.h>
#include <maya/MFnUnitAttribute.h>
#include <maya/MFnCompoundAttribute.h>


#include <maya/MQuaternion.h>
#include <maya/MVector.h>
#include <maya/MVectorArray.h>
#include <maya/MFloatPoint.h>
#include <maya/MFloatVector.h>
#include <maya/MMatrix.h>
#include <maya/MMatrixArray.h>
#include <maya/MFloatMatrix.h>
#include <maya/MTransformationMatrix.h>
#include <maya/MDoubleArray.h>
#include <maya/MEulerRotation.h>
#include <maya/MTime.h>


#include <maya/MFnMesh.h>
#include <maya/MItGeometry.h>
#include <maya/MDagModifier.h>
#include <maya/MPointArray.h>
#include <maya/MFnMeshData.h>
#include <maya/MFnMatrixData.h>



#include <maya/MFnNurbsCurve.h>
#include <maya/MPoint.h>

#include <maya/MTypeId.h>

#include <maya/MAngle.h>


#include <maya/MStatus.h>
//#include <minmax.h>
#include <cstdlib>



#define PI 3.14159265


/////////////////////////////////////////////////
// STRUCTS
/////////////////////////////////////////////////
struct s_GetFKTransform
{
   double lengthA;
   double lengthB;
   bool negate;
   MTransformationMatrix root;
   MTransformationMatrix bone1;
   MTransformationMatrix bone2;
   MTransformationMatrix eff;
};

struct s_GetIKTransform
{
   double lengthA;
   double lengthB;
   bool negate;
   double roll;
   double scaleA;
   double scaleB;
   double maxstretch;
   double softness;
   double slide;
   double reverse;
   MTransformationMatrix root;
   MTransformationMatrix eff;
   MTransformationMatrix	 upv;
};

/////////////////////////////////////////////////
// CLASSES
/////////////////////////////////////////////////
class mgear_slideCurve2 : public MPxDeformerNode
{
public:
                    mgear_slideCurve2() {};
    virtual MStatus deform( MDataBlock& data, MItGeometry& itGeo, const MMatrix &localToWorldMatrix, unsigned int mIndex );
    virtual SchedulingType schedulingType() const;
    static  void*   creator();
    static  MStatus initialize();

    static MTypeId      id;

	// Input
	static MObject	 master_crv;
	static MObject	 master_mat;

	static MObject	 slave_length;
	static MObject	 master_length;
	static MObject	 position;

	static MObject	 maxstretch;
	static MObject	 maxsquash;
	static MObject	 softness;
};

class mgear_curveCns : public MPxDeformerNode
{
public:
                    mgear_curveCns() {};
    virtual MStatus deform( MDataBlock& data, MItGeometry& itGeo, const MMatrix &localToWorldMatrix, unsigned int mIndex );
    virtual SchedulingType schedulingType() const;
    static  void*   creator();
    static  MStatus initialize();

    static MTypeId      id;
    static  MObject     inputs;
};

class mgear_rollSplineKine : public MPxNode
{
 public:
      mgear_rollSplineKine();
   virtual	 ~mgear_rollSplineKine();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 ctlParent;
	static MObject	 inputs;
	static MObject	 inputsRoll;
	static MObject	 outputParent;

	static MObject	 u;
	static MObject	 resample;
	static MObject	 subdiv;
	static MObject	 absolute;

	// Output
	static MObject	 output;

};
class mgear_squashStretch2 : public MPxNode
{
 public:
      mgear_squashStretch2();
   virtual	 ~mgear_squashStretch2();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 global_scale;
	static MObject	 global_scalex;
	static MObject	 global_scaley;
	static MObject	 global_scalez;

	static MObject	 blend;
	static MObject	 driver;
	static MObject	 driver_min;
	static MObject	 driver_ctr;
	static MObject	 driver_max;
	static MObject	 axis;
	static MObject	 squash;
	static MObject	 stretch;

	// Output
	static MObject	 output;

};

class mgear_percentageToU : public MPxNode
{
 public:
      mgear_percentageToU();
   virtual	 ~mgear_percentageToU();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 curve;
	static MObject	 normalizedU;
	static MObject	 percentage;
	static MObject	 steps;

	// Output
	static MObject	 u;

};

class mgear_uToPercentage : public MPxNode
{
 public:
      mgear_uToPercentage();
   virtual	 ~mgear_uToPercentage();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 curve;
	static MObject	 normalizedU;
	static MObject	 u;
	static MObject	 steps;

	// Output
	static MObject	 percentage;

};

class mgear_spinePointAt : public MPxNode
{
 public:
      mgear_spinePointAt();
   virtual	 ~mgear_spinePointAt();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 rotA;
	static MObject	 rotAx;
	static MObject	 rotAy;
	static MObject	 rotAz;
	static MObject	 rotB;
	static MObject	 rotBx;
	static MObject	 rotBy;
	static MObject	 rotBz;
	static MObject	 axe;
	static MObject	 blend;

	// Output
	static MObject	 pointAt;

};

class mgear_inverseRotOrder : public MPxNode
{
 public:
      mgear_inverseRotOrder();
   virtual	 ~mgear_inverseRotOrder();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 rotOrder;

	// Output
	static MObject	 output;

};

class mgear_mulMatrix : public MPxNode
{
 public:
      mgear_mulMatrix();
   virtual	 ~mgear_mulMatrix();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 matrixA;
	static MObject	 matrixB;

	// Output
	static MObject	 output;

};

class mgear_intMatrix : public MPxNode
{
 public:
      mgear_intMatrix();
   virtual	 ~mgear_intMatrix();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// ATTRIBUTES
	static MObject	 blend;

	// Input
	static MObject	 matrixA;
	static MObject	 matrixB;

	// Output
	static MObject	 output;

};

class mgear_ikfk2Bone : public MPxNode
{
 public:
      mgear_ikfk2Bone();
   virtual	 ~mgear_ikfk2Bone();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();
   MTransformationMatrix getIKTransform(s_GetIKTransform values, MString outportName);
   MTransformationMatrix getFKTransform(s_GetFKTransform values, MString outportName);

 public:

	// ATTRIBUTES
	static MObject	 blend;

	static MObject	 lengthA;
	static MObject	 lengthB;
	static MObject	 negate;

	static MObject	 scaleA;
	static MObject	 scaleB;
	static MObject	 roll;

	static MObject	 maxstretch;
	static MObject	 slide;
	static MObject	 softness;
	static MObject	 reverse;

	// INPUTS
	static MObject	 root;
	static MObject	 ikref;
	static MObject	 upv;
	static MObject	 fk0;
	static MObject	 fk1;
	static MObject	 fk2;

	// OUTPUTS
	static MObject	 inAparent;
	static MObject	 inBparent;
	static MObject	 inCenterparent;
	static MObject	 inEffparent;

	static MObject	 outA;
	static MObject	 outB;
	static MObject	 outCenter;
	static MObject	 outEff;

	static MTypeId id;
};


class mgear_add10scalarNode : public MPxNode
{
public:
	mgear_add10scalarNode();
	virtual			~mgear_add10scalarNode();
	virtual SchedulingType schedulingType() const;
	static	void*	creator();

	virtual MStatus		compute(const MPlug& plug, MDataBlock& data);
	static MStatus		initialize();

	static MTypeId id;
	static MObject aOutValue;  //start with "a" lower case to indicate attribute
	static MObject aInValue0;
	static MObject aInValue1;
	static MObject aInValue2;
	static MObject aInValue3;
	static MObject aInValue4;
	static MObject aInValue5;
	static MObject aInValue6;
	static MObject aInValue7;
	static MObject aInValue8;
	static MObject aInValue9;

};

class mgear_linearInterpolate3DvectorNode : public MPxNode
{
public:
	mgear_linearInterpolate3DvectorNode();
	virtual			~mgear_linearInterpolate3DvectorNode();
	virtual SchedulingType schedulingType() const;
	static	void*	creator();

	virtual MStatus		compute(const MPlug& plug, MDataBlock& data);
	static MStatus		initialize();

	static MTypeId id;

	//Inputs
	static MObject	 vecA;
	static MObject	 vecAx;
	static MObject	 vecAy;
	static MObject	 vecAz;
	static MObject	 vecB;
	static MObject	 vecBx;
	static MObject	 vecBy;
	static MObject	 vecBz;
	static MObject	 blend;

	//Outputs
	static MObject outVec;
	//static MObject outVecX;
	//static MObject outVecY;
	//static MObject outVecZ;

};

class mgear_springNode : public MPxNode
{
public:
	mgear_springNode();
	virtual			~mgear_springNode();
	virtual SchedulingType schedulingType() const;
	static	void*	creator();

	virtual MStatus		compute(const MPlug& plug, MDataBlock& data);
	static MStatus		initialize();

	static MTypeId id;
	static MObject aOutput;
	static MObject aGoal;
	static MObject aGoalX;
	static MObject aGoalY;
	static MObject aGoalZ;
	static MObject aDamping;
	static MObject aStiffness;
	static MObject aTime;
	//static MObject aParentInverse;
	static MObject aSpringIntensity;

	////variables

	bool _initialized;
	MTime _previousTime;
	MFloatVector _currentPosition;
	MFloatVector _previousPosition;

};

class mgear_rayCastPosition : public MPxNode
{
 public:
      mgear_rayCastPosition();
   virtual	 ~mgear_rayCastPosition();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 meshInput;
	static MObject	 raySource;
	static MObject	 rayDirection;

	// Output
	static MObject	 output;

};

class mgear_trigonometryAngle : public MPxNode
{
 public:
      mgear_trigonometryAngle();
   virtual	 ~mgear_trigonometryAngle();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static MObject	 trigoOperation;
	static MObject	 angle;

	// Output
	static MObject	 output;

};

class mgear_vertexPosition : public MPxNode
{
 public:
      mgear_vertexPosition();
   virtual	 ~mgear_vertexPosition();

   virtual MStatus compute( const MPlug& plug, MDataBlock& data );
   virtual SchedulingType schedulingType() const;
   static void* creator();
   static MStatus initialize();

 public:
	static MTypeId id;

	// Input
	static	MObject	inputShape;
	static	MObject	vertexIndex;
	static	MObject	constraintParentInverseMatrix;

	// Output
	static MObject	output;
    static MObject	outputX;
    static MObject	outputY;
    static MObject	outputZ;

};

class mgear_matrixConstraint : public MPxNode
{
public:

	mgear_matrixConstraint();
	virtual					~mgear_matrixConstraint();
	static void* creator();

	virtual MStatus			compute(const MPlug& plug, MDataBlock& data);
	static MStatus			initialize();

	static MTypeId			id;

	virtual SchedulingType	schedulingType() const;

	// ---------------------------------------------------
	// input plugs
	// ---------------------------------------------------
	static MObject aDriverMatrix;

	static MObject aDriverRotationOffset;
	static MObject aDriverRotationOffsetX;
	static MObject aDriverRotationOffsetY;
	static MObject aDriverRotationOffsetZ;

	static MObject aDrivenParentInverseMatrix;
	static MObject aDrivenRestMatrix;

	static MObject aRotationMultiplier;
	static MObject aRotationMultiplierX;
	static MObject aRotationMultiplierY;
	static MObject aRotationMultiplierZ;


	static MObject aScaleMultiplier;
	static MObject aScaleMultiplierX;
	static MObject aScaleMultiplierY;
	static MObject aScaleMultiplierZ;

	// -----------------------------------------
	// output attributes
	// -----------------------------------------
	static MObject aTranslate;
	static MObject aTranslateX;
	static MObject aTranslateY;
	static MObject aTranslateZ;

	static MObject aRotate;
	static MObject aRotateX;
	static MObject aRotateY;
	static MObject aRotateZ;

	static MObject aScale;
	static MObject aScaleX;
	static MObject aScaleY;
	static MObject aScaleZ;

	static MObject aShear;
	static MObject aShearX;
	static MObject aShearY;
	static MObject aShearZ;

	static MObject aDriverOffsetOutputMatrix;
	static MObject aOutputMatrix;

};

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////
MQuaternion e2q(double x, double y, double z);
MQuaternion slerp2(MQuaternion qA, MQuaternion qB, double blend);
double clamp(double d, double min_value, double max_value);
int clamp(int d, int min_value, int max_value);
double getDot(MQuaternion qA, MQuaternion qB);
double radians2degrees(double a);
double degrees2radians(double a);
double round(const double value, const int precision);
double normalizedUToU(double u, int point_count);
double uToNormalizedU(double u, int point_count);
unsigned findClosestInArray(double value, MDoubleArray in_array);
double set01range(double value, double first, double second);
double linearInterpolate(double first, double second, double blend);
MVector linearInterpolate(MVector v0, MVector v1, double blend);
MVectorArray bezier4point( MVector a, MVector tan_a, MVector d, MVector tan_d, double u);
MVector rotateVectorAlongAxis(MVector v, MVector axis, double a);
MQuaternion getQuaternionFromAxes(MVector vx, MVector vy, MVector vz);
MTransformationMatrix mapWorldPoseToObjectSpace(MTransformationMatrix objectSpace, MTransformationMatrix pose);
MTransformationMatrix mapObjectPoseToWorldSpace(MTransformationMatrix objectSpace, MTransformationMatrix pose);
MTransformationMatrix interpolateTransform(MTransformationMatrix xf1, MTransformationMatrix xf2, double blend);


#endif