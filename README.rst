======
plbmng
======

Description
-----------
``plbmng`` is a tool created for usage within PlanetLab network. Main purpose of this tool is to manage and monitor your PlanetLab nodes.

For this purpose there are several tools within this project:
        - to get all the servers and gather all available information about them
        - to create a map with location of the servers
        - filter servers based on their availability

Dependencies
------------
        - Python 3.6.5 (Python scripts have been tested on this version but they will probably work with other versions too.)
        - Python modules (all modules are available from pip):
                - geocoder
                - folium
                - numpy
                - vincent
                - pandas
                - paramiko
                - pythondialog

Instalation
-----------
To install the plbmng module, type:

.. code-block:: bash

         $ pip3 install plbmng

Basic usage
-----------
When you run plbmng for the first time, please add your credentials for Planetlab network. If you don't want to add your credentials right away, you can skip it and add it in the settings later.

Once you have added your credentials, use ``Update server list now`` option in the Monitor servers menu. In default you will have old data which can be updated by this function. It downloads all servers from your slice and exports it as ``default.node`` file.

``Main menu``

``Access servers``: If you are looking for some specific node or set of nodes, use ``Access servers`` option. In the next screen you can choose from four options: access last server, search by DNS, IP or location. If you choose search by DNS or IP you will be prompted to type a string, which indicates the domain you are looking for. If you want to search by location, you will be asked to choose a continent and a country. Then you will see all available nodes from this selected country and you can choose one of them to see more detailes about this particular node. At the bottom of the information screen you can choose from three options.

``Monitor servers``: In this menu you can set-up a cron job for monitoring your slice.
                 -  ``Set crontab for status update``, here you can specify how often you wish to run the monitoring.
                 -  ``Update server list now``, here you can update your list of servers.
                 -  ``Update server status now``, here you can update your list of available servers.

``Plot servers on map``:
             ``Generate map``, will create a map with all or specific nodes from ``planetlab.node`` file.
``Set credentials``:
      Will open interactive editor for you to insert your credentials to PlanetLab network.

Authors
-------

- `Ivan Andrasov`_ - Creator of the project
- `Filip Suba`_ - Improvements to the project and creator of planetlab_list_creator
- `Dan Komosny`_ - Maintainer and supervisor of the project
- `Martin Kacmarcik`_ - Contributor


.. _`Ivan Andrasov`: https://github.com/Andrasov
.. _`Filip Suba`: https://github.com/fsuba
.. _`Dan Komosny`: https://www.vutbr.cz/en/people/dan-komosny-3065
.. _`Martin Kacmarcik`: https://github.com/xxMAKMAKxx
