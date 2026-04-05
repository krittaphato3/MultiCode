"""
Filesystem tools for MultiCode agents.

Provides secure, async file operations restricted to the current working directory.
Agents can read, write, and list files without risking system file modifications.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path


class FileSystemError(Exception):
    """Base exception for filesystem operations."""
    pass


class PathSecurityError(FileSystemError):
    """Raised when a path operation violates security constraints."""
    pass


class FileOperationError(FileSystemError):
    """Raised when a file operation fails."""
    pass


@dataclass
class FileContent:
    """Represents the content of a file."""
    path: str
    content: str
    encoding: str = "utf-8"


@dataclass
class DirectoryListing:
    """Represents a directory listing."""
    path: str
    entries: list[str]
    directories: list[str]
    files: list[str]


class FileSystemTools:
    """
    Secure filesystem operations for agents.
    
    All paths are resolved relative to a base directory and validated
    to prevent path traversal attacks.
    """
    
    def __init__(
        self,
        base_dir: Path | None = None,
        dry_run: bool = False,
    ):
        """
        Initialize filesystem tools with a base directory.

        Args:
            base_dir: Base directory for all operations.
                Defaults to current working directory.
            dry_run: If True, preview file writes without executing them.
        """
        self._base_dir = base_dir or Path.cwd()
        self._lock = asyncio.Lock()
        self._dry_run = dry_run
        self._preview_log: list[dict] = []  # Track what would be written

    @property
    def dry_run(self) -> bool:
        """Check if dry-run mode is enabled."""
        return self._dry_run

    @property
    def preview_log(self) -> list[dict]:
        """Get list of file operations that would be performed."""
        return self._preview_log.copy()

    def clear_preview(self) -> None:
        """Clear the preview log."""
        self._preview_log.clear()
    
    @property
    def base_dir(self) -> Path:
        """Get the base directory for operations."""
        return self._base_dir
    
    def _resolve_path(self, path: str | Path) -> Path:
        """
        Resolve a path relative to base_dir and validate security.
        
        Args:
            path: Path to resolve (can be absolute or relative)
            
        Returns:
            Resolved absolute path
            
        Raises:
            PathSecurityError: If path is outside base_dir
        """
        path_obj = Path(path)
        
        # If absolute path, check if it's within base_dir
        if path_obj.is_absolute():
            resolved = path_obj.resolve()
        else:
            # Relative path - resolve against base_dir
            resolved = (self._base_dir / path_obj).resolve()
        
        # Security check: ensure resolved path is within base_dir
        try:
            resolved.relative_to(self._base_dir.resolve())
        except ValueError as e:
            raise PathSecurityError(
                f"Path '{path}' resolves to '{resolved}' which is outside "
                f"the allowed base directory '{self._base_dir}'"
            ) from e
        
        return resolved
    
    def _validate_encoding(self, encoding: str) -> str:
        """Validate and normalize encoding."""
        encoding = encoding.lower().strip()
        valid_encodings = ["utf-8", "utf8", "ascii", "latin-1", "cp1252"]
        
        if encoding not in valid_encodings:
            encoding = "utf-8"  # Default to utf-8
        
        return encoding.replace("-", "")  # Normalize utf-8 to utf8
    
    async def read_file(
        self, 
        path: str | Path, 
        encoding: str = "utf-8"
    ) -> FileContent:
        """
        Read the contents of a file.
        
        Args:
            path: Path to the file (relative to base_dir or absolute)
            encoding: File encoding (default: utf-8)
            
        Returns:
            FileContent object with path and content
            
        Raises:
            PathSecurityError: If path is outside base_dir
            FileOperationError: If file cannot be read
        """
        resolved_path = self._resolve_path(path)
        encoding = self._validate_encoding(encoding)
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                lambda: resolved_path.read_text(encoding=encoding)
            )
            
            return FileContent(
                path=str(resolved_path.relative_to(self._base_dir)),
                content=content,
                encoding=encoding
            )
            
        except FileNotFoundError as e:
            raise FileOperationError(f"File not found: {resolved_path}") from e
        except PermissionError as e:
            raise FileOperationError(f"Permission denied: {resolved_path}") from e
        except UnicodeDecodeError as e:
            raise FileOperationError(
                f"Cannot decode file {resolved_path} with encoding {encoding}"
            ) from e
        except Exception as e:
            raise FileOperationError(f"Error reading file: {e}") from e
    
    async def write_file(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True
    ) -> str:
        """
        Write content to a file (or preview if dry_run is enabled).

        Args:
            path: Path to the file (relative to base_dir or absolute)
            content: Content to write
            encoding: File encoding (default: utf-8)
            create_dirs: If True, create parent directories if they don't exist

        Returns:
            Path of the written file (relative to base_dir)

        Raises:
            PathSecurityError: If path is outside base_dir
            FileOperationError: If file cannot be written
        """
        resolved_path = self._resolve_path(path)
        encoding = self._validate_encoding(encoding)

        # Determine operation type
        file_exists = resolved_path.exists()
        operation = "EDIT" if file_exists else "CREATE"

        if self._dry_run:
            # Preview only - don't write
            rel_path = resolved_path.relative_to(self._base_dir)
            preview = content[:200]
            if len(content) > 200:
                preview += "..."
            self._preview_log.append({
                "operation": operation,
                "path": str(rel_path),
                "content_length": len(content),
                "content_preview": preview,
            })

            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
            file_logger = logging.getLogger('multicode.files')
            file_logger.info(
                "[%s] INFO [DRY-RUN] %s File '%s' [%d chars]",
                timestamp, operation, rel_path, len(content)
            )

            return str(resolved_path.relative_to(self._base_dir))

        async with self._lock:
            try:
                # Create parent directories if needed
                if create_dirs and resolved_path.parent != self._base_dir:
                    resolved_path.parent.mkdir(parents=True, exist_ok=True)

                # Run in executor to avoid blocking
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: resolved_path.write_text(content, encoding=encoding)
                )

                return str(resolved_path.relative_to(self._base_dir))

            except PermissionError as e:
                raise FileOperationError(f"Permission denied: {resolved_path}") from e
            except OSError as e:
                raise FileOperationError(f"Error writing file: {e}") from e
    
    async def list_directory(self, path: str | Path = ".") -> DirectoryListing:
        """
        List contents of a directory.
        
        Args:
            path: Path to directory (relative to base_dir or absolute)
            
        Returns:
            DirectoryListing with entries, directories, and files
            
        Raises:
            PathSecurityError: If path is outside base_dir
            FileOperationError: If directory cannot be listed
        """
        resolved_path = self._resolve_path(path)
        
        try:
            loop = asyncio.get_event_loop()
            entries = await loop.run_in_executor(
                None,
                lambda: list(resolved_path.iterdir())
            )
            
            # Sort entries: directories first, then files
            dirs = []
            files = []
            
            for entry in sorted(entries, key=lambda x: x.name.lower()):
                try:
                    if entry.is_dir():
                        dirs.append(entry.name)
                    else:
                        files.append(entry.name)
                except (PermissionError, OSError):
                    # Skip entries we can't access
                    continue
            
            return DirectoryListing(
                path=str(resolved_path.relative_to(self._base_dir)),
                entries=dirs + files,
                directories=dirs,
                files=files
            )
            
        except NotADirectoryError as e:
            raise FileOperationError(f"Not a directory: {resolved_path}") from e
        except PermissionError as e:
            raise FileOperationError(f"Permission denied: {resolved_path}") from e
        except Exception as e:
            raise FileOperationError(f"Error listing directory: {e}") from e
    
    async def file_exists(self, path: str | Path) -> bool:
        """Check if a file exists."""
        try:
            resolved_path = self._resolve_path(path)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: resolved_path.exists()
            )
        except PathSecurityError:
            return False
    
    async def is_directory(self, path: str | Path) -> bool:
        """Check if a path is a directory."""
        try:
            resolved_path = self._resolve_path(path)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: resolved_path.is_dir()
            )
        except PathSecurityError:
            return False
    
    async def delete_file(self, path: str | Path) -> bool:
        """
        Delete a file.
        
        Args:
            path: Path to the file
            
        Returns:
            True if file was deleted, False if it didn't exist
            
        Raises:
            PathSecurityError: If path is outside base_dir
            FileOperationError: If file cannot be deleted
        """
        resolved_path = self._resolve_path(path)
        
        async with self._lock:
            try:
                loop = asyncio.get_event_loop()
                if resolved_path.exists():
                    await loop.run_in_executor(
                        None,
                        lambda: resolved_path.unlink()
                    )
                    return True
                return False
                
            except PermissionError as e:
                raise FileOperationError(f"Permission denied: {resolved_path}") from e
            except Exception as e:
                raise FileOperationError(f"Error deleting file: {e}") from e
    
    async def get_file_info(self, path: str | Path) -> dict:
        """
        Get information about a file.
        
        Returns:
            Dict with size, modified time, created time, etc.
        """
        resolved_path = self._resolve_path(path)
        
        try:
            loop = asyncio.get_event_loop()
            stat_info = await loop.run_in_executor(
                None,
                lambda: resolved_path.stat()
            )
            
            return {
                "path": str(resolved_path.relative_to(self._base_dir)),
                "size": stat_info.st_size,
                "modified": stat_info.st_mtime,
                "created": stat_info.st_ctime,
                "is_file": resolved_path.is_file(),
                "is_directory": resolved_path.is_dir(),
            }
            
        except FileNotFoundError as e:
            raise FileOperationError(f"File not found: {resolved_path}") from e
        except Exception as e:
            raise FileOperationError(f"Error getting file info: {e}") from e


# Global instance for convenience
_fs_tools: FileSystemTools | None = None


def get_filesystem_tools(base_dir: Path | None = None) -> FileSystemTools:
    """Get or create the global filesystem tools instance."""
    global _fs_tools
    if _fs_tools is None:
        _fs_tools = FileSystemTools(base_dir)
    return _fs_tools


# Convenience functions for direct use
async def read_file(path: str | Path, encoding: str = "utf-8") -> FileContent:
    """Read a file's contents."""
    return await get_filesystem_tools().read_file(path, encoding)


async def write_file(
    path: str | Path, 
    content: str, 
    encoding: str = "utf-8",
    create_dirs: bool = True
) -> str:
    """Write content to a file."""
    return await get_filesystem_tools().write_file(path, content, encoding, create_dirs)


async def list_directory(path: str | Path = ".") -> DirectoryListing:
    """List directory contents."""
    return await get_filesystem_tools().list_directory(path)
