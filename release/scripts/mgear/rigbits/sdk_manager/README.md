# SDK_manager

Originally based off of one of Judd Simantov’s [facial rigging](https://vimeo.com/user5566082) workflows 
using joints and SDK’s to craft facial shapes with the power of blendshapes 
but the control of joints and weighting.

The toolset I’d like to make is based off of SuperCrumbly’s [abFaceRig](https://www.youtube.com/watch?v=NnECICrGg1k&index=38&list=WL&t=977s) toolset. 
It was designed to work hand in hand with Judd’s SDK workflow. 

----
## Pros

* Can get same results as Blendshape Based face Rig. Giving the rigger extreme control over every single shape.
* Can expose tweak control over every joint to Anim, This might be an alternative to shape fixing as they would have the same level of control.
* If implemented correctly can fit into the rebuild workflow, allowing pivots and controllers to be altered without destroying rig work.
* Can export one characters weight map, Guide, SDK’s and import to another character as a base to work from. Making time to rig less.
* Can Add blendshapes on top of  things for further deformation
* Low poly character faces work to this method’s favour as less SDK components need to be made, making the rig lighter. 

## Cons

* 1000’s of SDK’s are slower than blendshapes. (Rig performance) (This needs to be TESTED.)
* Controls might feel “floaty”, but the effect can be minimised.

----

### Component

Each component looks like this:
* ROOT
  * SDKBOX
    * Anim Tweak
      * Joint driver Grp

SDK’s are set on the SDK box, driven by normal driver controls using custom made tools for the workflow.

Blendshapes can also be attached to the driver controls in cases where further deformation is needed and cannot be achieved with only the SDK boxes and weight painting. 

NOTE: At present the SDK box controls still get added to the control's group. We highly reccomend that you remove them from this set as you do not want animators setting keys on them. There is also a function in the ui under the Tools menu to lock SDK ctls. I reccomend locking and hiding the shape nodes before sending off to the anim team.
