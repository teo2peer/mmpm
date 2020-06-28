#!/usr/bin/env python3
import re
import os
import json
import datetime
import shutil
import sys

from socket import gethostname, gethostbyname
from textwrap import fill, indent
from urllib.error import HTTPError
from urllib.request import urlopen
from collections import defaultdict
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Final

import mmpm.color as color
import mmpm.utils as utils
import mmpm.mmpm as _mmpm
import mmpm.consts as consts
import mmpm.models as models


MagicMirrorPackage = models.MagicMirrorPackage


def snapshot_details(packages: Dict[str, List[MagicMirrorPackage]]) -> None:
    '''
    Displays information regarding the most recent 'snapshot_file', ie. when it
    was taken, when the next scheduled snapshot will be taken, how many module
    categories exist, and the total number of modules available. Additionally,
    tells user how to forcibly request a new snapshot be taken.

    Parameters:
        packages (Dict[str, List[MagicMirrorPackage]]): Dictionary of MagicMirror modules

    Returns:
        None
    '''

    num_categories: int = len(packages.keys())
    num_packages: int = 0

    current_snapshot, next_snapshot = utils.calc_snapshot_timestamps()
    curr_snap_date = datetime.datetime.fromtimestamp(int(current_snapshot))
    next_snap_date = datetime.datetime.fromtimestamp(int(next_snapshot))

    for category in packages.values():
        num_packages += len(category)

    print(
        utils.colored_text(color.N_YELLOW, 'Most recent snapshot of MagicMirror Modules taken:'),
        f'{curr_snap_date}'
    )

    print(
        utils.colored_text(color.N_YELLOW, 'The next snapshot will be taken on or after:'),
        f'{next_snap_date}\n'
    )

    print(
        utils.colored_text(color.N_GREEN, 'Package Categories:'),
        f'{num_categories}'
    )

    print(
        utils.colored_text(color.N_GREEN, 'Packages Available:'),
        f'{num_packages}\n'
    )



def check_for_mmpm_updates(assume_yes=False, gui=False) -> bool:
    '''
    Scrapes the main file of MMPM off the github repo, and compares the current
    version, versus the one available in the master branch. If there is a newer
    version, the user is prompted for an upgrade.

    Parameters:
        None

    Returns:
        bool: True on success, False on failure
    '''

    try:
        utils.log.info(f'Checking for newer version of MMPM. Current version: {_mmpm.__version__}')
        utils.plain_print(f"Checking {utils.colored_text(color.N_GREEN, 'MMPM')} for updates")

        try:
            # just to keep the console output the same as all other update commands
            error_code, contents, _ = utils.run_cmd(['curl', consts.MMPM_FILE_URL])
        except KeyboardInterrupt:
            print()
            utils.fatal_msg('Caught keyboard interrupt. Exiting.')

        if error_code:
            utils.fatal_msg('Failed to retrieve MMPM version number')

    except HTTPError as error:
        message: str = 'Unable to retrieve available version number from MMPM repository'
        utils.log.error(error)
        return False

    version_line: List[str] = re.findall(r"__version__ = \d+\.\d+", contents)
    version_list: List[str] = re.findall(r"\d+\.\d+", version_line[0])
    version_number: float = float(version_list[0])

    print(consts.GREEN_CHECK_MARK)

    if not version_number:
        utils.fatal_msg('No version number found on MMPM repository')

    if _mmpm.__version__ >= version_number:
        print(f'No updates available for MMPM {consts.YELLOW_X}')
        utils.log.info(f'No newer version of MMPM found > {version_number} available. The current version is the latest')
        return True

    utils.log.info(f'Found newer version of MMPM: {version_number}')

    print(f'\nInstalled version: {_mmpm.__version__}')
    print(f'Available version: {version_number}\n')

    if gui:
        message = f"A newer version of MMPM is available ({version_number}). Please upgrade via terminal using 'mmpm uprade --mmpm"
        print(message)
        return True

    if not utils.prompt_user('A newer version of MMPM is available. Would you like to upgrade now?', assume_yes=assume_yes):
        return True

    message = "Upgrading MMPM"

    print(utils.colored_text(color.B_CYAN, message))

    utils.log.info(f'User chose to update MMPM')

    os.chdir(os.path.join('/', 'tmp'))
    shutil.rmtree('/tmp/mmpm')

    error_code, _, stderr = utils.clone('mmpm', consts.MMPM_REPO_URL)

    if error_code:
        utils.fatal_msg(stderr)

    os.chdir('/tmp/mmpm')

    # if the user needs to be prompted for their password, this can't be a subprocess
    os.system('make reinstall')
    return True


def upgrade_package(package: MagicMirrorPackage) -> str:
    '''
    Depending on flags passed in as arguments:

    Checks for available package updates, and alerts the user. Or, pulls latest
    version of module(s) from the associated repos.

    If upgrading, a user can upgrade all modules that have available upgrades
    by ommitting additional arguments. Or, upgrade specific modules by
    supplying their case-sensitive name(s) as an addtional argument.

    Parameters:
        package (MagicMirrorPackage): the MagicMirror module being upgraded

    Returns:
        stderr (str): the resulting error message of the upgrade. If the message is zero length, it was successful
    '''

    os.chdir(package.directory)

    utils.plain_print(f'{consts.GREEN_PLUS_SIGN} Retrieving upgrade for {package.title}')
    error_code, _, _ = utils.run_cmd(["git", "pull"])

    if error_code:
        message: str = "Unable to communicate with git server"
        utils.error_msg("Unable to communicate with git server")
        return message

    print(consts.GREEN_CHECK_MARK)

    stderr = utils.install_dependencies()

    if stderr:
        utils.error_msg(stderr)
        return stderr

    return ''


