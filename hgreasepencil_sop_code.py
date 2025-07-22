"""
This script is used to commit the geometry to the scene from the stroke data stored in the hgp_stroke_data node.
"""

import hou
import os

# Get the path to the .bgeo file (could be from a parameter)
hda_node = hou.node("..")
bgeo_file= hda_node.parm("stroke_file").eval()

geo = hou.pwd().geometry()
geo.clear()

if os.path.exists(bgeo_file):
    geo.loadFromFile(bgeo_file)
else:
    print("No .bgeo file found at", bgeo_file)

