/*

MGEAR is under the terms of the MIT License

Copyright (c) 2016 Jeremie Passerin, Miquel Campos
Copyright (c) 2022 Michael Abrahams

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
#include <maya/MFnCompoundAttribute.h>
#include <maya/MArrayDataHandle.h>
#include <maya/MArrayDataBuilder.h>

/////////////////////////////////////////////////
// GLOBAL
/////////////////////////////////////////////////
MTypeId		mgear_springGravityNode::id(0xF011FEC1);

//Static variables

MObject mgear_springGravityNode::aOutput;
// MObject mgear_springGravityNode::aDebugOutput;
MObject mgear_springGravityNode::aGoal;
MObject mgear_springGravityNode::aGoalX;
MObject mgear_springGravityNode::aGoalY;
MObject mgear_springGravityNode::aGoalZ;

MObject mgear_springGravityNode::aDamping;
MObject mgear_springGravityNode::aStiffness;
MObject mgear_springGravityNode::aTime;

MObject mgear_springGravityNode::aGravity;
MObject mgear_springGravityNode::aGravityDirection;

MObject mgear_springGravityNode::aCollider;
MObject mgear_springGravityNode::aColliderX;
MObject mgear_springGravityNode::aColliderY;
MObject mgear_springGravityNode::aColliderZ;
MObject mgear_springGravityNode::aColliderRadius;
MObject mgear_springGravityNode::aColliderList;
MObject mgear_springGravityNode::aColliderSoftness;

MObject mgear_springGravityNode::aSpringIntensity;
MObject mgear_springGravityNode::aSpringActive;

MObject mgear_springGravityNode::aUseGroundPlane;
MObject mgear_springGravityNode::aGroundPlaneTransform;



mgear_springGravityNode::mgear_springGravityNode(){}
mgear_springGravityNode::~mgear_springGravityNode(){}

mgear_springGravityNode::SchedulingType mgear_springGravityNode::schedulingType() const
{
	return kParallel;
}

void* mgear_springGravityNode::creator()
{
	return new mgear_springGravityNode();
}



//INIT
MStatus mgear_springGravityNode::initialize()
{
	MStatus status;
	MFnNumericAttribute nAttr;
	MFnUnitAttribute uAttr;
	MFnMatrixAttribute mAttr;
	MFnCompoundAttribute cmpAttr;


	aOutput = nAttr.createPoint("output", "out"); // initializing attribute
	nAttr.setWritable(false);
	nAttr.setStorable(false);
	nAttr.setReadable(true);
	addAttribute(aOutput); // adding the attribute to the node

	// aDebugOutput = nAttr.createPoint("debug_output", "debug");
	// nAttr.setStorable(false);
	// nAttr.setReadable(true);
	// nAttr.setKeyable(true);
	// addAttribute(aDebugOutput);

	aGoal = nAttr.createPoint("goal", "goal");
	aGoalX = nAttr.child(0);
	aGoalY = nAttr.child(1);
	aGoalZ = nAttr.child(2);
	nAttr.setKeyable(true);
	nAttr.setStorable(false);
	addAttribute(aGoal);
	attributeAffects(aGoal, aOutput);

	aTime = uAttr.create("time", "time", MFnUnitAttribute::kTime, 0.0f);
	addAttribute(aTime);
	attributeAffects(aTime, aOutput);

	aStiffness = nAttr.create("stiffness", "stiffness", MFnNumericData::kDouble, 1.0f);
	nAttr.setKeyable(true);
	nAttr.setMin(0.0f);
	nAttr.setMax(1.0f);
	addAttribute(aStiffness);
	attributeAffects(aStiffness, aOutput);

	aDamping = nAttr.create("damping", "damping", MFnNumericData::kDouble, 1.0f);
	nAttr.setKeyable(true);
	nAttr.setMin(0.0f);
	nAttr.setMax(1.0f);
	addAttribute(aDamping);
	attributeAffects(aDamping, aOutput);

	aSpringIntensity = nAttr.create("intensity", "intensity", MFnNumericData::kDouble, 1.0f);
	nAttr.setKeyable(true);
	nAttr.setMin(0.0f);
	nAttr.setMax(1.0f);
	addAttribute(aSpringIntensity);
	attributeAffects(aSpringIntensity, aOutput);

	aSpringActive = nAttr.create("active", "active", MFnNumericData::kDouble, 1.0f);
	nAttr.setKeyable(true);
	nAttr.setMin(0.0f);
	nAttr.setMax(1.0f);
	addAttribute(aSpringActive);
	attributeAffects(aSpringActive, aOutput);

	aGravity = nAttr.create("gravity", "gravity", MFnNumericData::kDouble, 0.0f);
	nAttr.setKeyable(true);
	nAttr.setMin(-10.0f);
	nAttr.setMax(10.0f);
	addAttribute(aGravity);
	attributeAffects(aGravity, aOutput);

	aGravityDirection = nAttr.createPoint("gravity_direction", "gravity_direction");
  nAttr.setDefault(0.0f, -1.0f, 0.0f);
	nAttr.setKeyable(true);
	nAttr.setStorable(false);
	addAttribute(aGravityDirection);
	attributeAffects(aGravityDirection, aOutput);


	aColliderSoftness = nAttr.create("collide_softness", "collide_softness", MFnNumericData::kDouble, 0.5f);
	nAttr.setKeyable(true);
	nAttr.setMin(0.0f);
	nAttr.setMax(1.0f);
	addAttribute(aColliderSoftness);
	attributeAffects(aColliderSoftness, aOutput);

	aUseGroundPlane = nAttr.create("use_ground", "use_ground", MFnNumericData::kBoolean, 0);
	nAttr.setKeyable(true);
	addAttribute(aUseGroundPlane);
	attributeAffects(aUseGroundPlane, aOutput);

	aGroundPlaneTransform = mAttr.create("ground_transform", "ground_transform");
  mAttr.setStorable(true);
  mAttr.setKeyable(true);
  mAttr.setConnectable(true);
  addAttribute(aGroundPlaneTransform);
  attributeAffects(aGroundPlaneTransform, aOutput);

	aCollider = nAttr.createPoint("collider", "collider");
	aColliderX = nAttr.child(0);
	aColliderY = nAttr.child(1);
	aColliderZ = nAttr.child(2);
	nAttr.setKeyable(true);
 	McheckErr(nAttr.setDisconnectBehavior(MFnAttribute::kDelete), "setDisconnectBehavior");
	addAttribute(aCollider);
	attributeAffects(aCollider, aOutput);


	aColliderRadius = nAttr.create("collide_radius", "collide_radius", MFnNumericData::kDouble, 0.0f);
	nAttr.setKeyable(true);
	nAttr.setMin(-1000.0f);
	nAttr.setMax(1000.0f);
 	McheckErr(nAttr.setDisconnectBehavior(MFnAttribute::kDelete), "setDisconnectBehavior");
	addAttribute(aColliderRadius);
	attributeAffects(aColliderRadius, aOutput);


	aColliderList = cmpAttr.create("colliders_list", "colliders_list", &status);
	cmpAttr.setArray(true);
	cmpAttr.setKeyable(true);
	McheckErr(cmpAttr.addChild(aCollider), "compoundAttr.addChild");
	McheckErr(cmpAttr.addChild(aColliderRadius), "compoundAttr.addChild");
 	McheckErr(cmpAttr.setDisconnectBehavior(MFnAttribute::kDelete), "setDisconnectBehavior");
 	McheckErr(addAttribute(aColliderList), "addAttribute");
	McheckErr(attributeAffects(aColliderList, aOutput), "attributeAffects");




	// bool _initialized = false;

	return MS::kSuccess;
}

// COMPUTE

MStatus mgear_springGravityNode::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus status;

	if (plug != aOutput)
	{
		return MS::kUnknownParameter;
	}



	// getting inputs attributes
	double damping = data.inputValue(aDamping, &status).asDouble();
	double stiffness = data.inputValue(aStiffness, &status).asDouble();
	double gravity = data.inputValue(aGravity, &status).asDouble();
	MFloatVector gravityDirection = data.inputValue(aGravityDirection, &status).asFloatVector();

	//MVector goal = data.inputValue(aGoal, &status).asVector();
	MDataHandle h;
	MVector goal;
	h = data.inputValue(aGoal, &status);
	McheckStatusAndReturnIt(status);
	goal = h.asFloatVector();


	MTime currentTime = data.inputValue(aTime, &status).asTime();
	double springIntensity = data.inputValue(aSpringIntensity, &status).asDouble();
	double springActive = data.inputValue(aSpringActive, &status).asDouble();


	if (_initialized == false) {
		// Initialize the point states
		//MGlobal::displayInfo( "mc_spring: Initialize the point states" );
		_previousPosition = goal;
		_currentPosition = goal;
		_previousTime = currentTime;
		_initialized = true;
		//return MS::kSuccess;
	}
	// Check if the timestep is just 1 frame since we want a stable simulation
	double timeDifference = currentTime.value() - _previousTime.value();
	if (timeDifference > 1.0 || timeDifference < 0.0) {
		_initialized = false;
		_previousPosition = goal;
		_currentPosition = goal;
		_previousTime = currentTime;
		//MGlobal::displayInfo( "mc_spring: time checker, reset position" );
		//return MS::kSuccess;
	}

	// computation
	MVector velocity = (_currentPosition - _previousPosition) * (1.0 - damping);
	MFloatVector newPosition = _currentPosition + velocity;
	MVector goalForce = (goal - newPosition) * stiffness;
	goalForce += (gravity * gravityDirection);
	newPosition += goalForce;



	// Apply collision
	double colliderStrength = 1.0 - data.inputValue(aColliderSoftness, &status).asDouble();
	MVector colliderPos;
	MVector distFromCollider;
	double colliderRadius;
  double collideAmount;
	MArrayDataHandle arrayHandle = data.inputArrayValue(aColliderList, &status);
	McheckErr(status, "arrayHandle construction for aColliderList failed\n");
	unsigned count = arrayHandle.elementCount();
	for( unsigned i = 0; i < count; i++) {
		arrayHandle.jumpToArrayElement(i);
		h = arrayHandle.inputValue(&status);
		McheckErr(status, "handle evaluation failed\n");
		colliderPos = h.child(aCollider).asVector();
		colliderRadius = h.child(aColliderRadius).asDouble();
		distFromCollider = newPosition - colliderPos;
		collideAmount = (colliderRadius - distFromCollider.length()) / distFromCollider.length() * colliderStrength;
		collideAmount = collideAmount > 0 ? collideAmount : 0;   // Only push outward
		newPosition += collideAmount * distFromCollider; // Move radially
	}


	MMatrix groundPlaneTransform = data.inputValue(aGroundPlaneTransform, &status).asMatrix();
	MMatrix groundPlaneInv = groundPlaneTransform.inverse();
  double groundPlaneHeight = groundPlaneTransform(4, 2);

  // Collide with a general plane
	bool useGroundPlane = data.inputValue(aUseGroundPlane, &status).asBool();
  MPoint transformedPosition = newPosition;
  transformedPosition *= groundPlaneInv;
	double distFromGround = transformedPosition[1] - groundPlaneHeight;
	collideAmount = -1.0f * distFromGround * colliderStrength;

  if (useGroundPlane && (collideAmount > 0)) {
      transformedPosition[1] += collideAmount;
      transformedPosition *= groundPlaneTransform;
      newPosition = transformedPosition;
  }


	// store the states for the next calculation
	_previousPosition = _currentPosition;
	_currentPosition = newPosition;
	_previousTime = currentTime;

	// multiply the position by the spring intensity
	newPosition = goal + (((newPosition - goal) * springIntensity) * springActive);



	MDataHandle hOutput = data.outputValue(aOutput, &status);
	McheckStatusAndReturnIt(status);
	hOutput.set(newPosition);

  // Debug
	// hOutput = data.outputValue(aDebugOutput, &status);
	// McheckStatusAndReturnIt(status);
	// hOutput.set(MFloatVector(transformedPosition));

	hOutput.setClean();
	data.setClean(plug);

	return MS::kSuccess;

}
