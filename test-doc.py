#!/usr/bin/env python

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
        

"""print(root)"""

