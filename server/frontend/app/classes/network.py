#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess as sp
import netifaces as ni
import requests as rq
import re
import sys
import time
import qrcode
import base64
import requests

from wifi import Cell
from os import path, remove
from io import BytesIO
from app.utils import terminate_process, read_config
import secrets


class Network(object):

    def __init__(self):
        self.AP_SSID = False
        self.AP_PASS = False
        self.iface_in = read_config(("network", "in"))
        self.iface_out = read_config(("network", "out"))
        self.enable_interface(self.iface_in)
        self.enable_interface(self.iface_out)
        self.enable_forwarding()
        self.reset_dnsmasq_leases()
        self.random_choice_alphabet = "abcdef1234567890"

    def check_status(self):
        """
            The method check_status check the IP addressing of each interface 
            and return their associated IP.

            :return: dict containing each interface status.
        """

        ctx = {"interfaces": {
            self.iface_in: False,
            self.iface_out: False,
            "eth0": False},
            "internet": self.check_internet()}

        for iface in ctx["interfaces"].keys():
            try:
                ip = ni.ifaddresses(iface)[ni.AF_INET][0]["addr"]
                if not ip.startswith("127") or not ip.startswith("169.254"):
                    ctx["interfaces"][iface] = ip
            except:
                ctx["interfaces"][iface] = "Interface not connected or present."
        return ctx

    def wifi_list_networks(self):
        """
            The method wifi_list_networks list the available WiFi networks
            by using wifi python package.
            :return: dict - containing the list of Wi-Fi networks.
        """
        networks = []
        try:
            for n in Cell.all(self.iface_out):
                if n.ssid not in [n["ssid"] for n in networks] and n.ssid and n.encrypted:
                    networks.append(
                        {"ssid": n.ssid, "type": n.encryption_type})
            return {"networks": networks}
        except:
            return {"networks": []}

    @staticmethod
    def wifi_setup(ssid, password):
        """
            Edit the wpa_supplicant file with provided credentials.
            If the ssid already exists, just update the password. Otherwise
            create a new entry in the file.

            :return: dict containing the status of the operation
        """
        if len(password) >= 8 and len(ssid):
            found = False
            networks = []
            header, content = "", ""

            with open("/etc/wpa_supplicant/wpa_supplicant.conf") as f:
                content = f.read()
                blocks = content.split("network={")
                header = blocks[0]

                for block in blocks[1:]:
                    net = {}
                    for line in block.splitlines():
                        if line and line != "}":
                            if "priority=10" not in line.strip():
                                key, val = line.strip().split("=")
                            if key != "disabled":
                                net[key] = val.replace("\"", "")
                    networks.append(net)

                for net in networks:
                    if net["ssid"] == ssid:
                        net["psk"] = password.replace('"', '\\"')
                        net["priority"] = "10"
                        found = True

                if not found:
                    networks.append({
                        "ssid": ssid,
                        "psk": password.replace('"', '\\"'),
                        "key_mgmt": "WPA-PSK",
                        "priority": "10"
                    })

            with open("/etc/wpa_supplicant/wpa_supplicant.conf", "w+") as f:
                content = header
                for network in networks:
                    net = "network={\n"
                    for k, v in network.items():
                        if k in ["ssid", "psk"]:
                            net += "    {}=\"{}\"\n".format(k, v)
                        else:
                            net += "    {}={}\n".format(k, v)
                    net += "}\n\n"
                    content += net
                if f.write(content):
                    return {"status": True,
                            "message": "Configuration saved"}
                else:
                    return {"status": False,
                            "message": "Error while writing wpa_supplicant configuration file."}
        else:
            return {"status": False,
                    "message": "Empty SSID or/and password length less than 8 chars."}

    def wifi_connect(self):
        """
            Connect to one of the WiFi networks present in the wpa_supplicant.conf.
            :return: dict containing the TinyCheck <-> AP status.
        """

        # Kill wpa_supplicant instances, if any.
        terminate_process("wpa_supplicant")
        # Launch a new instance of wpa_supplicant.
        sp.Popen(["wpa_supplicant", "-B", "-i", self.iface_out, "-c",
                  "/etc/wpa_supplicant/wpa_supplicant.conf"]).wait()
        # Check internet status
        for _ in range(1, 40):
            if self.check_internet():
                return {"status": True,
                        "message": "Wifi connected"}
            time.sleep(1)

        return {"status": False,
                "message": "Wifi not connected"}

    def start_ap(self):
        """
            The start_ap method generates an Access Point by using HostApd
            and provide to the GUI the associated ssid, password and qrcode.

            :return: dict containing the status of the AP
        """

        # Re-ask to enable interface, sometimes it just go away.
        if not self.enable_interface(self.iface_out):
            return {"status": False,
                    "message": "Interface not present."}

        # Generate the hostapd configuration
        if read_config(("network", "tokenized_ssids")):
            token = "".join([secrets.choice(self.random_choice_alphabet)
                             for i in range(4)])
            self.AP_SSID = secrets.choice(read_config(
                ("network", "ssids"))) + "-" + token
        else:
            self.AP_SSID = secrets.choice(read_config(("network", "ssids")))
        self.AP_PASS = "".join(
            [secrets.choice(self.random_choice_alphabet) for i in range(8)])

        # Launch hostapd
        if self.write_hostapd_config():
            if self.lauch_hostapd() and self.reset_dnsmasq_leases():
                return {"status": True,
                        "message": "AP started",
                        "ssid": self.AP_SSID,
                        "password": self.AP_PASS,
                        "qrcode": self.generate_qr_code()}
            else:
                return {"status": False,
                        "message": "Error while creating AP."}
        else:
            return {"status": False,
                    "message": "Error while writing hostapd configuration file."}

    def generate_qr_code(self):
        """
            The method generate_qr_code returns a QRCode based on 
            the SSID and the password.

            :return: - string containing the PNG of the QRCode.
        """
        qrc = qrcode.make("WIFI:S:{};T:WPA;P:{};;".format(
            self.AP_SSID, self.AP_PASS))
        buffered = BytesIO()
        qrc.save(buffered, format="PNG")
        return "data:image/png;base64,{}".format(base64.b64encode(buffered.getvalue()).decode("utf8"))

    def write_hostapd_config(self):
        """
            The method write_hostapd_config write the hostapd configuration 
            under a temporary location defined in the config file.

            :return: bool - if hostapd configuration file created
        """
        try:
            chan = self.set_ap_channel()
            with open("{}/app/assets/hostapd.conf".format(sys.path[0]), "r") as f:
                conf = f.read()
                conf = conf.replace("{IFACE}", self.iface_in)
                conf = conf.replace("{SSID}", self.AP_SSID)
                conf = conf.replace("{PASS}", self.AP_PASS)
                conf = conf.replace("{CHAN}", chan)
                with open("/tmp/hostapd.conf", "w") as c:
                    c.write(conf)
            return True
        except:
            return False

    def lauch_hostapd(self):
        """
            The method lauch_hostapd kill old instance of hostapd and launch a
            new one as a background process.

            :return: bool - if hostapd sucessfully launched.
        """

        # Kill potential zombies of hostapd
        terminate_process("hostapd")

        sp.Popen(["ip","link","set", self.iface_in, "up"]).wait()
        sp.Popen(
            "/usr/sbin/hostapd /tmp/hostapd.conf > /tmp/hostapd.log", shell=True)

        while True:
            if path.isfile("/tmp/hostapd.log"):
                with open("/tmp/hostapd.log", "r") as f:
                    log = f.read()
                    err = ["Could not configure driver mode",
                           "driver initialization failed"]
                    if not any(e in log for e in err):
                        if "AP-ENABLED" in log:
                            return True
                    else:
                        return False
            time.sleep(1)

    def stop_hostapd(self):
        """
            Stop hostapd instance.

            :return: dict - a little message for debug.
        """
        if terminate_process("hostapd"):
            return {"status": True,
                    "message": "AP stopped"}
        else:
            return {"status": False,
                    "message": "No AP running"}

    def reset_dnsmasq_leases(self):
        """
            This method reset the DNSMasq leases and logs to get the new
            connected device name & new DNS entries.

            :return: bool if everything goes well
        """
        try:
            sp.Popen("service dnsmasq stop", shell=True).wait()
            sp.Popen("cp /dev/null /var/lib/misc/dnsmasq.leases",
                     shell=True).wait()
            sp.Popen("cp /dev/null /var/log/messages.log", shell=True).wait()
            sp.Popen("service dnsmasq start", shell=True).wait()
            return True
        except:
            return False

    def enable_forwarding(self):
        """
            This enable forwarding to get internet working on the connected device. 
            Method tiggered during the Network class intialization.

            :return: bool if everything goes well
        """
        try:
            sp.Popen("echo 1 > /proc/sys/net/ipv4/ip_forward",
                     shell=True).wait()

            # Enable forwarding.
            
            sp.Popen("nft add table nat",shell=True).wait()
            sp.Popen("nft 'add chain nat prerouting { type nat hook prerouting priority 100; }'",shell=True).wait()
            sp.Popen("nft 'add chain nat postrouting { type nat hook postrouting priority 100; }'",shell=True).wait()
            sp.Popen("nft add table ip filter",shell=True).wait()
            sp.Popen("nft 'add chain ip filter INPUT { type filter hook input priority 0; }'",shell=True).wait()
            
            
            sp.Popen(["nft","add","rule","ip","nat","postrouting","oifname",
                       self.iface_out,"counter","masquerade"]).wait()

            # Prevent the device to reach the 80 and 443 of TinyCheck.
            sp.Popen(["nft","add","rule","ip","filter","INPUT","iifname",self.iface_in,"ip",
                      "protocol","tcp","ip","daddr","192.168.100.1","tcp","dport","{ 80,443}","counter","drop"]).wait()
            
            
            return True
        except:
            return False

    def enable_interface(self, iface):
        """
            This enable interfaces, with a simple check. 
            :return: bool if everything goes well 
        """
        sh = sp.Popen(["ip" ,"a","s", iface],
                      stdout=sp.PIPE, stderr=sp.PIPE)
        sh = sh.communicate()
        if b",UP" in sh[0]:
            return True  # The interface is up.
        elif sh[1]:
            return False  # The interface doesn't exists (most of the cases).
        else:
            sp.Popen(["ip","link","set", iface, "up"]).wait()
            return True

    def check_internet(self):
        """
            Check the internet link just with a small http request
            to an URL present in the configuration

            :return: bool - if the request succeed or not.
        """
        try:
            url = read_config(("network", "internet_check"))
            requests.get(url, timeout=10)
            return True
        except:
            return False

    def set_ap_channel(self):
        """
            Deduce the channel to have for the AP in order to prevent
            kind of jamming between the two wifi interfaces.
        """
        try:
            if self.iface_out[0] == "w":
                # Get the channel of the connected interface
                sh = sp.Popen(["iw", self.iface_out, "info"],
                              stdout=sp.PIPE, stderr=sp.PIPE).communicate()
                res = re.search("channel ([0-9]{1,2})", sh[0].decode('utf8'))
                chn = res.group(1)

                # Return a good candidate.
                return "11" if int(chn) < 7 else "1"
            else:
                return "1"
        except:
            return "1"
