from setuptools import setup, find_packages
from codecs import open
from os import path


def read(filename, encoding="utf-8"):
    here = path.abspath(path.dirname(__file__))
    with open(path.join(here, filename), encoding=encoding) as f:
        return f.read()


setup(
    name="Findig",
    version="0.1.0.dev1",

    description="A micro-framework for RESTful web applications.",
    long_description=read("DESCRIPTION.rst"),

    url="not-a-valid-url",

    author="Te-je Rodgers",
    author_email="tjd.rodgers@gmail.com",

    license="MIT",

    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI",
    ],

    keywords="web framework werkzeug REST",

    packages=find_packages(exclude=["tests*",]),

    install_requires=['werkzeug'],

)