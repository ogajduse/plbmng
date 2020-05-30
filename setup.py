from setuptools import setup, find_packages
import platform
import os

install_requires = ['vincent', 'folium', 'numpy', 'pandas', 'geocoder', 'paramiko', 'pythondialog']


def install_dialog_engine():
    """
    Try to install dialog if user is running setup for the first time. Supported OS are Fedora-like distributions.
    """
    with open("plbmng/database/first.boolean", 'r') as first:
        run = first.read().strip("\n")
    distribution = platform.platform()
    distro_check = False
    if "fc" in distribution or "el" in distribution:
        distro_check = True
    if run == "True" and distro_check:
        return_code = os.system("yum install -y dialog")
        return return_code
    return 0


ret = install_dialog_engine()
setup(name='plbmng',
      description='Tool for monitoring PlanetLab network',
      version="0.4.2.post1",
      license='MIT',
      packages=find_packages(),
      package_data={},
      include_package_data=True,
      install_requires=install_requires,
      dependency_links=['https://github.com/pandas-dev/pandas/archive/master.zip?ref=master#egg=pandas'],
      url='https://gitlab.com/utko-planetlab/plbmng',
      # author='',
      # author_email='xandra03@stud.feec.vutbr.cz',
      maintainer='Dan Komosny',
      maintainer_email='komosny@feec.vutbr.cz',
      project_urls={
          "Bug Tracker": "https://gitlab.com/utko-planetlab/plbmng/-/issues",
          "Documentation": "https://utko-planetlab.gitlab.io/plbmng/",
      },
      long_description=open("README.rst").read(),
      scripts=['bin/plbmng'],
      )

if ret != 0:
    print("INFO: Please make sure you have installed dialog-like engine!")
