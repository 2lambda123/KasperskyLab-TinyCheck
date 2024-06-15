#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess as sp
from app.utils import terminate_process, read_config
from os import mkdir, path
from flask import send_file, jsonify
import datetime
import shutil
import json
import sys
import re
import secrets


class Capture(object):

    def __init__(self):
        self.random_choice_alphabet = "ABCDEF1234567890"

    def start_capture(self):
        """
        Start a tshark capture on the created AP interface and save
        it in a temporary directory under /tmp/.

        :return: dict containing capture token and status. 
        """

        # Kill potential tshark zombies instances, if any.
        terminate_process("tshark")

        # Few context variable assignment
        self.capture_token = "".join(
            [secrets.choice(self.random_choice_alphabet) for i in range(8)])
        self.capture_dir = "/tmp/{}/".format(self.capture_token)
        self.assets_dir = "/tmp/{}/assets/".format(self.capture_token)
        self.pcap = self.capture_dir + "capture.pcap"
        self.iface = read_config(("network", "in"))

        # For packets monitoring
        self.list_pkts = []
        self.last_pkts = 0

        # Make the capture and the assets directory
        mkdir(self.capture_dir)
        mkdir(self.assets_dir)

        try:
            sp.Popen(["tshark",  "-i", self.iface, "-w",
                      self.pcap, "-f", "tcp or udp"])
            return {"status": True,
                    "message": "Capture started",
                    "capture_token": self.capture_token}
        except:
            return {"status": False,
                    "message": "Unexpected error: %s" % sys.exc_info()[0]}

    def get_capture_stats(self):
        """
            Get some dirty capture statistics in order to have a sparkline 
            in the background of capture view.

            :return: dict containing stats associated to the capture
        """
        with open("/sys/class/net/{}/statistics/tx_packets".format(self.iface)) as f:
            tx_pkts = int(f.read())
        with open("/sys/class/net/{}/statistics/rx_packets".format(self.iface)) as f:
            rx_pkts = int(f.read())

        if self.last_pkts == 0:
            self.last_pkts = tx_pkts + rx_pkts
            return {"status": True,
                    "packets": [0*400]}
        else:
            curr_pkts = (tx_pkts + rx_pkts) - self.last_pkts
            self.last_pkts = tx_pkts + rx_pkts
            self.list_pkts.append(curr_pkts)
            return {"status": True,
                    "packets": self.beautify_stats(self.list_pkts)}

    @staticmethod
    def beautify_stats(data):
        """
            Add 0 at the end of the array if the len of the array is less 
            than max_len. Else, get the last 100 stats. This allows to 
            show a kind of "progressive chart" in the background for 
            the first packets.

            :return: a list of integers.
        """
        max_len = 400
        if len(data) >= max_len:
            return data[-max_len:]
        else:
            return data + [1] * (max_len - len(data))

    def stop_capture(self):
        """
            Stop tshark if any instance present & ask create_capinfos.
            :return: dict as a small confirmation.
        """
        if terminate_process("tshark"):
            self.create_capinfos()
            return {"status": True,
                    "message": "Capture stopped"}
        else:
            return {"status": False,
                    "message": "No active capture"}

    def create_capinfos(self):
        """
            Creates a capinfo json file.
            :return: dict as a small confirmation.
        """
        infos = sp.Popen(["capinfos", self.pcap],
                         stdout=sp.PIPE, stderr=sp.PIPE)
        infos = infos.communicate()[0]
        data = {}
        for l in infos.decode().splitlines():
            try:
                l = l.split(": ") if ": " in l else l.split("= ")
                if len(l[0]) and len(l[1]):
                    data[l[0].strip()] = l[1].strip()
            except:
                continue
        with open("{}capinfos.json".format(self.assets_dir), 'w') as f:
            json.dump(data, f)
            return True