def check_for_package_updates(packages: Dict[str, List[MagicMirrorPackage]], assume_yes: bool = False) -> bool:
    '''
    Depending on flags passed in as arguments:

    Checks for available module updates, and alerts the user. Or, pulls latest
    version of module(s) from the associated repos.

    If upgrading, a user can upgrade all modules that have available upgrades
    by ommitting additional arguments. Or, upgrade specific modules by
    supplying their case-sensitive name(s) as an addtional argument.

    Parameters:
        packages (Dict[str, List[MagicMirrorPackage]]): Dictionary of MagicMirror modules
        assume_yes (bool): if True, assume yes for user response, and do not display prompt

    Returns:
        None
    '''

    os.chdir(consts.MAGICMIRROR_MODULES_DIR)

    installed_packages: Dict[str, List[MagicMirrorPackage]] = get_installed_packages(packages)

    updateable: List[MagicMirrorPackage] = []
    upgraded: bool = True

    for _, _packages in installed_packages.items():
        for package in _packages:
            os.chdir(package.directory)

            utils.plain_print(f'Checking {utils.colored_text(color.N_GREEN, package.title)} for updates')

            try:
                error_code, _, stdout = utils.run_cmd(['git', 'fetch', '--dry-run'])
            except KeyboardInterrupt:
                print()
                utils.fatal_msg('Caught keyboard interrupt. Exiting.')

            if error_code:
                utils.error_msg('Unable to communicate with git server')
                continue

            if stdout:
                updateable.append(package)

            print(consts.GREEN_CHECK_MARK)

    if not updateable:
        print(f'No updates available for installed packages {consts.YELLOW_X}')
        return False

    print(f'\n{len(updateable)} updates are available\n')

    for package in updateable:
        if not utils.prompt_user(f'An upgrade is available for {package.title}. Would you like to upgrade now?', assume_yes=assume_yes):
            upgraded = False
            continue

        if not upgrade_package(package):
            utils.error_msg('Unable to communicate with git server')

    if not upgraded:
        return False

    if utils.prompt_user('Would you like to restart MagicMirror now?', assume_yes=assume_yes):
        restart_magicmirror()

    return True


def search_packages(packages: Dict[str, List[MagicMirrorPackage]], query: str, case_sensitive: bool = False, by_title_only: bool = False) -> dict:
    '''
    Used to search the 'modules' for either a category, or keyword/phrase
    appearing within module descriptions. If the argument supplied is a
    category name, all modules from that category will be listed. Otherwise,
    all modules whose descriptions contain the keyword/phrase will be
    displayed.

    Parameters:
        packages (Dict[str, List[MagicMirrorPackage]]): Dictionary of MagicMirror modules
        query (str): user provided search string
        case_sensitive (bool): if True, the query's exact casing is used in search
        by_title_only (bool): if True, only the title is considered when matching packages to query

    Returns:
        dict
    '''

    # if the query matches one of the category names exactly, return everything in that category
    if query in packages:
        return {query: packages[query]}

    search_results = defaultdict(list)

    if by_title_only:
        match = lambda query, pkg: query == pkg.title
    elif case_sensitive:
        match = lambda query, pkg: query in pkg.description or query in pkg.title or query in pkg.author
    else:
        query = query.lower()
        match = lambda query, pkg: query in pkg.description.lower() or query in pkg.title.lower() or query in pkg.author.lower()

    for category, _packages in packages.items():
        search_results[category] = [package for package in _packages if match(query, package)]

    return search_results


def show_package_details(packages: dict) -> None:
    '''
    Used to display more detailed information that presented in normal search results

    Parameters:
        packages (List[defaultdict]): List of Categorized MagicMirror packages

    Returns:
        None
    '''

    for category, _packages  in packages.items():
        for package in _packages:
            print(utils.colored_text(color.N_GREEN, f'{package.title}'))
            print(f'  Category: {category}')
            print(f'  Repository: {package.repository}')
            print(f'  Author: {package.author}')
            print(indent(fill(f'Description: {package.description}\n', width=80), prefix='  '), '\n')


def get_installation_candidates(packages: Dict[str, List[MagicMirrorPackage]], packages_to_install: List[str]) -> List[MagicMirrorPackage]:
    '''
    Used to display more detailed information that presented in normal search results

    Parameters:
        packages (Dict[str, List[MagicMirrorPackage]]): MagicMirror modules database snapshot
        packages_to_install (List[str]): list of modules provided by user through command line arguments

    Returns:
        installation_candidates (List[MagicMirrorPackage]): list of modules whose module names match those of the modules_to_install
    '''

    installation_candidates: List[MagicMirrorPackage] = []

    if 'mmpm' in packages_to_install:
        utils.warning_msg("Removing 'mmpm' as an installation candidate. It's obviously already installed " + u'\U0001F609')
        packages_to_install.remove('mmpm')

    for package_to_install in packages_to_install:
        for category in packages.values():
            for package in category:
                if package.title == package_to_install:
                    utils.log.info(f'Matched {package.title} to installation candidate')
                    installation_candidates.append(package)

    return installation_candidates


def install_packages(installation_candidates: List[MagicMirrorPackage], assume_yes: bool = False) -> bool:
    '''
    Compares list of 'modules_to_install' to modules found within the
    'modules', clones the repository within the ~/MagicMirror/modules
    directory, and runs 'npm install' for each newly installed module.

    Parameters:
        installation_candidates (List[MagicMirrorPackage]): List of MagicMirrorPackages to install
        assume_yes (bool): if True, assume yes for user response, and do not display prompt

    Returns:
        bool: True upon success, False upon failure
    '''

    errors: List[dict] = []

    if not os.path.exists(consts.MAGICMIRROR_MODULES_DIR):
        utils.error_msg(f'MagicMirror directory not found in {consts.MAGICMIRROR_ROOT}. Is the MMPM_MAGICMIRROR_ROOT env variable set properly?')
        return False

    if not installation_candidates:
        utils.error_msg('Unable to match query any to installation candidates')
        return False

    utils.log.info(f'Changing into MagicMirror modules directory {consts.MAGICMIRROR_MODULES_DIR}')
    os.chdir(consts.MAGICMIRROR_MODULES_DIR)

    # a flag to check if any of the modules have been installed. Used for displaying a message later
    successes: int = 0
    match_count: int = len(installation_candidates)

    print(utils.colored_text(color.N_CYAN, f'Matched query to {match_count} package(s)\n'))

    for index, candidate in enumerate(installation_candidates):
        if not utils.prompt_user(f'Install {utils.colored_text(color.N_GREEN, candidate.title)} ({candidate.repository})?', assume_yes=assume_yes):
            utils.log.info(f'User not chose to install {candidate.title}')
            installation_candidates[index] = MagicMirrorPackage()
        else:
            utils.log.info(f'User chose to install {candidate.title} ({candidate.repository})')

    for package in installation_candidates:
        if package == None: # the module may be empty due to the above for loop
            continue

        package.directory = os.path.join(consts.MAGICMIRROR_MODULES_DIR, package.title)
        existing_module_dirs: List[str] = utils.get_existing_package_directories()

        # ideally, providiing alternative installation directories would be done, but it would require messing with file names within the renamed
        # module, which can cause a lot of problems when trying to update those repos
        if package.title in existing_module_dirs:
            utils.log.error(f'Conflict encountered. Found a package named {package.title} already at {package.directory}')
            utils.error_msg(f'A module named {package.title} is already installed in {package.directory}. Please remove {package.title} first.')
            continue

        try:
            success, _ = install_package(package, assume_yes=assume_yes)

            if success:
                successes += 1

        except KeyboardInterrupt:
            print()
            message = f'Cancelling installation of {package.title} {package.repository}'
            utils.log.info(message)
            utils.warning_msg(message)
            continue

    if not successes:
        return False

    print(f'Execute `mmpm open --config` to edit the configuration for newly installed modules')
    return True


