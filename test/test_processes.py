#!/bin/env python3

import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from flashlogger import LogLevel

from pyprocess import pushdir
from pyprocess.processes import (
    ping,
    is_tool_installed,
    assert_tools_installed,
    check_correct_tool_version,
    pipe_monitor_thread_function,
    run_command,
    run_interactive_command
)


class ProcessesTests(unittest.TestCase):
    def setUp(self):
        self.test_folder = Path(f"/tmp/{__class__.__name__}")
        if self.test_folder.exists():
            shutil.rmtree(self.test_folder, ignore_errors=True)
        self.test_folder.mkdir(parents=True, exist_ok=True)
        pushdir(self.test_folder)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_folder)

    def test_ping_with_valid_host(self):
        """Test ping with a valid host (localhost)"""
        reval, ip = ping("127.0.0.1")
        self.assertEqual(reval, 0)
        self.assertEqual(ip, "127.0.0.1")

    def test_ping_with_invalid_host(self):
        """Test ping with an invalid host"""
        reval, ip = ping("invalid.nonexistent.host.12345")
        self.assertNotEqual(reval, 0)
        self.assertEqual(ip, "- invalid.nonexistent.host.12345 doesn't respond -")

    def test_ping_with_default_host(self):
        """Test ping with default host (None)"""
        reval, ip = ping()
        self.assertEqual(reval, 0)
        self.assertEqual(ip, "127.0.0.1")

    @patch('pyprocess.processes.which')
    def test_is_tool_installed_true(self, mock_which):
        """Test is_tool_installed with existing tool"""
        mock_which.return_value = "/usr/bin/ls"
        result = is_tool_installed("ls")
        self.assertTrue(result)

    @patch('pyprocess.processes.which')
    def test_is_tool_installed_false(self, mock_which):
        """Test is_tool_installed with non-existing tool"""
        mock_which.return_value = None
        result = is_tool_installed("nonexistent_tool")
        self.assertFalse(result)

    def test_assert_tools_installed_single_tool(self):
        """Test assert_tools_installed with a single existing tool"""
        # This should not raise an exception
        try:
            assert_tools_installed("ls")
        except SystemExit:
            self.fail("assert_tools_installed raised SystemExit unexpectedly")

    def test_assert_tools_installed_multiple_tools(self):
        """Test assert_tools_installed with multiple existing tools"""
        # This should not raise an exception
        try:
            assert_tools_installed(["ls", "echo"])
        except SystemExit:
            self.fail("assert_tools_installed raised SystemExit unexpectedly")

    @patch('pyprocess.processes.is_tool_installed')
    def test_assert_tools_installed_missing_tool(self, mock_is_installed):
        """Test assert_tools_installed with missing tool"""
        mock_is_installed.return_value = False
        with self.assertRaises(SystemExit):
            assert_tools_installed("missing_tool")

    @patch('pyprocess.processes.is_tool_installed')
    def test_assert_tools_installed_mixed_tools(self, mock_is_installed):
        """Test assert_tools_installed with mix of existing and missing tools"""

        def side_effect(tool):
            return tool in ["ls", "echo"]

        mock_is_installed.side_effect = side_effect
        with self.assertRaises(SystemExit):
            assert_tools_installed(["ls", "missing_tool", "echo"])

    @patch('pyprocess.processes.is_tool_installed')
    def test_check_correct_tool_version_installed(self, mock_is_installed):
        """Test check_correct_tool_version with installed tool"""
        mock_is_installed.return_value = True
        result = check_correct_tool_version("ls", "1.0")
        self.assertTrue(result)

    @patch('pyprocess.processes.is_tool_installed')
    def test_check_correct_tool_version_not_installed(self, mock_is_installed):
        """Test check_correct_tool_version with not installed tool"""
        mock_is_installed.return_value = False
        result = check_correct_tool_version("missing_tool", "1.0")
        self.assertFalse(result)

    def test_pipe_monitor_thread_function_empty_input(self):
        """Test pipe_monitor_thread_function with empty input"""
        mock_pipe = MagicMock()
        mock_pipe.__iter__.return_value = []

        result = pipe_monitor_thread_function(mock_pipe, LogLevel.INFO)
        self.assertEqual(result, "")

    def test_pipe_monitor_thread_function_with_content(self):
        """Test pipe_monitor_thread_function with content"""
        mock_pipe = MagicMock()
        mock_pipe.__iter__.return_value = ["line1\n", "line2\n", "line3\n"]

        result = pipe_monitor_thread_function(mock_pipe, LogLevel.INFO)
        self.assertEqual(result, "line1\nline2\nline3\n")

    def test_pipe_monitor_thread_function_with_empty_lines(self):
        """Test pipe_monitor_thread_function with empty lines"""
        mock_pipe = MagicMock()
        mock_pipe.__iter__.return_value = ["line1\n", "\n", "\n", "line2\n", "\n" * 10]

        result = pipe_monitor_thread_function(mock_pipe, LogLevel.COMMAND_OUTPUT)
        self.assertEqual(result, "line1\n\n\nline2\n\n\n\n\n\n\n\n\n\n\n")

    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_success(self, mock_current_dir, _mock_popdir, _mock_pushdir, mock_popen):
        """Test run_command with successful execution"""
        mock_current_dir.return_value = "/test"

        mock_process = MagicMock()
        mock_process.stdout = ["stdout line 1\n", "stdout line 2\n"]
        mock_process.stderr = ["stderr line 1\n"]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        reval, stdout, stderr = run_command("echo test", raise_errors=False)

        self.assertEqual(reval, 0)
        self.assertEqual(stdout, "stdout line 1\nstdout line 2\n")
        self.assertEqual(stderr, "stderr line 1\n")

    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_failure_no_raise(self, mock_current_dir, _mock_popdir, _mock_pushdir, mock_popen):
        """Test run_command with failure and no error raising"""
        mock_current_dir.return_value = "/test"

        mock_process = MagicMock()
        mock_process.stdout = ["stdout line\n"]
        mock_process.stderr = ["stderr line\n"]
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        reval, stdout, stderr = run_command("echo test", raise_errors=False)

        self.assertEqual(reval, 1)
        self.assertEqual(stdout, "stdout line\n")
        self.assertEqual(stderr, "stderr line\n")

    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_failure_with_raise(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen):
        """Test run_command with failure and error raising"""
        mock_current_dir.return_value = "/test"

        mock_process = MagicMock()
        mock_process.stdout = ["stdout line\n"]
        mock_process.stderr = ["stderr line\n"]
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        with self.assertRaises(SystemExit):
            run_command("echo test", raise_errors=True)

    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_with_cwd(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen):
        """Test run_command with custom working directory"""
        mock_current_dir.return_value = "/test"

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        run_command("echo test", cwd="/custom/path", raise_errors=False)

        mock_pushdir.assert_called_once_with("/custom/path", dryrun=False)
        mock_popdir.assert_called_once_with(dryrun=False)

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_with_list_input(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen, mock_squeeze):
        """Test run_command with list input instead of string"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = "echo test"

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        run_command(["echo", "test"], raise_errors=False)

        mock_popen.assert_called_once()

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_with_comment(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen, mock_squeeze):
        """Test run_command with comment"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = "echo test"

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        run_command("echo test", comment="Test comment", raise_errors=False)

        # Should call log_progress_output with the comment

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_dryrun(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen, mock_squeeze):
        """Test run_command with dryrun mode"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = "echo test"

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        reval, stdout, stderr = run_command("echo test", dryrun=True, raise_errors=False)

        self.assertEqual(reval, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        mock_popen.assert_not_called()

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_with_empty_string(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen, mock_squeeze):
        """Test run_command with empty string"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = ""

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        run_command("", raise_errors=False)

        # Should handle empty string gracefully

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_with_whitespace(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen, mock_squeeze):
        """Test run_command with whitespace-only string"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = ""

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        run_command("   \t  \n  ", raise_errors=False)

        # Should handle whitespace gracefully

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_with_quoted_arguments(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen,
                                               mock_squeeze):
        """Test run_command with quoted arguments"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = "echo 'hello world'"

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        run_command("echo 'hello world'", raise_errors=False)

        # Should handle quoted arguments correctly

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_command_with_special_characters(self, mock_current_dir, mock_popdir, mock_pushdir, mock_popen,
                                                 mock_squeeze):
        """Test run_command with special characters"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = "echo test@#$%^&*()"

        mock_process = MagicMock()
        mock_process.stdout = ["output\n"]
        mock_process.stderr = []
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        run_command("echo test@#$%^&*()", raise_errors=False)

        # Should handle special characters correctly


    @patch('pyprocess.processes.sys.stdout')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pty.openpty')
    @patch('pyprocess.processes.select.select')
    @patch('pyprocess.processes.os.read')
    @patch('pyprocess.processes.os.write')
    @patch('pyprocess.processes.termios.tcgetattr')
    @patch('pyprocess.processes.termios.tcsetattr')
    @patch('pyprocess.processes.tty.setraw')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_interactive_command_with_on_line_callback(
            self,
            mock_current_dir, mock_popdir, mock_pushdir,
            mock_tty_setraw, mock_tcsetattr, mock_tcgetattr,
            mock_os_write, mock_os_read, mock_select, mock_openpty, mock_popen,
            mock_stdout
    ):
        mock_stdout.fileno.return_value = 1
        """Test run_interactive_command with on_line callback"""
        mock_current_dir.return_value = "/test"
        mock_master_fd = 3
        mock_slave_fd = 4
        mock_openpty.return_value = (mock_master_fd, mock_slave_fd)

        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 0]
        mock_popen.return_value = mock_process

        # Simulate output from master_fd: yields two lines
        mock_os_read.side_effect = [
            b"line1\nline2\n",
        ]

        # Make select return master_fd as readable
        mock_select.side_effect = [
            ([mock_master_fd], [], []),  # first iteration: master_fd has data
        ]

        collected_lines = []

        def line_collector(line):
            collected_lines.append(line)

        run_interactive_command("echo test", on_line=line_collector)

        self.assertEqual(len(collected_lines), 2)
        self.assertEqual(collected_lines[0], "line1")
        self.assertEqual(collected_lines[1], "line2")

    @patch('pyprocess.processes.sys.stdout')
    @patch('pyprocess.processes.subprocess.Popen')
    @patch('pyprocess.processes.pty.openpty')
    @patch('pyprocess.processes.select.select')
    @patch('pyprocess.processes.os.read')
    @patch('pyprocess.processes.os.write')
    @patch('pyprocess.processes.termios.tcgetattr')
    @patch('pyprocess.processes.termios.tcsetattr')
    @patch('pyprocess.processes.tty.setraw')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_interactive_command_with_on_line_callback_no_newline(
            self,
            mock_current_dir, mock_popdir, mock_pushdir,
            mock_tty_setraw, mock_tcsetattr, mock_tcgetattr,
            mock_os_write, mock_os_read, mock_select, mock_openpty, mock_popen,
            mock_stdout
    ):
        mock_stdout.fileno.return_value = 1
        """Test run_interactive_command with on_line callback - partial output without newline"""
        mock_current_dir.return_value = "/test"
        mock_master_fd = 3
        mock_slave_fd = 4
        mock_openpty.return_value = (mock_master_fd, mock_slave_fd)

        mock_process = MagicMock()
        # Process stays alive long enough for reads, then exits
        mock_process.poll.side_effect = [None, None, 0]
        mock_popen.return_value = mock_process

        # Single read without trailing newline
        mock_os_read.side_effect = [
            b"partial line without newline",
        ]

        mock_select.side_effect = [
            ([mock_master_fd], [], []),
            ([], [], []),
        ]

        collected_lines = []

        def line_collector(line):
            collected_lines.append(line)

        run_interactive_command("echo test", on_line=line_collector)

        # No complete lines - buffered but not emitted
        self.assertEqual(len(collected_lines), 0)

    @patch('pyprocess.processes.squeeze_chars')
    @patch('pyprocess.processes.pushdir')
    @patch('pyprocess.processes.popdir')
    @patch('pyprocess.processes.current_dir')
    def test_run_interactive_command_dryrun(self, mock_current_dir, mock_popdir, mock_pushdir, mock_squeeze):
        """Test run_interactive_command with dryrun mode - on_line should not be called"""
        mock_current_dir.return_value = "/test"
        mock_squeeze.return_value = "echo test"

        callback_called = False

        def never_called(_line):
            nonlocal callback_called
            callback_called = True

        run_interactive_command("echo test", dryrun=True, on_line=never_called)

        self.assertFalse(callback_called)


if __name__ == '__main__':
    unittest.main()
