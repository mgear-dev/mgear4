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
MTypeId mgear_vertexPosition::id( 0x0011FEEF  );


MObject mgear_vertexPosition::inputShape;
MObject mgear_vertexPosition::output;
MObject mgear_vertexPosition::outputX;
MObject mgear_vertexPosition::outputY;
MObject mgear_vertexPosition::outputZ;
MObject mgear_vertexPosition::vertexIndex;
MObject mgear_vertexPosition::constraintParentInverseMatrix;

mgear_vertexPosition::mgear_vertexPosition() {}
mgear_vertexPosition::~mgear_vertexPosition() {}

/////////////////////////////////////////////////
// METHODS
/////////////////////////////////////////////////

mgear_vertexPosition::SchedulingType mgear_vertexPosition::schedulingType() const
{
    return kParallel;
}

// CREATOR ======================================
void* mgear_vertexPosition::creator()
{
    return new mgear_vertexPosition();
}

// INIT =========================================
MStatus mgear_vertexPosition::initialize()
{

    MFnNumericAttribute nAttr;
    MFnTypedAttribute	tAttr;
    MFnMatrixAttribute	mAttr;
    MFnCompoundAttribute cAttr;
    MStatus	stat;

    inputShape = tAttr.create( "inputShape", "inS", MFnMeshData::kMesh);
    tAttr.setStorable(false);
    tAttr.setKeyable(false);

    vertexIndex= nAttr.create( "vertex", "vert", MFnNumericData::kLong);
    nAttr.setWritable(true);
    nAttr.setStorable(true);
    nAttr.setArray(false);

    constraintParentInverseMatrix = mAttr.create("drivenParentInverseMatrix", "dPIM",     MFnMatrixAttribute::kDouble);
    mAttr.setStorable(false);
    mAttr.setKeyable(false);

    outputX = nAttr.create( "outputX", "X", MFnNumericData::kDouble);
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setArray(false);

    outputY = nAttr.create( "outputY", "Y", MFnNumericData::kDouble);
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setArray(false);

    outputZ = nAttr.create( "outputZ", "Z", MFnNumericData::kDouble);
    nAttr.setWritable(false);
    nAttr.setStorable(false);
    nAttr.setArray(false);

    output = cAttr.create("output", "out");
    cAttr.addChild(outputX);
    cAttr.addChild(outputY);
    cAttr.addChild(outputZ);

    stat = addAttribute( inputShape );
    if (!stat) { stat.perror("addAttribute"); return stat;}
    stat = addAttribute( vertexIndex);
    if (!stat) { stat.perror("addAttribute"); return stat;}
    stat = addAttribute( output );
    if (!stat) { stat.perror("addAttribute"); return stat;}
    stat = addAttribute( constraintParentInverseMatrix );
    if (!stat) { stat.perror("addAttribute"); return stat;}


    stat = attributeAffects( inputShape, output );
    if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects( vertexIndex, output );
    if (!stat) { stat.perror("attributeAffects"); return stat;}
    stat = attributeAffects( constraintParentInverseMatrix, output );
    if (!stat) { stat.perror("attributeAffects"); return stat;}

    return MS::kSuccess;

}
// COMPUTE ======================================
MStatus mgear_vertexPosition::compute( const MPlug& plug, MDataBlock& data )

{
    MStatus returnStatus;
    if( plug == output )
    {
        MDataHandle inputData =	data.inputValue( inputShape, &returnStatus );
        MDataHandle outputHandle = data.outputValue( mgear_vertexPosition::output );
        MDataHandle vertHandle = data.inputValue( vertexIndex, &returnStatus );
        MDataHandle inverseMatrixHandle	=	data.inputValue(constraintParentInverseMatrix, &returnStatus);

        if( returnStatus != MS::kSuccess )
            MGlobal::displayError( "Node mgear_vertexPosition cannot get value\n" );
         else
        {

            MObject mesh = inputData.asMesh();
             unsigned int index = vertHandle.asInt();

            MFnMesh vert(mesh);

            MMatrix inverseMatrix = inverseMatrixHandle.asMatrix();
            MPoint pos;
            returnStatus = vert.getPoint(index, pos, MSpace::kWorld);
            if(MS::kSuccess != returnStatus )
                returnStatus.perror("Could not get vertex position");

            pos *= inverseMatrix;

            MDataHandle posX = outputHandle.child(outputX);
            posX.set(double(pos.x));

            MDataHandle posY = outputHandle.child(outputY);
            posY.set(double(pos.y));

            MDataHandle posZ = outputHandle.child(outputZ);
            posZ.set(double(pos.z));

            data.setClean(plug);
        }
    }
    else
    {
        return MS::kUnknownParameter;
    }

return MS::kSuccess;
}

