#!/usr/bin/env python3
from datetime import datetime
from os import chdir
from shutil import make_archive

from flask import Blueprint, Response, request, send_file
from mmpm.api.constants import http
from mmpm.api.endpoints.endpoint import Endpoint
from mmpm.constants import paths
from mmpm.logger import MMPMLogger
from mmpm.magicmirror.package import MagicMirrorPackage

logger = MMPMLogger.get_logger(__name__)


class Logs(Endpoint):
    def __init__(self):
        self.name = "logs"
        self.blueprint = Blueprint(self.name, __name__, url_prefix=f"/api/{self.name}")
        self.handler = None

        @self.blueprint.route("/zip", methods=[http.GET])
        def zip() -> Response:
            logger.debug("Creating zip of log files")
            chdir("/tmp")
            today = datetime.now()
            zip_file_name = f"mmpm-logs-{today.year}-{today.month}-{today.day}"
            logger.debug(f"Creating zip of log files named '{zip_file_name}'")
            archive_name = make_archive(zip_file_name, "zip", paths.MMPM_LOG_DIR)

            logger.debug(f"Archive created: {True if archive_name else False}")

            return send_file(f"/tmp/{zip_file_name}.zip", f"{zip_file_name}.zip", as_attachment=True)
