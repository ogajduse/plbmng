import logging
import re
import time
from contextlib import contextmanager
from typing import Union

import paramiko

from plbmng.utils.config import settings

logger = logging.getLogger(__name__)

CONNECTION_TIMEOUT = settings.remote_execution.connection_timeout
COMMAND_TIMEOUT = settings.remote_execution.command_timeout
SSH_USERNAME = settings.planetlab.slice
SSH_KEY = settings.remote_execution.ssh_key

# TODO impmlement https://pypi.org/project/parallel-ssh/ into this library


class SSHCommandTimeoutError(Exception):
    """Raised when the SSH command has not finished executing after a predefined period of time."""


def decode_to_utf8(text) -> bytes:  # pragma: no cover
    """
    Paramiko returns bytes object and we need to ensure it is utf-8 before parsing.

    :param text: non-decoded bytes
    :return: decoded text
    """
    try:
        return text.decode("utf-8")
    except (AttributeError, UnicodeEncodeError):
        return text


class SSHCommandResult:
    """Structure that returns in all ssh commands results."""

    def __init__(self, stdout=None, stderr=None, return_code=0) -> None:
        """
        Construct object of SSHCommandResult class.

        :param stdout: command stdout, defaults to None
        :type stdout: list, optional
        :param stderr: command stderr, defaults to None
        :type stderr: str, optional
        :param return_code: command return code, defaults to 0
        :type return_code: int, optional
        """
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code

    def __repr__(self):
        tmpl = "SSHCommandResult(stdout={stdout!r}, stderr={stderr!r}, " + "return_code={return_code!r})"
        return tmpl.format(**self.__dict__)


class SSHClient(paramiko.SSHClient):
    """Representation of SSH client."""

    def run(self, cmd, *args, **kwargs) -> SSHCommandResult:
        """
        Run SSH client.

        .. # noqa: DAR101
        .. # noqa: DAR201

        This method exists to allow the reuse of existing connections when
        running multiple ssh commands as in the following example of use::

            with plbmng.ssh.get_connection() as connection:
                connection.run('ls /tmp')
                connection.run('another command')
                ...

        `self` is always passed as the connection when used in context manager
        only when using `ssh.get_connection` function.
        Note: This method is named `run` to avoid conflicts with existing
        `exec_command` and local function `execute_command`.
        """
        return execute_command(cmd, self, *args, **kwargs)


def _call_paramiko_sshclient() -> SSHClient:  # pragma: no cover
    """
    Call ``:py:class:`paramiko.client.SSHClient```.

    .. # noqa: DAR201
    """
    return SSHClient()


def get_client(hostname=None, username=None, key_filename=None, timeout=None, port=22) -> SSHClient:
    """
    Return a SSH client connected to given hostname.

    :param hostname: The hostname of the server to establish connection. If
        it is :py:obj:`None` ``hostname`` from configuration's ``server`` section
        will be used.
    :type hostname: str
    :param username: The username to use when connecting. If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    :type username: str
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :type key_filename: str
    :param timeout: Time to wait for establish the connection.
    :type timeout: int
    :param port: The server port to connect to, the default port is 22.
    :type port: int
    :raises ValueError: if ``hostname`` argument is missing
    :return: An SSH connection.
    """
    if hostname is None:
        raise ValueError("Can not start SSH client. The 'hostname' argument is missing.")
    if username is None:
        username = SSH_USERNAME
    if key_filename is None:
        key_filename = SSH_KEY
    if timeout is None:
        timeout = CONNECTION_TIMEOUT
    client = _call_paramiko_sshclient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=hostname, username=username, key_filename=key_filename, timeout=timeout, port=port)
    client._id = hex(id(client))
    return client


@contextmanager
def get_connection(hostname=None, username=None, key_filename=None, timeout=None, port=22):
    """
    Yield an ssh connection object.

    The connection will be configured with the specified arguments or will
    fall-back to server configuration in the configuration file.
    Yield this SSH connection. The connection is automatically closed when the
    caller is done using it using :py:obj:`contextlib <contextlib>`, so clients should use the
    ``with`` statement to handle the object::

        with get_connection() as connection:
            ...

    :param hostname: The hostname of the server to establish connection. If
        it is :py:obj:`None` ``hostname`` from configuration's ``server`` section
        will be used.
    :type hostname: str
    :param username: The username to use when connecting. If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    :type username: str
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :type key_filename: str
    :param timeout: Time to wait for establish the connection.
    :type timeout: int
    :param port: The server port to connect to, the default port is 22.
    :type port: int
    :yield: :py:class:`paramiko.client.SSHClient`
    """
    if timeout is None:
        timeout = CONNECTION_TIMEOUT
    client = get_client(hostname, username, key_filename, timeout, port)
    try:
        logger.debug(f"Instantiated Paramiko client {client._id}")
        logger.info("Connected to [%s]", hostname)
        yield client
    finally:
        client.close()
        logger.debug(f"Destroyed Paramiko client {client._id}")


