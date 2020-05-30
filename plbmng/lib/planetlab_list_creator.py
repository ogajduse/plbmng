#!/usr/bin/env python

import xmlrpc.client
import geocoder
import codecs
import argparse
import sys
import os
import socket
import traceback
from time import sleep, asctime, localtime, time

plc_host = "www.planet-lab.eu"

auth = {'AuthMethod': 'password',
        'AuthString': '',
        'Username': ''
        }

arg = {"path": "",
       "id": 1,
       "start_id": 1,
       "quiet": False}

api_url = "https://%s:443/PLCAPI/" % plc_host
plc_api = xmlrpc.client.ServerProxy(api_url, allow_none=True)

locations = {}

continents = {
    "AD": "EU", "AE": "AS", "AF": "AS", "AG": "NA", "AI": "NA", "AL": "EU", "AM": "AS", "AN": "NA", "AO": "AF",
    "AQ": "AQ", "AR": "SA", "AS": "OC", "AT": "EU", "AU": "OC", "AW": "NA", "AZ": "AS", "BA": "EU", "BB": "NA",
    "BD": "AS", "BE": "EU", "BF": "AF", "BG": "EU", "BH": "AS", "BI": "AF", "BJ": "AF", "BM": "NA", "BN": "AS",
    "BO": "SA", "BR": "SA", "BS": "NA", "BT": "AS", "BW": "AF", "BY": "EU", "BZ": "NA", "CA": "NA", "CC": "AS",
    "CD": "AF", "CF": "AF", "CG": "AF", "CH": "EU", "CI": "AF", "CK": "OC", "CL": "SA", "CM": "AF", "CN": "AS",
    "CO": "SA", "CR": "NA", "CU": "NA", "CV": "AF", "CX": "AS", "CY": "AS", "CZ": "EU", "DE": "EU", "DJ": "AF",
    "DK": "EU", "DM": "NA", "DO": "NA", "DZ": "AF", "EC": "SA", "EE": "EU", "EG": "AF", "EH": "AF", "ER": "AF",
    "ES": "EU", "ET": "AF", "FI": "EU", "FJ": "OC", "FK": "SA", "FM": "OC", "FO": "EU", "FR": "EU", "GA": "AF",
    "GB": "EU", "GD": "NA", "GE": "AS", "GF": "SA", "GG": "EU", "GH": "AF", "GI": "EU", "GL": "NA", "GM": "AF",
    "GN": "AF", "GP": "NA", "GQ": "AF", "GR": "EU", "GS": "AQ", "GT": "NA", "GU": "OC", "GW": "AF", "GY": "SA",
    "HK": "AS", "HN": "NA", "HR": "EU", "HT": "NA", "HU": "EU", "ID": "AS", "IE": "EU", "IL": "AS", "IM": "EU",
    "IN": "AS", "IO": "AS", "IQ": "AS", "IR": "AS", "IS": "EU", "IT": "EU", "JE": "EU", "JM": "NA", "JO": "AS",
    "JP": "AS", "KE": "AF", "KG": "AS", "KH": "AS", "KI": "OC", "KM": "AF", "KN": "NA", "KP": "AS", "KR": "AS",
    "KW": "AS", "KY": "NA", "KZ": "AS", "LA": "AS", "LB": "AS", "LC": "NA", "LI": "EU", "LK": "AS", "LR": "AF",
    "LS": "AF", "LT": "EU", "LU": "EU", "LV": "EU", "LY": "AF", "MA": "AF", "MC": "EU", "MD": "EU", "ME": "EU",
    "MG": "AF", "MH": "OC", "MK": "EU", "ML": "AF", "MM": "AS", "MN": "AS", "MO": "AS", "MP": "OC", "MQ": "NA",
    "MR": "AF", "MS": "NA", "MT": "EU", "MU": "AF", "MV": "AS", "MW": "AF", "MX": "NA", "MY": "AS", "MZ": "AF",
    "NA": "AF", "NC": "OC", "NE": "AF", "NF": "OC", "NG": "AF", "NI": "NA", "NL": "EU", "NO": "EU", "NP": "AS",
    "NR": "OC", "NU": "OC", "NZ": "OC", "OM": "AS", "PA": "NA", "PE": "SA", "PF": "OC", "PG": "OC", "PH": "AS",
    "PK": "AS", "PL": "EU", "PM": "NA", "PN": "OC", "PR": "NA", "PS": "AS", "PT": "EU", "PW": "OC", "PY": "SA",
    "QA": "AS", "RE": "AF", "RO": "EU", "RS": "EU", "RU": "EU", "RW": "AF", "SA": "AS", "SB": "OC", "SC": "AF",
    "SD": "AF", "SE": "EU", "SG": "AS", "SH": "AF", "SI": "EU", "SJ": "EU", "SK": "EU", "SL": "AF", "SM": "EU",
    "SN": "AF", "SO": "AF", "SR": "SA", "ST": "AF", "SV": "NA", "SY": "AS", "SZ": "AF", "TC": "NA", "TD": "AF",
    "TF": "AQ", "TG": "AF", "TH": "AS", "TJ": "AS", "TK": "OC", "TM": "AS", "TN": "AF", "TO": "OC", "TR": "AS",
    "TT": "NA", "TV": "OC", "TW": "AS", "TZ": "AF", "UA": "EU", "UG": "AF", "US": "NA", "UY": "SA", "UZ": "AS",
    "VC": "NA", "VE": "SA", "VG": "NA", "VI": "NA", "VN": "AS", "VU": "OC", "WF": "OC", "WS": "OC", "YE": "AS",
    "YT": "AF", "ZA": "AF", "ZM": "AF", "ZW": "AF"}