def install_package(package: MagicMirrorPackage, assume_yes: bool = False) -> Tuple[bool, str]:
    '''
    Used to display more detailed information that presented in normal search results

    Parameters:
        package (MagicMirrorPackage): the MagicMirrorPackage to be installed
        assume_yes (bool): if True, all prompts are assumed to have a response of yes from the user

    Returns:
        installation_candidates (List[dict]): list of modules whose module names match those of the modules_to_install
    '''

    os.chdir(consts.MAGICMIRROR_MODULES_DIR)
    error_code, _, stderr = utils.clone(package.title, package.repository, package.directory)

    if error_code:
        utils.warning_msg("\n" + stderr)
        return False, stderr

    print(consts.GREEN_CHECK_MARK)

    os.chdir(package.directory)
    error: str = utils.install_dependencies()
    os.chdir('..')

    if error:
        utils.error_msg(error)
        message: str = f"Failed to install {package.title} at '{package.directory}'"
        utils.log.info(message)

        yes = utils.prompt_user(
            f"{utils.colored_text(color.B_RED, 'ERROR:')} Failed to install {package.title} at '{package.directory}'. Remove the directory?",
            assume_yes=assume_yes
        )

        if yes:
            message = f"User chose to remove {package.title} at '{package.directory}'"
            utils.run_cmd(['rm', '-rf', package.directory], progress=False)
            print(f"\nRemoved '{package.directory}'\n")
        else:
            message = f"Keeping {package.title} at '{package.directory}'"
            print(f'\n{message}\n')
            utils.log.info(message)

        return False, error

    return True, str()


def check_for_magicmirror_updates(assume_yes: bool = False) -> bool:
    '''
    Checks for updates available to the MagicMirror repository. Alerts user if an upgrade is available.

    Parameters:
        assume_yes (bool): if True, assume yes for user response, and do not display prompt

    Returns:
        bool: True upon success, False upon failure
    '''
    if not os.path.exists(consts.MAGICMIRROR_ROOT):
        utils.error_msg(f'{consts.MAGICMIRROR_ROOT} not found. Is the MMPM_MAGICMIRROR_ROOT env variable set properly?')
        return False

    if not os.path.exists(os.path.join(consts.MAGICMIRROR_ROOT, '.git')):
        utils.error_msg('The MagicMirror root does not appear to be a git repo. If running MagicMirror as a Docker container, updates cannot be performed via mmpm.')
        return False

    os.chdir(consts.MAGICMIRROR_ROOT)
    utils.plain_print(f"Checking {utils.colored_text(color.N_GREEN, 'MagicMirror')} for updates")

    # stdout and stderr are flipped for git command output, because that totally makes sense
    # except now stdout doesn't even contain error messages...thanks git
    try:
        error_code, _, stdout = utils.run_cmd(['git', 'fetch', '--dry-run'])
    except KeyboardInterrupt:
        print()
        utils.fatal_msg('Caught keyboard interrupt. Exiting.')

    print(consts.GREEN_CHECK_MARK)

    if error_code:
        utils.error_msg('Unable to communicate with git server')
        return False

    if not stdout:
        print(f'No updates available for MagicMirror {consts.YELLOW_X}')
        return False

    if not utils.prompt_user('An update is available for MagicMirror. Would you like to upgrade now?', assume_yes=assume_yes):
        return False

    if not upgrade_magicmirror():
        utils.error_msg('Unable to upgrade MagicMirror')
        return False

    if not utils.prompt_user('Would you like to restart MagicMirror now?', assume_yes=assume_yes):
        return True

    restart_magicmirror()
    return True


def upgrade_magicmirror() -> bool:
    '''
    Handles upgrade processs of MagicMirror by pulling changes from MagicMirror
    repo, and installing dependencies.

    Parameters:
        None

    Returns:
        success (bool): True if success, False if failure

    '''

    print(f"\n{utils.colored_text(color.N_CYAN, 'Upgrading MagicMirror')}")
    os.chdir(consts.MAGICMIRROR_ROOT)
    error_code, _, _ = utils.run_cmd(['git', 'pull'])

    if error_code:
        utils.error_msg('Failed to communicate with git server')
        return False

    error: str = utils.install_dependencies()

    if error:
        utils.error_msg(error)
        return False

    print('\nUpgrade complete!\n')
    return True


def install_magicmirror() -> bool:
    '''
    Installs MagicMirror. First checks if a MagicMirror installation can be
    found, and if one is found, prompts user to update the MagicMirror.
    Otherwise, searches for current version of NodeJS on the system. If one is
    found, the MagicMirror is then installed. If an old version of NodeJS is
    found, a newer version is installed before installing MagicMirror.

    Parameters:
        None

    Returns:
        bool: True upon succcess, False upon failure
    '''

    if os.path.exists(consts.MAGICMIRROR_ROOT):
        utils.fatal_msg('MagicMirror is installed already')

    if utils.prompt_user(f"Use '{consts.HOME_DIR}' as the parent directory of the MagicMirror installation?"):
        parent = consts.HOME_DIR
    else:
        parent = os.path.abspath(input('Absolute path to MagicMirror parent directory: '))
        print(f'Please set the MMPM_MAGICMIRROR_ROOT env variable in your bashrc to {parent}/MagicMirror')

    if not shutil.which('curl'):
        utils.fatal_msg("'curl' command not found. Please install 'curl', then re-run mmpm install --magicmirror")

    os.chdir(parent)
    print(utils.colored_text(color.N_CYAN, f'Installing MagicMirror in {parent}/MagicMirror ...'))
    os.system('bash -c "$(curl -sL https://raw.githubusercontent.com/sdetweil/MagicMirror_scripts/master/raspberry.sh)"')
    return True


