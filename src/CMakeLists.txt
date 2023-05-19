set(SOURCE_FILES

	"add10scalarNode.cpp"
	"curveCns.cpp"
	"ikfk2Bone.cpp"
	"interpolateMatrix.cpp"
	"inverseRotOrder.cpp"
	"linearInterpolate3DvectorNode.cpp"
	"matrixConstraint.cpp"
	"mulMatrix.cpp"
	"percentageToU.cpp"
	"rayCastPosition.cpp"
	"register.cpp"
	"rollSplineKine.cpp"
	"slideCurve2.cpp"
	"spinePointAt.cpp"
	"springGravityNode.cpp"
	"springNode.cpp"
	"squashStretch2.cpp"
	"trigonometryAngle.cpp"
	"utils.cpp"
	"uToPercentage.cpp"
	"vertexPosition.cpp"
	"mgear_solvers.h"
)

find_package(Maya REQUIRED)

include_directories(${MAYA_INCLUDE_DIR})
link_directories(${MAYA_LIBRARY_DIR})


add_library(${PROJECT_NAME} SHARED ${SOURCE_FILES})
target_link_libraries(${PROJECT_NAME} ${MAYA_LIBRARIES})
MAYA_PLUGIN(${PROJECT_NAME})
