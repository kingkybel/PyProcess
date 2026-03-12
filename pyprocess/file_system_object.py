import glob
import grp
import os
import pwd
import re
import shutil
import psutil

from collections.abc import Iterable
from datetime import datetime
from enum import auto
from os import PathLike
from pathlib import Path
from typing import TypeAlias
import fnmatch

from flashlogger import log_warning, log_command, error
from fundamentals import ExtendedEnum, ExtendedFlag, is_empty_string, matches_any, always_match, overrides

# Type aliases for path handling
PathType: TypeAlias = str | PathLike | Path
PathIterable: TypeAlias = PathType | Iterable[PathType]

LINUX_PROTECTED_DIR_PATTERNS = ["^/$", "^/bin", "^/boot", "^/dev", "^/lib",
                                "^/media", "^/proc", "^/root", "^/run",
                                "^/sbin", "^/sys", "^/usr"]


def valid_absolute_path(path: PathType,
                        protect_system_patterns: (str | list[str]) = None,
                        allow_system_paths: bool = False) -> Path:
    """
    Create an absolute path from the given path.
    :param path: the original path.
    :param protect_system_patterns: a list of patterns to prevent the returned path to be a protected system-path.
                                    By default, the Unix/Linux system paths are protected.
    :param allow_system_paths: if set to True then system paths are allowed, default False
    :return: the absolute path as string.
    """
    if protect_system_patterns is None:
        protect_system_patterns = LINUX_PROTECTED_DIR_PATTERNS
    if is_empty_string(path):
        path = Path(".")
    if not isinstance(path, Path):
        path = Path(path)

    path = path.absolute()
    if isinstance(protect_system_patterns, str):
        protect_system_patterns = [protect_system_patterns]
    if not allow_system_paths:
        for protected in protect_system_patterns:
            if bool(re.match(pattern=protected, string=str(path))):
                raise SystemError(f"Path '{path}' is a protected path. Change protect_system_patterns - parameter")
    if str(path).find("/") and \
            not str(path).startswith("/") and \
            not str(path).startswith("."):
        path = f"./{path}"
    return Path(path).absolute()


class FindSortField(ExtendedEnum):
    """
    An enumeration of fields by which the results of a 'find' command can be sorted.
    """
    NONE = 0
    BY_NAME = 1
    BY_TYPE = 2
    BY_DEPTH = 3


class FileSystemObjectType(ExtendedFlag):
    """
    An enumeration of file system object types.
    """
    NONE = 0
    FILE = auto()
    EMPTY_DIR = auto()
    NOT_EMPTY_DIR = auto()
    DIR = EMPTY_DIR | NOT_EMPTY_DIR
    STALE_LINK = auto()
    NOT_STALE_LINK = auto()
    LINK = STALE_LINK | NOT_STALE_LINK
    MOUNT = auto()
    ALL = FILE | DIR | LINK | MOUNT

    def is_a(self, types: str | FileSystemObjectType | Iterable[str | FileSystemObjectType]) -> bool:
        if isinstance(types, (str, FileSystemObjectType)):
            types = [types]
        
        for tp in types:
            target_type = FileSystemObjectType.from_string(tp)
            # Check if self is a subset of target_type (hierarchical relationship)
            # For example: EMPTY_DIR is_a DIR should return True because DIR = EMPTY_DIR | NOT_EMPTY_DIR
            if (self & target_type) == self and self != FileSystemObjectType.NONE:
                return True
        return False

    @classmethod
    def from_file_system_object(cls, file_system_object: PathType):
        """
        guess the file system object type from a given path
        :param file_system_object: path to the file system object
        :return: the corresponding 'FileSystemObjectType'
        """
        if is_empty_string(file_system_object):
            return FileSystemObjectType.NONE
        file_system_object = Path(file_system_object)

        if file_system_object.exists():
            if file_system_object.is_file() and not file_system_object.is_symlink():
                return FileSystemObjectType.FILE
            if file_system_object.is_dir():
                if len((os.listdir(file_system_object))) == 0:
                    return FileSystemObjectType.EMPTY_DIR
                else:
                    return FileSystemObjectType.NOT_EMPTY_DIR
            if file_system_object.is_symlink():
                return FileSystemObjectType.NOT_STALE_LINK
            if file_system_object.is_mount():
                return FileSystemObjectType.MOUNT
        else:
            if file_system_object.is_symlink():
                return FileSystemObjectType.STALE_LINK
        return FileSystemObjectType.NONE

    @classmethod
    @overrides
    def from_string(cls, partial: str | FileSystemObjectType, predicate=always_match):
        """
        Create a 'FileSystemObjectType' from a single character string.
        'f' -> FILE
        'd' -> DIRECTORY
        'l' -> LINK
        :param partial: the single character string
        :param predicate: a method to determine the match.
        :return: the corresponding 'FileSystemObjectType'
        """
        if isinstance(partial, FileSystemObjectType):
            return partial
        sorted_partial = "".join(sorted(partial, key=lambda x: x.lower()))
        if sorted_partial == "f":
            return FileSystemObjectType.FILE
        if sorted_partial == "d":
            return FileSystemObjectType.DIR
        if sorted_partial == "df":
            return FileSystemObjectType.FILE | FileSystemObjectType.DIR
        if sorted_partial == "fl":
            return FileSystemObjectType.FILE | FileSystemObjectType.LINK
        if sorted_partial == "dl":
            return FileSystemObjectType.DIR | FileSystemObjectType.LINK
        if sorted_partial == "dfl":
            return FileSystemObjectType.DIR | FileSystemObjectType.FILE | FileSystemObjectType.LINK
        return super().from_string(partial=partial, predicate=predicate)