def remove_packages(installed_packages: Dict[str, List[MagicMirrorPackage]], packages_to_remove: List[str], assume_yes: bool = False) -> bool:
    '''
    Gathers list of modules currently installed in the ~/MagicMirror/modules
    directory, and removes each of the modules from the folder, if modules are
    currently installed. Otherwise, the user is shown an error message alerting
    them no modules are currently installed.

    Parameters:
        installed_packages (Dict[str, List[MagicMirrorPackage]]): List of dictionary of MagicMirror packages
        modules_to_remove (list): List of modules to remove
        assume_yes (bool): if True, all prompts are assumed to have a response of yes from the user

    Returns:
        bool: True upon success, False upon failure
    '''

    cancelled_removal: List[str] = []
    marked_for_removal: List[str] = []

    package_dirs: List[str] = os.listdir(consts.MAGICMIRROR_MODULES_DIR)

    try:
        for _, packages in installed_packages.items():
            for package in packages:
                dir_name = os.path.basename(package.directory)
                if dir_name in package_dirs and dir_name in packages_to_remove:
                    prompt: str = f'Would you like to remove {utils.colored_text(color.N_GREEN, package.title)} ({dir_name})?'
                    if utils.prompt_user(prompt, assume_yes=assume_yes):
                        marked_for_removal.append(dir_name)
                        utils.log.info(f'User marked {dir_name} for removal')
                    else:
                        cancelled_removal.append(dir_name)
                        utils.log.info(f'User chose not to remove {dir_name}')
    except KeyboardInterrupt:
        print()
        utils.log.info('Caught keyboard interrupt during attempt to remove modules')
        return True

    for title in packages_to_remove:
        if title not in marked_for_removal and title not in cancelled_removal:
            utils.error_msg(f"No module named '{title}' found in {consts.MAGICMIRROR_MODULES_DIR}")
            utils.log.info(f"User attemped to remove {title}, but no module named '{title}' was found in {consts.MAGICMIRROR_MODULES_DIR}")

    for dir_name in marked_for_removal:
        shutil.rmtree(dir_name)
        print(f'{consts.GREEN_PLUS_SIGN} Removed {dir_name} {consts.GREEN_CHECK_MARK}')
        utils.log.info(f'Removed {dir_name}')

    if marked_for_removal:
        print(f'Execute `mmpm open --config` to delete associated configurations of any removed modules')

    return True


def load_packages(force_refresh: bool = False) -> Dict[str, List[MagicMirrorPackage]]:
    '''
    Reads in modules from the hidden 'snapshot_file'  and checks if the file is
    out of date. If so, the modules are gathered again from the MagicMirror 3rd
    Party Modules wiki.

    Parameters:
        force_refresh (bool): Boolean flag to force refresh of snapshot

    Returns:
        packages (Dict[str, List[MagicMirrorPackage]]): dictionary of MagicMirror 3rd party modules
    '''

    packages: dict = {}

    if not utils.assert_snapshot_directory():
        message: str = 'Failed to create directory for MagicMirror snapshot'
        utils.fatal_msg(message)

    # if the snapshot has expired, or doesn't exist, get a new one
    if force_refresh or not os.path.exists(consts.MAGICMIRROR_3RD_PARTY_PACKAGES_SNAPSHOT_FILE):
        utils.plain_print(f'{consts.GREEN_PLUS_SIGN} Refreshing MagicMirror 3rd party packages database ')
        packages = retrieve_packages()

        # save the new snapshot
        with open(consts.MAGICMIRROR_3RD_PARTY_PACKAGES_SNAPSHOT_FILE, 'w') as snapshot:
            json.dump(packages, snapshot, default=lambda pkg: pkg.serialize())

        print(consts.GREEN_CHECK_MARK)

    if not packages:
        with open(consts.MAGICMIRROR_3RD_PARTY_PACKAGES_SNAPSHOT_FILE, 'r') as snapshot_file:
            packages = json.load(snapshot_file)

            for category in packages.keys():
                packages[category] = utils.list_of_dict_to_magicmirror_packages(packages[category])

    if os.path.exists(consts.MMPM_EXTERNAL_SOURCES_FILE) and os.stat(consts.MMPM_EXTERNAL_SOURCES_FILE).st_size:
        packages[consts.EXTERNAL_MODULE_SOURCES] = load_external_packages()

    return packages


def load_external_packages() -> List[MagicMirrorPackage]:
    '''
    Extracts the external packages from the JSON files stored in
    ~/.config/mmpm/mmpm-external-sources.json

    If no data is found, an empty list is returned

    Parameters:
        None

    Returns:
        external_packages (List[MagicMirrorPackage]): the list of manually added MagicMirror packages
    '''
    external_packages: List[MagicMirrorPackage] = []

    try:
        with open(consts.MMPM_EXTERNAL_SOURCES_FILE, 'r') as f:
            external_packages = utils.list_of_dict_to_magicmirror_packages(json.load(f)[consts.EXTERNAL_MODULE_SOURCES])
    except Exception:
        message = f'Failed to load data from {consts.MMPM_EXTERNAL_SOURCES_FILE}. Please examine the file, as it may be malformed and required manual corrective action.'
        utils.warning_msg(message)

    return external_packages

