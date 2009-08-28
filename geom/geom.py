from OCC.gp import *
from OCC.Precision import *
from OCC.BRepBuilderAPI import *
import OCC.Utils.DataExchange.STEP
from skdb import Connection, Part, Interface, Unit, FennObject, round
import os, math
from copy import copy, deepcopy
from string import Template

def move_shape(shape, from_pnt, to_pnt):
    trsf = gp_Trsf()
    trsf.SetTranslation(from_pnt, to_pnt)
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()
    
def point_shape(shape, direction):
    '''rotates a shape to point along origin's direction. this function ought to be unnecessary'''
    shape = BRepBuilderAPI_Transform(shape, point_along(Direction(direction)), True).Shape()
    return shape
    
def angle_to(x,y,z):                                                         
    '''returns polar coordinates in radians to a point from the origin            
    el rotates around the x-axis; then az rotates around the z axis; r is the distance'''
    azimuth = math.atan2(y, x) #longitude                                       
    elevation = math.atan2(z, math.sqrt(x**2 + y**2))                              
    radius = math.sqrt(x**2+y**2+z**2)                                                 
    return((azimuth-math.pi/2, elevation-math.pi/2, radius))  
    #glRotatef(az-90,0,0,1)                                                        
    #glRotatef(el-90,1,0,0) 

def point_along(direction):
    ox, oy, oz = 0, 0, 0
    dx, dy, dz = Direction(direction).Coord()
    (az, el, rad) = angle_to(dx-ox, dy-oy, dz-oz)
    #print "az: %s, el: %s, rad: %s... dx: %s, dy: %s, dz %s)" % (az, el, rad, dx, dy, dz)
    trsf = gp_Trsf()
    trsf.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(1,0,0)), el)
    trsf2 = gp_Trsf()
    trsf2.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(0,0,1)), az)
    trsf2.Multiply(trsf)
    return trsf2
    
def build_trsf(point, x_vec, y_vec):
    point, x_vec, y_vec = Point(point), Direction(x_vec), Direction(y_vec)
    z_vec = Direction(x_vec.Crossed(y_vec))
    trsf=gp_Trsf()
    #from heekscad/src/Geom.cpp, sorta
    #TODO make sure x,y,z are orthonormal
    o, x, y, z = point.Coord(), x_vec.Coord(), y_vec.Coord(), z_vec.Coord()
    trsf.SetValues( x[0], y[0], z[0], o[0],
                            x[1], y[1], z[1], o[1],
                            x[2], y[2], z[2], o[2],
                            #0,     0,      0,     1,   #for you math types
                            0.0001, 0.00000001) #angular tolerance, linear tolerance
    return trsf

class OCC_triple(FennObject):
    '''simplifies wrapping pythonOCC classes like gp_Pnt, gp_Vec etc'''
    doc_format = Template('''wraps $occ_class: $cls(1,2,3) or $cls([1,2,3]) or $cls($occ_name(1,2,3))
    Caution: assigning an attribute like "x" will not affect the underlying $occ_name,
    you have to make a new one instead.''')
    wrapped_classes = gp_Pnt, gp_Vec, gp_Dir, gp_XYZ
    def __init__(self, x=None, y=None, z=None):
        if isinstance(x, self.__class__): #Point(Point(1,2,3))
            self.__dict__ = copy(x.__dict__) #does this use the same gp_Pnt object? (it shouldnt)
        for cls in OCC_triple.wrapped_classes: 
            if isinstance(x, cls): #Point(gp_Pnt()) or Point(Vector(1,2,3))
                self.x, self.y, self.z = (x.X(), x.Y(), x.Z())
                self.post_init_hook(); return
        if isinstance(x, list) or isinstance(x, tuple):
            self.x, self.y, self.z = float(x[0]), float(x[1]), float(x[2])
        elif x is not None and y is not None and z is not None:
            self.x, self.y, self.z = float(x), float(y), float(z)
        self.post_init_hook()
    def post_init_hook(self): #for instantiating from yaml
        try: self.__class__.occ_class.__init__(self,self.x,self.y,self.z)
        except ValueError: self.__class__.occ_class.__init__(self) #return a null point
    def __eq__(self, other): 
        if not isinstance(other, self.__class__.occ_class): return False
        else: return self.IsEqual(other, Precision().Confusion()) == 1
    def __repr__(self):
        return "%s(%s, %s, %s)" % (self.__class__.__name__, round(self.X()), round(self.Y()), round(self.Z()))
    def yaml_repr(self):
        return [round(self.X()), round(self.Y()), round(self.Z())]
    def transformed(self, transformation):
        '''transform is a verb'''
        result = self.occ_class.Transformed(self, transformation)
        return self.__class__(result)

