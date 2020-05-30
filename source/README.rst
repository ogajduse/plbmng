======
plbmng
======

.. image:: images/plbmng.png
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


Dependencies
------------
        - Python 3.5 or higher
        - Dialog engine(TUI)
        - Python modules (all modules are available from pip):
                - geocoder
                - folium
                - numpy
                - vincent
                - pandas
                - paramiko
                - pythondialog

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
When you run plbmng for the first time, please add your credentials for PlanetLab network. If you don't want to add your credentials right away, you can skip it and add it in the settings later.

Once you have added your credentials, use ``Update server list now`` option in the Monitor servers menu. In default you will have old data which can be updated by this function. It downloads all servers from your slice and exports it as ``default.node`` file.

``Main menu``

``Access servers``: If you are looking for some specific node or set of nodes, use ``Access servers`` option. In the next screen you can choose from four options: access last server, search by DNS, IP or location. If you choose search by DNS or IP you will be prompted to type a string, which indicates the domain you are looking for. If you want to search by location, you will be asked to choose a continent and a country. Then you will see all available nodes from this selected country and you can choose one of them to see more detailes about this particular node. At the bottom of the information screen you can choose from three options.

.. image:: images/access_servers.png
    :alt: plbmng access servers menu
    :align: center

``Monitor servers``: Menu contains monitoring tools.
                 -  ``Update server list now`` - here you can update your list of servers.
                 -  ``Update server status now`` - here you can update your list of available servers.

.. image:: images/monitoring.png
    :alt: plbmng monitor servers menu
    :align: center

``Plot servers on map``:
             - ``Plot all servers`` - will create and open HTML file with plotted servers on map.
             - ``Plot servers responding to ping``
             - ``Plot ssh available servers``

.. image:: images/plot.png
    :alt: plbmng plot servers on map menu
    :align: center

``Set credentials``:
      Will open interactive editor for you to insert your credentials to PlanetLab network.

.. image:: images/set_credentials.png
    :alt: plbmng plot servers on map menu
    :align: center

Extras
------
In the extras menu you can find tool for managing your own server by adding them to the database. Another new feature added to extras menu is parallel copy to server/servers from database.

.. image:: images/extras.png
    :alt: plbmng plot servers on map menu
    :align: center

``Add server to database``: Allows user to add a server to the plbmng database. By adding info about server to the prepared file, you are able to filter and monitor your server with this tool just like with the others within PlanetLab network.

.. image:: images/add_server.png
    :alt: plbmng plot servers on map menu
    :align: center

``Copy files to server/servers``: User is prompted to select file/files, server/servers from plbmng database and destination path on the target. DO NOT FORGET TO SET PATH TO SSH KEY AND SLICE NAME(user on the target) IN THE CONFIG FILE!

.. image:: images/select.png
    :alt: plbmng plot servers on map menu
    :align: center

.. image:: images/target.png
    :alt: plbmng plot servers on map menu
    :align: center


Authors
-------

- `Dan Komosny`_ - Maintainer and supervisor
- `Ivan Andrasov`_ - Contributor
- `Filip Suba`_ - Contributor
- `Martin Kacmarcik`_ - Contributor


.. _`Ivan Andrasov`: https://github.com/Andrasov
.. _`Filip Suba`: https://github.com/fsuba
.. _`Dan Komosny`: https://www.vutbr.cz/en/people/dan-komosny-3065
.. _`Martin Kacmarcik`: https://github.com/xxMAKMAKxx
