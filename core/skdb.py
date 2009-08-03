#skdb.py
#(c) ben lipkowitz 11/16/08, distributed under the GPL version 2 or later

import yaml
import re
import os
from string import Template

from units import Unit, Range, Uncertainty, UnitError, NaNError
from interface import Interface, Connection, Mate
from part import Part
from yamlcrap import FennObject, Dummy, tag_hack
from threads import Thread
import settings

debug = False

# the following aren't our responsibility, actually (pythonOCC?)
#class Circle(yaml.YAMLObject)
#class Cylinder(yaml.YAMLObject)
#class InterfaceGeom(yaml.YAMLObject):

class Contributor(yaml.YAMLObject):
    '''used in package metadata'''
    yaml_tag='!contributor'
    def __init__(self, name, email=None, url=None):
        self.name = name
        self.email = email
        self.url = url

class Author(Contributor):
    yaml_tag='!author'

class Package(yaml.YAMLObject):
    yaml_tag='!package'
    def __init__(self, name, unix_name=None, license=None, urls=None, contributors=None):
        self.name = name
        self.unix_name = unix_name
        if unix_name == None:
            #TODO: complain if it's not a valid "unix name"
            self.unix_name = name
        self.license = license
        self.urls = urls
        self.contributors = contributors
        #TODO inherit from some pretty container class
    def load(self, content):
        '''loads some yaml (not necessarily into type Package)
        it's kind of fishy since a package is multiple files at the moment.'''
        return yaml.load(content)
    def dump(self):
        '''returns this object in yaml'''
        return yaml.dump(self)
    def dump_metadata(self):
        '''dump only the content for or from metadata.yaml'''
        pass
    def dump_template(self):
        '''dump only the content for or from template.yaml'''
        pass
    def dump_data(self):
        '''dump only the content for or from data.yaml'''
        pass
    def open(self, path=None):
        if path == None: path = self.unix_name
        #else: pass #TODO: check if the named parameter references a valid unix_name
        assert hasattr(settings,"paths")
        assert settings.paths.has_key("SKDB_PACKAGE_DIR") #FIXME: load up from environmental variables or global skdb config
        #the path must actually exist
        assert not (os.listdir(settings.paths["SKDB_PACKAGE_DIR"]).count(path) == 0)
        package_path = os.path.join(settings.paths["SKDB_PACKAGE_DIR"],path)
        #must have the required files
        required_files = ["metadata.yaml", "template.yaml", "data.yaml"] #maybe last one should be s/path/self\.name/?
        for file in required_files:
            assert not (os.listdir(os.path.join(settings.paths["SKDB_PACKAGE_DIR"],path)).count(file) == 0)
        #TODO: load metadata, load template
        #self = yaml.load(..) didn't work wtf?
        return yaml.load(open(os.path.join(package_path, "metadata.yaml")))

class Distribution(FennObject):
    yaml_path = ['typical', 'feasible']

class RuntimeSwitch(FennObject):
    '''return different values depending on what parameters have been selected.
    example: !example
        temperature: !which teatype, temp
        parameters:
            teatype:
                iced:
                    flavor: lemon
                    temp: 280K
                hot:
                    flavor: earl grey
                    temp: 340K
    >>> example(teatype=iced) #note this doesnt actually work yet
    >>> example.temperature
    280K'''
    
    yaml_tag = '!which'
    def __init__(self, depends, parameter=None): #i dont like 'depends' but cant think of a better word
        self.depends, self.parameter = depends, parameter
    def __repr__(self):
        return 'RuntimeSwitch(%s, %s)' % (self.depends, self.parameter)
    def yaml_repr(self):
        return '%s, %s' % (self.depends, self.parameter)
    def get(self):
        if self.parameter:
            valid_values = package.parameters[self.depends].keys()
            if package.runtime[self.depends] in valid_values: 
                return package.parameters[self.depends][package.runtime[self.depends]][self.parameter] #zoinks
            else: 
                return None 
        else: 
            try: return getattr(package.runtime, self.depends) #uh, this is probably wrong
            except AttributeError: return package[self.depends] #not an object
  #some function to search for similar values here

    @classmethod
    def from_yaml(cls, loader, node):
        '''see http://pyyaml.org/wiki/PyYAMLDocumentation#Constructorsrepresentersresolvers'''
        data = loader.construct_scalar(node)
        try: depends, parameter = [i.strip() for i in data.split(',')]
        except ValueError: #only one argument
            depends = data.strip()
            return cls(depends)
        return cls(depends, parameter=parameter)


class Formula(FennObject, str):
    yaml_tag = '!formula'

class Geometry(FennObject):
    yaml_tag = '!geometry'
    
class Process: #(FennObject):
    yaml_tag = '!process'
    def __init__(self, name):
        self.name, self.classification, self.mechanism, self.geometry, self.surface_finish, self.consumables, self.functionality, self.effects, self.parameters, self.safety = None, None, None, None, None, None, None, None, None, None
        self.name = name

    #def __repr__(self):
        #return "Process(%s)" % (self.name)
    

class Material(Package):
    yaml_tag = '!material'
    def __init__(self, name, density=1, specific_heat=1, etc=None): #TODO figure out what goes here
        self.name = name
        self.density = density
        self.specific_heat = specific_heat

class Fastener(Package):
    yaml_tag = '!fastener'
    '''could be a rivet, could be a bolt. duct tape? superglue? twine? hose clamp?
    these methods are what actually get called by higher levels of abstraction'''
    def __init__(self, force, rigidity, safety_factor=7):
        pass

class Component(yaml.YAMLObject):
    '''is this sufficiently generic or what?'''
    yaml_tag = '!component'
    interfaces = []
    #def __init__(self):
    #        pass
    pass

class Bolt(Fastener):
    '''a screw by itself cannot convert torque to force. a bolt is a screw with a nut'''
    def __init__(self, screw, nut):
        self.screw = screw
        self.nut = nut

def load(string):
    for cls in [Range, RuntimeSwitch, Formula, Uncertainty]: #only one at a time works so far?
        if hasattr(cls, 'yaml_pattern'):
            yaml.add_implicit_resolver(cls.yaml_tag, re.compile(cls.yaml_pattern))
    return yaml.load(string)

def dump(value, filename=None):
    retval = yaml.dump(value, default_flow_style=False)
    if filename is not None:
        f = open(filename, 'w')
        f.write(retval)
    else:
        return retval
    #some stdout call here might not be a bad idea

package = 'blah'
def main():
    #basic self-test demo
    package = load(open('tags.yaml'))
    print dump(package)

if __name__ == "__main__":
    main()
