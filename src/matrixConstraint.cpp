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
Author:     Jascha Wohlkinger     jwohlkinger@gmail.com
Date:       2020/ 11 / 06

*/

#include "mgear_solvers.h"

MTypeId mgear_matrixConstraint::id(0x0011FEF0);

// ---------------------------------------------------
// input plugs
// ---------------------------------------------------
MObject mgear_matrixConstraint::aDriverMatrix;

MObject mgear_matrixConstraint::aDriverRotationOffset;
MObject mgear_matrixConstraint::aDriverRotationOffsetX;
MObject mgear_matrixConstraint::aDriverRotationOffsetY;
MObject mgear_matrixConstraint::aDriverRotationOffsetZ;

MObject mgear_matrixConstraint::aDrivenParentInverseMatrix;
MObject mgear_matrixConstraint::aDrivenRestMatrix;

MObject mgear_matrixConstraint::aRotationMultiplier;
MObject mgear_matrixConstraint::aRotationMultiplierX;
MObject mgear_matrixConstraint::aRotationMultiplierY;
MObject mgear_matrixConstraint::aRotationMultiplierZ;


MObject mgear_matrixConstraint::aScaleMultiplier;
MObject mgear_matrixConstraint::aScaleMultiplierX;
MObject mgear_matrixConstraint::aScaleMultiplierY;
MObject mgear_matrixConstraint::aScaleMultiplierZ;

// ---------------------------------------------------
// output plugs
// ---------------------------------------------------
MObject mgear_matrixConstraint::aOutputMatrix;
MObject mgear_matrixConstraint::aDriverOffsetOutputMatrix;

MObject mgear_matrixConstraint::aTranslate;
MObject mgear_matrixConstraint::aTranslateX;
MObject mgear_matrixConstraint::aTranslateY;
MObject mgear_matrixConstraint::aTranslateZ;

MObject mgear_matrixConstraint::aRotate;
MObject mgear_matrixConstraint::aRotateX;
MObject mgear_matrixConstraint::aRotateY;
MObject mgear_matrixConstraint::aRotateZ;

MObject mgear_matrixConstraint::aScale;
MObject mgear_matrixConstraint::aScaleX;
MObject mgear_matrixConstraint::aScaleY;
MObject mgear_matrixConstraint::aScaleZ;

MObject mgear_matrixConstraint::aShear;
MObject mgear_matrixConstraint::aShearX;
MObject mgear_matrixConstraint::aShearY;
MObject mgear_matrixConstraint::aShearZ;

// MObject mgear_matrixConstraint::aRestOrient;
// MObject mgear_matrixConstraint::aRestOrientX;
// MObject mgear_matrixConstraint::aRestOrientY;
// MObject mgear_matrixConstraint::aRestOrientZ;

mgear_matrixConstraint::mgear_matrixConstraint()
{
}

mgear_matrixConstraint::~mgear_matrixConstraint()
{
}

void* mgear_matrixConstraint::creator()
{
	return (new mgear_matrixConstraint());
}

