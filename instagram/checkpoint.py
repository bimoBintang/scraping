"""
Algorithm 13: Smart Resume & Checkpoint System

Menyimpan checkpoint state secara periodik saat scraping. Jika proses terhenti
(error, mati listrik, restart), bisa dilanjutkan dari titik terakhir tanpa
mengulang dari awal.

Checkpoint file: .checkpoint/<username>.json
Format: atomic write (tmp → rename) untuk mencegah corruption.

Usage:
    from instagram.checkpoint import CheckpointManager

    cp = CheckpointManager()

    # Save checkpoint
    cp.save(CheckpointState(username="cristiano", cursor="QVF...", ...))

    # Resume
    state = cp.load("cristiano")
    if state and state.is_resumable():
        # continue from state.cursor
        ...

    # List all
    cp.print_status()
"""

import json
import os
import tempfile
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ==================== CHECKPOINT STATE ====================

@dataclass
class CheckpointState:
    """
    Serializable scraping state for resume capability.

    Stores everything needed to resume a streaming scrape:
    cursor position, counts, configuration, and timing.
    """

    # Identity
    username: str
    user_id: str = ""

    # Pagination state
    cursor: str = ""
    total_fetched: int = 0
    total_written: int = 0
    chunk_num: int = 0

    # Target config (so we know what to resume)
    target_count: int = 0
    fmt: str = "jsonl"
    output: str = "."
    chunk_size: int = 50
    filters: Dict[str, Any] = field(default_factory=dict)

    # Timing
    started_at: str = ""
    updated_at: str = ""
    elapsed_seconds: float = 0.0

    # Status
    status: str = "in_progress"  # in_progress, completed, failed
    error_message: str = ""

    # Version
    version: str = "1.9.0"

    def is_resumable(self) -> bool:
        """Can this checkpoint be resumed?"""
        return (
            self.status == "in_progress"
            and self.cursor != ""
            and self.total_fetched < self.target_count
        )

    def progress_pct(self) -> float:
        """Percentage complete"""
        if self.target_count <= 0:
            return 0.0
        return min(self.total_fetched / self.target_count * 100, 100.0)

    def remaining(self) -> int:
        """Posts remaining to fetch"""
        return max(0, self.target_count - self.total_fetched)

    def age_seconds(self) -> float:
        """Seconds since last update"""
        if not self.updated_at:
            return 0
        try:
            updated = datetime.fromisoformat(self.updated_at)
            return (datetime.now() - updated).total_seconds()
        except (ValueError, TypeError):
            return 0

    def age_human(self) -> str:
        """Human-readable age string"""
        secs = self.age_seconds()
        if secs < 60:
            return f"{secs:.0f}s ago"
        elif secs < 3600:
            return f"{secs / 60:.0f}m ago"
        elif secs < 86400:
            return f"{secs / 3600:.1f}h ago"
        else:
            return f"{secs / 86400:.1f}d ago"

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'CheckpointState':
        """Create CheckpointState from dict, ignoring unknown keys"""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ==================== CHECKPOINT MANAGER ====================

class CheckpointManager:
    """
    Manage checkpoint files for fault-tolerant scraping.

    Checkpoints are stored as JSON files in a directory.
    Uses atomic writes (write tmp → rename) to prevent corruption.
    """

    def __init__(self, checkpoint_dir: str = ".checkpoint"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _filepath(self, username: str) -> Path:
        """Get checkpoint file path for a username"""
        safe_name = username.replace('/', '_').replace('\\', '_')
        return self.checkpoint_dir / f"{safe_name}.json"

    def save(self, state: CheckpointState):
        """
        Save checkpoint atomically (tmp file → rename).

        This prevents corruption if the process is killed mid-write.
        """
        state.updated_at = datetime.now().isoformat()
        filepath = self._filepath(state.username)

        data = state.to_dict()

        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.checkpoint_dir),
            suffix='.tmp',
            prefix=f'{state.username}_',
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(filepath))
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def load(self, username: str) -> Optional[CheckpointState]:
        """
        Load checkpoint for a username.

        Returns:
            CheckpointState or None if no checkpoint exists
        """
        filepath = self._filepath(username)
        if not filepath.exists():
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return CheckpointState.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"  [!] Corrupt checkpoint for @{username}: {e}")
            return None

    def exists(self, username: str) -> bool:
        """Check if a checkpoint exists for this username"""
        return self._filepath(username).exists()

    def delete(self, username: str) -> bool:
        """Delete checkpoint for a username"""
        filepath = self._filepath(username)
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def mark_completed(self, username: str):
        """Mark a checkpoint as completed (keeps file for reference)"""
        state = self.load(username)
        if state:
            state.status = "completed"
            state.updated_at = datetime.now().isoformat()
            self.save(state)

    def mark_failed(self, username: str, error: str = ""):
        """Mark a checkpoint as failed"""
        state = self.load(username)
        if state:
            state.status = "failed"
            state.error_message = error
            state.updated_at = datetime.now().isoformat()
            self.save(state)

    def list_all(self) -> List[CheckpointState]:
        """List all checkpoint states"""
        states = []
        for filepath in sorted(self.checkpoint_dir.glob("*.json")):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                states.append(CheckpointState.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue
        return states

    def list_resumable(self) -> List[CheckpointState]:
        """List only resumable checkpoints"""
        return [s for s in self.list_all() if s.is_resumable()]

    def print_status(self):
        """Print formatted table of all checkpoints"""
        states = self.list_all()

        if not states:
            print("\n  📋 No checkpoints found.")
            return

        # Status icons
        status_icon = {
            'in_progress': '🔄',
            'completed': '✅',
            'failed': '❌',
        }

        print(f"\n  📋 Checkpoint Status ({len(states)} total)")
        print(f"  {'─' * 75}")
        print(f"  {'Username':<20} {'Status':<14} {'Progress':<15} {'Fetched':<10} {'Updated':<12}")
        print(f"  {'─' * 75}")

        for s in states:
            icon = status_icon.get(s.status, '❓')
            pct = f"{s.progress_pct():.1f}%"
            bar_len = int(s.progress_pct() / 10)
            bar = f"{'█' * bar_len}{'░' * (10 - bar_len)}"
            fetched = f"{s.total_fetched}/{s.target_count}"
            age = s.age_human()

            print(f"  @{s.username:<19} {icon} {s.status:<10} [{bar}] {pct:<5} {fetched:<10} {age}")

        print(f"  {'─' * 75}")

        resumable = [s for s in states if s.is_resumable()]
        if resumable:
            print(f"\n  💡 {len(resumable)} checkpoint(s) can be resumed with --resume")
