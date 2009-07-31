#!/usr/bin/python
from skdb.pymates import Interface

class Hole(Interface):
    def compatible(self, other):
        if isinstance(other, Peg):
            if not other.mated:
                return True #ok so type based checking sucks. wah.
        else: return False
    def __repr__(self):
        return "Hole(part=%s,id=%s)" % (self.part.name, self.identifier)