def retrieve_packages() -> Dict[str, List[MagicMirrorPackage]]:
    '''
    Scrapes the MagicMirror 3rd Party Wiki, and saves all modules along with
    their full, available descriptions in a hidden JSON file in the users home
    directory.

    Parameters:
        None

    Returns:
        packages (dict): dictionary of MagicMirror 3rd party modules
    '''

    packages: Dict[str, List[MagicMirrorPackage]] = {}

    try:
        url = urlopen(consts.MAGICMIRROR_MODULES_URL)
        web_page = url.read()
    except HTTPError:
        utils.error_msg('Unable to retrieve MagicMirror modules. Is your internet connection down?')
        return {}

    soup = BeautifulSoup(web_page, 'html.parser')
    table_soup: list = soup.find_all('table')

    category_soup: list = soup.find_all(attrs={'class': 'markdown-body'})
    categories_soup: list = category_soup[0].find_all('h3')

    categories: list = []

    for index, _ in enumerate(categories_soup):
        last_element: object = len(categories_soup[index].contents) - 1
        new_category: object = categories_soup[index].contents[last_element]

        if new_category != 'General Advice':
            categories.append(new_category)

    tr_soup: list = []

    for table in table_soup:
        tr_soup.append(table.find_all("tr"))

    for index, row in enumerate(tr_soup):
        packages.update({categories[index]: list()})

        for column_number, _ in enumerate(row):
            # ignore cells that literally say "Title", "Author", "Description"
            if column_number > 0:
                td_soup: list = tr_soup[index][column_number].find_all('td')

                package = MagicMirrorPackage()

                title: str = consts.NOT_AVAILABLE
                repo: str = consts.NOT_AVAILABLE
                author: str = consts.NOT_AVAILABLE
                desc: str = consts.NOT_AVAILABLE

                for idx, _ in enumerate(td_soup):
                    if idx == 0:
                        for td in td_soup[idx]:
                            title = td.contents[0]

                        for a in td_soup[idx].find_all('a'):
                            if a.has_attr('href'):
                                repo = a['href']

                        package.repository = str(repo).strip()
                        package.title = str(title)

                    elif idx == 1:
                        for contents in td_soup[idx].contents:
                            if type(contents).__name__ == 'Tag':
                                for tag in contents:
                                    author = tag.strip()
                            else:
                                author = contents

                        author = str(author)

                    else:
                        if contents:
                            desc = str()
                        for contents in td_soup[idx].contents:
                            if type(contents).__name__ == 'Tag':
                                for content in contents:
                                    desc += content.string
                            else:
                                desc += contents.string

                packages[categories[index]].append(
                    MagicMirrorPackage(
                        title=utils.sanitize_name(title).strip(),
                        author=author.strip(),
                        description=desc.strip(),
                        repository=repo.strip()
                    )
                )

    return packages


def display_categories(packages: Dict[str, List[MagicMirrorPackage]], table_formatted: bool = False) -> None:
    '''
    Prints module category names and the total number of modules in one of two
    formats. The default is similar to the Debian apt package manager, and the
    prettified table alternative

    Parameters:
        packages (Dict[str, List[MagicMirrorPackage]]): list of dictionaries containing category names and module count
        table_formatted (bool): if True, the output is printed as a prettified table

    Returns:
        None
    '''

    categories: List[dict] = [
        {
            consts.CATEGORY: key,
            consts.PACKAGES: len(packages[key])
        } for key in packages.keys()
    ]

    if not table_formatted:
        for category in categories:
            print(utils.colored_text(color.N_GREEN, category[consts.CATEGORY]), f'\n  Packages: {category[consts.PACKAGES]}\n')
        return

    global_row: int = 1
    columns: int = 2
    rows = len(categories) + 1  # to include the header row

    table = utils.allocate_table_memory(rows, columns)
    table[0][0], table[0][1] = utils.to_bytes(consts.CATEGORY.title()), utils.to_bytes(consts.PACKAGES.title())

    for category in categories:
        table[global_row][0] = utils.to_bytes(category[consts.CATEGORY])
        table[global_row][1] = utils.to_bytes(str(category[consts.PACKAGES]))
        global_row += 1

    utils.display_table(table, rows, columns)


def display_packages(packages: Dict[str, List[MagicMirrorPackage]], table_formatted: bool = False, include_path: bool = False) -> None:
    '''
    Depending on the user flags passed in from the command line, either all
    existing packages may be displayed, or the names of all categories of
    packages may be displayed.

    Parameters:
        packages (Dict[str, List[MagicMirrorPackage]]): dictionary of MagicMirror 3rd party packages
        list_categories (bool): Boolean flag to list categories

    Returns:
        None
    '''
    format_description = lambda desc: desc[:MAX_LENGTH] + '...' if len(desc) > MAX_LENGTH else desc
    MAX_LENGTH: int = 120

    if table_formatted:
        columns: int = 2
        global_row: int = 1
        rows: int = 1  # to include the header row

        for row in packages.values():
            rows += len(row)

        if include_path:
            columns += 1
            MAX_LENGTH = 80

        table = utils.allocate_table_memory(rows, columns)

        table[0][0] = utils.to_bytes(consts.TITLE.title())
        table[0][1] = utils.to_bytes(consts.DESCRIPTION.title())

        if include_path:
            table[0][2] = utils.to_bytes(consts.DIRECTORY.title())

            def __fill_row__(table, row, package: MagicMirrorPackage):
                table[row][0] = utils.to_bytes(package.title)
                table[row][1] = utils.to_bytes(format_description(package.description))
                table[row][2] = utils.to_bytes(os.path.basename(package.directory))
        else:
            def __fill_row__(table, row, package: MagicMirrorPackage):
                table[row][0] = utils.to_bytes(package.title)
                table[row][1] = utils.to_bytes(format_description(package.description))

        for _, _packages in packages.items():
            for _, package in enumerate(_packages):
                __fill_row__(table, global_row, package)
                global_row += 1

        utils.display_table(table, rows, columns)

    else:
        if include_path:
            _print_ = lambda package: print(
                utils.colored_text(color.N_GREEN, f'{package.title}'),
                (f'\n  Directory: {os.path.basename(package.directory)}'),
                (f"\n  {format_description(package.description)}\n")
            )

        else:
            _print_ = lambda package: print(
                utils.colored_text(color.N_GREEN, f'{package.title}'),
                (f"\n  {format_description(package.description)}\n")
            )

        for _, _packages in packages.items():
            for _, package in enumerate(_packages):
                _print_(package)


