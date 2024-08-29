# Another FUSE filesystem wrapper for reMarkable documents (Work in progress)

## Context and motivation

This project comme after nick8325's [remarkable-fs](https://github.com/nick8325/remarkable-fs) which is based on [https://github.com/fusepy/fusepy](https://github.com/fusepy/fusepy) FUSE python binding.
Both seems to be unmaintained for years. The only active python FUSE library for now (summer 2024) is [python-fuse](https://github.com/libfuse/python-fuse) which is part of the reference implementation of the Linux FUSE.

I decided to:

* port `remarkable-fs` to `python-fuse`
* make it work with a local backup of the reMarkable files (easyier debugging and less risks of ruining the actual documents)
* decide latter if it'd worth implementing direct ssh connection again (several options already exist for syncing or backuping the tablet)

## Status : Proof Of Concept

You can mount a reMarkable documents backup directory and browse it as a document arborescence.

### Done

* Browse a local backup
* Open and read "plain files" (such as pdf) or copy it to another filesystem
* Copy (cp) "plain files" (annotations are lost in the duplicate)
* Create and write "plain files" (such as pdf) to xochitl filesystem
	- Create a new node (done)
	- Create a temporary file for data (done but not useful any more)
	- Actually save node with all the metadata files by calling node.save() from flush() call (done)
* Use node.read() to read node data.
* Transfer the `.file` object from the `XochitlFile` object to the `XochitlFile.node` so it can be acceded from the documents module (`node.read()`) and we can get rid of the "@lazy property" (then the `lazy` module dependency)
* Figure-out the fd management without temporary file
* Forge better fgetattr() result

### To Do


* Check if something is to be done with `NewNodes` to make them regular `Nodes` after they have been saved.
* Figure-out iolock
* Read notebook file in a single data structure which can be latter used to create a duplicate in the xochitl filesystem (i.e. implement a true copy/paste or cp command)
* Create and write new notebook files from a previously read data structure
* Better detection of epub files (any kind of zip file begins with `PK`):

~~~
00000000  50 4b 03 04 0a 00 00 00  00 00 00 5c 99 48 6f 61  |PK.........\.Hoa|
00000010  ab 2c 14 00 00 00 14 00  00 00 08 00 00 00 6d 69  |.,............mi|
00000020  6d 65 74 79 70 65 61 70  70 6c 69 63 61 74 69 6f  |metypeapplicatio|
00000030  6e 2f 65 70 75 62 2b 7a  69 70 50 4b 03 04 0a 00  |n/epub+zipPK....|
~~~


### Might Do
* Auto convert notebook files to the latest version when written
* Dolphin "services" to implement useful menus like convert to pdf or svg.

### Dependencies

#### `python-fuse`

You need a release ≥ v1.0.5 to run with Python ≥ v3.10.
Unfortunately Ubuntu has not updated and still distribute python-fuse 1.0.2.
Fortunately, python-fuse can be installed easily from https://github.com/libfuse/python-fuse

