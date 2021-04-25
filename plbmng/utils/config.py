import os
from pathlib import Path

from dynaconf import Dynaconf
from dynaconf import loaders

from plbmng.executor import ensure_basic_structure
from plbmng.utils.logger import logger

# from dynaconf import Validator


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

dynaconf_setting_files = [
    __local_settings_path,
    __local_secrets_path,
    __settings_path,
    __secrets_path,
]


def get_plbmng_user_dir():
    return __plbmng_root_dir


def get_install_dir() -> str:
    """
    Return absolute path to the source directory of plbmng.

    :return: absolute path to the source directory of plbmng as str.
    :rtype: str
    """
    path = os.path.dirname(os.path.realpath(__file__)).rstrip("/utils")
    os.chdir(path)
    return path


def _write_settings(data: str):
    loaders.write(__settings_path, data, env="plbmng")


def ensure_settings_file():
    if not Path(__settings_path).exists():
        logger.info(
            f'Settings in path directory not found "{Path(__settings_path).absolute()}". '
            f"I'll create default settings here: {__settings_path}",
        )
        Path(__settings_path).parent.mkdir(parents=True, exist_ok=True)

        base_settings = {
            "planetlab": {"SLICE": "", "USERNAME": "", "PASSWORD": ""},
            "remote_execution": {"SSH_KEY": ""},
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


def __db_file_exist(path, failsafe=False):
    if not Path(path).exists() and not failsafe:
        raise FileNotFoundError(f"Database file not found in path {path}")
    return path


def get_db_path(db_name, failsafe=False):
    return __db_file_exist(f"{__plbmng_database_dir}/{getattr(settings.database, db_name)}", failsafe)


def get_map_path(map_name):
    return f"{__plbmng_geolocation_dir}/{getattr(settings.geolocation, map_name)}"


def get_remote_jobs_path():
    return f"{__plbmng_remote_jobs_dir}"


def _create_dir(dir_name: str, dir_path: str):
    if not Path(dir_path).exists():
        logger.info(
            f'{dir_name} directory not found here: "{Path(dir_path).absolute()}". I\'ll create it here: {dir_path}',
        )
        Path(dir_path).mkdir(exist_ok=True)


def _copy_distribution_file(src: str, dst: str):
    if not Path(dst).exists():
        with open(dst, "w") as default_node:
            default_node.write(Path(src).read_text())


def ensure_directory_structure(settings):
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


def ensure_initial_structure(settings):
    ensure_basic_structure()
    ensure_directory_structure(settings)


def first_run():
    data = settings.as_dict(env="plbmng")
    data.pop("FIRST_RUN")
    logger.info("Program is being run for the first time. Removing the first run setting from settings.")
    _write_settings(data)


validators = [
    # Ensure some parameters exists (are required)
    # Validator(
    #     "plbmng.username",
    #     must_exist=True,
    # )
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