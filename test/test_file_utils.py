#!/bin/env python3

import os
import shutil
import unittest
from pathlib import Path

from pyprocess import touch, pushdir, generate_incremental_filename, read_file, write_file, extract_dict_from_string, \
    parse_env_file


class FileUtilsTests(unittest.TestCase):
    def setUp(self):
        self.test_folder = Path(f"/tmp/{__class__.__name__}")
        if self.test_folder.exists():
            shutil.rmtree(self.test_folder, ignore_errors=True)
        self.test_folder.mkdir(parents=True, exist_ok=True)
        pushdir(self.test_folder)
        self.test_file = self.test_folder / "test.txt"
        self.test_env_file = self.test_folder / ".env"

    def tearDown(self):
        shutil.rmtree(self.test_folder)

    def test_generate_incremental_filename_basic(self):
        """Test basic incremental filename generation"""
        base_path = self.test_folder / "test"
        result = generate_incremental_filename(base_path)
        self.assertEqual(result, base_path)

        # Create file and test increment
        with open(base_path, 'w') as f:
            f.write("test")

        result = generate_incremental_filename(base_path)
        self.assertEqual(result, Path(f"{base_path}_1"))

    def test_generate_incremental_filename_with_extension(self):
        """Test incremental filename generation with file extension"""
        base_path = self.test_folder / "test.txt"
        result = generate_incremental_filename(base_path)
        self.assertEqual(result, base_path)

        # Create file and test increment
        with open(base_path, 'w') as f:
            f.write("test")

        result = generate_incremental_filename(base_path)
        self.assertEqual(result, self.test_folder / "test_1.txt")

    def test_generate_incremental_filename_with_spaces(self):
        """Test incremental filename generation with spaces in filename"""
        base_path = self.test_folder / "test file name.txt"
        result = generate_incremental_filename(base_path)
        expected = self.test_folder / "test_file_name.txt"
        self.assertEqual(result, expected)

    def test_generate_incremental_filename_multiple_increments(self):
        """Test multiple incremental filename generations"""
        base_path = self.test_folder / "test"

        touch(base_path)
        # Create multiple files
        for i in range(3):
            with open(f"{base_path}_{i}", 'w') as f:
                f.write(f"test {i}")

        result = generate_incremental_filename(base_path)
        self.assertEqual(result, Path(f"{base_path}_3"))

    def test_read_file_existing(self):
        """Test reading an existing file"""
        test_content = "Hello, World!\nThis is a test file."
        with open(self.test_file, 'w') as f:
            f.write(test_content)

        result = read_file(self.test_file)
        self.assertEqual(result, test_content)

    def test_read_file_nonexistent(self):
        """Test reading a nonexistent file"""
        nonexistent_file = os.path.join(self.test_folder, "nonexistent.txt")
        with self.assertRaises(FileNotFoundError):
            result = read_file(nonexistent_file)

    def test_write_file_new_file(self):
        """Test writing to a new file"""
        content = "This is test content"
        write_file(self.test_file, content)

        self.assertTrue(os.path.exists(self.test_file))
        with open(self.test_file, 'r') as f:
            result = f.read()
        self.assertEqual(result, content)

    def test_write_file_append_mode(self):
        """Test writing to a file in append mode"""
        initial_content = "Initial content\n"
        append_content = "Appended content"

        write_file(self.test_file, initial_content)
        write_file(self.test_file, append_content, mode='a')

        with open(self.test_file, 'r') as f:
            result = f.read()
        expected = f"{initial_content}{append_content}"
        self.assertEqual(result, expected)

    def test_write_file_list_content(self):
        """Test writing list of strings to file"""
        content_list = ["Line 1", "Line 2", "Line 3"]
        write_file(self.test_file, content_list)

        with open(self.test_file, 'r') as f:
            result = f.read()
        expected = "Line 1\nLine 2\nLine 3"
        self.assertEqual(result, expected)

    def test_write_file_empty_content(self):
        """Test writing empty content to file"""
        write_file(self.test_file, "")

        with open(self.test_file, 'r') as f:
            result = f.read()
        self.assertEqual(result, "")

    def test_write_file_invalid_mode(self):
        """Test writing with invalid mode"""
        with self.assertRaises(SystemExit):
            write_file(self.test_file, "test", mode='x')

    def test_extract_dict_from_string_basic(self):
        """Test basic dictionary extraction from string"""
        content = "KEY1=value1\nKEY2=value2\nKEY3=value3"
        result = extract_dict_from_string(content)
        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        self.assertEqual(result, expected)

    def test_extract_dict_from_string_with_comments(self):
        """Test dictionary extraction with comments"""
        content = "KEY1=value1\n# This is a comment\nKEY2=value2\nKEY3=value3 # inline comment"
        result = extract_dict_from_string(content)
        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        self.assertEqual(result, expected)

    def test_extract_dict_from_string_empty_lines(self):
        """Test dictionary extraction with empty lines"""
        content = "KEY1=value1\n\n\nKEY2=value2\n\nKEY3=value3"
        result = extract_dict_from_string(content)
        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        self.assertEqual(result, expected)

    def test_extract_dict_from_string_whitespace(self):
        """Test dictionary extraction with whitespace"""
        content = "  KEY1  =  value1  \n  KEY2  =  value2  "
        result = extract_dict_from_string(content)
        expected = {"KEY1": "value1", "KEY2": "value2"}
        self.assertEqual(result, expected)

    def test_extract_dict_from_string_no_equals(self):
        """Test dictionary extraction with lines without equals"""
        content = "KEY1=value1\nKEY2\nKEY3=value3"
        result = extract_dict_from_string(content)
        expected = {"KEY1": "value1", "KEY2": "", "KEY3": "value3"}
        self.assertEqual(result, expected)

    def test_parse_env_file_existing(self):
        """Test parsing an existing .env file"""
        env_content = """# Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=admin
DB_PASS=secret123

# Application settings
DEBUG=true
LOG_LEVEL=info"""

        with open(self.test_env_file, 'w') as f:
            f.write(env_content)

        result = parse_env_file(self.test_env_file)
        expected = {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_NAME": "myapp",
            "DB_USER": "admin",
            "DB_PASS": "secret123",
            "DEBUG": "true",
            "LOG_LEVEL": "info"
        }
        self.assertEqual(result, expected)

    def test_parse_env_file_nonexistent(self):
        """Test parsing a nonexistent .env file"""
        nonexistent_file = self.test_folder/".env.nonexistent"
        with self.assertRaises(FileNotFoundError):
            result = parse_env_file(nonexistent_file)

    def test_parse_env_file_empty(self):
        """Test parsing an empty .env file"""
        with open(self.test_env_file, 'w') as f:
            f.write("")

        result = parse_env_file(self.test_env_file)
        self.assertEqual(result, {})

    def test_parse_env_file_only_comments(self):
        """Test parsing a .env file with only comments"""
        env_content = """# This is a comment
# Another comment
# DB_HOST=localhost"""

        with open(self.test_env_file, 'w') as f:
            f.write(env_content)

        result = parse_env_file(self.test_env_file)
        self.assertEqual(result, {})

    def test_parse_env_file_mixed_content(self):
        """Test parsing a .env file with mixed content"""
        env_content = """# Comment
KEY1=value1

# Another comment
KEY2=value2
# Comment in between
KEY3=value3

# Final comment"""

        with open(self.test_env_file, 'w') as f:
            f.write(env_content)

        result = parse_env_file(self.test_env_file)
        expected = {"KEY1": "value1", "KEY2": "value2", "KEY3": "value3"}
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