MStatus mgear_matrixConstraint::compute(const MPlug& plug, MDataBlock& data)
{
	MStatus status;

	// -- our needed variables
	MTransformationMatrix result;
	double scale[3];
	double shear[3];

	// -- our final output variables
	double scale_result[3] = { 1.0, 1.0, 1.0 };
	double shear_result[3];

	// -----------------------------------------
	// input attributes
	// -----------------------------------------
	MMatrix driver_matrix = data.inputValue(aDriverMatrix, &status).asMatrix();

	// -- driver rotation offset
	double in_driver_rotation_offset_x = data.inputValue(aDriverRotationOffsetX, &status).asDouble();
	double in_driver_rotation_offset_y = data.inputValue(aDriverRotationOffsetY, &status).asDouble();
	double in_driver_rotation_offset_z = data.inputValue(aDriverRotationOffsetZ, &status).asDouble();

	MMatrix driven_inverse_matrix = data.inputValue(aDrivenParentInverseMatrix, &status).asMatrix();
	MMatrix rest_matrix = data.inputValue(aDrivenRestMatrix, &status).asMatrix();

	// -- rotation multiplier
	double in_rotation_multiplier_x = data.inputValue(aRotationMultiplierX, &status).asDouble();
	double in_rotation_multiplier_y = data.inputValue(aRotationMultiplierY, &status).asDouble();
	double in_rotation_multiplier_z = data.inputValue(aRotationMultiplierZ, &status).asDouble();


	// -- scale multiplier
	double in_scale_multiplier_x = data.inputValue(aScaleMultiplierX, &status).asDouble();
	double in_scale_multiplier_y = data.inputValue(aScaleMultiplierY, &status).asDouble();
	double in_scale_multiplier_z = data.inputValue(aScaleMultiplierZ, &status).asDouble();


	// -- add the rotation offset.
	// We need to add the offset on top of the driver matrix, to calculate the outputDriverOffsetMatrix and the
	// the rest matrix correctly
	MEulerRotation  euler_off(
		degrees2radians(in_driver_rotation_offset_x),
		degrees2radians(in_driver_rotation_offset_y),
		degrees2radians(in_driver_rotation_offset_z) );
	MTransformationMatrix driver_matrix_tfm(driver_matrix);
	MTransformationMatrix driver_matrix_off = driver_matrix_tfm.rotateBy(euler_off,  MSpace::kPreTransform);


	// MMatrix mult_matrix = driver_matrix * driven_inverse_matrix;
	MMatrix mult_matrix = driver_matrix_off.asMatrix() * driven_inverse_matrix;

	// -- multiply the result of the mult matrix by the rest
	// -- need to have the rotation calculated seperaltely - (joint orientation)
	MMatrix rotate_matrix = mult_matrix * rest_matrix.inverse();

	MTransformationMatrix matrix(mult_matrix);
	MTransformationMatrix rotate_tfm(rotate_matrix);


	// -- the quaternion rotation of the rotate matrix
	// MQuaternion rotation = rotate_tfm_off.rotation();
	MQuaternion rotation = rotate_tfm.rotation();

	// -- apply the rotation multiplier
	rotation.x *= in_rotation_multiplier_x;
	rotation.y *= in_rotation_multiplier_y;
	rotation.z *= in_rotation_multiplier_z;

	// -- decompose the matrix values to construct into the final matrix
	MVector translation = matrix.getTranslation(MSpace::kWorld);
	matrix.getScale(scale, MSpace::kWorld);
	matrix.getShear(shear, MSpace::kWorld);

	// -- add in the scale multiplication
	scale[0] *= in_scale_multiplier_x;
	scale[1] *= in_scale_multiplier_y;
	scale[2] *= in_scale_multiplier_z;

	// -- compose our matrix
	result.setTranslation(translation, MSpace::kWorld);
	result.setRotationQuaternion(rotation.x, rotation.y, rotation.z, rotation.w);
	result.setScale(scale, MSpace::kWorld);
	result.setShear(shear, MSpace::kWorld);

	// -----------------------------------------
	// output
	// -----------------------------------------
	MDataHandle matrix_handle = data.outputValue(aOutputMatrix, &status);
	matrix_handle.setMMatrix(result.asMatrix());
	data.setClean(aOutputMatrix);
	MDataHandle matrix_driver_off_handle = data.outputValue(aDriverOffsetOutputMatrix, &status);
	matrix_driver_off_handle.setMMatrix(driver_matrix_off.asMatrix());
	data.setClean(aDriverOffsetOutputMatrix);

	MDataHandle translate_handle = data.outputValue(aTranslate, &status);
	translate_handle.setMVector(result.getTranslation(MSpace::kWorld));

	MEulerRotation rotation_result = result.eulerRotation();
	MDataHandle rotate_handle = data.outputValue(aRotate, &status);
	rotate_handle.set3Double(rotation_result.x, rotation_result.y, rotation_result.z);

	result.getScale(scale_result, MSpace::kWorld);
	MDataHandle scale_handle = data.outputValue(aScale, &status);
	scale_handle.set3Double(scale_result[0], scale_result[1], scale_result[2]);

	result.getShear(shear_result, MSpace::kWorld);
	MDataHandle shear_handle = data.outputValue(aShear, &status);
	shear_handle.set3Double(shear_result[0], shear_result[1], shear_result[2]);

	data.setClean(plug);

	return MS::kSuccess;
}