def get_installed_packages(packages: Dict[str, List[MagicMirrorPackage]]) -> Dict[str, List[MagicMirrorPackage]]:
    '''
    Saves a list of all currently installed packages in the
    ~/MagicMirror/modules directory, and compares against the known packages
    from the MagicMirror 3rd Party Wiki.

    Parameters:
        packages (Dict[str, List[MagicMirrorPackage]]): Dictionary of MagicMirror packages

    Returns:
        installed_modules (Dict[str, List[MagicMirrorPackage]]): Dictionary of installed MagicMirror packages
    '''

    package_dirs: List[str] = utils.get_existing_package_directories()

    if not package_dirs:
        msg = "Failed to find MagicMirror root. Have you installed MagicMirror properly? "
        msg += "You may also set the env variable 'MMPM_MAGICMIRROR_ROOT' to the MagicMirror root directory."
        utils.error_msg(msg)
        return {}

    os.chdir(consts.MAGICMIRROR_MODULES_DIR)

    installed_packages: Dict[str, List[MagicMirrorPackage]] = {}
    packages_found: Dict[str, List[MagicMirrorPackage]] = {consts.PACKAGES: []}

    for package_dir in package_dirs:
        if not os.path.isdir(package_dir) or not os.path.exists(os.path.join(os.getcwd(), package_dir, '.git')):
            continue

        try:
            os.chdir(os.path.join(consts.MAGICMIRROR_MODULES_DIR, package_dir))

            error_code, remote_origin_url, stderr = utils.run_cmd(
                ['git', 'config', '--get', 'remote.origin.url'],
                progress=False
            )

            if error_code:
                utils.error_msg('Unable to communicate with git server')
                continue

            error_code, project_name, stderr = utils.run_cmd(
                ['basename', remote_origin_url.strip(), '.git'],
                progress=False
            )

            if error_code:
                utils.error_msg(f'Unable to determine repository origin for {project_name}')
                continue

            packages_found[consts.PACKAGES].append(
                MagicMirrorPackage(
                    title=project_name.strip(),
                    repository=remote_origin_url.strip(),
                    directory=os.getcwd()
                )
            )

        except Exception:
            utils.error_msg(stderr)

        finally:
            os.chdir('..')

    for category, package_names in packages.items():
        installed_packages.setdefault(category, [])
        for package in package_names:
            for package_found in packages_found[consts.PACKAGES]:
                if package.repository == package_found.repository:
                    package.directory = package_found.directory
                    installed_packages[category].append(package)

    return installed_packages


def add_external_package(title: str = None, author: str = None, repo: str = None, description: str = None) -> str:
    '''
    Adds an external source for user to install a module from. This may be a
    private git repo, or a specific branch of a public repo. All modules added
    in this manner will be added to the 'External Module Sources' category.
    These sources are stored in ~/.config/mmpm/mmpm-external-sources.json

    Parameters:
        title (str): External source title
        author (str): External source author
        repo (str): External source repo url
        description (str): External source description

    Returns:
        (bool): Upon success, a True result is returned
    '''
    try:
        if not title:
            title = utils.assert_valid_input('Title: ')
        else:
            print(f'Title: {title}')

        if not author:
            author = utils.assert_valid_input('Author: ')
        else:
            print(f'Author: {author}')

        if not repo:
            repo = utils.assert_valid_input('Repository: ')
        else:
            print(f'Repository: {repo}')

        if not description:
            description = utils.assert_valid_input('Description: ')
        else:
            print(f'Description: {description}')

    except KeyboardInterrupt:
        print()
        utils.log.info('User cancelled creation of external package')
        sys.exit(1)

    external_package = MagicMirrorPackage(title=title, repository=repo, author=author, description=description)

    try:
        if os.path.exists(consts.MMPM_EXTERNAL_SOURCES_FILE) and os.stat(consts.MMPM_EXTERNAL_SOURCES_FILE).st_size:
            config: dict = {}

            with open(consts.MMPM_EXTERNAL_SOURCES_FILE, 'r') as mmpm_ext_srcs:
                config[consts.EXTERNAL_MODULE_SOURCES] = utils.list_of_dict_to_magicmirror_packages(json.load(mmpm_ext_srcs)[consts.EXTERNAL_MODULE_SOURCES])

            with open(consts.MMPM_EXTERNAL_SOURCES_FILE, 'w') as mmpm_ext_srcs:
                config[consts.EXTERNAL_MODULE_SOURCES].append(external_package)
                json.dump(config, mmpm_ext_srcs, default=lambda pkg: pkg.serialize())
        else:
            # if file didn't exist previously, or it was empty, this is the first external package that's been added
            with open(consts.MMPM_EXTERNAL_SOURCES_FILE, 'w') as mmpm_ext_srcs:
                json.dump({consts.EXTERNAL_MODULE_SOURCES: [external_package]}, mmpm_ext_srcs, default=lambda pkg: pkg.serialize())

        print(utils.colored_text(color.N_GREEN, f"\nSuccessfully added {title} to '{consts.EXTERNAL_MODULE_SOURCES}'\n"))

    except IOError as error:
        utils.error_msg('Failed to save external module')
        return str(error)

    return ''


