#!/usr/bin/env python

from setuptools import setup
import sys

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except:
    print('Skipping md->rst conversion for long_description')
    long_description = 'Error converting Markdown from git repo'

if len(long_description) < 100:
    print("\n***\n***\nWARNING: %s\n***\n***\n" % long_description)

setup(
    name='anthemav_x00',
    version='0.0.0',
    author='Tim Inglis',
    author_email='tinglis1@gmail.com',
    url='https://github.com/tinglis1/python-anthemav',
    license="LICENSE",
    packages=['anthemav_x00'],
    scripts=[],
    description='Python API for controlling x00 Anthem Receivers',
    long_description=long_description,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    include_package_data=True,
    zip_safe=True,

    entry_points={
        'console_scripts': [ 'anthemav_monitor = anthemav.tools:monitor', ]
    }
)