@contextmanager
def get_sftp_session(hostname=None, username=None, key_filename=None, timeout=None):
    """
    Yield a SFTP session object.

    The session will be configured with the host whose hostname is
    passed as argument.
    Yield this SFTP Session. The session is automatically closed when
    the caller is done using it using :py:obj:`contextlib <contextlib>`, so clients should use
    the ``with`` statement to handle the object::

        with get_sftp_session() as session:
            ...

    :param hostname: The hostname of the server to establish connection. If
        it is :py:obj:`None` ``hostname`` from configuration's ``server`` section
        will be used.
    :type hostname: str
    :param username: The username to use when connecting.If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    :type username: str
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :type key_filename: str
    :param timeout: Time to wait for establish the connection.
    :type timeout: int
    :yield: SFTP session
    """
    with get_connection(hostname=hostname, username=username, key_filename=key_filename, timeout=timeout) as connection:
        try:
            sftp = connection.open_sftp()
            yield sftp
        finally:
            sftp.close()


@contextmanager
def get_transport(hostname=None, username=None, key_filename=None, timeout=None, port=22):
    """
    Create connection and return the transport object for this SSH connection.

    This can be used to perform lower-level tasks, like opening specific
    kinds of channels.

    :param hostname: The hostname of the server to establish connection. If
        it is :py:obj:`None` ``hostname`` from configuration's ``server`` section
        will be used.
    :type hostname: str
    :param username: The username to use when connecting. If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    :type username: str
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :type key_filename: str
    :param timeout: Time to wait for establish the connection.
    :type timeout: int
    :param port: The server port to connect to, the default port is 22.
    :type port: int
    :yield: :py:class:`paramiko.transport.Transport` object
    """
    client = get_client(hostname, username, key_filename, timeout, port)
    transport = client.get_transport()
    try:
        logger.debug(f"Instantiated Paramiko client {client._id}")
        logger.debug(f"Instantiated Paramiko transport {transport.native_id}")
        logger.info("Connected to [%s]", hostname)
        yield transport
    finally:
        transport.close()
        logger.debug(f"Destroyed Paramiko transport {transport.native_id}")
        client.close()
        logger.debug(f"Destroyed Paramiko client {client._id}")


@contextmanager
def get_channel(hostname=None, username=None, key_filename=None, timeout=None, port=22):
    """
    Yield a SSH channel.

    :param hostname: The hostname of the server to establish connection. If
        it is :py:obj:`None` ``hostname`` from configuration's ``server`` section
        will be used.
    :type hostname: str
    :param username: The username to use when connecting.If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    :type username: str
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :type key_filename: str
    :param timeout: Time to wait for establish the connection.
    :type timeout: int
    :param port: The server port to connect to, the default port is 22.
    :type port: int
    :yield: :py:class:`paramiko.channel.Channel` object
    """
    with get_transport(hostname, username, key_filename, timeout, port) as transport:
        try:
            channel = transport.open_session()
            yield channel
        finally:
            channel.close()


def upload_file(local_file, remote_file, key_filename=None, hostname=None, username=None) -> None:
    """
    Upload a local file to a remote machine.

    :param local_file: either a file path or a file-like object to be uploaded.
    :param remote_file: a remote file path where the uploaded file will be
        placed.
    :param hostname: target machine hostname. If not provided will be used the
        ``server.hostname`` from the configuration.
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :param username: The username to use when connecting. If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    """
    with get_sftp_session(hostname=hostname, username=username, key_filename=key_filename) as sftp:
        _upload_file(sftp, local_file, remote_file)


def _upload_file(sftp, local_file, remote_file) -> None:
    """
    Upload a file using existent sftp session.

    :param sftp: sftp session object
    :param local_file: either a file path or a file-like object to be uploaded.
    :param remote_file: a remote file path where the uploaded file will be
        placed.
    """
    # Check if local_file is a file-like object and use the proper
    # paramiko function to upload it to the remote machine.
    if hasattr(local_file, "read"):
        sftp.putfo(local_file, remote_file)
    else:
        sftp.put(local_file, remote_file)


def download_file(remote_file, local_file=None, key_filename=None, hostname=None, username=None) -> None:
    """
    Download a remote file to the local machine.

    :param remote_file: path to the file on the remote host
    :type remote_file: str
    :param local_file: path to the local file where the remote file should be copied to, defaults to None
    :type local_file: str
    :param hostname: target machine hostname. If not provided will be used the
        ``server.hostname`` from the configuration.
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :param username: The username to use when connecting. If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    """
    if local_file is None:  # pragma: no cover
        local_file = remote_file
    with get_connection(
        hostname=hostname, username=username, key_filename=key_filename
    ) as connection:  # pragma: no cover
        try:
            sftp = connection.open_sftp()
            sftp.get(remote_file, local_file)
        finally:
            sftp.close()