MStatus mgear_matrixConstraint::initialize()
{
	MStatus status;

	MFnMatrixAttribute mAttr;
	MFnNumericAttribute nAttr;
	MFnUnitAttribute uAttr;

	// -----------------------------------------
	// input attributes
	// -----------------------------------------
	aDriverMatrix = mAttr.create("driverMatrix", "driverMatrix", MFnMatrixAttribute::kDouble);
	mAttr.setKeyable(true);
	mAttr.setReadable(false);
	mAttr.setWritable(true);
	mAttr.setStorable(true);

	aDriverRotationOffsetX = nAttr.create("driverRotationOffsetX", "driverRotationOffsetX", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-360.0);
	nAttr.setMax(360.0);

	aDriverRotationOffsetY = nAttr.create("driverRotationOffsetY", "driverRotationOffsetY", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-360.0);
	nAttr.setMax(360.0);

	aDriverRotationOffsetZ = nAttr.create("driverRotationOffsetZ", "driverRotationOffsetZ", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-360.0);
	nAttr.setMax(360.0);

	aDriverRotationOffset = nAttr.create("driverRotationOffset", "driverRotationOffset", aDriverRotationOffsetX, aDriverRotationOffsetY, aDriverRotationOffsetZ);
	nAttr.setKeyable(true);
	nAttr.setDefault(0.0, 0.0, 0.0);

	aDrivenParentInverseMatrix = mAttr.create("drivenParentInverseMatrix", "drivenParentInverseMatrix", MFnMatrixAttribute::kDouble);
	mAttr.setKeyable(true);
	mAttr.setReadable(false);
	mAttr.setWritable(true);
	mAttr.setStorable(true);

	aDrivenRestMatrix = mAttr.create("drivenRestMatrix", "drivenRestMatrix", MFnMatrixAttribute::kDouble);
	mAttr.setKeyable(true);
	mAttr.setReadable(false);
	mAttr.setWritable(true);
	mAttr.setStorable(true);

	aRotationMultiplierX = nAttr.create("rotationMultX", "rotationMultX", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-1.0);
	nAttr.setMax(1.0);

	aRotationMultiplierY = nAttr.create("rotationMultY", "rotationMultY", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-1.0);
	nAttr.setMax(1.0);

	aRotationMultiplierZ = nAttr.create("rotationMultZ", "rotationMultZ", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-1.0);
	nAttr.setMax(1.0);

	aRotationMultiplier = nAttr.create("rotationMultiplier", "rotationMultiplier", aRotationMultiplierX, aRotationMultiplierY, aRotationMultiplierZ);
	nAttr.setKeyable(true);
	nAttr.setDefault(1.0, 1.0, 1.0);


	aScaleMultiplierX = nAttr.create("scaleMultX", "scaleMultX", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-1.0);
	nAttr.setMax(1.0);

	aScaleMultiplierY = nAttr.create("scaleMultY", "scaleMultY", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-1.0);
	nAttr.setMax(1.0);

	aScaleMultiplierZ = nAttr.create("scaleMultZ", "scaleMultZ", MFnNumericData::kDouble);
	nAttr.setKeyable(true);
	nAttr.setMin(-1.0);
	nAttr.setMax(1.0);

	aScaleMultiplier = nAttr.create("scaleMultiplier", "scaleMultiplier", aScaleMultiplierX, aScaleMultiplierY, aScaleMultiplierZ);
	nAttr.setKeyable(true);
	nAttr.setDefault(1.0, 1.0, 1.0);

	// -----------------------------------------
	// output attributes
	// -----------------------------------------
	aOutputMatrix = mAttr.create("outputMatrix", "outputMatrix", MFnMatrixAttribute::kDouble);
	mAttr.setKeyable(false);
	mAttr.setWritable(true);
	mAttr.setStorable(false);

	aDriverOffsetOutputMatrix = mAttr.create("outputDriverOffsetMatrix", "outputDriverOffsetMatrix", MFnMatrixAttribute::kDouble);
	mAttr.setKeyable(false);
	mAttr.setWritable(true);
	mAttr.setStorable(false);

	// -- out translation
	aTranslateX = nAttr.create("translateX", "translateX", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aTranslateY = nAttr.create("translateY", "translateY", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aTranslateZ = nAttr.create("translateZ", "translateZ", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aTranslate = nAttr.create("translate", "translate", aTranslateX, aTranslateY, aTranslateZ);
	nAttr.setWritable(false);

	// -- out rotation
	aRotateX = uAttr.create("rotateX", "rotateX", MFnUnitAttribute::kAngle);
	uAttr.setWritable(false);
	uAttr.setStorable(true);

	aRotateY = uAttr.create("rotateY", "rotateY", MFnUnitAttribute::kAngle);
	uAttr.setWritable(false);
	uAttr.setStorable(true);

	aRotateZ = uAttr.create("rotateZ", "rotateZ", MFnUnitAttribute::kAngle);
	uAttr.setWritable(false);
	uAttr.setStorable(true);

	aRotate = nAttr.create("rotate", "rotate", aRotateX, aRotateY, aRotateZ);
	nAttr.setWritable(false);

	// -- out scale
	aScaleX = nAttr.create("scaleX", "scaleX", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aScaleY = nAttr.create("scaleY", "scaleY", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aScaleZ = nAttr.create("scaleZ", "scaleZ", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aScale = nAttr.create("scale", "scale", aScaleX, aScaleY, aScaleZ);
	nAttr.setWritable(false);

	// -- out shear
	aShearX = nAttr.create("shearX", "shearX", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aShearY = nAttr.create("shearY", "shearY", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aShearZ = nAttr.create("shearZ", "shearZ", MFnNumericData::kDouble);
	nAttr.setWritable(false);
	nAttr.setStorable(true);

	aShear = nAttr.create("shear", "shear", aShearX, aShearY, aShearZ);
	nAttr.setWritable(false);

	// -----------------------------------------
	// add attributes
	// -----------------------------------------
	addAttribute(aDriverMatrix);

	addAttribute(aDriverRotationOffset);
	addAttribute(aDriverRotationOffsetX);
	addAttribute(aDriverRotationOffsetY);
	addAttribute(aDriverRotationOffsetZ);

	addAttribute(aDrivenParentInverseMatrix);
	addAttribute(aDrivenRestMatrix);

	addAttribute(aRotationMultiplier);
	addAttribute(aRotationMultiplierX);
	addAttribute(aRotationMultiplierY);
	addAttribute(aRotationMultiplierZ);


	addAttribute(aScaleMultiplier);
	addAttribute(aScaleMultiplierX);
	addAttribute(aScaleMultiplierY);
	addAttribute(aScaleMultiplierZ);

	addAttribute(aOutputMatrix);
	addAttribute(aDriverOffsetOutputMatrix);

	addAttribute(aTranslate);
	addAttribute(aTranslateX);
	addAttribute(aTranslateY);
	addAttribute(aTranslateZ);

	addAttribute(aRotate);
	addAttribute(aRotateX);
	addAttribute(aRotateY);
	addAttribute(aRotateZ);

	addAttribute(aScale);
	addAttribute(aScaleX);
	addAttribute(aScaleY);
	addAttribute(aScaleZ);

	addAttribute(aShear);
	addAttribute(aShearX);
	addAttribute(aShearY);
	addAttribute(aShearZ);

	// -----------------------------------------
	// attribute affects
	// -----------------------------------------
	attributeAffects(aDriverMatrix, aOutputMatrix);
	attributeAffects(aDrivenParentInverseMatrix, aOutputMatrix);
	attributeAffects(aDrivenRestMatrix, aOutputMatrix);

	attributeAffects(aRotationMultiplier, aOutputMatrix);
	attributeAffects(aDriverRotationOffset, aOutputMatrix);
	attributeAffects(aScaleMultiplier, aOutputMatrix);

	attributeAffects(aDriverMatrix, aDriverOffsetOutputMatrix);
	// attributeAffects(aDrivenParentInverseMatrix, aDriverOffsetOutputMatrix);
	// attributeAffects(aDrivenRestMatrix, aDriverOffsetOutputMatrix);
	attributeAffects(aDriverRotationOffset, aDriverOffsetOutputMatrix);


	attributeAffects(aScaleMultiplier, aTranslate);
	attributeAffects(aScaleMultiplier, aRotate);
	attributeAffects(aScaleMultiplier, aScale);
	attributeAffects(aScaleMultiplier, aShear);

	attributeAffects(aRotationMultiplier, aTranslate);
	attributeAffects(aRotationMultiplier, aRotate);
	attributeAffects(aRotationMultiplier, aScale);
	attributeAffects(aRotationMultiplier, aShear);

	attributeAffects(aDriverRotationOffset, aTranslate);
	attributeAffects(aDriverRotationOffset, aRotate);
	attributeAffects(aDriverRotationOffset, aScale);
	attributeAffects(aDriverRotationOffset, aShear);

	attributeAffects(aDriverMatrix, aTranslate);
	attributeAffects(aDriverMatrix, aRotate);
	attributeAffects(aDriverMatrix, aScale);
	attributeAffects(aDriverMatrix, aShear);

	attributeAffects(aDrivenParentInverseMatrix, aTranslate);
	attributeAffects(aDrivenParentInverseMatrix, aRotate);
	attributeAffects(aDrivenParentInverseMatrix, aScale);
	attributeAffects(aDrivenParentInverseMatrix, aShear);

	attributeAffects(aDrivenRestMatrix, aTranslate);
	attributeAffects(aDrivenRestMatrix, aRotate);
	attributeAffects(aDrivenRestMatrix, aScale);
	attributeAffects(aDrivenRestMatrix, aShear);

	return MS::kSuccess;
}

mgear_matrixConstraint::SchedulingType mgear_matrixConstraint::schedulingType() const
{
	return kParallel;
}
