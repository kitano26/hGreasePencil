import hou

# Get the stroke data from the parameter in null hgp_stroke_data node
stroke_data_node = hou.node("../hgp_stroke_data")

if stroke_data_node:
    stroke_data = stroke_data_node.parm("stroke_data").eval()
else:
    stroke_data = ""

if stroke_data:
    # Clear all geometry from stored data
    geo = hou.pwd().geometry()
    geo.clear()  
    
    # Rebuild geometry from stored data
    strokes = stroke_data.split("|")    # Split into individual strokes
    
    for i, stroke in enumerate(strokes):
        if stroke.strip():
            # Parse points in this stroke
            points = []
            for point_str in stroke.split(";"):
                if point_str.strip():
                    coords = point_str.split(",")
                    if len(coords) == 3:
                        try:
                            x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
                            points.append((x, y, z))
                        except ValueError:
                            print(f"Invalid coordinates: {coords}")
            
            # Create geometry for this stroke
            if len(points) > 1:
                point_objs = []
                for pos in points:
                    point = geo.createPoint()
                    point.setPosition(hou.Vector3(*pos))
                    point_objs.append(point)
                
                polyline = geo.createPolygon()
                polyline.setIsClosed(False)
                for point in point_objs:
                    polyline.addVertex(point)
    # Check if geometry is actually created
    if len(geo.points()) > 0:
        # Print first few point positions
        for i in range(min(3, len(geo.points()))):
            pos = geo.points()[i].position()
    else:
        print("No geometry created")
