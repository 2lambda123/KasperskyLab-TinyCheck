#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app.utils import read_config
import subprocess as sp
import requests
import json
import os
import re


class Update(object):

    def __init__(self):
        self.project_url = "https://api.github.com/repos/KasperskyLab/TinyCheck/tags"
        self.app_path = "/usr/share/tinycheck"
        return None

    def check_version(self):
        """
            Check if a new version of TinyCheck is available 
            by quering the Github api and comparing the last
            tag inside the VERSION file.
            :return: dict containing the available versions.
        """
        if read_config(("frontend", "update")):
            try:
                res = requests.get(self.project_url, timeout=60)
                res = json.loads(res.content.decode("utf8"))

                with open(os.path.join(self.app_path, "VERSION")) as f:
                    cv = f.read()
                    if cv != res[0]["name"]:
                        return {"status": True,
                                "message": "A new version is available",
                                "current_version": cv,
                                "next_version": res[0]["name"]}
                    else:
                        return {"status": True,
                                "message": "This is the latest version",
                                "current_version": cv}
            except:
                return {"status": False,
                        "message": "Something went wrong (no API access nor version file)"}
        else:
            return {"status": False,
                    "message": "You don't have rights to do this operation."}

    def get_current_version(self):
        """
            Get the current version of the TinyCheck instance
            :return: dict containing the current version or error.
        """
        if read_config(("frontend", "update")):
            try:
                with open(os.path.join(self.app_path, "VERSION")) as f:
                    return {"status": True,
                            "current_version": f.read()}
            except:
                return {"status": False,
                        "message": "Something went wrong - no version file ?"}
        else:
            return {"status": False,
                    "message": "You don't have rights to do this operation."}

    def update_instance(self):
        """
            Update the instance by executing the update script.
            :return: dict containing the update status.
        """
        if read_config(("frontend", "update")):
            try:
                os.chdir(self.app_path)
                sp.Popen(["bash", os.path.join(self.app_path, "update.sh")])
                return {"status": True,
                        "message": "Update successfully launched"}
            except:
                return {"status": False,
                        "message": "Issue during the update"}
        else:
            return {"status": False,
                    "message": "You don't have rights to do this operation."}
