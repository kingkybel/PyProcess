#!/bin/env python3

import unittest

from pyprocess import *


class FileSystemObjectTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.test_folder = Path(f"/tmp/{__class__.__name__}")
        if self.test_folder.exists():
            shutil.rmtree(self.test_folder, ignore_errors=True)
        mkdir(self.test_folder)
        pushdir(self.test_folder)

    def tearDown(self):
        shutil.rmtree(self.test_folder, ignore_errors=True)
        return super().tearDown()

    def test_make_path_list(self):
        path1 = Path("/xyz/abc")
        path2 = Path("/usr/bin")
        path3 = "/home/user"
        self.assertEqual(["/xyz/abc"], make_path_str_list(path1))
        self.assertEqual(["/home/user"], make_path_str_list(path3))
        self.assertListEqual(["/xyz/abc", "/usr/bin", "/home/user"], make_path_str_list([path1, path2, path3]))

        has_thrown = False
        try:
            make_path_str_list("")
        except SystemExit:
            has_thrown = True
        self.assertTrue(has_thrown)

        has_thrown = False
        try:
            make_path_str_list([])
        except SystemExit:
            has_thrown = True
        self.assertTrue(has_thrown)

        has_thrown = False
        try:
            make_path_str_list([path1, "", path3])
        except SystemExit:
            has_thrown = True
        self.assertTrue(has_thrown)

        self.assertTrue(has_thrown)

        has_thrown = False
        try:
            make_path_str_list([path1, [], path3])
        except SystemExit:
            has_thrown = True
        self.assertTrue(has_thrown)

    def test_glob_path_patterns_successful(self):
        dir1 = self.test_folder / "test-glob/sub/sub1"
        dir2 = f"{self.test_folder}/test-glob/sub/sub2"
        dir3 = self.test_folder / "test-glob/sub/DIR3"
        dir1.mkdir(exist_ok=True, parents=True)
        Path(dir2).mkdir(exist_ok=True, parents=True)
        dir3.mkdir(exist_ok=True, parents=True)
        self.assertListEqual([Path(f"{self.test_folder}/test-glob")],
                             glob_path_patterns(f"{self.test_folder}/test-glob"))
        self.assertListEqual([Path(f"{self.test_folder}/test-glob")], glob_path_patterns(f"{self.test_folder}/*-glob"))
        self.assertListEqual([Path(dir2)], glob_path_patterns(f"{self.test_folder}/*-glob/*/*2"))
        self.assertListEqual([Path(dir1), Path(dir2)], glob_path_patterns(f"{self.test_folder}/*-glob/sub/sub*"))

        expected = [Path(dir1), Path(dir2)]
        expected.sort()
        globbed = glob_path_patterns(f"{self.test_folder}/*-glob/*/sub*")
        globbed.sort()
        self.assertListEqual(expected, globbed)

        expected = [Path(dir1), Path(dir2), Path(dir3)]
        expected.sort()
        globbed = glob_path_patterns(f"{self.test_folder}/*-glob/*/*")
        globbed.sort()
        self.assertListEqual(expected, globbed)
        shutil.rmtree(f"{self.test_folder}/test-glob", ignore_errors=True)

    def test_glob_path_patterns_failure(self):
        dir1 = self.test_folder / "test-glob/sub/sub1"
        dir2 = f"{self.test_folder}/test-glob/sub/sub2"
        dir3 = self.test_folder / "test-glob/sub/DIR3"
        dir1.mkdir(exist_ok=True, parents=True)
        Path(dir2).mkdir(exist_ok=True, parents=True)
        dir3.mkdir(exist_ok=True, parents=True)

        with self.assertRaises(FileNotFoundError):
            glob_path_patterns(f"{self.test_folder}/test-glob/sub/subXXX")

        has_thrown = False
        returned_list = list()
        try:
            returned_list = glob_path_patterns("/tmp/test-glob/sub/subXXX", glob_mode=GlobMode.KEEP_EMPTY)
        except FileNotFoundError:
            has_thrown = True
        self.assertFalse(has_thrown)
        self.assertEqual(1, len(returned_list))
        self.assertEqual(returned_list[0], Path("/tmp/test-glob/sub/subXXX"))

        shutil.rmtree("/tmp/test-glob", ignore_errors=True)

    def test_touch_mkdir_remove(self):
        tmp_dir = self.test_folder / "test_mkdir_touch_remove"
        shutil.rmtree(tmp_dir, ignore_errors=True)

        mkdir(f"{tmp_dir}/sub1")
        self.assertTrue(os.path.isdir(f"{tmp_dir}/sub1"))
        remove(f"{tmp_dir}/sub1")
        self.assertFalse(os.path.exists(f"{tmp_dir}/sub1"))

        mkdir([f"{tmp_dir}/sub1", f"{tmp_dir}/sub2"])
        self.assertTrue(os.path.isdir(f"{tmp_dir}/sub1"))
        self.assertTrue(os.path.isdir(f"{tmp_dir}/sub2"))
        remove([f"{tmp_dir}/sub1", f"{tmp_dir}/sub2"])
        self.assertFalse(os.path.exists(f"{tmp_dir}/sub1"))
        self.assertFalse(os.path.exists(f"{tmp_dir}/sub2"))

        touch(f"{tmp_dir}/text.txt")
        self.assertTrue(os.path.isfile(f"{tmp_dir}/text.txt"))
        remove(f"{tmp_dir}/text.txt")
        self.assertFalse(os.path.exists(f"{tmp_dir}/text.txt"))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_pwd_pushdir_popdir(self):
        tmp_dir = self.test_folder / "test_pwd_pushdir_popdir"
        mkdir([f"{tmp_dir}/sub1/sub11", f"{tmp_dir}/sub1/sub12", f"{tmp_dir}/sub2/sub21", f"{tmp_dir}/sub2/sub22"])
        pushdir(tmp_dir)
        self.assertEqual(current_dir(), tmp_dir)

        pushdir(f"{tmp_dir}/sub1/sub11")
        pushdir(f"{tmp_dir}/sub1/sub12")
        pushdir(f"{tmp_dir}/sub2/sub21")
        pushdir(f"{tmp_dir}/sub2/sub22")
        self.assertEqual(current_dir(), tmp_dir / "sub2/sub22")
        popdir()
        self.assertEqual(current_dir(), tmp_dir / "sub2/sub21")
        popdir()
        self.assertEqual(current_dir(), tmp_dir / "sub1/sub12")
        popdir()
        self.assertEqual(current_dir(), tmp_dir / "sub1/sub11")
        popdir()
        self.assertEqual(current_dir(), tmp_dir)

        remove(tmp_dir)

    def test_valid_absolute_path_basic(self):
        """Test valid_absolute_path with basic paths"""
        # Create a test file in the test folder to ensure the path exists
        test_file = self.test_folder / "test.txt"
        touch(test_file)
        
        # Test with absolute path instead of relative path
        result = valid_absolute_path(str(test_file))
        self.assertEqual(result, test_file)

        result = valid_absolute_path("/absolute/path")
        self.assertEqual(result, Path("/absolute/path"))

    def test_valid_absolute_path_protected_system_paths(self):
        """Test valid_absolute_path with protected system paths"""
        with self.assertRaises(SystemError):
            valid_absolute_path("/bin")

        with self.assertRaises(SystemError):
            valid_absolute_path("/usr")

    def test_valid_absolute_path_allow_system_paths(self):
        """Test valid_absolute_path with allow_system_paths=True"""
        result = valid_absolute_path("/bin", allow_system_paths=True)
        self.assertEqual(result, Path("/bin"))

    def test_valid_absolute_path_custom_protect_patterns(self):
        """Test valid_absolute_path with custom protect patterns"""
        with self.assertRaises(SystemError):
            valid_absolute_path("/custom/protected", protect_system_patterns=["^/custom"])

    def test_file_system_object_type_from_path(self):
        """Test FileSystemObjectType.from_file_system_object"""
        tmp_dir = self.test_folder / "test_fs_type"

        # Test file
        test_file = tmp_dir / "test.txt"
        mkdir(tmp_dir)
        touch(test_file)
        self.assertEqual(FileSystemObjectType.from_file_system_object(test_file), FileSystemObjectType.FILE)

        # Test empty directory
        empty_dir = tmp_dir / "empty"
        mkdir(empty_dir)
        self.assertEqual(FileSystemObjectType.from_file_system_object(empty_dir), FileSystemObjectType.EMPTY_DIR)

        # Test non-empty directory
        non_empty_dir = tmp_dir / "nonempty"
        mkdir(non_empty_dir)
        touch(non_empty_dir / "file.txt")
        self.assertEqual(FileSystemObjectType.from_file_system_object(non_empty_dir),
                         FileSystemObjectType.NOT_EMPTY_DIR)

        # Test stale link
        stale_link = tmp_dir / "stale_link"
        os.symlink("/nonexistent/path", stale_link)
        self.assertEqual(FileSystemObjectType.from_file_system_object(stale_link), FileSystemObjectType.STALE_LINK)

        # Test valid link
        valid_link = tmp_dir / "valid_link"
        os.symlink(test_file, valid_link)
        self.assertEqual(FileSystemObjectType.from_file_system_object(valid_link), FileSystemObjectType.NOT_STALE_LINK)

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_file_system_object_type_from_string(self):
        """Test FileSystemObjectType.from_string"""
        self.assertEqual(FileSystemObjectType.from_string("f"), FileSystemObjectType.FILE)
        self.assertEqual(FileSystemObjectType.from_string("d"), FileSystemObjectType.DIR)
        self.assertEqual(FileSystemObjectType.from_string("df"), FileSystemObjectType.FILE | FileSystemObjectType.DIR)
        self.assertEqual(FileSystemObjectType.from_string("fl"), FileSystemObjectType.FILE | FileSystemObjectType.LINK)
        self.assertEqual(FileSystemObjectType.from_string("dl"), FileSystemObjectType.DIR | FileSystemObjectType.LINK)
        self.assertEqual(FileSystemObjectType.from_string("dfl"),
                         FileSystemObjectType.DIR | FileSystemObjectType.FILE | FileSystemObjectType.LINK)

    def test_set_file_last_modified(self):
        """Test set_file_last_modified"""
        tmp_dir = self.test_folder / "test_set_mtime"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir(tmp_dir)

        test_file = tmp_dir/"test.txt"
        touch(test_file)

        import datetime
        new_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
        modified = set_file_last_modified(test_file, new_time)

        self.assertEqual(len(modified), 1)
        self.assertEqual(modified[0], test_file)

        # Check if modification time was actually set
        stat = os.stat(test_file)
        self.assertAlmostEqual(stat.st_mtime, new_time.timestamp(), delta=1)

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_symbolic_link(self):
        """Test symbolic_link function"""
        tmp_dir = self.test_folder / "test_symlink"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir(tmp_dir)

        existing_file = f"{tmp_dir}/existing.txt"
        new_link = f"{tmp_dir}/link.txt"

        touch(existing_file)
        symbolic_link(existing_file, new_link)

        self.assertTrue(os.path.islink(new_link))
        self.assertEqual(os.readlink(new_link), existing_file)

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_symbolic_link_overwrite(self):
        """Test symbolic_link with overwrite_link=True"""
        tmp_dir = self.test_folder / "test_symlink_overwrite"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir(tmp_dir)

        existing_file = f"{tmp_dir}/existing.txt"
        new_link = f"{tmp_dir}/link.txt"
        different_file = f"{tmp_dir}/different.txt"

        touch(existing_file)
        touch(different_file)
        symbolic_link(existing_file, new_link)

        # Overwrite the link
        symbolic_link(different_file, new_link, overwrite_link=True)

        self.assertTrue(os.path.islink(new_link))
        self.assertEqual(os.readlink(new_link), different_file)

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_find_files_and_directories(self):
        """Test find function"""

        mkdir([f"{self.test_folder}/sub1", f"{self.test_folder}/sub2", f"{self.test_folder}/sub1/sub11"])

        touch(f"{self.test_folder}/file1.txt")
        touch(f"{self.test_folder}/sub1/file2.txt")
        touch(f"{self.test_folder}/sub2/file3.txt")

        # Find all files
        all_files = find(self.test_folder, file_type_filter=FileSystemObjectType.FILE)
        self.assertEqual(len(all_files), 3)

        # Find files with name pattern
        txt_files = find(self.test_folder, file_type_filter=FileSystemObjectType.FILE, name_patterns="*.txt")
        self.assertEqual(len(txt_files), 3)

        # Find directories
        dirs = find(self.test_folder, file_type_filter=FileSystemObjectType.DIR)
        self.assertEqual(len(dirs), 4)  # tmp_dir, sub1, sub2, sub11

        shutil.rmtree(self.test_folder, ignore_errors=True)

    def test_find_with_sorting(self):
        """Test find function with sorting"""
        tmp_dir = self.test_folder / "test_find_sort"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir([f"{tmp_dir}/sub1", f"{tmp_dir}/sub2"])

        touch(f"{tmp_dir}/file1.txt")
        touch(f"{tmp_dir}/sub1/file2.txt")

        # Sort by name
        sorted_by_name = find(tmp_dir, file_type_filter=FileSystemObjectType.FILE, sort_field=FindSortField.BY_NAME)
        self.assertTrue(all("file" in str(path) for path in sorted_by_name))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_is_stale_link(self):
        """Test is_stale_link function"""
        tmp_dir = self.test_folder / "test_stale_link"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir(tmp_dir)

        # Create a stale link
        stale_link = f"{tmp_dir}/stale_link"
        os.symlink("/nonexistent/path", stale_link)

        self.assertTrue(is_stale_link(stale_link))

        # Create a valid link
        existing_file = f"{tmp_dir}/existing.txt"
        touch(existing_file)
        valid_link = f"{tmp_dir}/valid_link"
        os.symlink(existing_file, valid_link)

        self.assertFalse(is_stale_link(valid_link))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_is_empty_dir(self):
        """Test is_empty_dir function"""
        tmp_dir = self.test_folder / "test_empty_dir"
        shutil.rmtree(tmp_dir, ignore_errors=True)

        # Test empty directory
        empty_dir = f"{tmp_dir}/empty"
        mkdir(empty_dir)
        self.assertTrue(is_empty_dir(empty_dir))

        # Test non-empty directory
        non_empty_dir = f"{tmp_dir}/nonempty"
        mkdir(non_empty_dir)
        touch(f"{non_empty_dir}/file.txt")
        self.assertFalse(is_empty_dir(non_empty_dir))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_remove_stale_links(self):
        """Test remove_stale_links function"""
        tmp_dir = self.test_folder / "test_remove_stale"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir(tmp_dir)

        # Create some stale links
        stale_link1 = f"{tmp_dir}/stale1"
        stale_link2 = f"{tmp_dir}/stale2"
        os.symlink("/nonexistent1", stale_link1)
        os.symlink("/nonexistent2", stale_link2)

        # Create a valid link
        existing_file = f"{tmp_dir}/existing.txt"
        touch(existing_file)
        valid_link = f"{tmp_dir}/valid"
        os.symlink(existing_file, valid_link)

        # Remove stale links
        remove_stale_links(tmp_dir)

        self.assertFalse(os.path.exists(stale_link1))
        self.assertFalse(os.path.exists(stale_link2))
        self.assertTrue(os.path.exists(valid_link))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_remove_empty_dirs(self):
        """Test remove_empty_dirs function"""
        tmp_dir = self.test_folder / "test_remove_empty"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir([tmp_dir / "empty1", tmp_dir / "empty2", tmp_dir / "nonempty"])

        # Make one directory non-empty
        touch(f"{tmp_dir}/nonempty/file.txt")

        # Remove empty directories
        remove_empty_dirs(tmp_dir)

        self.assertFalse((tmp_dir / "empty1").is_dir())
        self.assertFalse((tmp_dir / "empty2").is_dir())
        self.assertTrue((tmp_dir / "nonempty").is_dir())

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_cp_file_to_directory(self):
        """Test cp function - file to directory"""
        tmp_dir = self.test_folder / "test_cp"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir([f"{tmp_dir}/src", f"{tmp_dir}/dest"], force=True)

        src_file = f"{tmp_dir}/src/file.txt"
        touch(src_file)
        dest_dir = tmp_dir / "dest"
        cp(src_file, dest_dir)
        dest_file = dest_dir / "file.txt"

        self.assertTrue(dest_file.exists())

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_cp_directory_to_directory(self):
        """Test cp function - directory to directory"""
        tmp_dir = self.test_folder / "test_cp_dir"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir([f"{tmp_dir}/src/sub", f"{tmp_dir}/dest"])

        src_file = f"{tmp_dir}/src/sub/file.txt"
        touch(src_file)

        cp(f"{tmp_dir}/src", f"{tmp_dir}/dest")

        self.assertTrue(os.path.exists(f"{tmp_dir}/dest/src/sub/file.txt"))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_mv_file(self):
        """Test mv function - move file"""
        tmp_dir = self.test_folder / "test_mv"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir([f"{tmp_dir}/src", f"{tmp_dir}/dest"])

        src_file = f"{tmp_dir}/src/file.txt"
        dest_file = f"{tmp_dir}/dest/file.txt"
        touch(src_file)

        mv(src_file, dest_file)

        self.assertFalse(os.path.exists(src_file))
        self.assertTrue(os.path.exists(dest_file))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_mv_directory(self):
        """Test mv function - move directory"""
        tmp_dir = self.test_folder / "test_mv_dir"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        mkdir([f"{tmp_dir}/src/sub", f"{tmp_dir}/dest"])

        src_file = f"{tmp_dir}/src/sub/file.txt"
        touch(src_file)

        mv(f"{tmp_dir}/src", f"{tmp_dir}/dest")

        self.assertFalse(os.path.exists(f"{tmp_dir}/src"))
        self.assertTrue(os.path.exists(f"{tmp_dir}/dest/src/sub/file.txt"))

        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