def arguments():
    """
    Argument parser for command line usage.
    """
    global plc_host
    parser = argparse.ArgumentParser(
        prog="planetlab_list_creator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Plb list creator is script, which will return you file with all available nodes from"
                    " www.planet-lab.eu. \nRequired arguments: USERNAME, PASSWORD and OUTPUT.")
    parser.add_argument("-u", "--username", required=True)
    parser.add_argument("-p", "--password", required=True)
    parser.add_argument("-o", "--output", required=True, action="store", help="Path where you want to save output.")
    parser.add_argument("--start_id", type=int, help="ID for the first node")
    parser.add_argument("-q", "--quiet", action="store_true", default=False, help="Suppress stdout")
    args, unknown_argument = parser.parse_known_args()
    if args.username:
        auth["Username"] = args.username
    if args.password:
        auth["AuthString"] = args.password
    if args.output:
        if not os.path.isdir(args.output):
            print("Directory doesn't exist.")
            sys.exit(1)
        arg["path"] = args.output

    if args.start_id:
        arg["id"] = args.start_id
        arg["start_id"] = args.start_id

    if args.quiet:
        arg["quiet"] = True

    if unknown_argument:
        print("Unknown argument")
        sys.exit(1)


def get_continent(country_code):
    """
    Function returns continent based on country code provided as parameter.\n
    :param country_code: string containing country code\n
    :return: None if country code is not recognized. Otherwise it will return continent code.\n
    """
    global continents
    if country_code is None:
        return None
    if country_code.upper() in list(continents.keys()):
        return continents[country_code.upper()]
    return None


def get_ip_address(hostname):
    """
    Function translates hostname to IP address.\n
    :param hostname: HOSTNAME\n
    :return: if hostname cannot be translated to IP address returns None. Otherwise it returns IP address as a string.
    """
    if hostname is not None or hostname == '':
        try:
            ip_addr = socket.gethostbyname(hostname)
            return ip_addr
        except socket.error:
            pass
    return None


def append_to_file(node):
    """
    Function for writing information about a node into the file\n
    :param node:  dictionary containing information about a node
    """
    if arg["id"] == arg["start_id"]:
        try:
            f = open(os.path.join(arg["path"] + '/database/default2.node'), "w")
            f.write("# ID\tIP\tDNS\tCONTINENT\tCOUNTRY\tREGION\tCITY\tURL\tFULL NAME\tLATITUDE\tLONGITUDE\n")
            f.close()
        except Exception as err:
            traceback.print_exc()
            print(err)
            sys.exit(1)

    try:
        with codecs.open(os.path.join(arg["path"] + '/database/default2.node'),
                         mode="a", encoding="utf-8") as f:
            f.write("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(str(arg["id"]), node["ip"],
                                                                          node["hostname"],
                                                                          node["continent"], node["country"],
                                                                          node["region"],
                                                                          node["city"], node["url"], node["name"],
                                                                          node["latitude"], node["longitude"]))
    except Exception as err:
        traceback.print_exc()
        print(err)
        sys.exit(1)