class Point(OCC_triple, gp_Pnt):
    yaml_tag='!point'
    occ_class = gp_Pnt
    __doc__ = OCC_triple.doc_format.safe_substitute(occ_class=occ_class, cls='Point', occ_name = occ_class.__name__)

class XYZ(OCC_triple, gp_XYZ):
    occ_class = gp_XYZ
    __doc__ = OCC_triple.doc_format.safe_substitute(occ_class=occ_class, cls='XYZ', occ_name = occ_class.__name__)
    def __repr__(self):
        return "[%s, %s, %s]" % (self.X(), self.Y(), self.Z())

class Vector(OCC_triple, gp_Vec):
    yaml_tag='!vector'
    occ_class = gp_Vec
    __doc__ = OCC_triple.doc_format.safe_substitute(occ_class=occ_class, cls='Vector', occ_name = occ_class.__name__)
    def __eq__(self, other):
        '''vec needs LinearTolerance and AngularTolerance'''
        if not isinstance(other, self.__class__.occ_class): return False
        else: return self.IsEqual(other, Precision().Confusion(), Precision().Confusion()) == 1

class Direction(OCC_triple, gp_Dir):
    yaml_tag='!direction'
    occ_class = gp_Dir
    __doc__ = OCC_triple.doc_format.safe_substitute(occ_class=occ_class, cls='Vector', occ_name = occ_class.__name__)

    
class Transformation(gp_Trsf):
    '''wraps gp_Trsf for stackable transformations'''
    def __init__(self, parent=None, description="root node"):
        gp_Trsf.__init__(self)
        self.children = []
        self.description = description
        if parent:
            self.parent = parent
    def __repr__(self):
        '''see also Transformation.get_children'''
        return self.description
    def process_result(self, trsf, description=""):
        '''hides some redundancy from the other methods'''
        new_transformation = Transformation(gptrsf=trsf, parent=self, description=description)
        self.children.append(new_transformation)
        return new_transformation
    def get_children(self):
        '''returns a list of all children'''
        if self.children == []:
            return None
        return_list = copy(self.children)
        for each in self.children:
            more = each.get_children()
            if more:
                return_list.append(more)
        return return_list
    def run(self, result=None):
        '''multiplies all of the Transformations together'''
        if self.children == []:
            return self
        if result == None:
            result = Transformation()
        for each in self.children:
            result.Multiply(each.run())
        return result
    def Invert(self):
        '''wraps gp_Trsf.Inverted'''
        result = gp_Trsf.Inverted(self)
        return self.process_result(result, description="inverted")
    def Multiplied(self, *args):
        '''wraps gp_Trsf.Multiplied'''
        result = gp_Trsf.Multiplied(self, args)
        return self.process_result(result, description="multiplied")
    def SetRotation(self, pivot_point=Point([0,0,0]), direction=Direction([0,0,1]), angle=Unit("pi/2 radians")):
        '''SetRotation(pivot_point=Point(), direction=Direction(), angle=Unit())'''
        new_transformation = Rotation(parent=self, description="rotated", pivot_point=pivot_point, direction=direction, angle=angle)
        self.children.append(new_transformation)
        return new_transformation
    def SetTranslation(self, point1, point2):
        '''SetTranslation(point1=Point(), point2=Point())'''
        new_transformation = Translation(parent=self, description="translated", point1=point1, point2=point2)
        self.children.append(new_transformation)
        return new_transformation
    def SetMirror(self, point):
        '''wraps gp_Trsf.Mirror -- mirror about a point'''
        self_copy = copy(self)
        result = gp_Trsf.SetMirror(self_copy, Point(point))
        desc = "mirrored about %s" % (point)
        return self.process_result(result, description=desc)

