#!/usr/bin/env python

#    Test the documents module

from documents import DocumentRoot, Collection

root=DocumentRoot("/home/chris/local/reMarkable-backup/")


"""print(root.children.items())"""
print(root.name)

for s in root.children:
    n=root.get(s)
    print("---")
    print(n.metadata["visibleName"] + " ", n.size)
    print(n.metadata)
    print(n)

node = root
if isinstance(node, Collection):
    print (".")
    print ("..")
    for s in node:
        print(s)
        
node = root.get("Autres")
print (".")
print ("..")
for s in node:
    print(node.get(s))

print("=======")
node = root.get_node_from_path("/Autres/DYL.notebook")
print (node)

"""print(root)"""