def print_info(node):
    """
    Function prints information about a node.\n
    :param node:  dictionary containing information about the node
    """
    print("ID: %s \n"
          "IP ADDRESS: \t%s\n"
          "HOSTNAME: \t%s\n"
          "CONTINENT: \t%s\n"
          "COUNTRY: \t%s\n"
          "REGION: \t%s\n"
          "CITY: \t\t%s\n"
          "URL: \t\t%s\n"
          "NAME: \t\t%s\n"
          "LATITUDE: \t%s\n"
          "LONGITUDE: \t%s\n\n"
          % (arg["id"], node["ip"], node["hostname"], node["continent"], node["country"], node["region"],
             node["city"], node["url"], node["name"], node["latitude"], node["longitude"]))


def run(path=None, username=None, password=None, start_id=None, quiet=False, return_output=False):
    """
    Function creates output file with all information about the nodes. It takes
    username and password from Planetlab web to authenticate for the API. In path param
    you specify the path where output shall be saved. These parameters are required and
    function will not work properly without them. Start id is optional and you should
    use it only if you want to use different numbering for nodes. Default value for
    start id is '1'. Quiet is boolean value for printing standard output.\n
    :param path: path to file as string. REQUIRED\n
    :param username: username of your Planetlab web account. REQUIRED\n
    :param password: password of your Planetlab web account. REQUIRED\n
    :param start_id: integer value for numbering. Optional: default=1\n
    :param quiet:  boolean value deciding whether to print information as standard output. Optional: default=False\n
    :param return_output: boolean value deciding whether to return output as list of nodes. Optional: default=False\n
    :return: lib/default2.node file, which contains following information about node:\n
        - ID\n
        - IP address\n
        - Hostname\n
        - Continent\n
        - Country\n
        - Region\n
        - City\n
        - URL\n
        - Name of an institution, which owns the node\n
        - Latitude\n
        - Longitude\n
    """
    global auth

    if path and username and password:
        auth["AuthString"] = password
        auth["Username"] = username
        arg["path"] = path
        if start_id:
            arg[start_id] = start_id
        if quiet:
            arg["quiet"] = quiet
    try:
        all_nodes = plc_api.GetNodes(auth, {"-SORT": "node_id"}, ["site_id", "hostname", "interface_ids"])
        for node in all_nodes:
            if len(node["interface_ids"]):
                interfaces = plc_api.GetInterfaces(auth, {"interface_id": node["interface_ids"][0]}, ["ip"])
                if len(interfaces) > 0:
                    node.update(interfaces[0])
                else:
                    node.update({"ip": "unknown"})
            else:
                addr = get_ip_address(node["hostname"])
                node["ip"] = addr

            node.update(plc_api.GetSites(auth, node["site_id"], ["latitude", "longitude", "url", "name"])[0])

            if node["site_id"] in list(locations.keys()):
                location = locations[node["site_id"]]
                node.update(
                    {"city": location[0], "region": location[1], "country": location[2], "continent": location[3]})
            else:
                sleep(1)  # Usage policy https://operations.osmfoundation.org/policies/nominatim/
                if node["latitude"] is not None and node["longitude"] is not None:
                    g = geocoder.osm([node["latitude"], node["longitude"]], method="reverse")
                    node["city"] = g.city
                    node["region"] = g.county
                    node["country"] = "unknown"
                    node["continent"] = "unknown"
                    if g.country_code is not None:
                        node["country"] = g.country_code.upper()
                        node["continent"] = get_continent(g.country_code)
                    locations.update(
                        {node["site_id"]: [node["city"], node["region"], node["country"], node["continent"]]})
                else:
                    node.update(
                        {"city": "unknown", "region": "unknown", "country": "unknown", "continent": "unknown"})

            # if value is None it is changed to unknown in info dictionary about node
            for value in list(node.values()):
                if value is None:
                    node[list(node.keys())[list(node.values()).index(value)]] = "unknown"

            append_to_file(node)
            if not arg["quiet"]:
                print_info(node)
            arg["id"] += 1

    except (KeyboardInterrupt, SystemExit):
        print("Program stopped by user. Exiting....")
        sys.exit(1)

    except Exception as err:
        traceback.print_exc()
        print(err)
        sys.exit(1)

    if return_output:
        return all_nodes


if __name__ == "__main__":
    print("Start: %s" % asctime(localtime(time())))
    arguments()
    run()
    print("Finish: %s" % asctime(localtime(time())))
