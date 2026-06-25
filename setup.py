"""
Setup script for geomesh package.
"""

import os

from setuptools import find_packages, setup

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="geomesh",
    version="0.1.0",
    author="shingo405nagano",
    author_email="atodekakuyo@gmail.com",
    description="A Python library for generating and manipulating mesh grids used in GIS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shingo405nagano/geomesh",
    project_urls={
        "Bug Reports": "https://github.com/shingo405nagano/geomesh/issues",
        "Source": "https://github.com/shingo405nagano/geomesh",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "geopandas>=0.10.0",
        "shapely>=2.0.0",
        "pyproj>=3.0.0",
        "pyyaml>=5.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=0.990",
        ],
    },
    keywords="gis mesh grid geospatial japan jpmesh tile",
    package_data={
        "geomesh": ["py.typed"],
    },
    include_package_data=True,
    zip_safe=False,
)
