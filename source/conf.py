# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
# -- Path setup --------------------------------------------------------------
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

from sphinx_pyproject import SphinxConfig

config = SphinxConfig("../pyproject.toml", globalns=globals())

sys.path.insert(1, os.path.abspath("."))

# -- Project information -----------------------------------------------------
copyright = f"2020-2021, {config.author}"
documentation_summary = config.description

# The short X.Y version and the full version, including alpha/beta/rc tags
release = version = config.version

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "rst2pdf.pdfbuilder",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
# exclude_patterns = []


pdf_documents = [
    ("index", "rst2pdf", "PlanetLab Server Manager documentation", "UTKO"),
]


intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pythondialog": ("http://pythondialog.sourceforge.net/doc/", None),
    "paramiko": ("http://docs.paramiko.org/en/stable/", None),
}

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = []
