"""
Algorithm 12: Memory-Efficient Streaming Parser for Large Dataset

Untuk scraping skala besar (jutaan postingan), data diproses chunk-by-chunk
dan langsung di-stream ke file atau database tanpa menyimpan semua di memory.

Pipeline:
  Fetch batch → ChunkProcessor (filter + transform) → StreamWriter (sink)
  Repeat until done. Each chunk is discarded after writing.

Supported sinks:
  - JSONL  (one JSON object per line, appendable)
  - CSV    (auto-header on first chunk)
  - SQLite (INSERT batch, auto-create table)
  - MongoDB (insert_many via pymongo, optional)

Usage:
    from instagram.streaming_parser import StreamOrchestrator

    orch = StreamOrchestrator(client)
    orch.run(
        usernames=["<username>"],
        count=100000,
        output="output/<username>.jsonl",
        fmt="jsonl",
        filters={"min_likes": 100},
    )
"""

import csv
import gc
import json
import os
import resource
import sqlite3
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import InstagramPost


# ==================== MEMORY MONITOR ====================

class MemoryMonitor:
    """
    Track RSS memory usage and trigger GC when approaching limit.

    Uses resource.getrusage() on macOS/Linux for accurate RSS.
    """

    def __init__(self, warn_mb: float = 500.0, limit_mb: float = 1000.0):
        self.warn_mb = warn_mb
        self.limit_mb = limit_mb
        self.peak_mb = 0.0
        self._start_mb = self.current_rss_mb()
        self._chunk_history: List[float] = []

    def current_rss_mb(self) -> float:
        """Get current RSS memory in MB"""
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # macOS reports in bytes, Linux in KB
        if sys.platform == 'darwin':
            return usage.ru_maxrss / (1024 * 1024)
        return usage.ru_maxrss / 1024

    def check(self, chunk_num: int) -> bool:
        """
        Check memory after processing a chunk.

        Returns:
            True if safe to continue, False if limit exceeded
        """
        current = self.current_rss_mb()
        self.peak_mb = max(self.peak_mb, current)
        self._chunk_history.append(current)

        if current >= self.limit_mb:
            print(f"\n  [🚨] Memory LIMIT exceeded: {current:.1f} MB >= {self.limit_mb:.1f} MB")
            self._force_gc()
            current_after = self.current_rss_mb()
            if current_after >= self.limit_mb:
                print(f"  [!] Still over limit after GC: {current_after:.1f} MB — stopping")
                return False

        elif current >= self.warn_mb:
            print(f"\n  [⚠️] Memory WARNING: {current:.1f} MB (limit: {self.limit_mb:.1f} MB)")
            self._force_gc()

        return True

    def _force_gc(self):
        """Force garbage collection"""
        collected = gc.collect()
        if collected > 0:
            print(f"  [GC] Collected {collected} objects")

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        current = self.current_rss_mb()
        return {
            'current_mb': round(current, 1),
            'peak_mb': round(self.peak_mb, 1),
            'start_mb': round(self._start_mb, 1),
            'delta_mb': round(current - self._start_mb, 1),
            'chunks_tracked': len(self._chunk_history),
        }

    def print_stats(self):
        """Print memory usage summary"""
        stats = self.get_stats()
        print(f"\n  📊 Memory Stats:")
        print(f"    Start:   {stats['start_mb']:.1f} MB")
        print(f"    Current: {stats['current_mb']:.1f} MB")
        print(f"    Peak:    {stats['peak_mb']:.1f} MB")
        print(f"    Delta:   +{stats['delta_mb']:.1f} MB")
        print(f"    Chunks:  {stats['chunks_tracked']}")


# ==================== STREAM WRITERS (Sinks) ====================

class StreamWriter(ABC):
    """Abstract base class for streaming data sinks."""

    def __init__(self):
        self.total_written = 0

    @abstractmethod
    def open(self):
        """Open the writer / establish connection"""
        pass

    @abstractmethod
    def write_chunk(self, chunk: List[Dict]):
        """Write a batch of records"""
        pass

    @abstractmethod
    def close(self):
        """Flush and close the writer"""
        pass

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class JsonlStreamWriter(StreamWriter):
    """
    Write records as JSON Lines (one JSON object per line).

    Ideal for large datasets — appendable, streamable, grep-friendly.
    """

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        self._file = None

    def open(self):
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filepath, 'a', encoding='utf-8')
        print(f"  [📝] JSONL writer → {self.filepath}")

    def write_chunk(self, chunk: List[Dict]):
        for record in chunk:
            self._file.write(json.dumps(record, ensure_ascii=False) + '\n')
        self._file.flush()
        self.total_written += len(chunk)

    def close(self):
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None


class CsvStreamWriter(StreamWriter):
    """
    Write records as CSV with auto-header on first chunk.

    Flattens nested dicts and lists for CSV compatibility.
    """

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        self._file = None
        self._writer = None
        self._header_written = False

    def open(self):
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
        file_exists = Path(self.filepath).exists() and Path(self.filepath).stat().st_size > 0
        self._file = open(self.filepath, 'a', newline='', encoding='utf-8')
        self._header_written = file_exists
        print(f"  [📝] CSV writer → {self.filepath}")

    def write_chunk(self, chunk: List[Dict]):
        if not chunk:
            return

        flat_chunk = [self._flatten(record) for record in chunk]

        if not self._header_written:
            self._writer = csv.DictWriter(self._file, fieldnames=flat_chunk[0].keys())
            self._writer.writeheader()
            self._header_written = True
        elif self._writer is None:
            self._writer = csv.DictWriter(self._file, fieldnames=flat_chunk[0].keys())

        self._writer.writerows(flat_chunk)
        self._file.flush()
        self.total_written += len(chunk)

    def close(self):
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None

    @staticmethod
    def _flatten(record: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flatten nested dicts/lists for CSV compatibility"""
        items = {}
        for k, v in record.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(CsvStreamWriter._flatten(v, new_key, sep))
            elif isinstance(v, list):
                items[new_key] = '; '.join(str(x) for x in v)
            else:
                items[new_key] = v
        return items


class SqliteStreamWriter(StreamWriter):
    """
    Write records to SQLite database using batch INSERTs.

    Auto-creates table from first chunk's keys.
    """

    def __init__(self, filepath: str, table_name: str = 'posts'):
        super().__init__()
        self.filepath = filepath
        self.table_name = table_name
        self._conn = None
        self._table_created = False

    def open(self):
        Path(self.filepath).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.filepath)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        print(f"  [📝] SQLite writer → {self.filepath} (table: {self.table_name})")

    def write_chunk(self, chunk: List[Dict]):
        if not chunk:
            return

        flat_chunk = [self._serialize_values(record) for record in chunk]

        if not self._table_created:
            self._create_table(flat_chunk[0])
            self._table_created = True

        columns = list(flat_chunk[0].keys())
        placeholders = ', '.join(['?'] * len(columns))
        col_names = ', '.join(f'"{c}"' for c in columns)
        sql = f'INSERT OR IGNORE INTO "{self.table_name}" ({col_names}) VALUES ({placeholders})'

        rows = [tuple(r.get(c) for c in columns) for r in flat_chunk]
        self._conn.executemany(sql, rows)
        self._conn.commit()
        self.total_written += len(chunk)

    def close(self):
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def _create_table(self, sample: Dict):
        """Auto-create table from first record's keys"""
        columns = []
        for key, value in sample.items():
            if isinstance(value, int):
                col_type = "INTEGER"
            elif isinstance(value, float):
                col_type = "REAL"
            else:
                col_type = "TEXT"
            columns.append(f'"{key}" {col_type}')

        sql = f'CREATE TABLE IF NOT EXISTS "{self.table_name}" ({", ".join(columns)})'
        self._conn.execute(sql)
        self._conn.commit()

    @staticmethod
    def _serialize_values(record: Dict) -> Dict:
        """Convert lists/dicts to JSON strings for SQLite"""
        serialized = {}
        for k, v in record.items():
            if isinstance(v, (dict, list)):
                serialized[k] = json.dumps(v, ensure_ascii=False)
            else:
                serialized[k] = v
        return serialized


class MongoStreamWriter(StreamWriter):
    """
    Write records to MongoDB using batch insert_many.

    Requires pymongo: pip install pymongo
    """

    def __init__(
        self,
        mongo_uri: str = "mongodb://localhost:27017",
        db_name: str = "instascope",
        collection_name: str = "posts",
    ):
        super().__init__()
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def open(self):
        try:
            import pymongo
        except ImportError:
            raise ImportError(
                "pymongo required for MongoDB sink. Install: pip install pymongo"
            )

        self._client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
        # Test connection
        self._client.server_info()
        db = self._client[self.db_name]
        self._collection = db[self.collection_name]

        # Create index on shortcode for dedup
        self._collection.create_index("shortcode", unique=True, sparse=True)

        print(f"  [📝] MongoDB writer → {self.mongo_uri}/{self.db_name}.{self.collection_name}")

    def write_chunk(self, chunk: List[Dict]):
        if not chunk or self._collection is None:
            return

        import pymongo

        try:
            self._collection.insert_many(chunk, ordered=False)
        except pymongo.errors.BulkWriteError:
            # Some duplicates — fine, skip silently
            pass

        self.total_written += len(chunk)

    def close(self):
        if self._client:
            self._client.close()
            self._client = None


# ==================== CHUNK PROCESSOR ====================

class ChunkProcessor:
    """
    Process each chunk: apply filters and transforms before writing.

    Pluggable filters (return True to keep) and transforms (modify in-place).
    """

    def __init__(self):
        self._filters: List[Callable[[Dict], bool]] = []
        self._transforms: List[Callable[[Dict], Dict]] = []
        self.total_input = 0
        self.total_output = 0
        self.total_filtered = 0

    def add_filter(self, fn: Callable[[Dict], bool], name: str = ""):
        """Add a filter function. Return True to keep the record."""
        fn._filter_name = name  # type: ignore
        self._filters.append(fn)

    def add_transform(self, fn: Callable[[Dict], Dict], name: str = ""):
        """Add a transform function. Modifies record in-place."""
        fn._transform_name = name  # type: ignore
        self._transforms.append(fn)

    def process(self, chunk: List[Dict]) -> List[Dict]:
        """Apply all filters and transforms to a chunk"""
        self.total_input += len(chunk)

        # Apply filters
        filtered = []
        for record in chunk:
            keep = all(f(record) for f in self._filters)
            if keep:
                filtered.append(record)

        self.total_filtered += (len(chunk) - len(filtered))

        # Apply transforms
        for record in filtered:
            for transform in self._transforms:
                record = transform(record)

        self.total_output += len(filtered)
        return filtered

    def get_stats(self) -> Dict:
        return {
            'total_input': self.total_input,
            'total_output': self.total_output,
            'total_filtered': self.total_filtered,
            'filter_rate': (
                f"{self.total_filtered / self.total_input:.1%}"
                if self.total_input > 0 else "0%"
            ),
        }


# ==================== BUILT-IN FILTERS ====================

def filter_min_likes(min_likes: int) -> Callable[[Dict], bool]:
    """Keep posts with at least min_likes"""
    def _filter(record: Dict) -> bool:
        return record.get('likes', 0) >= min_likes
    _filter._filter_name = f"min_likes>={min_likes}"  # type: ignore
    return _filter


def filter_has_location(record: Dict) -> bool:
    """Keep posts that have location data"""
    loc = record.get('location')
    return loc is not None and loc != {}


def filter_has_caption(record: Dict) -> bool:
    """Keep posts with non-empty caption"""
    return bool(record.get('caption', '').strip())


def filter_date_range(start_ts: int = 0, end_ts: int = 0) -> Callable[[Dict], bool]:
    """Keep posts within timestamp range"""
    def _filter(record: Dict) -> bool:
        ts = record.get('timestamp', 0)
        if start_ts and ts < start_ts:
            return False
        if end_ts and ts > end_ts:
            return False
        return True
    return _filter


# ==================== STREAMING POST FETCHER ====================

class StreamingPostFetcher:
    """
    Fetch posts chunk-by-chunk and stream to a writer.

    Never holds more than 1 batch in memory at a time.
    Integrates with ChunkProcessor for filtering/transforms.
    """

    def __init__(self, client):
        self.client = client

    def stream_posts(
        self,
        username: str,
        count: int,
        writer: StreamWriter,
        processor: Optional[ChunkProcessor] = None,
        monitor: Optional[MemoryMonitor] = None,
        chunk_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Stream posts for a user to a writer, chunk by chunk.

        Args:
            username: Instagram username
            count: Total posts to fetch
            writer: StreamWriter sink
            processor: Optional ChunkProcessor for filtering
            monitor: Optional MemoryMonitor for RSS tracking
            chunk_size: Batch size per fetch (max 50)

        Returns:
            Stats dict with totals and timing
        """
        print(f"\n  [🔄] Streaming {count} posts for @{username}...")

        # Get user_id first
        profile = self.client.get_profile(username)
        if not profile or not profile.user_id:
            print("  [!] Could not get user_id")
            return {'error': 'no_user_id', 'fetched': 0}

        chunk_size = min(chunk_size, 50)
        cursor = ""
        total_fetched = 0
        total_written = 0
        chunk_num = 0
        start_time = time.time()

        while total_fetched < count:
            fetch_count = min(chunk_size, count - total_fetched)

            # Fetch one batch
            batch = self.client._fetch_posts_batch(
                profile.user_id,
                cursor=cursor,
                count=fetch_count,
            )

            if not batch:
                break

            posts, pagination = batch
            chunk_num += 1

            # Convert to dicts immediately (frees InstagramPost objects)
            records = [p.to_dict() for p in posts]
            records_for_write = records  # will be reassigned after processing
            del posts  # free the original list

            # Apply processor (filter + transform)
            if processor:
                records_for_write = processor.process(records)

            # Write to sink
            if records_for_write:
                writer.write_chunk(records_for_write)
                total_written += len(records_for_write)

            total_fetched += len(records)

            # Progress
            pct = min(total_fetched / count * 100, 100)
            elapsed = time.time() - start_time
            rate = total_fetched / elapsed if elapsed > 0 else 0
            eta = (count - total_fetched) / rate if rate > 0 else 0

            sys.stdout.write(
                f"\r  [{'█' * int(pct // 5)}{'░' * (20 - int(pct // 5))}] "
                f"{pct:5.1f}% | {total_fetched}/{count} fetched | "
                f"{total_written} written | {rate:.0f}/s | ETA {eta:.0f}s"
            )
            sys.stdout.flush()

            # Memory check
            if monitor and not monitor.check(chunk_num):
                print("\n  [!] Stopping due to memory limit")
                break

            # Free chunk memory
            del records
            del records_for_write

            # Pagination
            if not pagination.get('has_next_page'):
                break
            cursor = pagination.get('end_cursor', '')

            # Rate limiting
            from .utils import smart_delay
            smart_delay(1.5, 3.0)

        elapsed = time.time() - start_time
        print(f"\n  [✓] Done: {total_fetched} fetched, {total_written} written "
              f"in {elapsed:.1f}s")

        return {
            'username': username,
            'total_fetched': total_fetched,
            'total_written': total_written,
            'chunks': chunk_num,
            'elapsed_seconds': round(elapsed, 1),
            'rate_per_second': round(total_fetched / elapsed, 1) if elapsed > 0 else 0,
        }


# ==================== STREAM ORCHESTRATOR (Entry Point) ====================

class StreamOrchestrator:
    """
    Orchestrate streaming scrape for one or more usernames.

    Usage:
        orch = StreamOrchestrator(client)
        orch.run(["cristiano", "leomessi"], count=10000, fmt="jsonl")
    """

    FORMATS = ('jsonl', 'csv', 'sqlite', 'mongodb')

    def __init__(self, client):
        self.client = client
        self.fetcher = StreamingPostFetcher(client)

    def run(
        self,
        usernames: List[str],
        count: int = 1000,
        fmt: str = "jsonl",
        output: str = ".",
        chunk_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
        mongo_uri: str = "mongodb://localhost:27017",
        mongo_db: str = "instascope",
        memory_limit_mb: float = 1000.0,
    ) -> Dict[str, Any]:
        """
        Run the streaming pipeline.

        Args:
            usernames: List of Instagram usernames
            count: Posts to fetch per user
            fmt: Output format (jsonl, csv, sqlite, mongodb)
            output: Output directory or file path
            chunk_size: Batch size per chunk
            filters: Filter config dict (min_likes, has_location, etc.)
            mongo_uri: MongoDB connection URI
            mongo_db: MongoDB database name
            memory_limit_mb: Memory limit in MB

        Returns:
            Combined stats for all usernames
        """
        print(f"\n{'='*60}")
        print(f"  📦 Streaming Parser — {fmt.upper()} mode")
        print(f"  Users: {len(usernames)}, Count: {count}/user, Chunk: {chunk_size}")
        print(f"{'='*60}")

        monitor = MemoryMonitor(
            warn_mb=memory_limit_mb * 0.7,
            limit_mb=memory_limit_mb,
        )

        # Build processor with filters
        processor = self._build_processor(filters)

        all_stats = []
        start_total = time.time()

        for username in usernames:
            username = username.lstrip('@').strip()

            # Create writer for this user
            writer = self._create_writer(
                fmt, output, username, mongo_uri, mongo_db,
            )

            with writer:
                stats = self.fetcher.stream_posts(
                    username=username,
                    count=count,
                    writer=writer,
                    processor=processor,
                    monitor=monitor,
                    chunk_size=chunk_size,
                )
                stats['sink'] = fmt
                all_stats.append(stats)

        total_elapsed = time.time() - start_total

        # Print summary
        self._print_summary(all_stats, processor, monitor, total_elapsed)

        return {
            'users': all_stats,
            'total_elapsed': round(total_elapsed, 1),
            'memory': monitor.get_stats(),
            'processor': processor.get_stats() if processor else {},
        }

    def _create_writer(
        self,
        fmt: str,
        output: str,
        username: str,
        mongo_uri: str,
        mongo_db: str,
    ) -> StreamWriter:
        """Create the appropriate StreamWriter"""
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        if fmt == 'jsonl':
            return JsonlStreamWriter(str(output_dir / f"{username}_posts.jsonl"))
        elif fmt == 'csv':
            return CsvStreamWriter(str(output_dir / f"{username}_posts.csv"))
        elif fmt == 'sqlite':
            return SqliteStreamWriter(
                str(output_dir / f"{username}_posts.db"),
                table_name='posts',
            )
        elif fmt == 'mongodb':
            return MongoStreamWriter(
                mongo_uri=mongo_uri,
                db_name=mongo_db,
                collection_name=f"{username}_posts",
            )
        else:
            raise ValueError(f"Unknown format: {fmt}. Use: {self.FORMATS}")

    def _build_processor(self, filters: Optional[Dict]) -> ChunkProcessor:
        """Build ChunkProcessor from filter config"""
        processor = ChunkProcessor()

        if not filters:
            return processor

        if 'min_likes' in filters:
            processor.add_filter(
                filter_min_likes(filters['min_likes']),
                f"min_likes>={filters['min_likes']}",
            )

        if filters.get('has_location'):
            processor.add_filter(filter_has_location, "has_location")

        if filters.get('has_caption'):
            processor.add_filter(filter_has_caption, "has_caption")

        if 'start_ts' in filters or 'end_ts' in filters:
            processor.add_filter(
                filter_date_range(
                    filters.get('start_ts', 0),
                    filters.get('end_ts', 0),
                ),
                "date_range",
            )

        return processor

    @staticmethod
    def _print_summary(
        stats: List[Dict],
        processor: ChunkProcessor,
        monitor: MemoryMonitor,
        total_elapsed: float,
    ):
        """Print final streaming summary"""
        total_fetched = sum(s.get('total_fetched', 0) for s in stats)
        total_written = sum(s.get('total_written', 0) for s in stats)
        total_chunks = sum(s.get('chunks', 0) for s in stats)

        print(f"""
╔══════════════════════════════════════════════════════════════╗
║   📦 Streaming Parser — Summary                             ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Total Fetched:  {total_fetched:<8}                                   ║
║  Total Written:  {total_written:<8}                                   ║
║  Total Chunks:   {total_chunks:<8}                                   ║
║  Total Time:     {total_elapsed:<6.1f}s                                  ║
║  Throughput:     {total_fetched / total_elapsed if total_elapsed > 0 else 0:<6.1f} posts/s                            ║
║                                                              ║""")

        # Processor stats
        p = processor.get_stats()
        if p['total_filtered'] > 0:
            print(f"║  Filtered Out:   {p['total_filtered']:<8} ({p['filter_rate']})                     ║")

        # Memory stats
        mem = monitor.get_stats()
        print(f"║  Peak Memory:    {mem['peak_mb']:.1f} MB                                ║")
        print(f"║  Memory Delta:   +{mem['delta_mb']:.1f} MB                               ║")

        print(f"║                                                              ║")
        print(f"╚══════════════════════════════════════════════════════════════╝")

        # Per-user breakdown
        if len(stats) > 1:
            print(f"\n  Per-user breakdown:")
            for s in stats:
                print(f"    @{s.get('username', '?')}: {s.get('total_fetched', 0)} fetched, "
                      f"{s.get('total_written', 0)} written in {s.get('elapsed_seconds', 0)}s")
