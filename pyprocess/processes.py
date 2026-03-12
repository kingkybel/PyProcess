import os
import pty
import re
import select
import subprocess
import sys
import termios
import tty
from shutil import which

from flashlogger import log_progress_output, LogLevel, error
from fundamentals import squeeze_chars, ReturningThread
from fundamentals.basic_functions import is_empty_string

from pyprocess.file_system_object import pushdir, current_dir, popdir, PathType


def ping(host_name: str = None) -> tuple[int, str]:
    if is_empty_string(host_name):
        host_name = "127.0.0.1"
    ip = f"- {host_name} doesn't respond -"
    reval, s_out, s_err = run_command(f"ping -c 1 {host_name}", raise_errors=False)
    if reval == 0:
        ip_list = re.findall(rf"PING {host_name}\s+\(([0-9.]+)\)", s_out)
        ip = ip_list[0]
    return reval, ip


def is_tool_installed(name: str) -> bool:
    return which(name) is not None


def assert_tools_installed(tools: (str | list[str])):
    if isinstance(tools, str):
        tools = [tools]
    missing_tools = list()
    for tool in tools:
        if not is_tool_installed(tool):
            missing_tools.append(tool)
    if len(missing_tools) > 0:
        error(f"Please install the following tools {missing_tools} "
              "to run this script (or add location to PATH variable)")


def check_correct_tool_version(tool: str, version: str) -> bool:
    if not is_tool_installed(tool):
        return False
    return True


def pipe_monitor_thread_function(pipe, verbosity: LogLevel):
    """
    Function that runs as thread and is monitoring the output of a pipe.
    :param pipe: file-pipe: either stdin or stdout.
    :param verbosity: log-level so out put can be customised.
    :return: the string that was piped to the pipe.
    """
    piped_str = ""
    pipe_empty = 0
    for line in pipe:
        piped_str += line
        if is_empty_string(line.strip()):
            pipe_empty += 1
            if pipe_empty >= 10:
                break
        else:
            pipe_empty = 0
        log_progress_output(line.strip(), verbosity=verbosity)
    return piped_str


def run_command(cmd: str | list[str],
                cwd: PathType = None,
                raise_errors: bool = True,
                comment: str = None,
                as_sudo: bool = False,
                dryrun: bool = False) -> tuple[int, str, str]:
    """
    Run a command in a sub-process.
    :param cmd: command to execute.
    :param cwd: the working directory to use.
    :param raise_errors: if set to True (default) then raise errors instead of returning an error code.
    :param comment: a comment to enhance the log-output.
    :param as_sudo: run with elevated permissions.
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return: only if raise_errors == False: tuple (error-code, stout-string, stderr-string)
    """
    if isinstance(cmd, str):
        cmd = squeeze_chars(source=cmd, squeeze_set="\t\n\r ", replace_with=" ")
        cmd = cmd.split()

    # Add sudo prefix if requested
    if as_sudo:
        if isinstance(cmd, list):
            cmd = ["sudo"] + cmd
        else:
            cmd = f"sudo {cmd}"

    cmd_copy = []
    for c in cmd:
        if c.find(" ") != -1:
            cmd_copy.append(f"\"{c}\"")
        else:
            cmd_copy.append(c)
    cmd_str = " ".join(cmd_copy)

    if is_empty_string(cwd):
        cwd = current_dir()

    pushdir(cwd, dryrun=dryrun)
    # log_progress_output(message=cmd_str, extra_comment=comment, verbosity=LogLevel.COMMAND, dryrun=dryrun)
    log_progress_output(message=cmd_str, extra_comment=comment, verbosity=LogLevel.COMMAND)

    return_code = 0
    if dryrun:
        popdir(dryrun=dryrun)
        return 0, "", ""
    else:
        process = subprocess.Popen(cmd,
                                   cwd=cwd,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   bufsize=1,
                                   universal_newlines=True)
        log_progress_output("-" * 10 + "sub-process output" + "-" * 10, verbosity=LogLevel.COMMAND_OUTPUT)

        out_thread = ReturningThread(target=pipe_monitor_thread_function,
                                     args=(process.stdout, LogLevel.COMMAND_OUTPUT))
        err_thread = ReturningThread(target=pipe_monitor_thread_function,
                                     args=(process.stderr, LogLevel.WARNING))
        out_thread.start()
        err_thread.start()
        # let the process do its job
        # ...
        # then join the threads and read the output.
        std_out_str = str(out_thread.join())
        std_err_str = str(err_thread.join())
        try:
            if process.stdout:
                process.stdout.close()
        except (AttributeError, TypeError):
            pass

        try:
            if process.stderr:
                process.stderr.close()
        except (AttributeError, TypeError):
            pass

        return_code = process.wait()
        popdir(dryrun=dryrun)
        log_progress_output("-" * 40, LogLevel.COMMAND_OUTPUT)

        if return_code != 0:
            if raise_errors:
                error(f"run_command(cmd='{cmd_str}' failed with error-code '{return_code}':\n{std_err_str}")

        return return_code, std_out_str, std_err_str


