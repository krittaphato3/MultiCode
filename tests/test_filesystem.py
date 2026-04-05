"""Tests for the filesystem tools module."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from tools.filesystem import (
    FileSystemTools,
    PathSecurityError,
)


class TestFileSystemTools:
    """Test filesystem tools."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def fs_tools(self, temp_dir):
        """Create filesystem tools instance with temp directory."""
        return FileSystemTools(base_dir=temp_dir)

    def test_resolve_path_within_base(self, temp_dir):
        """Path resolution should work for paths within base."""
        tools = FileSystemTools(base_dir=temp_dir)
        resolved = tools._resolve_path("test.txt")
        assert resolved == temp_dir / "test.txt"

    def test_resolve_path_traversal_blocked(self, temp_dir):
        """Path traversal should be blocked."""
        tools = FileSystemTools(base_dir=temp_dir)
        with pytest.raises(PathSecurityError):
            tools._resolve_path("../../etc/passwd")

    def test_resolve_absolute_path_outside_base(self, temp_dir):
        """Absolute paths outside base should be blocked."""
        tools = FileSystemTools(base_dir=temp_dir)
        # Use a path clearly outside the base
        outside_path = Path("/this/path/does/not/exist.txt")
        with pytest.raises(PathSecurityError):
            tools._resolve_path(outside_path)

    def test_write_and_read_file(self, fs_tools, temp_dir):
        """Should write and read files correctly."""
        async def _test():
            content = "Hello, World!"
            path = await fs_tools.write_file("test.txt", content)
            assert path == "test.txt"

            result = await fs_tools.read_file("test.txt")
            assert result.content == content

        asyncio.run(_test())

    def test_create_dirs_automatically(self, fs_tools, temp_dir):
        """Should create parent directories automatically."""
        async def _test():
            content = "Nested file"
            path = await fs_tools.write_file("subdir/nested/test.txt", content)
            assert "subdir" in path or "nested" in path

            result = await fs_tools.read_file("subdir/nested/test.txt")
            assert result.content == content

        asyncio.run(_test())

    def test_list_directory(self, fs_tools, temp_dir):
        """Should list directory contents."""
        async def _test():
            # Create some files
            await fs_tools.write_file("file1.txt", "content1")
            await fs_tools.write_file("file2.py", "content2")
            (temp_dir / "subdir").mkdir(exist_ok=True)

            listing = await fs_tools.list_directory(".")
            assert "file1.txt" in listing.entries
            assert "file2.py" in listing.entries
            assert "subdir" in listing.directories

        asyncio.run(_test())

    def test_file_exists(self, fs_tools, temp_dir):
        """Should detect file existence."""
        async def _test():
            await fs_tools.write_file("exists.txt", "content")
            assert await fs_tools.file_exists("exists.txt") is True
            assert await fs_tools.file_exists("notexists.txt") is False

        asyncio.run(_test())

    def test_delete_file(self, fs_tools, temp_dir):
        """Should delete files."""
        async def _test():
            await fs_tools.write_file("todelete.txt", "content")
            assert await fs_tools.file_exists("todelete.txt") is True

            result = await fs_tools.delete_file("todelete.txt")
            assert result is True
            assert await fs_tools.file_exists("todelete.txt") is False

        asyncio.run(_test())

    def test_dry_run_does_not_write(self, temp_dir):
        """Dry run mode should not write files."""
        async def _test():
            tools = FileSystemTools(base_dir=temp_dir, dry_run=True)
            await tools.write_file("dryrun.txt", "content")

            # File should not exist
            assert (temp_dir / "dryrun.txt").exists() is False
            # But preview log should have entry
            assert len(tools.preview_log) == 1
            assert tools.preview_log[0]["operation"] == "CREATE"

        asyncio.run(_test())

    def test_get_file_info(self, fs_tools, temp_dir):
        """Should return file info."""
        async def _test():
            await fs_tools.write_file("info.txt", "test content")
            info = await fs_tools.get_file_info("info.txt")

            assert info["path"] == "info.txt"
            assert info["size"] == len("test content")
            assert info["is_file"] is True
            assert info["is_directory"] is False

        asyncio.run(_test())
