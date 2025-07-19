"""
State:          hGreasePencil
State type:     hGreasePencil_state
Description:    Grease Pencil Effect
Author:         Katelyn_Itano
Date Created:   July 15, 2025 - 17:46:53
"""
# STRING PARAM FOR STROKE DATA - WORKING

import hou
import viewerstate.utils as su
import os

class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.points = []
        self.isDrawing = False
        self.mouse_pos = None

        # Set up GeometryDrawable for real-time brush drawing
        self.brush_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "brush_drawable"
        )
        self.brush_drawable.setParams({
            "color1": hou.Vector4(1, 0, 0, 1),  # Red
            "line_width": 3.0
        })
        self.brush_drawable.show(True)

        # Ensure internal nodes are created and wired up
        self.stroke_data_node, self.python_sop, self.output_node = self.setup_internal_network()

    def onMouseEvent(self, kwargs):
        """ Process mouse and tablet events """
        ui_event = kwargs["ui_event"]
        dev = ui_event.device()
        reason = ui_event.reason()
        isLMB = dev.isLeftButton()
        
        if reason == hou.uiEventReason.Start and isLMB: # LMB is pressed - start drawing
            self.isDrawing = True
            self.points.clear()
            self.update_brush_drawable()
        elif reason == hou.uiEventReason.Active and isLMB: # LMB is held down - continue drawing
            curr_view = self.scene_viewer.curViewport()

            # Convert mouse position to world position
            world_pos = curr_view.mapToWorld(dev.mouseX(), dev.mouseY())
            if isinstance(world_pos, tuple):
                world_pos = world_pos[0]

            self.points.append(world_pos)   # Append world position to points list
            self.update_brush_drawable()   # Update brush drawable
        elif reason == hou.uiEventReason.Changed and self.isDrawing: # LMB is released - commit stroke to geo
            self.commit_stroke()   # Commit stroke to geo

            # Reset drawing state
            self.isDrawing = False
            self.points.clear()

        # Must return True to continue processing events
        return True

    def onDraw(self, kwargs):
        """Draws the brush drawable in the viewport (real-time drawing feedback)
           Renders brush_drawable's geometry"""
        handle = kwargs["draw_handle"]
        self.brush_drawable.draw(handle)
    
    """
    HELPER FUNCTIONS
    """
    def update_brush_drawable(self):
        """Creates geometry based on points list and assigns the geo to brush_drawable"""

        if len(self.points) > 1:
            geo = hou.Geometry()    # create Geometry container
            point_objs = [geo.createPoint() for curr_pt in self.points] # create Point objects
            
            # set position of each point
            for pt, point_obj in zip(self.points, point_objs):
                if isinstance(pt, hou.Vector3):
                    point_obj.setPosition(pt) 
            polyline = geo.createPolygon() # create Polygon object
            polyline.setIsClosed(False)    # set polygon to be open (so it's a polyline)

            # add each point to the polygon as a vertex
            for point in point_objs:
                polyline.addVertex(point)  

            # set brush drawable geometry
            self.brush_drawable.setGeometry(geo)
        else:
            self.brush_drawable.setGeometry(hou.Geometry())

    def commit_stroke(self):
        """Commits the stroke so it persists in the scene"""
        if len(self.points) > 1:
            # Convert points to string format for storage
            stroke_data = []
            for pt in self.points:
                if isinstance(pt, hou.Vector3):
                    stroke_data.append(f"{pt.x()},{pt.y()},{pt.z()}")
            try:
                # Append to existing stroke data
                existing_data = self.stroke_data_node.parm("stroke_data").eval()
                if existing_data:
                    all_strokes = existing_data + "|" + ";".join(stroke_data)
                else:
                    all_strokes = ";".join(stroke_data)
                self.stroke_data_node.parm("stroke_data").set(all_strokes)
                
                # Force the Python SOP to recook
                self.python_sop.cook(force=True)
            except Exception as e:
                error_msg = f"Could not store stroke data:\n{e}"
                hou.ui.displayMessage(error_msg)

    def get_stroke_data_node(self, parent):
        node = parent.node("hgp_stroke_data")
        if not node:
            node = parent.createNode("null", "hgp_stroke_data")
            node.moveToGoodPosition()
            node.addSpareParmTuple(hou.StringParmTemplate("stroke_data", "Stroke Data", 1))
            node.parm("stroke_data").set("")
        return node

    def get_python_sop(self, parent):
        node = parent.node("hgp_geometry")
        if not node:
            node = parent.createNode("python", "hgp_geometry")
            node.moveToGoodPosition()
        return node

    def get_output_node(self, parent):
        node = parent.node("output0")
        if not node:
            node = parent.createNode("output", "output0")
            node.moveToGoodPosition()
        return node

    def setup_internal_network(self):
        parent = self.scene_viewer.currentNode()
        stroke_data_node = self.get_stroke_data_node(parent)
        python_sop = self.get_python_sop(parent)
        output_node = self.get_output_node(parent)

        # Always update the Python SOP code from the external file
        sop_code_path = os.path.join(os.path.dirname(__file__), "hgreasepencil_sop_code.py")
        with open(sop_code_path, "r") as f:
            python_code = f.read()
        python_sop.parm("python").set(python_code)

        # Connect and set flags as before
        output_node.setInput(0, python_sop)
        output_node.setDisplayFlag(True)
        output_node.setRenderFlag(True)
        
        # Return internal nodes
        return stroke_data_node, python_sop, output_node

def createViewerStateTemplate():
    """ Mandatory entry point to create and return the viewer state 
        template to register. """

    state_typename = "hGreasePencil_state"
    state_label = "hGreasePencil"
    state_cat = hou.sopNodeTypeCategory()  

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("MISC_python")

    return template
