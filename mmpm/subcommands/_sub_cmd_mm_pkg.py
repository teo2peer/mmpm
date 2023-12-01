#!/usr/bin/env python3
""" Command line options for 'add-mm-pkg' subcommand """
from mmpm.logger import MMPMLogger
from mmpm.magicmirror.database import MagicMirrorDatabase
from mmpm.subcommands.sub_cmd import SubCmd

logger = MMPMLogger.get_logger(__name__)


class MmPkg(SubCmd):
    def __init__(self, app_name):
        self.app_name = app_name
        self.name = "mm-pkg"
        self.help = "Manually add/remove MagicMirror packages in your local database (similar to add-apt-repository)"
        self.usage = f"{self.app_name} {self.name} <add/remove> [--<option>]"
        self.database = MagicMirrorDatabase()

    def register(self, subparser):
        self.parser = subparser.add_parser(self.name, usage=self.usage, help=self.help)

        subparsers = self.parser.add_subparsers(
            dest="command",
            description=f"use `{self.app_name} {self.name} <add/remove> --help` to see more details",
            title=f"{self.app_name} {self.name} subcommands",
            metavar="",
        )

        add_parser = subparsers.add_parser(
            "add",
            help="Add a custom MagicMirror package to the local database",
            usage=f"{self.app_name} {self.name} add -t <title> -a <author> -r <repo> -d <description>",
        )

        add_parser.add_argument(
            "-t",
            "--title",
            type=str,
            help="title of MagicMirror package",
            dest="title",
        )

        add_parser.add_argument(
            "-a",
            "--author",
            type=str,
            help="author of MagicMirror package",
            dest="author",
        )

        add_parser.add_argument(
            "-r",
            "--repo",
            type=str,
            help="repo URL of MagicMirror package",
            dest="repo",
        )

        add_parser.add_argument(
            "-d",
            "--desc",
            type=str,
            help="description of MagicMirror package",
            dest="desc",
        )

        remove_parser = subparsers.add_parser(
            "remove",
            help="Remove a custom MagicMirror package from the local database",
            usage=f"{self.app_name} {self.name} remove <package(s)> [--yes]",
        )

        remove_parser.add_argument(
            "pkg_name",
            nargs="+",
            help="name(s) of the MagicMirror package(s) to remove",
        )
        remove_parser.add_argument(
            "-y",
            "--yes",
            action="store_true",
            default=False,
            help="assume yes for user response and do not show prompt",
            dest="assume_yes",
        )

    def exec(self, args, extra):
        if not self.database.is_initialized():
            self.database.load()

        if args.command == "add":
            self.database.add_mm_pkg(args.title, args.author, args.repo, args.desc)
        elif args.command == "remove":
            self.database.remove_mm_pkg(args.pkg_name, assume_yes=args.assume_yes)
        else:
            logger.error(f"Invalid subcommand. See '{self.app_name} {self.name} --help'")
