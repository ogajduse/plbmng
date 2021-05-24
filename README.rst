======
plbmng
======

.. image:: source/images/plbmng.png
    :scale: 50 %
    :alt: plbmng main menu
    :align: center

Description
-----------
``plbmng`` is a tool for monitoring servers within and outside of Planetlab network.

For this purpose there are several tools within this project:
        - to get all servers from PlanetLab network and gather all available information about them
        - to create a map with pin pointed location of the servers
        - filter servers based on their availability, location, software, hardware.
        - to add server which are not from PlanetLab network into plbmng database
        - copy file/files to multiple server/servers from plbmng database
        - schedule jobs to run commands on remote servers
        - manage jobs lifecycle


Dependencies
------------
        - Python 3.8 or higher
        - Dialog engine(TUI)
        - Python modules (all modules are available from pip):
                - geocoder
                - folium
                - vincent
                - paramiko
                - pythondialog
                - dynaconf
                - loguru
                - parallel-ssh
                - pysftp

Installation
------------
To install the plbmng module, type:

.. code-block:: bash

         $ pip3 install plbmng

Install dialog-like engine. If you are using Fedora-like distributions:

.. code-block:: bash

        $ sudo yum install -y dialog

On Mac OS you can install it from brew:

.. code-block:: bash

        $ brew install dialog

Basic usage
-----------
When you run plbmng for the first time, please add your credentials for Planetlab network to the configuration file located at ``~/.plbmng/settings.yaml``. If you don't want to add your credentials right away, you can skip it and add it in the settings later.

Once you have added your credentials, use ``Update server list now`` option in the Monitor servers menu. In default you will have old data which can be updated by this function. It downloads all servers from your slice and exports it as ``default.node`` file.

``Main menu``

``Access servers``: If you are looking for some specific node or set of nodes, use ``Access servers`` option. In the next screen you can choose from four options: access last server, search by DNS, IP or location. If you choose search by DNS or IP you will be prompted to type a string, which indicates the domain you are looking for. If you want to search by location, you will be asked to choose a continent and a country. Then you will see all available nodes from this selected country and you can choose one of them to see more detailes about this particular node. At the bottom of the information screen you can choose from three options.

``Monitor servers``: Monitoring tools are there.
                 -  ``Update server list now``, here you can update your list of servers.
                 -  ``Update server status now``, here you can update your list of available servers.

``Plot servers on map``:
             ``Generate map``, will create a map with all or specific nodes from ``planetlab.node`` file.

``Run jobs on servers``:
             - ``Copy files to server(s)`` - User is prompted to select file/files, server/servers from plbmng database and destination path on the target. DO NOT FORGET TO SET PATH TO SSH KEY AND SLICE NAME(user on the target) IN THE CONFIG FILE!
             - ``Run one-off remote command`` - Allows to run a command on a set of servers.
             - ``Schedule remote job`` - Allows user to schedule remote jobs that run commands on the servers at the specified time. It uses local database for storing details about all scheduled jobs.
             - ``Display jobs state`` - Provides a menu to display either non-finished or finished jobs.
             - ``Refresh jobs state`` - Refreshes state of non-finished jobs.
             - ``Job artefacts`` - Allows user to view the artefacts that the job produced.
             - ``Clean up jobs`` - Provides user with the ability to delete old/unused jobs.

Extras
------
In the extras menu you can find tool for managing your own server by adding them to the database. Another new feature added to extras menu is parallel copy to server/servers from database.

``Add server to database``: Allows user to add a server to the plbmng database. By adding info about server to the prepared file, you are able to filter and monitor your server with this tool just like with the others within PlanetLab network.


Development process
-------------------

Check out the project

.. code-block:: bash

         $ git clone git@gitlab.com:utko-planetlab/plbmng.git

Install required packages and development dependencies by

.. code-block:: bash

         $ poetry install

Install pre-commit for code check

.. code-block:: bash

         $ pre-commit install --install-hooks

Make changes of your choice and commit them

.. code-block:: bash

         $ git commit -m "Your beautiful commit message"

If you want to issue new version, run the following command. This issues minor version. It updates version strings in the whole repository and creates git commit and git tag. Then it pushes the tag and the commit to the upstream repository.

.. code-block:: bash

         $ bumpver update --patch


Authors
-------

- `Dan Komosny`_ - Maintainer and supervisor
- `Ivan Andrasov`_ - Contributor
- `Filip Suba`_ - Contributor
- `Martin Kacmarcik`_ - Contributor
- `Ondrej Gajdusek`_ - Contributor


.. _`Ivan Andrasov`: https://github.com/Andrasov
.. _`Filip Suba`: https://github.com/fsuba
.. _`Dan Komosny`: https://www.vutbr.cz/en/people/dan-komosny-3065
.. _`Martin Kacmarcik`: https://github.com/xxMAKMAKxx
.. _`Ondrej Gajdusek`: https://github.com/ogajduse
