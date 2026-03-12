![PyProcess banner](assets/banners/pyprocess-banner.svg)
# kingkybel-pyprocess

Comprehensive Python utility library for file system operations and process management.

## Features

- 📂 **File System Operations**: Robust implementations of `mkdir`, `touch`, `remove`, and `symbolic_link` with glob support
- 🛡️ **Path Protection**: Absolute path validation with automatic protection of critical Linux system directories
- 🥞 **Directory Stack**: `pushd` and `popd` functionality for clean working directory management
- 🔍 **Advanced Finding**: Flexible `find` utility with type filtering, name patterns, exclusion, and sorting
- 📝 **File Utilities**: Easy `read_file` and `write_file` operations with automatic directory creation
- ⚙️ **Env Parsing**: Simple `.env` file parser for configuration management
- 🚀 **Process Management**: Run standard and interactive commands with real-time output monitoring and thread-safe capture
- 🌐 **Network Tools**: Simple `ping` implementation and IP retrieval
- 🛠️ **Tool Validation**: Check for installed system tools and versions
- 🪵 **Logger Integration**: Built-in support for `PyFlashLogger` for command and error logging
- ✅ **Comprehensive Testing**: Robust test suite using Python's `unittest` framework

## Installation

```bash
pip install kingkybel-pyprocess
```

Or from source:
```bash
git clone https://github.com/kingkybel/PyProcess.git
cd PyProcess
pip install -e .
```

## Quick Start

### File System Operations

```python
from pyprocess import mkdir, touch, remove, pushdir, popdir

# Create directories and files
mkdir("path/to/my/project")
touch("path/to/my/project/config.ini")

# Directory stack management
pushdir("path/to/my/project")
# ... do something ...
popdir()

# Clean up
remove("path/to/my/project")
```

### Process Management

```python
from pyprocess import run_command, run_interactive_command

# Run a simple command
reval, stdout, stderr = run_command("ls -la", cwd="/tmp")

# Run an interactive command (e.g., top, vim)
run_interactive_command("top")
```

### Advanced Finding

```python
from pyprocess import find, FileSystemObjectType, FindSortField

# Find all python files, sorted by name
py_files = find(
    paths=".",
    file_type_filter=FileSystemObjectType.FILE,
    name_patterns="*.py",
    sort_field=FindSortField.BY_NAME
)
```

## Releasing to PyPI

1. Bump the package version in `pyprocess/__init__.py` (`__version__`).
2. Clean old build artifacts:
   ```bash
   rm -rf build dist *.egg-info
   ```
3. Build distributions:
   ```bash
   python -m build
   ```
4. Upload to TestPyPI first (recommended):
   ```bash
   python -m twine upload --repository testpypi dist/*
   ```
5. Upload to PyPI:
   ```bash
   python -m twine upload dist/*
   ```

## License

GPLv2 - See the LICENSE file for details.

## Contributing

Contributions welcome! Please open issues for bugs or feature requests.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request