def run_interactive_command(cmd: str | list,
                            cwd: PathType = None,
                            comment: str = "",
                            as_sudo: bool = False,
                            dryrun: bool = False):
    """
    Run an interactive command in a sub-process.
    :param cmd: command to execute.
    :param cwd: the working directory to use.
    :param comment: a comment to enhance the log-output.
    :param as_sudo: run with elevated permissions.
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return: None.
    """
    if isinstance(cmd, str):
        cmd = squeeze_chars(source=cmd, squeeze_set="\t\n\r ", replace_with=" ")
        cmd = cmd.split()

    # Add sudo prefix if requested
    if as_sudo:
        if isinstance(cmd, list):
            cmd = ["sudo"] + cmd
        else:
            cmd = f"sudo {cmd}"

    cmd_copy = []
    for c in cmd:
        if c.find(" ") != -1:
            cmd_copy.append(f"\"{c}\"")
        else:
            cmd_copy.append(c)
    cmd_str = " ".join(cmd_copy)

    if cwd is None or is_empty_string(cwd):
        cwd = current_dir()

    pushdir(cwd, dryrun=dryrun)
    log_progress_output(message=cmd_str, extra_comment=comment, verbosity=LogLevel.COMMAND)

    if not dryrun:
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        master_fd, slave_fd = pty.openpty()

        try:
            process = subprocess.Popen(cmd,
                                       # cwd=cwd,
                                       preexec_fn=os.setsid,
                                       stdin=slave_fd,
                                       stdout=slave_fd,
                                       stderr=slave_fd,
                                       universal_newlines=True)
            while process.poll() is None:
                r, w, e = select.select([sys.stdin, master_fd], [], [])
                if sys.stdin in r:
                    d = os.read(sys.stdin.fileno(), 10240)
                    os.write(master_fd, d)
                elif master_fd in r:
                    o = os.read(master_fd, 10240)
                    if o:
                        os.write(sys.stdout.fileno(), o)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

    popdir(dryrun=dryrun)


def ssh_run(host: str,
            cmd: str | list[str],
            cwd: PathType = None,
            raise_errors: bool = True,
            comment: str = None,
            timeout_in_secs: int = 60,
            as_sudo: bool = False,
            dryrun: bool = False) -> tuple[int, str, str]:
    """
    Run an SSH command in a sub-process.
    :param host:
    :param cmd: command to execute.
    :param cwd: the working directory to use.
    :param raise_errors: if set to True (default) then raise errors instead of returning an error code.
    :param comment: a comment to enhance the log-output.
    :param timeout_in_secs: timeout after this many seconds.
    :param as_sudo: run with elevated permissions.
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return: only if raise_errors == False: tuple (error-code, stout-string, stderr-string)
    """

    if isinstance(cmd, str):
        cmd = squeeze_chars(cmd, squeeze_set="\n \t", replace_with=' ')
        cmd = cmd.split()
    ssh_cmd = ["ssh", "-q", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
               "-o", f"ConnectTimeout={timeout_in_secs}", host] + cmd
    return run_command(cmd=ssh_cmd, cwd=cwd, raise_errors=raise_errors, comment=comment, as_sudo=as_sudo, dryrun=dryrun)


def rsync(source: PathType,
          dest: PathType,
          options: str | list[str] = None,
          cwd: PathType = None,
          raise_errors: bool = True,
          comment: str = None,
          as_sudo: bool = False,
          dryrun: bool = False) -> tuple[int, str, str]:
    """
    Run rsync command.

    :param source: Source path
    :param dest: Destination path
    :param options: List of rsync options (default: ["-av"])
    :param cwd: the working directory to use.
    :param raise_errors: if set to True (default) then raise errors instead of returning an error code.
    :param comment: a comment to enhance the log-output.
    :param as_sudo: run with elevated permissions.
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return: only if raise_errors == False: tuple (error-code, stout-string, stderr-string)
    """
    if options is None:
        options = ["-av"]
    cmd = ["rsync"] + options + [str(source), str(dest)]
    return run_command(cmd=cmd, cwd=cwd, raise_errors=raise_errors, comment=comment, as_sudo=as_sudo, dryrun=dryrun)


def mkdir_remote(host: str,
                 path: PathType,
                 parents: bool = True,
                 cwd: PathType = None,
                 raise_errors: bool = True,
                 comment: str = None,
                 as_sudo: bool = False,
                 dryrun: bool = False) -> tuple[int, str, str]:
    """
    Create directory on remote host.

    :param host: Remote host
    :param path: Directory path
    :param parents: Whether to create parents
    :param cwd: the working directory to use.
    :param raise_errors: if set to True (default) then raise errors instead of returning an error code.
    :param comment: a comment to enhance the log-output.
    :param as_sudo: run with elevated permissions.
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return: only if raise_errors == False: tuple (error-code, stout-string, stderr-string)
    """
    cmd = ["mkdir"]
    if parents:
        cmd.append("-p")
    cmd.append(str(path))
    return ssh_run(host, cmd, raise_errors=raise_errors, comment=comment, as_sudo=as_sudo, dryrun=dryrun)
