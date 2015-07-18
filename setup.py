#-*- coding: utf-8 -*-
from setuptools import setup, find_packages
from codecs import open
from os import path


def read(filename, encoding="utf-8"):
    here = path.abspath(path.dirname(__file__))
    with open(path.join(here, filename), encoding=encoding) as f:
        return f.read()


setup(
    name="Findig",
    version=read("findig/VERSION").strip(),

    description="A micro-framework for RESTful web applications.",
    long_description=read("DESCRIPTION.rst"),

    url="https://github.com/geniphi/findig",

    author="Te-je Rodgers",
    author_email="tjd.rodgers@gmail.com",

    license="MIT",

    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
    ],

    keywords="web framework werkzeug REST",

    packages=find_packages(exclude=["test*",]),

    package_data={
        'findig': ['VERSION'],
    },

    setup_requires=['setuptools_scm'],
    use_setuptools_scm={'write_to': 'findig/VERSION'},

    install_requires=['werkzeug'],
    extras_require={
        'redis': ['redis'],
        'sql': ['sqlalchemy'],
    },

)
