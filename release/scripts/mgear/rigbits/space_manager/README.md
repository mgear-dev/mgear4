# Space Manager 1.0.0
Manager for creating and managing space switches[^1]for rigs with and without mGear.  
User builds a rig, launches the GUI, configures needed settings and either runs the process straight from the GUI or exports configurations as smd file and creates a build based on the file later programmatically.  
Authored by Elina Sievänen @ Remedy Entertainment 2022.

----
## Features
- Generates following constraints : parent, point, orient and scale.
- Generates two types of menus: enumerated and float.
- Exports and Imports Spaces in human readable  *Space Manager Dictionary* (.smd) format.  
- Has a conventional GUI and a right click context menu for filling selected objects.
- Can be used with GUI or run as a post script using wrapper functions, see script template below.
----

#### Script Templates
An example on how to use space manager without GUI.

`import mgear.rigbits.space_manager.spaceManagerUtils as smu`
`smu.create_spaces(path="C:\Users\dummy\myRigs\rig01\extras\rig01.smd")`  

----

#### Structure
Space Manager consists of two files: Utils and UI, most functionality is on utils, while UI contains the pySide2 visuals + functionality of context menu. MGear rigbits menu reference to these can be found on `mgear>rigbits>menu.py`  

----
###### Special Thanks
Special thanks to Dave Reuling and Jose Martin, and the rest of the character tech team at Remedy for the valuable python and design tips.
[^1]:Space Switch is a feature that enables animator to change control's parent space between predetermined parents.  A classic case is a character's leg switching between world and hip spaces.