def remove_external_package_source(titles: List[str] = None, assume_yes: bool = False) -> bool:
    '''
    Allows user to remove an external source from the sources saved in
    ~/.config/mmpm/mmpm-external-sources.json

    Parameters:
        titles (List[str]): External source titles

    Returns:
        success (bool): True on success, False on error
    '''

    if not os.path.exists(consts.MMPM_EXTERNAL_SOURCES_FILE):
        utils.fatal_msg(f'{consts.MMPM_EXTERNAL_SOURCES_FILE} does not appear to exist')

    elif not os.stat(consts.MMPM_EXTERNAL_SOURCES_FILE).st_size:
        utils.fatal_msg(f'{consts.MMPM_EXTERNAL_SOURCES_FILE} is empty')

    ext_packages: Dict[str, List[MagicMirrorPackage]] = {}
    marked_for_removal: List[MagicMirrorPackage] = []
    cancelled_removal: List[MagicMirrorPackage] = []

    with open(consts.MMPM_EXTERNAL_SOURCES_FILE, 'r') as mmpm_ext_srcs:
        ext_packages[consts.EXTERNAL_MODULE_SOURCES] = utils.list_of_dict_to_magicmirror_packages(json.load(mmpm_ext_srcs)[consts.EXTERNAL_MODULE_SOURCES])

    if not ext_packages[consts.EXTERNAL_MODULE_SOURCES]:
        utils.fatal_msg('No external packages found in database')

    for title in titles:
        for package in ext_packages[consts.EXTERNAL_MODULE_SOURCES]:
            if package.title == title:
                prompt: str = f'Would you like to remove {utils.colored_text(color.N_GREEN, title)} ({package.repository}) from the MMPM/MagicMirror local database?'
                if utils.prompt_user(prompt, assume_yes=assume_yes):
                    marked_for_removal.append(package)
                else:
                    cancelled_removal.append(package)

    if not marked_for_removal and not cancelled_removal:
        utils.error_msg('No external sources found matching provided query')
        return False

    for package in marked_for_removal:
        ext_packages[consts.EXTERNAL_MODULE_SOURCES].remove(package)
        print(f'{consts.GREEN_PLUS_SIGN} Removed {package.title} ({package.repository})')

    # if the error_msg was triggered, there's no need to even bother writing back to the file
    with open(consts.MMPM_EXTERNAL_SOURCES_FILE, 'w') as mmpm_ext_srcs:
        json.dump(ext_packages, mmpm_ext_srcs, default=lambda pkg: pkg.serialize())

    return True


def display_active_packages(table_formatted: bool = False) -> None:

    '''
    Parses the MagicMirror config file for the modules listed, and reports
    which modules are currently enabled. A module is considered disabled if the
    module explictly contains a 'disabled' flag with a 'true' value. Otherwise,
    the module is considered enabled.

    Parameters:
        table_formatted (bool): if True, output is displayed in a table

    Returns:
        None
    '''

    if not os.path.exists(consts.MAGICMIRROR_CONFIG_FILE):
        utils.fatal_msg('MagicMirror config file not found. Is the MMPM_MAGICMIRROR_ROOT env variable set properly?')

    temp_config: str = f'{consts.MAGICMIRROR_ROOT}/config/temp_config.js'
    shutil.copyfile(consts.MAGICMIRROR_CONFIG_FILE, temp_config)

    with open(temp_config, 'a') as temp:
        temp.write('console.log(JSON.stringify(config))')

    _, stdout, _ = utils.run_cmd(['node', temp_config], progress=False)
    config: dict = json.loads(stdout.split('\n')[0])

    # using -f so any errors can be ignored
    utils.run_cmd(['rm', '-f', temp_config], progress=False)

    if 'modules' not in config or not config['modules']:
        utils.error_msg(f'No modules found in {consts.MAGICMIRROR_CONFIG_FILE}')

    if not table_formatted:
        for module_config in config['modules']:
            print(
                utils.colored_text(color.N_GREEN, module_config['module']),
                f"\n  Status: {'disabled' if 'disabled' in module_config and module_config['disabled'] else 'enabled'}\n"
            )
        return

    global_row: int = 1
    columns: int = 2
    rows: int = 1  # to include the header row

    rows = len(config['modules']) + 1

    table = utils.allocate_table_memory(rows, columns)

    table[0][0] = utils.to_bytes('Module')
    table[0][1] = utils.to_bytes('Status')

    for module_config in config['modules']:
        table[global_row][0] = utils.to_bytes(module_config['module'])
        table[global_row][1] = utils.to_bytes('disabled') if 'disabled' in module_config and module_config['disabled'] else utils.to_bytes('enabled')
        global_row += 1

    utils.display_table(table, rows, columns)


def get_web_interface_url() -> str:
    '''
    Parses the MMPM nginx conf file for the port number assigned to the web
    interface, and returns a string containing containing the host IP and
    assigned port.

    Parameters:
        None

    Returns:
        str: The URL of the MMPM web interface
    '''

    if not os.path.exists(consts.MMPM_NGINX_CONF_FILE):
        utils.fatal_msg('The MMPM NGINX configuration file does not appear to exist. Is the GUI installed?')

    # this value needs to be retrieved dynamically in case the user modifies the nginx conf
    with open(consts.MMPM_NGINX_CONF_FILE, 'r') as conf:
        mmpm_conf = conf.read()

    try:
        port: str = re.findall(r"listen\s?\d+", mmpm_conf)[0].split()[1]
    except IndexError:
        utils.fatal_msg('Unable to retrieve the port number of the MMPM web interface')

    return f'http://{gethostbyname(gethostname())}:{port}'



def stop_magicmirror() -> bool:
    '''
    Stops MagicMirror using pm2, if found, otherwise the associated
    processes are killed

    Parameters:
       None

    Returns:
        None
    '''
    if shutil.which('pm2'):
        utils.log.info("Using 'pm2' to stop MagicMirror")
        _, _, stderr = utils.run_cmd(['pm2', 'stop', consts.MMPM_ENV_VARS[consts.MAGICMIRROR_PM2_PROC]], progress=False)

        if stderr:
            utils.error_msg(f'{stderr.strip()}. Is the MAGICMIRROR_PM2_PROC env variable set correctly?')
            return False

        utils.log.info('stopped MagicMirror using PM2')
        return True

    utils.kill_magicmirror_processes()
    return True


def start_magicmirror() -> bool:
    '''
    Launches MagicMirror using pm2, if found, otherwise a 'npm start' is run as
    a background process

    Parameters:
       None

    Returns:
        None
    '''
    utils.log.info('Starting MagicMirror')
    os.chdir(consts.MAGICMIRROR_ROOT)

    utils.log.info("Running 'npm start' in the background")

    if shutil.which('pm2'):
        utils.log.info("Using 'pm2' to start MagicMirror")
        error_code, _, stderr = utils.run_cmd(
            ['pm2', 'start', consts.MMPM_ENV_VARS[consts.MAGICMIRROR_PM2_PROC]],
            background=True
        )

        if error_code:
            utils.error_msg(f'{stderr.strip()}. Is the MAGICMIRROR_PM2_PROC env variable set correctly?')
            return False

        utils.log.info('started MagicMirror using PM2')
        return True

    os.system('npm start &')
    utils.log.info("Using 'npm start' to start MagicMirror. Stdout/stderr capturing not possible in this case")
    return False if error_code else True


