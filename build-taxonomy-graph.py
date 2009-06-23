import os
import yaml
import graph

linnaeus = yaml.load(open('taxonomy.yaml'))

taxonomy = graph.graph()
node_id=0

def walk(treebeard, name, parent_node):
    global node_id
    try:
        for key in treebeard.keys():
            node_id += 1
            taxonomy.add_node(node_id, [('label', key)])
            taxonomy.add_edge(parent_node, node_id)
            walk(treebeard[key], key, node_id)
    except AttributeError: #leaf node, need some way to peek at contents
        pass #node_id += 1

taxonomy.add_node(node_id, [('label', 'root')])
walk(linnaeus['processes']['shaping']['joining'], 'root', node_id)

#run with: python build-taxonomy-graph.py  |dot -Tpng -o'foo.png
print graph.readwrite.write_dot_graph(taxonomy, False)