def command(
    cmd,
    hostname=None,
    username=None,
    key_filename=None,
    timeout=None,
    connection_timeout=None,
    port=22,
    background=False,
) -> Union[None, SSHCommandResult]:
    """
    Execute SSH command(s) on remote hostname.

    .. # noqa: D402

    :param cmd: The command to run
    :type cmd: str
    :param hostname: The hostname of the server to establish connection.If
        it is :py:obj:`None` ``hostname`` from configuration's ``server`` section
        will be used.
    :type hostname: str
    :param username: The username to use when connecting. If it is :py:obj:`None`
        ``ssh_username`` from configuration's ``server`` section will be used.
    :type username: str
    :param key_filename: The path of the ssh private key to use when
        connecting to the server. If it is :py:obj:`None` ``key_filename`` from
        configuration's ``server`` section will be used.
    :type key_filename: str
    :param timeout: Time to wait for the ssh command to finish.
    :type timeout: int
    :param connection_timeout: Time to wait for establishing the connection.
    :type connection_timeout: int
    :param port: The server port to connect to, the default port is 22.
    :type port: int
    :param background: Specifies whether the command should run in background.
        If the command is running in the background, no result will be returned.
    :type background: bool
    :raises ValueError: if ``hostname`` argument is missing
    :return: :py:class:`SSHCommandResult` | :py:obj:`None` if ``background`` is :py:obj:`True`
    """
    if hostname is None:
        raise ValueError("Can not start SSH client. The 'hostname' argument is missing.")
    if timeout is None:
        timeout = COMMAND_TIMEOUT
    if connection_timeout is None:
        connection_timeout = CONNECTION_TIMEOUT
    if background:
        with get_channel(
            hostname=hostname, username=username, key_filename=key_filename, timeout=timeout, port=port
        ) as channel:
            channel.exec_command(cmd)
    else:
        with get_connection(
            hostname=hostname, username=username, key_filename=key_filename, timeout=connection_timeout, port=port
        ) as connection:
            return execute_command(cmd, connection, timeout, connection_timeout)


def execute_command(cmd, connection, timeout=None, connection_timeout=None) -> SSHCommandResult:
    """Execute a command via ssh in the given connection.

    :param cmd: a command to be executed via ssh
    :param connection: SSH Paramiko client connection
    :param timeout: Time to wait for the ssh command to finish.
    :param connection_timeout: Time to wait for establishing the connection.
    :raises SSHCommandTimeoutError: if the command does not respond in time
    :return: :py:class:`SSHCommandResult`
    """
    if timeout is None:
        timeout = COMMAND_TIMEOUT
    if connection_timeout is None:
        connection_timeout = CONNECTION_TIMEOUT
    logger.info(">>> %s", cmd)
    _, stdout, stderr = connection.exec_command(cmd, timeout=connection_timeout)
    if timeout:
        # wait for the exit status ready
        end_time = time.time() + timeout
        while time.time() < end_time:
            if stdout.channel.exit_status_ready():
                break
            time.sleep(1)
        else:
            logger.error(
                "ssh command did not respond in the predefined time" " (timeout=%s) and will be interrupted", timeout
            )
            stdout.channel.close()
            stderr.channel.close()
            logger.error(f"[Captured stdout]\n{stdout.read()}\n-----\n")
            logger.error(f"[Captured stderr]\n{stderr.read()}\n-----\n")
            raise SSHCommandTimeoutError(
                f"ssh command: {cmd} \n did not respond in the predefined time (timeout={timeout})"
            )

    errorcode = stdout.channel.recv_exit_status()

    stdout = stdout.read()
    stderr = stderr.read()
    # Remove escape code for colors displayed in the output
    regex = re.compile(r"\x1b\[\d\d?m")
    if stdout:
        # Convert to unicode string
        stdout = decode_to_utf8(stdout)
        logger.info("<<< stdout\n%s", stdout)
    if stderr:
        # Convert to unicode string and remove all color codes characters
        stderr = regex.sub("", decode_to_utf8(stderr))
        logger.info("<<< stderr\n%s", stderr)
    if stdout:
        # Mostly only for hammer commands
        # for output we don't really want to see all of Rails traffic
        # information, so strip it out.
        # Empty fields are returned as "" which gives us '""'
        stdout = stdout.replace('""', "")
        stdout = "".join(stdout).split("\n")
        stdout = [regex.sub("", line) for line in stdout if not line.startswith("[")]
    return SSHCommandResult(stdout, stderr, errorcode)