class Rotation(Transformation):
    '''a special type of Transformation for rotation
    Rotation(pivot_point=Point(), direction=Direction(), angle=Unit())'''
    def __init__(self, pivot_point=Point([0,0,0]), direction=Direction([0,0,1]), angle=Unit("pi/2 radians"), parent=None, description=None):
        if not pivot_point and not direction and not angle: raise NotImplementedError, "you must pass parameters to Rotation.__init__"
        self.pivot_point = pivot_point
        self.direction = direction
        self.angle = angle
        Transformation.__init__(self, parent=parent, description=description)
        gp_Trsf.SetRotation(self, gp_Ax1(pivot_point, direction), float(angle))
    def __repr__(self):
        '''just a guess for now, please test'''
        xyz = gp_Trsf.RotationPart(self)
        return "Rotation[%s, %s, %s]" % (xyz.X(), xyz.Y(), xyz.Z())

class Translation(Transformation):
    '''a special type of Transformation for translation
    Translation(point1=, point2=)
    Translation(vector=) (not implemented)'''
    def __init__(self, point1=None, point2=None, vector=None, parent=None, description=None):
        if not point1 and not point2 and not vector: raise NotImplementedError, "you must pass parameters to Translation.__init__"
        if vector: raise NotImplementedError, "Translation.__init__ doesn't yet take a vector (sorry)" #FIXME
        self.point1 = point1
        self.point2 = point2
        self.vector = vector
        self.parent = parent
        self.description = description
        self.children = []
        Transformation.__init__(self, parent=parent, description=description)
        gp_Trsf.SetTranslation(self, point1, point2)
    def __repr__(self):
        xyz = gp_Trsf.TranslationPart(self)
        return "Translation[%s, %s, %s]" % (xyz.X(), xyz.Y(), xyz.Z())

def mate_first(part1):
    '''sets up the first part in your system. should be thrown into a class somewhere.'''
    def compatible(self, other):
        return True
    fake_interface = Interface(name="fake interface")
    fake_interface.compatible = compatible
    fake_interface.point = Point(0,0,0)
    fake_interface.orientation = Vector(0, 0, 1)
    fake_interface.connected = []
    fake_interface.x_vec = Vector(1,0,0) #ask fenn?
    fake_interface.y_vec = Vector(0,-1,0) #ask fenn?
    fake_part = Part(name="fake part", interfaces=[fake_interface]) #should never be seen by the user
    fake_part.post_init_hook()
    connecter = Connection(fake_part.interfaces[0], part1.interfaces[0])
    connecter.connect()
    return mate_connection(connecter)


def mate_connection(connection): 
    '''returns the gp_Trsf to move/rotate i2 to connect with i1. should have no side effects'''
    i1, i2 = connection.interface1, connection.interface2
    connection.connect()
    assert i1.part.transformation is not None
    if i1.part.transformation is None: i1.part.transformation = build_trsf(Point(0,0,0), Vector(1,0,0), Vector(0,1,0)); print 'hi'
    if hasattr(i1.part, "transformation"):
       tmp_point = Point(i1.point).Transformed(i1.part.transformation)
    else: tmp_point = i1.point #FIXME actually use this value or stacked parts won't work
    opposite = gp_Trsf()
    opposite.SetRotation(gp_Ax1(Point(i1.point), Direction(i1.x_vec)), math.pi) #rotate 180 so that interface z axes are opposed
    t = gp_Trsf()
    t.Multiply(i1.part.transformation)
    t.Multiply(opposite)
    t.Multiply(i1.get_transformation())
    t.Multiply(i2.get_transformation().Inverted())
    return t

    #i2.part.transformation.Multiply(opposite)
    return i2.part.transformation
   
