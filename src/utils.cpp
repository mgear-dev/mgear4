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
// UTLIS METHODS
/////////////////////////////////////////////////
MQuaternion e2q(double x, double y, double z){

    x = degrees2radians(x);
    y = degrees2radians(y);
    z = degrees2radians(z);

    // Assuming the angles are in radians.
    double c1 = cos(y/2.0);
    double s1 = sin(y/2.0);
    double c2 = cos(z/2.0);
    double s2 = sin(z/2.0);
    double c3 = cos(x/2.0);
    double s3 = sin(x/2.0);
    double c1c2 = c1*c2;
    double s1s2 = s1*s2;
    double qw =c1c2*c3 - s1s2*s3;
    double qx =c1c2*s3 + s1s2*c3;
    double qy =s1*c2*c3 + c1*s2*s3;
    double qz =c1*s2*c3 - s1*c2*s3;
        
    return MQuaternion(qx,qy,qz,qw);
}

MQuaternion slerp2(MQuaternion qA, MQuaternion qB, double blend){
    
	double dot = getDot(qA, qB);
        
	double scaleA, scaleB;
	// if q1 and target are really close then we can interpolate linerarly.
	if (dot >= (1 - 1.0e-12)){
		scaleA = 1 - blend;
		scaleB = blend;
	}
	else {
		// use standard spherical linear interpolation
		dot = clamp(dot, -1.0, 1.0);
	}
    
	double angle;
	if (round((-dot * dot+ 1),5) == 0)
		return qA;
	else
		angle = acos(dot);

	double factor;
	if (round(sin(angle), 6) != 0)
		factor = 1 / sin(angle);
	else
		return qA;

	scaleA = sin( (1.0 - blend) * angle ) * factor;
	scaleB = sin( blend * angle ) * factor;

	double qx  = scaleA * qA.x + scaleB * qB.x;
	double qy  = scaleA * qA.y + scaleB * qB.y;
	double qz  = scaleA * qA.z + scaleB * qB.z;
	double qw  = scaleA * qA.w + scaleB * qB.w;
	
	return MQuaternion(qx, qy, qz, qw);
}

double clamp(double d, double min_value, double max_value){

        d = std::max(d, min_value);
        d = std::min(d, max_value);
        return d;
}
int clamp(int d, int min_value, int max_value){

        d = std::max(d, min_value);
        d = std::min(d, max_value);
        return d;
}

double getDot(MQuaternion qA, MQuaternion qB){

    double dot = qA.w * qB.w +
				qA.x * qB.x + 
				qA.y * qB.y + 
				qA.z * qB.z;

	return dot;
}

double radians2degrees(double a){
	return a * 57.2957795;
}
double degrees2radians(double a){
	return a * 0.0174532925;
}

double round(double value, int precision)
 {
     if (precision>=0) {
         int p = clamp(precision,-15,15);
         double pwr[] = { 
                 1e0,  1e1,  1e2,  1e3,  1e4, 
                 1e5,  1e6,  1e7,  1e8,  1e9, 
                 1e10, 1e11, 1e12, 1e13, 1e14 };
 
         double invpwr[] = {
                 1e0,   1e-1,  1e-2,  1e-3,  1e-4, 
                 1e-5,  1e-6,  1e-7,  1e-8,  1e-9, 
                 1e-10, 1e-11, 1e-12, 1e-13, 1e-14 };
 
         double val = value;
 
         if (value<0.0)
             val = ceil(val*pwr[p]-0.5);
 
         if (value>0.0)
             val = floor(val*pwr[p]+0.5);

         return val*invpwr[p];
     }

    return value;
}

double normalizedUToU(double u, int point_count){
	return u * (point_count-3.0);
}
double uToNormalizedU(double u, int point_count){
	return u / (point_count-3.0);
}

unsigned findClosestInArray(double value, MDoubleArray in_array){
   
	double ref = 9999999999.999999;
	unsigned index = (unsigned)-1;
	double diff;
	unsigned count = sizeof(in_array) / sizeof(double);
	for(unsigned i = 0; i < count; i++){
		diff = abs(in_array[i] - value);
		if (diff < ref){
			ref = diff;
			index = i;
		}
	}

	return index;
}
      