class GlobMode(ExtendedEnum):
    """
    An enumeration of modes for handling glob patterns that do not yield results.
    """
    IGNORE_EMPTY = auto()
    FAIL_ON_EMPTY = auto()
    KEEP_EMPTY = auto()
    WARN_EMPTY = auto()


def make_path_str_list(paths: PathIterable) -> list[str]:
    """
    Create a list of path-strings from a given input.
    :param paths: one or more path-type
    :return: a str list of paths
    """
    if isinstance(paths, PathType):
        paths = str(paths)
    if isinstance(paths, str):
        paths = [paths]
    if len(paths) == 0:
        error("path-list is empty")
    reval_paths = []
    for path in paths:
        if not isinstance(path, (str, PathLike, Path)):
            error(f"paths contains path with invalid type '{path}'({type(path)})")
        if is_empty_string(path):
            error(f"paths contains empty path-strings {paths}")
        else:
            reval_paths.append(str(path))
    return reval_paths


def glob_path_patterns(paths: PathIterable, glob_mode: GlobMode = GlobMode.FAIL_ON_EMPTY) -> list[Path]:
    """
    Glob a list of paths and return the results.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param glob_mode: the mode to use for globbing
    :return: a list of globbed paths
    """
    results = []
    paths = make_path_str_list(paths)

    for path in paths:
        globbed_paths = glob.glob(path)
        if len(globbed_paths) > 0:
            results.extend([Path(p) for p in globbed_paths])
        elif glob_mode == GlobMode.KEEP_EMPTY:
            results.append(Path(path))
        elif glob_mode == GlobMode.FAIL_ON_EMPTY:
            raise (FileNotFoundError(f"Globbing of path '{path}' did not yield results"))
        elif glob_mode == GlobMode.WARN_EMPTY:
            log_warning(f"Globbing of path '{path}' did not yield results")
        else:  # GobMode.IGNORE_EMPTY
            pass
    return results


def remove(paths: PathIterable,
           force: bool = False,
           allow_system_paths: bool = False,
           dryrun: bool = False):
    """
    Remove files or directories.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param force: if set to True, then do not raise errors on failing operations
    :param allow_system_paths: if set to True then system paths are allowed, default False
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    glob_mode = GlobMode.WARN_EMPTY
    if force:
        glob_mode = GlobMode.KEEP_EMPTY
    paths = glob_path_patterns(paths, glob_mode=glob_mode)
    log_command(f"rm -rf {paths}", dryrun=dryrun)
    if not dryrun:
        for path in paths:
            path = valid_absolute_path(path, allow_system_paths=allow_system_paths)
            try:
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=force)
                elif path.is_symlink():
                    os.unlink(path)
                else:
                    os.remove(path)
            except FileNotFoundError:
                pass


def set_file_last_modified(paths: PathIterable, dt: datetime, dryrun: bool = False) -> list:
    """
    Set the last modified time of a file or directory.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param dt: the datetime object to set the last modified time to
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    :return: a list of modified paths
    """
    paths = glob_path_patterns(paths, glob_mode=GlobMode.WARN_EMPTY)
    modified = []
    if not dryrun:
        for path in paths:
            dt_epoch = dt.timestamp()
            os.utime(path, (dt_epoch, dt_epoch))
            modified.append(path)
    return modified


def touch(paths: PathIterable,
          glob_mode: GlobMode = GlobMode.KEEP_EMPTY,
          allow_system_paths: bool = False,
          dryrun: bool = False):
    """
    Create a file or update the last modified time of a file or directory.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param glob_mode: the mode to use for globbing
    :param allow_system_paths: if set to True then system paths are allowed, default False
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    paths = glob_path_patterns(paths, glob_mode=glob_mode)
    if not dryrun:
        touched = []
        for path in paths:
            path = valid_absolute_path(path, allow_system_paths=allow_system_paths)
            parent_path = os.path.dirname(path)
            log_command(f"touch {path}")
            if not os.path.isdir(parent_path):
                mkdir(parent_path)
                touched.append(parent_path)
            if os.path.islink(path) or os.path.isdir(path):
                set_file_last_modified(path, dt=datetime.now())
            else:
                f = open(path, "a")
                f.close()
            touched.append(path)
    else:
        return 0, []
    if len(touched) == 0:
        return -1, None
    return 0, touched


