import os
import os.path
import re
from os import PathLike
from pathlib import Path

from flashlogger import log_command, error
from fundamentals import squeeze_chars, is_empty_string, assert_tools_installed

from pyprocess.file_system_object import mkdir, valid_absolute_path, PathType
from pyprocess.processes import run_command


def generate_incremental_filename(filename: PathType, allow_system_paths: bool = False) -> Path:
    """
    Generate a filename with incremental numbers if file exists.
    :param filename: The basic path of the file, may contain spaces, which will be replaced by underscores.
    :param allow_system_paths: allow to manipulate system paths
    :return: A unique filename string with an incremental number.
    """
    filename = squeeze_chars(source=str(filename), squeeze_set="\n\t\r ", replace_with="_")
    base_filename = Path(filename).name
    extension = ""
    ext_index = base_filename.rfind(".")
    if ext_index > -1:
        extension = base_filename[ext_index:]
        base_filename = base_filename[:ext_index]
    dir_path = Path(filename).parent

    full_path = dir_path / f"{base_filename}{extension}"

    # If the file already exists, append an incremental number
    counter = 1
    while full_path.exists():
        full_path = dir_path/f"{base_filename}_{counter}{extension}"
        counter += 1

    return valid_absolute_path(full_path, allow_system_paths=allow_system_paths)


def read_file(filename: PathType, dryrun: bool = False) -> str:
    """
    Read a text file and return the contents as string.
    :param filename: filename to read.
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return: the contents of the file as string.
    """
    content = ""
    log_command(f"read_file {str(filename)}", extra_comment=f"Python command in {__file__}", dryrun=dryrun)
    if not dryrun:
        with open(filename, "r") as file:
            content = file.read()
    return content


def write_file(filename: PathType,
               content: (str | list[str]) = None,
               mode: str = "w",
               allow_system_paths: bool = False,
               dryrun: bool = False):
    """
    Write the given content to the given filename.
    :param filename: filename to read.
    :param content: string or list of strings to write.
    :param mode: one of 'a': append, 'w': write
    :param allow_system_paths: whether system paths are allowed
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return:
    """
    filename = valid_absolute_path(filename, allow_system_paths=allow_system_paths)
    log_command(f"write_file({filename}, mode='{mode}')",
                extra_comment=f"Python command in {__file__}",
                dryrun=dryrun)
    if mode not in ["a", "w"]:
        error(f"Cannot write file {filename}. Unknown mode '{mode}'. Choose from 'a' and 'W'")
    if not dryrun:
        mkdir(os.path.dirname(filename))
        if is_empty_string(content):
            content = ""
        if isinstance(content, str):
            content = [content]
        if len(content) > 0:
            last = content[len(content) - 1]
            # add line feeds to lines 0 .. len(contents) - 2
            content = [l + "\n" for l in content[:len(content) - 1]]
            # no line-feed at the last line
            content.append(last)
        with open(filename, mode) as file:
            file.writelines(content)


def extract_dict_from_string(content: (str | list[str])):
    key_val_dict = dict()
    lines = content.split("\n")
    for line in lines:
        key_val = squeeze_chars(source=(line.split("#")[0]), squeeze_set="\t ").split("=")
        key = (key_val[0]).strip()
        if not is_empty_string(key):
            if len(key_val) == 1:
                val = ""
            else:
                val = key_val[1].strip()
            key_val_dict[key] = val
    return key_val_dict


def parse_env_file(filename: PathType, dryrun: bool = False) -> dict[str, str]:
    """
    Simple *.env file parser.
    Ignores:
        – comments (Everything after '#')
        – empty or whitespace-only lines, ignoring comments
    Creates dictionary of key/value pairs given as
    MY_KEY1  = My value 1
    MY_KEY_2 = 234
    :param filename: path to the .env file
    :param dryrun: if set to True, then do not execute but just output a comment describing the command.
    :return: dictionary of key/value pairs.
    """
    content = read_file(filename=filename, dryrun=dryrun)
    key_val_dict = dict()
    if not dryrun:
        key_val_dict = extract_dict_from_string(content)
    return key_val_dict


def get_git_config(path: PathType = None,
                   allow_system_paths: bool = False,
                   dryrun: bool = False) -> dict[str, str]:
    key_val_dict = dict()
    if path is None:
        path = valid_absolute_path(".", allow_system_paths=allow_system_paths)
    assert_tools_installed("git")
    reval, s_out, s_err = run_command(cmd="git config --list", cwd=path, raise_errors=False, dryrun=dryrun)
    if reval != 0:
        error(f"Could not retrieve git-config in path '{path}': {s_err}")
    if not dryrun:
        key_val_dict = extract_dict_from_string(s_out)

    return key_val_dict
