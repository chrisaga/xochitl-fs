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


### To Do

* Create and write "plain files" (such as pdf) to xochitl filesystem
* Read notebook file in a single data structure which can be latter used to create a duplicate in the xochitl filesystem (i.e. implement a true copy/paste or cp command)
* Create and write new notebook files from a previously read data structure

### Might Do
* Auto convert notebook files to the latest version when written
* Dolphin "services" to implement useful menus like convert to pdf or svg.