def mkdir(paths: PathIterable,
          force: bool = False,
          recreate: bool = False,
          expect_1: bool = False,
          allow_system_paths: bool = False,
          dryrun: bool = False):
    """
    Create a directory.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param force: if set to True, then do not raise errors on failing operations
    :param recreate: if set to True, then remove the directory if it exists
    :param expect_1: if set to True, then expect exactly one directory to be created
    :param allow_system_paths: if set to True then system paths are allowed, default False
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    :return: a list of created paths or a single path if expect_1 is set to True
    """
    paths = glob_path_patterns(paths, glob_mode=GlobMode.KEEP_EMPTY)
    log_command(f"mkdir {paths}", dryrun=dryrun)
    created_paths = []
    if not dryrun:
        for path in paths:
            path = valid_absolute_path(path, allow_system_paths=allow_system_paths)
            if os.path.isfile(path) and not recreate:
                raise FileExistsError(f"Cannot create directory {path}. Path is regular file")
            try:
                if recreate:
                    remove(paths=path, force=force)
                os.makedirs(path, exist_ok=force)
                created_paths.append(path)
            except FileExistsError:
                created_paths.append(path)
                pass
    if len(created_paths) == 1 and expect_1:
        return created_paths[0]
    elif expect_1:
        error(f"Expected to create exactly one directory but created {len(created_paths)} {created_paths}")
    return created_paths


def symbolic_link(existing_path: PathType,
                  new_link: PathType,
                  overwrite_link: bool = False,
                  allow_system_paths: bool = False,
                  dryrun: bool = False):
    """
    Create a symbolic link.
    :param existing_path: the path to the existing file or directory
    :param new_link: the path to the new link
    :param overwrite_link: if set to True, then overwrite the link if it exists
    :param allow_system_paths: if set to True then system paths are allowed, default False
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    if isinstance(existing_path, PathLike):
        existing_path = str(existing_path)
    if isinstance(new_link, PathLike):
        new_link = str(new_link)
    if os.path.isdir(new_link):
        new_link = f"{new_link}/{os.path.basename(existing_path)}"
    if not dryrun:
        if is_empty_string(existing_path):
            error(f"Cannot link empty path to {new_link}")
        force = ""
        if overwrite_link and (os.path.exists(new_link) or os.path.islink(new_link)):
            remove(new_link, allow_system_paths=allow_system_paths, force=True)
            force = "-f "
        log_command(f"ln {force}-s {existing_path} {new_link}")
        symlink = Path(new_link)
        symlink.symlink_to(existing_path)


def current_dir() -> Path:
    """
    Get the current working directory.
    :return: the current working directory
    """
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = psutil.Process(os.getpid()).cwd()
    return valid_absolute_path(cwd, protect_system_patterns=[])


push_stack: list[Path] = []


def pushdir(path: PathType, dryrun: bool = False):
    """
    Change the current working directory and push the old directory onto a stack.
    :param path: the path to change to
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    global push_stack
    push_stack.append(current_dir())
    log_command(f"pushd {path}", dryrun=dryrun)
    if not dryrun:
        os.chdir(path)


