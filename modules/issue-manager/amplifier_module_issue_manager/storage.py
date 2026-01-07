"""Storage layer with defensive file I/O for issue data."""

import json
import logging
import time
from pathlib import Path
from typing import Any

from .models import Dependency
from .models import Issue
from .models import IssueEvent

logger = logging.getLogger(__name__)


class Storage:
    """JSONL-based storage with defensive file I/O.

    Implements retry logic for cloud-synced filesystems (OneDrive, Dropbox, etc.).
    """

    def __init__(self, data_dir: Path):
        """Initialize storage.

        Args:
            data_dir: Directory for JSONL files
        """
        self.data_dir = data_dir
        self.issues_file = data_dir / "issues.jsonl"
        self.deps_file = data_dir / "dependencies.jsonl"
        self.events_file = data_dir / "events.jsonl"

    def load_issues(self) -> list[Issue]:
        """Load all issues from JSONL file.

        Returns:
            List of Issue objects
        """
        if not self.issues_file.exists():
            return []

        issues = []
        for line in self._read_jsonl(self.issues_file):
            issues.append(Issue.from_dict(line))
        return issues

    def load_dependencies(self) -> list[Dependency]:
        """Load all dependencies from JSONL file.

        Returns:
            List of Dependency objects
        """
        if not self.deps_file.exists():
            return []

        deps = []
        for line in self._read_jsonl(self.deps_file):
            deps.append(Dependency.from_dict(line))
        return deps

    def load_events(self) -> list[IssueEvent]:
        """Load all events from JSONL file.

        Returns:
            List of IssueEvent objects
        """
        if not self.events_file.exists():
            return []

        events = []
        for line in self._read_jsonl(self.events_file):
            events.append(IssueEvent.from_dict(line))
        return events

    def save_issues(self, issues: list[Issue]) -> None:
        """Save all issues to JSONL file.

        Args:
            issues: List of Issue objects to save
        """
        data = [issue.to_dict() for issue in issues]
        self._write_jsonl(self.issues_file, data)

    def save_dependencies(self, deps: list[Dependency]) -> None:
        """Save all dependencies to JSONL file.

        Args:
            deps: List of Dependency objects to save
        """
        data = [dep.to_dict() for dep in deps]
        self._write_jsonl(self.deps_file, data)

    def append_event(self, event: IssueEvent) -> None:
        """Append an event to the events file.

        Args:
            event: IssueEvent to append
        """
        self._append_jsonl(self.events_file, event.to_dict())

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        """Read JSONL file with retry logic.

        Args:
            path: Path to JSONL file

        Returns:
            List of parsed JSON objects
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with open(path, encoding="utf-8") as f:
                    return [json.loads(line) for line in f if line.strip()]
            except OSError as e:
                if e.errno == 5 and attempt < max_retries - 1:
                    if attempt == 0:
                        logger.warning(
                            f"File I/O error reading {path} - retrying. "
                            "This may be due to cloud-synced files (OneDrive, Dropbox, etc.). "
                            "If using cloud sync, consider enabling 'Always keep on this device' "
                            f"for the data folder: {path.parent}"
                        )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

        return []

    def _write_jsonl(self, path: Path, data: list[dict[str, Any]]) -> None:
        """Write JSONL file with retry logic.

        Args:
            path: Path to JSONL file
            data: List of dicts to write as JSONL
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    for item in data:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    f.flush()
                return
            except OSError as e:
                if e.errno == 5 and attempt < max_retries - 1:
                    if attempt == 0:
                        logger.warning(
                            f"File I/O error writing to {path} - retrying. "
                            "This may be due to cloud-synced files (OneDrive, Dropbox, etc.). "
                            "If using cloud sync, consider enabling 'Always keep on this device' "
                            f"for the data folder: {path.parent}"
                        )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

    def _append_jsonl(self, path: Path, item: dict[str, Any]) -> None:
        """Append to JSONL file with retry logic.

        Args:
            path: Path to JSONL file
            item: Dict to append as JSON line
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    f.flush()
                return
            except OSError as e:
                if e.errno == 5 and attempt < max_retries - 1:
                    if attempt == 0:
                        logger.warning(
                            f"File I/O error appending to {path} - retrying. "
                            "This may be due to cloud-synced files (OneDrive, Dropbox, etc.). "
                            "If using cloud sync, consider enabling 'Always keep on this device' "
                            f"for the data folder: {path.parent}"
                        )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
