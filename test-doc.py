#!/usr/bin/env python

from documents import DocumentRoot

root=DocumentRoot("/home/chris/local/reMarkable-backup/")


"""print(root.children.items())"""
print(root.name)

for s in root.children:
    n=root.get(s)
    print("---")
    print(n.metadata["visibleName"] + " ", n.size)
    print(n.metadata)
    print(n)

"""print(root)"""