def popdir(dryrun: bool = False):
    """
    Change the current working directory to the last directory pushed onto the stack.
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    global push_stack
    current = current_dir()
    if len(push_stack) > 0:
        current = push_stack.pop()
        while not current.is_dir() and push_stack:
            current = push_stack.pop()
        os.chdir(current)
        log_command("popd", extra_comment=f"leaving {current}", dryrun=dryrun)
    else:
        log_command(";", extra_comment=f"popd stack empty. Staying in {current}")


def _glob_to_regex(glob_pattern: str) -> str:
    """
    Convert a glob pattern to a regex pattern.
    :param glob_pattern: the glob pattern to convert
    :return: the equivalent regex pattern
    """
    # Escape regex special characters except for * and ?
    regex = re.escape(glob_pattern)
    # Convert glob wildcards to regex
    regex = regex.replace(r'\*', '.*').replace(r'\?', '.')
    return regex


def find(paths: PathIterable,
         file_type_filter: (str | FileSystemObjectType) = FileSystemObjectType.ALL,
         name_patterns: (str | list) = None,
         exclude_patterns: (str | list) = None,
         sort_field: FindSortField = FindSortField.NONE,
         reverse: bool = False,
         allow_system_paths: bool = False,
         dryrun: bool = False) -> list[Path]:
    """
    Find files and directories.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param file_type_filter: a filter for the file system object type
    :param name_patterns: a list of name patterns to search for
    :param exclude_patterns: a list of name patterns to exclude
    :param sort_field: the field to sort the results by
    :param reverse: if set to True, then reverse the sort order
    :param allow_system_paths: if set to True then system paths are allowed, default False
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    :return: a list of found paths (can be empty)
    """
    paths = glob_path_patterns(paths)
    
    # Validate that all paths are directories
    non_directories = [str(path) for path in paths if not path.is_dir()]
    if non_directories:
        error(f"The following paths are not directories {non_directories}")

    # Convert file_type_filter to FileSystemObjectType
    file_type_filter = FileSystemObjectType.from_string(file_type_filter)
    
    # Prepare patterns
    if name_patterns is not None:
        if isinstance(name_patterns, str):
            name_patterns = [name_patterns]
        # Convert glob patterns to regex patterns
        name_patterns = [_glob_to_regex(pattern) for pattern in name_patterns]
    
    if exclude_patterns is not None:
        if isinstance(exclude_patterns, str):
            exclude_patterns = [exclude_patterns]
    
    # Log the command
    pattern_str = ""
    if name_patterns is not None:
        pattern_str = f' -name "{name_patterns[0]}"'
        for pattern in name_patterns[1:]:
            pattern_str += f' -o -name "{pattern}"'
    file_type_str = f" -type ({file_type_filter})"
    log_command(f"find {' '.join([str(p) for p in paths])}{file_type_str}{pattern_str}", dryrun=dryrun)

    result_paths = []
    if not dryrun:
        for path in paths:
            for dir_name, sub_dir_list, file_list in os.walk(path):
                # Check directories
                dir_path = Path(dir_name)
                dir_type = FileSystemObjectType.from_file_system_object(dir_path)
                
                if dir_type.is_a(file_type_filter):
                    # Check name patterns for directories
                    dir_matches = True
                    if name_patterns is not None:
                        dir_matches = matches_any(search_string=dir_path.name, patterns=name_patterns)
                    
                    # Check exclude patterns
                    if dir_matches and exclude_patterns is not None:
                        dir_matches = not matches_any(search_string=dir_path.name, patterns=exclude_patterns)
                    
                    if dir_matches:
                        result_paths.append(valid_absolute_path(dir_path, allow_system_paths=allow_system_paths))
                
                # Check files
                for file_name in file_list:
                    file_path = dir_path / file_name
                    file_type = FileSystemObjectType.from_file_system_object(file_path)
                    
                    if file_type.is_a(file_type_filter):
                        # Check name patterns for files
                        file_matches = True
                        if name_patterns is not None:
                            file_matches = matches_any(search_string=file_name, patterns=name_patterns)
                        
                        # Check exclude patterns
                        if file_matches and exclude_patterns is not None:
                            file_matches = not matches_any(search_string=file_name, patterns=exclude_patterns)
                        
                        if file_matches:
                            result_paths.append(valid_absolute_path(file_path, allow_system_paths=allow_system_paths))

        # Apply sorting
        if sort_field != FindSortField.NONE:
            if sort_field == FindSortField.BY_NAME:
                result_paths.sort(key=lambda p: p.name.lower(), reverse=reverse)
            elif sort_field == FindSortField.BY_TYPE:
                result_paths.sort(key=lambda p: FileSystemObjectType.from_file_system_object(p).value, reverse=reverse)
            elif sort_field == FindSortField.BY_DEPTH:
                result_paths.sort(key=lambda p: str(p).count(os.path.sep), reverse=reverse)
        elif reverse:
            result_paths.sort(reverse=reverse)

    return result_paths


def is_stale_link(path: PathType):
    """
    Check if a path is a stale link.
    :param path: the path to check
    :return: True if the path is a stale link, False otherwise
    """
    return FileSystemObjectType.from_file_system_object(path) == FileSystemObjectType.STALE_LINK


def is_empty_dir(path: PathType):
    """
    Check if a path is an empty directory.
    :param path: the path to check
    :return: True if the path is an empty directory, False otherwise
    """
    return FileSystemObjectType.from_file_system_object(path) == FileSystemObjectType.EMPTY_DIR


def remove_stale_links(paths: PathIterable, dryrun: bool = False):
    """
    Remove stale links.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    log_command(f"remove_stale_links {paths}", extra_comment="python function", dryrun=dryrun)
    if not dryrun:
        paths = glob_path_patterns(paths)
        all_stale_links = find(paths=paths,
                               file_type_filter=FileSystemObjectType.STALE_LINK,
                               sort_field=FindSortField.BY_DEPTH,
                               reverse=True)
        for stale_link in all_stale_links:
            remove(stale_link)