#skdb.Interface
def get_transformation(self): #i wish this were a property instead
    '''returns the transformation to align the interface vector at the origin along the Z axis'''
    trsf = gp_Trsf()
    z_vec = Vector(self.x_vec).Crossed(Vector(self.y_vec)) #find the interface vector
    return build_trsf(self.point, self.x_vec, self.y_vec)
Interface.get_transformation = get_transformation

#skdb.Part
def load_CAD(self):
    '''load this object's CAD file. assumes STEP.'''
    if len(self.files) == 0: return #no files to load
    assert hasattr(self,"package"), "Part.load_CAD doesn't have its package loaded."
    #FIXME: assuming STEP
    #TODO: check/verify filename path
    #FIXME: does not properly load in models from multiple files (2009-07-30)
    for file in self.files:
        full_path = os.path.join(self.package.path(), str(file))
        my_step_importer = OCC.Utils.DataExchange.STEP.STEPImporter(full_path)
        my_step_importer.ReadFile()
        self.shapes = my_step_importer.GetShapes()
        self.compound = my_step_importer.GetCompound()
    #i, j, k, point = self.interfaces[0].i, self.interfaces[0].j, self.interfaces[0].k, self.interfaces[0].point
    #x,y,point = self.interfaces[0].x,self.interfaces[0].y,self.interfaces[0].point
    return self.shapes

Part.load_CAD = load_CAD
def add_shape(self, result):
    '''add a shape to self.ais_shapes. this isn't as exciting as you think it is.'''
    if type(result) == type([]): self.ais_shapes = result[0]
    else: self.ais_shapes = result
    return
Part.add_shape = add_shape

def get_point(self): return list(self.__gp_Pnt_point.Coord())
def set_point(self, value): 
    if isinstance(value, Unit):
        raise NotImplementedError, 'coords must be in mm'
    self.__gp_Pnt_point = gp_Pnt(val[0], val[1], val[2])
def del_point(self): del self.__gp_Pnt_point

def get_gp_Pnt(self):
    return self.__gp_Pnt

def transformed(self, trsf):
    return self.__gp_Pnt.Transformed(trsf)

#stuff the class with new funcs
for i in [load_CAD, add_shape, get_gp_Pnt, transformed]:
    setattr(Part, i.__name__, i)

def common_volume(part1, part2):
    '''returns the volume of the intersection of two parts'''
    shape1 = part1.shapes[0]
    shape2 = part2.shapes[0]
    fused_shape = BRepAlgoAPI_Common(shape1, shape2)
    #use BRepGProp.VolumeProperties()
    #see http://adl.serveftp.org/lab/opencascade/doc/ReferenceDocumentation/ModelingAlgorithms/html/classBRepGProp.html
    #see http://www.opencascade.org/org/forum/thread_4685/
    #see http://www.opencascade.org/org/forum/thread_6622/ (a comment by rob bachrach)
    tmp_useless = GProp.GProp_GProps()
    calculator = BRepGProp()
    calculator.VolumeProperties(fused_shape.Shape(), tmp_useless)
    volume = tmp_useless.Mass()
    return volume 

def part_collision(part1, part2, threshold=0.0):
    '''determines whether or not two parts are colliding, given a threshold of maximum allowable intersection
    returns True or False'''
    volume = common_volume(part1, part2)
    if volume > threshold: return True
    else: return False

def connection_interference(conn, threshold=0.0):
    '''determines whether or not a connection has a geometric collision (only for the two mating parts) within a threshold
    returns True or False'''
    part1 = conn.interface1.part
    part2 = conn.interface2.part
    return part_collision(part1, part2, threshold=threshold)

def deep_part_collider(parts):
    '''given a list of parts, checks whether or not any of them geometrically overlap
    returns a list of triples in the form: (volume, part1, part2) where volumetric interference was found'''
    errors = []
    for part in parts:
        for part2 in parts:
            volume = common_volume(part1, part2)
            if volume > 0:
               errors.append((volume, part1, part2))
    return errors