double set01range(double value, double first, double second){
        return (value - first) / (second - first);
}
 
double linearInterpolate(double first, double second, double blend){
        return first * (1-blend) + second * blend;
}
MVector linearInterpolate(MVector v0, MVector v1, double blend){
	MVector v;
	v.x = linearInterpolate(v0.x, v1.x, blend);
	v.y = linearInterpolate(v0.y, v1.y, blend);
	v.z = linearInterpolate(v0.z, v1.z, blend);

    return v;
}

MVectorArray bezier4point( MVector a, MVector tan_a, MVector d, MVector tan_d, double u){

    MVector b = a + tan_a;
    MVector c = -tan_d + d;

    MVector ab = linearInterpolate(a,b,u);
    MVector bc = linearInterpolate(b,c,u);
    MVector cd = linearInterpolate(c,d,u);
    MVector abbc = linearInterpolate(ab,bc,u);
    MVector bccd = linearInterpolate(bc,cd,u);
    MVector abbcbccd = linearInterpolate(abbc,bccd,u);

	MVector tan = bccd - abbc;
	tan.normalize();

	MVectorArray output(2);
	output[0] = abbcbccd;
	output[1] = tan;

    return output;
}

MVector rotateVectorAlongAxis(MVector v, MVector axis, double a){

    // Angle as to be in radians

    double sa = sin(a / 2.0);
    double ca = cos(a / 2.0);

    MQuaternion q1 = MQuaternion(v.x, v.y, v.z, 0);
    MQuaternion q2 = MQuaternion(axis.x * sa, axis.y * sa, axis.z * sa, ca);
    MQuaternion q2n = MQuaternion(-axis.x * sa, -axis.y * sa, -axis.z * sa, ca);
    MQuaternion q = q2 * q1;
    q *= q2n;

    return MVector(q.x, q.y, q.z);
}

MQuaternion getQuaternionFromAxes(MVector vx, MVector vy, MVector vz){
	
	MMatrix m;
	m[0][0] = vx.x;
	m[0][1] = vx.y;
	m[0][2] = vx.z;
	m[1][0] = vy.x;
	m[1][1] = vy.y;
	m[1][2] = vy.z;
	m[2][0] = vz.x;
	m[2][1] = vz.y;
	m[2][2] = vz.z;

	MTransformationMatrix t(m);

	return t.rotation();
}


MTransformationMatrix mapWorldPoseToObjectSpace(MTransformationMatrix objectSpace, MTransformationMatrix pose){
        return MTransformationMatrix(pose.asMatrix() * objectSpace.asMatrixInverse());
}

MTransformationMatrix  mapObjectPoseToWorldSpace(MTransformationMatrix objectSpace, MTransformationMatrix pose){
        return MTransformationMatrix(pose.asMatrix() * objectSpace.asMatrix());
}

MTransformationMatrix interpolateTransform(MTransformationMatrix xf1, MTransformationMatrix xf2, double blend){

    if (blend == 1.0)
        return xf2;
    else if (blend == 0.0)
        return xf1;

    // translate
    MVector t = linearInterpolate(xf1.getTranslation(MSpace::kWorld), xf2.getTranslation(MSpace::kWorld), blend);

    // scale
	double threeDoubles[3];
	xf1.getScale(threeDoubles, MSpace::kWorld);
	MVector xf1_scl(threeDoubles[0],threeDoubles[1],threeDoubles[2]);

	xf2.getScale(threeDoubles, MSpace::kWorld);
	MVector xf2_scl(threeDoubles[0],threeDoubles[1],threeDoubles[2]);

    MVector vs = linearInterpolate(xf1_scl, xf2_scl, blend);
	double s[3] = {vs.x, vs.y, vs.z};
        
    // rotate
    MQuaternion q = slerp(xf1.rotation() ,xf2.rotation(), blend);
        
    // out
    MTransformationMatrix result;

	result.setTranslation(t, MSpace::kWorld);
	result.setRotationQuaternion(q.x, q.y, q.z, q.w);
	result.setScale(s, MSpace::kWorld);

    return result;
}