def remove_empty_dirs(paths: PathIterable, dryrun: bool = False):
    """
    Remove empty directories.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    log_command(f"remove_stale_links {paths}", extra_comment="python function", dryrun=dryrun)
    if not dryrun:
        paths = glob_path_patterns(paths)
        all_empty_dirs = find(paths=paths,
                              file_type_filter=FileSystemObjectType.EMPTY_DIR,
                              sort_field=FindSortField.BY_DEPTH,
                              reverse=True)
        for empty_dir in all_empty_dirs:
            remove(empty_dir)


def cp(paths: PathIterable, dest: PathType, dryrun: bool = False):
    """
    Copy file-system objects to a target
    cases:
        1) path is a directory and target is existing directory:
           -> copy whole directory into the target(-dir), thus making a subdirectory
        2) path is a directory and target is existing file or symbolic link:
           -> ERROR: cannot copy a directory onto file or link
        3) path is directory and target is link to existing directory:
           -> copy directory onto target, thus making a subdirectory to the one the link is referring
        4) path is directory and target does not exist and is no link
           -> mkdir the target and copy contents of path into this new directoryOS is 'Linux'
        5) path is file and target is (link to) directory
           -> copy the file into the directory
        6) path is file and target existing file or does not exist at all
          -> create the target path if necessary and (possibly over-)write the file
    :param paths:
    :param dest:
    :param dryrun:
     """
    log_command(f"cp -R {paths} {dest}", dryrun=dryrun)
    if not dryrun:
        paths = glob_path_patterns(paths)
        # Convert dest to Path object to use Path methods
        dest = Path(dest)
        for src_path in paths:
            # Ensure src_path is a Path object
            src_path = Path(src_path)
            if src_path.is_dir() and dest.is_dir():
                dest_dir = dest / src_path.name
                if (dest_dir.exists() or dest_dir.is_symlink()) and not dest_dir.is_file():
                    remove(dest_dir)
                shutil.copytree(src_path, dest_dir)
            elif src_path.is_dir() and dest.is_file():
                error(f"Cannot copy directory '{src_path}' onto regular file '{dest}'")
            elif src_path.is_dir() and not dest.exists():
                # make sure there's no dangling link
                if dest.is_symlink() or dest.exists():
                    remove(dest)
                mkdir(dest)
                shutil.copytree(src=src_path, dst=dest / src_path.name)
            elif src_path.is_file() and dest.is_dir():
                target_file = dest / src_path.name
                if target_file.exists() or target_file.is_dir():
                    remove(target_file)
                shutil.copy(src_path, target_file)
            elif src_path.is_file():  # and (dest.is_dir()) or not dest.exists()
                mkdir(dest.parent)
                if dest.exists() or dest.is_symlink():
                    remove(dest)
                shutil.copy(src_path, dest)
            else:
                error(f"Cannot copy '{src_path}' to '{dest}'")


def mv(paths: PathIterable, target: PathType, dryrun: bool = False):
    """
    Move files or directories.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param target: the target to move the paths to
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    log_command(f"mv {paths} {target}", dryrun=dryrun)
    paths = glob_path_patterns(paths)
    if len(paths) > 1 and not os.path.isdir(target):
        error(f"Cannot move multiple files to target-file '{target}'")
    for path in paths:
        shutil.move(path, target)


def chown(paths: PathIterable,
          user: (str | int),
          group: (str | int) = None,
          dryrun: bool = False):
    """
    Change the ownership of filesystem objects.
    :param paths: a string, a PathLike object or a list of strings or PathLike objects
    :param user: the new owner
    :param group: the new group
    :param dryrun: if set to True, then do not execute but just output a comment describing the command
    """
    if group is None:
        group = user
    log_command(f"chown {user}:{group} {paths}", dryrun=dryrun)
    paths = glob_path_patterns(paths)
    for path in paths:
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
        os.chown(path, uid, gid)
