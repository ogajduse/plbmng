import os
from pathlib import Path

from dynaconf import Dynaconf
from dynaconf import loaders

from plbmng.executor import ensure_basic_structure
from plbmng.utils.logger import logger


local = Path(__file__).parent.absolute()

__env_switcher: str = "ENV_FOR_PLBMNG"
__plbmng_root_dir: str = os.getenv("PLBMNG_CONFIG_ROOT") or "~/.plbmng"
__plbmng_database_dir: str = os.path.expanduser(f"{__plbmng_root_dir}/database")
__plbmng_geolocation_dir: str = os.path.expanduser(f"{__plbmng_root_dir}/geolocation")
__plbmng_remote_jobs_dir: str = os.path.expanduser(f"{__plbmng_root_dir}/remote-jobs")
__settings_path: str = os.path.expanduser(f"{__plbmng_root_dir}/settings.yaml")
__secrets_path: str = os.path.expanduser(f"{__plbmng_root_dir}/.secrets.yaml")
__local_settings_path: str = os.path.expanduser(f"{local}/settings.yaml")
__local_secrets_path: str = os.path.expanduser(f"{local}/.secrets.yaml")

dynaconf_setting_files = [__local_settings_path, __local_secrets_path, __settings_path, __secrets_path]


def get_plbmng_user_dir() -> str:
    """
    Return absolute path to the plbmng user directory.

    :return: absolute path to the plbmng user directory
    """
    return __plbmng_root_dir


def get_plbmng_geolocation_dir() -> str:
    """
    Return absolute path to the geolocation directory inside the plbmng user directory.

    :return: absolute path to the geolocation directory inside the plbmng user directory
    """
    return __plbmng_geolocation_dir


def get_remote_jobs_path() -> str:
    """
    Get the absolute path of the remote_jobs directory in the plbmng user directory.

    :return: path of the remote_jobs directory in the plbmng user directory
    """
    return f"{__plbmng_remote_jobs_dir}"


def get_install_dir() -> str:
    """
    Return absolute path to the source directory of plbmng.

    :return: absolute path to the source directory of plbmng
    """
    path = os.path.dirname(os.path.realpath(__file__)).rstrip("/utils")
    os.chdir(path)
    return path


def _write_settings(data: dict) -> None:
    """
    Write plbmng settings to the settings file.

    :param data: Data to write to the settings file represented as dictionary
    """
    loaders.write(__settings_path, data, env="plbmng")


def ensure_settings_file() -> None:
    """
    Ensure that the settings file exists.

    If it does not exist, creates base settings and stores it in the user settings directory.
    """
    if not Path(__settings_path).exists():
        logger.info(
            f'Settings in directory not found "{Path(__settings_path).absolute()}".'
            f"I'll create default settings here: {__settings_path}"
        )
        Path(__settings_path).parent.mkdir(parents=True, exist_ok=True)

        base_settings = {
            "planetlab": {"SLICE": "", "USERNAME": "", "PASSWORD": ""},
            "remote_execution": {"SSH_KEY": "", "CONNECTION_TIMEOUT": 30, "COMMAND_TIMEOUT": 60},
            "database": {
                "USER_NODES": "user_servers.node",
                "LAST_SERVER": "last_server.node",
                "PLBMNG_DATABASE": "internal.db",
                "DEFAULT_NODE": "default.node",
            },
            "geolocation": {"map_file": "plbmng_server_map.html"},
            "first_run": True,
        }

        _write_settings(base_settings)


def __db_file_exist(path: str, failsafe: bool = False) -> str:
    """
    Check that the specified file exists in the database directory. Returns respective boolean.

    :param path: path to the database file
    :param failsafe: specifies if the exception should be raised in case
        the file is not found, defaults to :py:obj:`False`
    :raises FileNotFoundError: if the specified file is not found
    :return: path of the database file
    """
    if not Path(path).exists() and not failsafe:
        raise FileNotFoundError(f"Database file not found in path {path}")
    return path


def get_db_path(db_name: str, failsafe: bool = False) -> bool:
    """
    Check that the specified database file exists in the database directory.

    :param db_name: name of the database file to be found in the database directory
    :param failsafe: specifies if the exception should be raised
        in case the file is not found, defaults to :py:obj:`False`
    :return: boolean indicating that the the file with ``db_name`` exists in the database directory
    """
    return __db_file_exist(f"{__plbmng_database_dir}/{getattr(settings.database, db_name)}", failsafe)


def get_map_path(map_name: str) -> str:
    """
    Get the path of the map file located in the geolocation directory.

    :param map_name: name of the map file to look for
    :return: path to the map file located in the geolocation directory
    """
    return f"{__plbmng_geolocation_dir}/{getattr(settings.geolocation, map_name)}"


def _create_dir(dir_name: str, dir_path: str) -> None:
    """
    Create directory of ``dir_name`` in the specified ``dir_path``.

    :param dir_name: name of the directory that should be created. Used only for logging purpose.
    :param dir_path: path to the directory that should be created
    """
    if not Path(dir_path).exists():
        logger.info(
            f'{dir_name} directory not found here: "{Path(dir_path).absolute()}". I\'ll create it here: {dir_path}'
        )
        Path(dir_path).mkdir(exist_ok=True)


def _copy_distribution_file(src: str, dst: str) -> None:
    """
    Copy file from ``src`` to ``dst``. Used to copy files from the package distribution to the plbmng user directory.

    :param src: path of the source file
    :param dst: path of the destination file
    """
    if not Path(dst).exists():
        with open(dst, "w") as default_node:
            default_node.write(Path(src).read_text())


def ensure_directory_structure(settings: Dynaconf) -> None:
    """
    Ensure base directory structure in the plbmng user directory.

    Ensures base directory structure and copies files from the plbmng package distribution to the user directory.

    :param settings: Dynaconf object from which the settings attributes should be read
    """
    dirs = {
        "Database": __plbmng_database_dir,
        "Geolocation": __plbmng_geolocation_dir,
        "Rebote jobs": __plbmng_remote_jobs_dir,
    }
    for name, path in dirs.items():
        _create_dir(name, path)

    distro_files = {
        f"{get_install_dir()}/database/default.node": f"{__plbmng_database_dir}/{settings.database.default_node}",
        f"{get_install_dir()}/database/user_servers.node": f"{__plbmng_database_dir}/{settings.database.user_nodes}",
    }
    for src, dst in distro_files.items():
        _copy_distribution_file(src, dst)


def ensure_initial_structure(settings: Dynaconf) -> None:
    """
    Ensure initial structure in the plbmng user directory.

    :param settings: Dynaconf settings
    """
    ensure_basic_structure()
    ensure_directory_structure(settings)


def first_run() -> None:
    """Remove ``FIRST_RUN`` key from the settings file and write the settings."""
    data = settings.as_dict(env="plbmng")
    data.pop("FIRST_RUN")
    logger.info("Program is being run for the first time. Removing the first run setting from settings.")
    _write_settings(data)


validators = [
    # TODO: Use Dynaconf validators to validate settings
    # Ensure some parameters exists (are required)
    # Ensure that each DB file exists
]

ensure_settings_file()

settings = Dynaconf(
    envvar_prefix="PLBMNG",
    env_switcher=__env_switcher,
    settings_files=dynaconf_setting_files,
    environments=True,
    load_dotenv=True,
    root_path=os.path.expanduser(__plbmng_root_dir),
    validators=validators,
    merge_enabled=True,
)

logger.info("Settings successfully loaded")

ensure_initial_structure(settings)
