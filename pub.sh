#! /bin/bash

rm -rf showdownpy.egg-info build dist
python setup.py sdist bdist_wheel
twine upload dist/*
