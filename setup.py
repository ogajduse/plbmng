import os
import sys
from setuptools import setup, find_packages

install_requires = ['vincent', 'folium', 'numpy', 'pandas', 'geocoder', 'paramiko', 'pythondialog']

setup(name='plbmng',
      description='Tool for monitoring PlanetLab network',
      version="0.3.8-2",
      license='MIT',
      packages=find_packages(),
      package_data={},
      include_package_data=True,
      install_requires=install_requires,
      dependency_links=['https://github.com/pandas-dev/pandas/archive/master.zip?ref=master#egg=pandas'],
      url='https://github.com/Andrasov/PlanetLab.git',
      author='Ivan Andrasov',
      author_email='xandra03@stud.feec.vutbr.cz',
      # maintainer='Dan Komosny',
      # maintainer_email='komosny@feec.vutbr.cz'
      long_description=open("README.rst").read(),
      scripts=['bin/plbmng']
      )
