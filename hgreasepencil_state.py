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
import uuid
import copy

class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.node = self.scene_viewer.currentNode()

        # Drawing state
        self.mouse_points = []
        self.isDrawing = False

        # Stroke data
        self.geo = hou.Geometry()
        self.strokes = []
        self.bgeo_file = self.get_bgeo_path()
        self.load_strokes_from_bgeo()   # Load past saved strokes from .bgeo file

        # Stroke functionality
        self.redo_stack = []

        # Set up GeometryDrawable for real-time brush drawing
        self.brush_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "brush_drawable"
        )
        self.brush_drawable.setParams({
            "color1": self.node.parmTuple("color_alpha").eval(),  
            "line_width": 3.0
        })
        self.brush_drawable.show(True)

        # Ensure internal nodes are created and wired up
        self.python_sop, self.output_node = self.setup_internal_network()
        self.python_sop.cook(force=True)

    def onMouseEvent(self, kwargs):
        """ Process mouse and tablet events """
        ui_event = kwargs["ui_event"]
        dev = ui_event.device()
        reason = ui_event.reason()
        isLMB = dev.isLeftButton()
        
        if reason == hou.uiEventReason.Start and isLMB: # LMB is pressed - start drawing
            self.isDrawing = True
            self.mouse_points.clear()
            self.update_brush_drawable()
        elif reason == hou.uiEventReason.Active and isLMB: # LMB is held down - continue drawing
            curr_view = self.scene_viewer.curViewport()

            # Convert mouse position to world position (hou.Vector3)
            world_pos = self.get_mouse_world_position(kwargs)

            self.mouse_points.append(world_pos)  
            self.update_brush_drawable()   
        elif reason == hou.uiEventReason.Changed and self.isDrawing: # LMB is released - commit stroke to geo
            self.commit_stroke()   # Commit stroke to geo

            # Reset drawing state
            self.isDrawing = False
            self.mouse_points.clear()
            self.update_brush_drawable()

        # Must return True to continue processing events
        return True

    def onDraw(self, kwargs):
        """Draws the brush drawable in the viewport (real-time drawing feedback)
           Renders brush_drawable's geometry"""
        handle = kwargs["draw_handle"]
        self.brush_drawable.draw(handle)

    def onKeyEvent(self, kwargs):
        """ Called for processing a keyboard event"""
        ui_event = kwargs["ui_event"]
        state_parms = kwargs["state_parms"]
        pressed_keys = ui_event.device().keyString().split("+")

        if "y" in pressed_keys and "Ctrl" in pressed_keys:
            if "Shift" in pressed_keys:
                print("redo draw")
                self.redo_draw()
            else:
                self.undo_draw()

        # Must returns True to consume the event
        return True
    
    def update_brush_drawable(self):
        """Creates geometry based on points list and assigns the geo to brush_drawable"""

        if len(self.mouse_points) > 1:
            temp_geo = hou.Geometry()

            # create Point objects
            point_objs = [temp_geo.createPoint() for curr_pt in self.mouse_points] 
            
            # Set position of each point
            for pt, point_obj in zip(self.mouse_points, point_objs):
                if isinstance(pt, hou.Vector3):
                    point_obj.setPosition(pt) 

            # Create a polyline
            polyline = temp_geo.createPolygon() 
            polyline.setIsClosed(False)    # Set polygon to be open (so it's a polyline)

            # Add each point to the polygon as a vertex
            for point in point_objs:
                polyline.addVertex(point)  

            # Set brush drawable geometry
            self.brush_drawable.setParams({
                "color1": self.node.parmTuple("color_alpha").eval(),
                "line_width": 3.0
            })
            self.brush_drawable.setGeometry(temp_geo)
        else:
            self.brush_drawable.setGeometry(hou.Geometry())

    def commit_stroke(self):
        """Commits the stroke so it persists in the scene"""
        if len(self.mouse_points) > 1:
            # Create a new Stroke object for the in-memory list
            color_alpha = self.node.parmTuple("color_alpha").eval()
            curr_stroke = Stroke(
                points=[(pt.x(), pt.y(), pt.z()) for pt in self.mouse_points],
                color=color_alpha[:3]
            )
            self.strokes.append(curr_stroke)

            # Add the stroke to the .bgeo file and display all the strokes
            curr_stroke.convert_to_geo_format(self.geo)
            self.geo.saveToFile(self.bgeo_file)
            self.python_sop.cook(force=True)

    def undo_draw(self):
        if self.strokes:
            undo_stroke = self.strokes.pop()
            self.redo_stack.append(copy.deepcopy(undo_stroke))
            
            # Remove the stroke from the .bgeo file
            self.geo.clear()
            for curr_stroke in self.strokes:
                curr_stroke.convert_to_geo_format(self.geo)
            
            self.geo.saveToFile(self.bgeo_file)
            self.python_sop.cook(force=True)
    
    def redo_draw(self):
        if self.redo_stack:
            redo_stroke = self.redo_stack.pop()
            self.strokes.append(copy.deepcopy(redo_stroke))

            # Add the stroke to the .bgeo file
            redo_stroke.convert_to_geo_format(self.geo)
            self.geo.saveToFile(self.bgeo_file)
            self.python_sop.cook(force=True)

    def get_mouse_world_position(self, kwargs):
        try:
            # Get ray starting at camera and passes thru mouse position
            ray_origin, ray_dir = kwargs["ui_event"].ray()
            
            # Intersect with Z=0 plane
            plane_normal = hou.Vector3(0, 0, 1)
            plane_point = hou.Vector3(0, 0, 0)
            denom = ray_dir.dot(plane_normal)

            if abs(denom) > 1e-6:   # if ray is not parallel to plane
                t = (plane_point - ray_origin).dot(plane_normal) / denom
                if t > 0:
                    intersection = ray_origin + ray_dir * t
                    return intersection
                    
            # Otherwise, use ray origin
            return ray_origin
        except Exception as e:
            print(f"Error in getting mouse world position: {e}")
            return hou.Vector3(0, 0, 0)
    
    def get_default_bgeo_path(self):
        # Get the current .hip file directory
        hip_dir = os.path.dirname(hou.hipFile.path())
        # Make a subfolder for strokes if it doesn't exist
        strokes_dir = os.path.join(hip_dir, "strokes")
        if not os.path.exists(strokes_dir):
            os.makedirs(strokes_dir)
        # Use the node's name and session id for uniqueness
        node_name = self.node.name()
        node_id = self.node.sessionId()
        bgeo_filename = f"{node_name}_{node_id}_strokes.bgeo"
        return os.path.join(strokes_dir, bgeo_filename)

    def get_bgeo_path(self):
        parm = self.node.parm("stroke_file").eval()
        
        if parm:
            return parm
        else:
            path = self.get_default_bgeo_path()
            node.parm("stroke_file").set(path)
            return self.get_default_bgeo_path()

    def load_strokes_from_bgeo(self):
        """Loads strokes from .bgeo file"""
        if os.path.exists(self.bgeo_file):
            self.geo.loadFromFile(self.bgeo_file)

            for prim in self.geo.prims():
                self.strokes.append(Stroke.convert_from_geo_format(prim))

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
        python_sop = self.get_python_sop(self.node)
        output_node = self.get_output_node(self.node)

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
        return python_sop, output_node


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

class Stroke(object):
    def __init__(self, points, color=(1.0,0.0,0.0), uid=None):
        self.points = points
        self.color = color
        self.uid = uid or str(uuid.uuid4())

    def convert_to_geo_format(self, geo):       
        point_objs = [geo.createPoint() for _ in self.points]
        for pt, pos in zip(point_objs, self.points):
            pt.setPosition(hou.Vector3(*pos))

        if len(point_objs) > 1:
            # Create vertices for polyline
            polyline = geo.createPolygon()
            polyline.setIsClosed(False)
            for pt in point_objs:
                polyline.addVertex(pt)

            # Set attributes
            color_attr = geo.findPrimAttrib("Cd")
            if not color_attr:
                color_attr = geo.addAttrib(hou.attribType.Prim, "Cd", hou.Vector3(1.0, 0.0, 0.0))
            polyline.setAttribValue(color_attr, hou.Vector3(*self.color))

            uid_attr = geo.findPrimAttrib("uid")
            if not geo.findPrimAttrib("uid"):
                uid_attr = geo.addAttrib(hou.attribType.Prim, "uid", "")
            polyline.setAttribValue(uid_attr, self.uid)
    
    
    def convert_from_geo_format(prim):
        points = [tuple(v.point().position()) for v in prim.vertices()]
        color = tuple(prim.attribValue("Cd"))
        uid = prim.attribValue("uid")
        return Stroke(points,color,uid)