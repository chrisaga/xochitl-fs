#!/usr/bin/env python

from documents import DocumentRoot

root=DocumentRoot("/home/chris/local/reMarkable-backup/")


"""print(root.children.items())"""
for n in root.children.items():
    print(n)