def restart_magicmirror() -> bool:
    '''
    Restarts MagicMirror using pm2, if found, otherwise the associated
    processes are killed and 'npm start' is re-run a background process

    Parameters:
       None

    Returns:
        None
    '''
    if shutil.which('pm2'):
        utils.log.info("Using 'pm2' to restart MagicMirror")
        _, _, stderr = utils.run_cmd(
            ['pm2', 'restart', consts.MMPM_ENV_VARS[consts.MAGICMIRROR_PM2_PROC]],
            progress=False
        )

        if stderr:
            utils.error_msg(f'{stderr.strip()}. Is the MAGICMIRROR_PM2_PROC env variable set correctly?')
            return False

        utils.log.info('restarted MagicMirror using PM2')
        return True

    if not stop_magicmirror():
        utils.log.error('Failed to stop MagicMirror using npm commands')
        return False

    if not start_magicmirror():
        utils.log.error('Failed to start MagicMirror using npm commands')
        return False

    utils.log.info('Restarted MagicMirror using npm commands')
    return True


def display_log_files(cli_logs: bool = False, gui_logs: bool = False, tail: bool = False) -> None:
    '''
    Displays contents of log files to stdout. If the --tail option is supplied,
    log contents will be displayed in real-time

    Parameters:
       cli_logs (bool): if True, the CLI log files will be displayed
       gui_logs (bool): if True, the Gunicorn log files for the web interface will be displayed
       tail (bool): if True, the contents will be displayed in real time

    Returns:
        None
    '''
    logs: List[str] = []

    if cli_logs:
        if os.path.exists(consts.MMPM_LOG_FILE):
            logs.append(consts.MMPM_LOG_FILE)
        else:
            utils.error_msg('MMPM log file not found')

    if gui_logs:
        if os.path.exists(consts.MMPM_GUNICORN_ACCESS_LOG_FILE):
            logs.append(consts.MMPM_GUNICORN_ACCESS_LOG_FILE)
        else:
            utils.error_msg('Gunicorn access log file not found')
        if os.path.exists(consts.MMPM_GUNICORN_ERROR_LOG_FILE):
            logs.append(consts.MMPM_GUNICORN_ERROR_LOG_FILE)
        else:
            utils.error_msg('Gunicorn error log file not found')

    if logs:
        os.system(f"{'tail -F' if tail else 'cat'} {' '.join(logs)}")


def display_mmpm_env_vars() -> None:
    '''
    Displays the environment variables associated with MMPM, as well as their
    current value. A user may modify these values by setting them in their
    shell configuration file

    Parameters:
        None

    Returns:
        None
    '''

    for key, value in consts.MMPM_ENV_VARS.items():
        print(f'{key}={value}')


def install_autocompletion(assume_yes: bool = False) -> None:
    '''
    Adds autocompletion configuration to a user's shell configuration file.
    Detects configuration files for bash, zsh, fish, and tcsh

    Parameters:
        assume_yes (bool): if True, assume yes for user response, and do not display prompt

    Returns:
        None
    '''

    if not utils.prompt_user('Are you sure you want to install the autocompletion feature for the MMPM CLI?', assume_yes=assume_yes):
        utils.log.info('User cancelled installation of autocompletion for MMPM CLI')
        return

    utils.log.info('user attempting to install MMPM autocompletion')
    shell: Final[str] = os.environ['SHELL']

    utils.log.info(f'detected user shell to be {shell}')

    autocomplete_url: Final[str] = 'https://github.com/kislyuk/argcomplete#activating-global-completion'
    error_message: Final[str] = f'Please see {autocomplete_url} for help installing autocompletion'

    complete_message = lambda config: f'Autocompletion installed. Please source {config} for the changes to take effect'
    failed_match_message = lambda shell, configs: f'Unable to locate {shell} configuration file (looked for {configs}). {error_message}'

    def __match_shell_config__(configs: List[str]) -> str:
        utils.log.info(f'searching for one of the following shell configuration files {configs}')
        for config in configs:
            config = os.path.join(consts.HOME_DIR, config)
            if os.path.exists(config):
                utils.log.info(f'found {config} shell configuration file for {shell}')
                return config
        return ''

    def __echo_and_eval__(command: str) -> None:
        utils.log.info(f'executing {command} to install autocompletion')
        print(f'{consts.GREEN_PLUS_SIGN} {utils.colored_text(color.N_GREEN, command)}')
        os.system(command)

    if 'bash' in shell:
        files = ['.bashrc', '.bash_profile', '.bash_login', '.profile']
        config = __match_shell_config__(files)

        if not config:
            utils.fatal_msg(failed_match_message('bash', files))

        __echo_and_eval__(f'echo \'eval "$(register-python-argcomplete mmpm)"\' >> {config}')

        print(complete_message(config))

    elif 'zsh' in shell:
        files = ['.zshrc', '.zprofile', '.zshenv', '.zlogin', '.profile']
        config = __match_shell_config__(files)

        if not config:
            utils.fatal_msg(failed_match_message('zsh', files))

        __echo_and_eval__(f"echo 'autoload -U bashcompinit' >> {config}")
        __echo_and_eval__(f"echo 'bashcompinit' >> {config}")
        __echo_and_eval__(f'echo \'eval "$(register-python-argcomplete mmpm)"\' >> {config}')

        print(complete_message(config))

    elif 'tcsh' in shell:
        files = ['.tcshrc', '.cshrc', '.login']
        config = __match_shell_config__(files)

        if not config:
            utils.fatal_msg(failed_match_message('tcsh', files))

        __echo_and_eval__(f"echo 'eval `register-python-argcomplete --shell tcsh mmpm`' >> {config}")

        print(complete_message(config))

    elif 'fish' in shell:
        files = ['.config/fish/config.fish']
        config = __match_shell_config__(files)

        if not config:
            utils.fatal_msg(failed_match_message('fish', files))

        __echo_and_eval__(f"register-python-argcomplete --shell fish mmpm >> {config}")

        print(complete_message(config))

    else:
        utils.fatal_msg(f'Unable install autocompletion for ({shell}). Please see {autocomplete_url} for help installing autocomplete')
