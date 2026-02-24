"""Tests for GDPVal Data Loader

Usage:
    pytest                          # mock only (CI default)
    pytest -m integration           # real HF API + download (needs HF_TOKEN)
    pytest -m ""                    # all tests
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from core.data_loader import GDPValDataLoader, GDPValTask
from core.config import (
    DATASET_ID,
    EXPECTED_TASK_COUNT,
    EXPECTED_SECTOR_COUNT,
    EXPECTED_SECTORS,
    EXPECTED_SECTOR_DISTRIBUTION,
    HF_DATASET_URI_PREFIX,
)


@pytest.fixture
def temp_local_path(tmp_path):
    """Create temporary directory for local snapshot"""
    return tmp_path / "test-snapshot"


@pytest.fixture
def mock_dataset():
    """Create mock dataset with EXPECTED_TASK_COUNT tasks"""
    mock_data = []
    for i in range(EXPECTED_TASK_COUNT):
        mock_data.append({
            'task_id': f'task_{i:03d}',
            'occupation': f'Occupation_{i % 10}',
            'sector': f'Sector_{i % 5}',
            'prompt': f'Prompt for task {i}',
            'reference_files': [f'file_{i}.pdf'],
            'reference_file_urls': [f'https://example.com/file_{i}.pdf'],
            'reference_file_hf_uris': [f'{HF_DATASET_URI_PREFIX}/file_{i}.pdf'],
            'deliverable_text': f'Deliverable text for task {i}',
            'deliverable_files': [f'deliverable_{i}.pdf', f'deliverable_{i}.xlsx'],
        })

    # Create mock dataset object
    mock_ds = MagicMock()
    mock_ds.__getitem__ = Mock(return_value={'train': mock_data})
    mock_ds.__len__ = Mock(return_value=EXPECTED_TASK_COUNT)
    mock_ds.save_to_disk = Mock()

    return mock_ds


class TestGDPValDataLoader:
    """Test suite for GDPValDataLoader"""

    def test_init_default_path(self):
        """Test initialization with default path"""
        loader = GDPValDataLoader()
        assert loader.local_path.name == "gdpval-local"
        assert loader.local_path.parent.name == "data"
        assert loader.local_path.is_absolute()
        assert loader.auto_download is True

    def test_init_custom_path(self, temp_local_path):
        """Test initialization with custom path"""
        loader = GDPValDataLoader(local_path=str(temp_local_path))
        assert loader.local_path == temp_local_path

    def test_init_auto_download_false(self):
        """Test initialization with auto_download=False"""
        loader = GDPValDataLoader(auto_download=False)
        assert loader.auto_download is False

    def test_download_snapshot_creates_directory(self, temp_local_path, mock_dataset):
        """Test that download_snapshot creates local directory"""
        loader = GDPValDataLoader(local_path=str(temp_local_path))

        with patch('prepare_dataset.snapshot_download'):
            with patch('prepare_dataset.load_dataset', return_value=mock_dataset):
                with patch.object(GDPValDataLoader, '_add_deliverable_columns', return_value=mock_dataset):
                    with patch.object(mock_dataset, 'save_to_disk'):
                        result = loader.download_snapshot()

                        assert result == temp_local_path
                        assert temp_local_path.parent.exists()

    def test_download_snapshot_skip_if_exists(self, temp_local_path):
        """Test that download_snapshot skips if valid snapshot exists"""
        temp_local_path.mkdir(parents=True)
        # Create marker file so it looks like a valid snapshot
        (temp_local_path / "dataset_dict.json").write_text("{}")
        loader = GDPValDataLoader(local_path=str(temp_local_path))

        # Should not call load_dataset
        with patch('prepare_dataset.load_dataset') as mock_load:
            result = loader.download_snapshot(force=False)

            assert result == temp_local_path
            mock_load.assert_not_called()

    def test_download_snapshot_force_overwrite(self, temp_local_path, mock_dataset):
        """Test that download_snapshot overwrites with force=True"""
        temp_local_path.mkdir(parents=True)
        (temp_local_path / "old_file.txt").touch()

        loader = GDPValDataLoader(local_path=str(temp_local_path))

        with patch('prepare_dataset.snapshot_download'):
            with patch('prepare_dataset.load_dataset', return_value=mock_dataset):
                with patch.object(GDPValDataLoader, '_add_deliverable_columns', return_value=mock_dataset):
                    with patch.object(mock_dataset, 'save_to_disk'):
                        result = loader.download_snapshot(force=True)

                        assert result == temp_local_path

    def test_load_raises_error_when_no_snapshot_and_no_auto_download(self, temp_local_path):
        """Test that load() raises error when snapshot doesn't exist and auto_download=False"""
        loader = GDPValDataLoader(local_path=str(temp_local_path), auto_download=False)

        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load()

        assert "Local snapshot not found" in str(exc_info.value)
        assert "download()" in str(exc_info.value)

    def test_parse_task_with_all_fields(self):
        """Test _parse_task with all fields present"""
        loader = GDPValDataLoader()
        row = {
            'task_id': 'test_001',
            'occupation': 'Engineer',
            'sector': 'Finance',
            'prompt': 'Do something',
            'reference_files': ['file1.pdf'],
            'reference_file_urls': ['https://example.com/file1.pdf'],
            'reference_file_hf_uris': [f'{HF_DATASET_URI_PREFIX}/file1.pdf'],
            'deliverable_text': 'Expected output',
            'deliverable_files': ['output.pdf'],
        }

        task = loader._parse_task(row)

        assert task.task_id == 'test_001'
        assert task.occupation == 'Engineer'
        assert task.sector == 'Finance'
        assert task.deliverable_text == 'Expected output'
        assert task.deliverable_files == ['output.pdf']

    def test_parse_task_handles_missing_fields(self):
        """Test _parse_task handles missing optional fields"""
        loader = GDPValDataLoader()
        row = {
            'task_id': 'test_001',
            'occupation': 'Engineer',
            'sector': 'Tech',
            'prompt': 'Do something',
        }

        task = loader._parse_task(row)

        assert task.reference_files == []
        assert task.reference_file_urls == []
        assert task.reference_file_hf_uris == []
        assert task.deliverable_text == ''
        assert task.deliverable_files == []

    def test_get_snapshot_info_when_not_exists(self, temp_local_path):
        """Test get_snapshot_info when snapshot doesn't exist"""
        loader = GDPValDataLoader(local_path=str(temp_local_path))
        info = loader.get_snapshot_info()

        assert info['exists'] is False
        assert info['path'] == str(temp_local_path)
        assert info['size_mb'] == 0
        assert info['dataset_id'] == DATASET_ID

    def test_get_snapshot_info_when_exists(self, temp_local_path):
        """Test get_snapshot_info when valid snapshot exists"""
        temp_local_path.mkdir(parents=True)
        # Create marker file to simulate valid snapshot
        (temp_local_path / "dataset_dict.json").write_text("{}")
        # Write file with actual content (not empty)
        (temp_local_path / "test_file.txt").write_bytes(b"test content" * 1000)

        loader = GDPValDataLoader(local_path=str(temp_local_path))
        info = loader.get_snapshot_info()

        assert info['exists'] is True
        assert info['valid'] is True
        assert info['size_mb'] > 0


class TestGDPValTask:
    """Test suite for GDPValTask dataclass"""

    def test_task_creation_with_all_fields(self):
        """Test that GDPValTask can be created with all fields"""
        task = GDPValTask(
            task_id='test_001',
            occupation='Engineer',
            sector='Finance',
            prompt='Calculate something',
            reference_files=['data.csv'],
            reference_file_urls=['https://example.com/data.csv'],
            reference_file_hf_uris=[f'{HF_DATASET_URI_PREFIX}/data.csv'],
            deliverable_text='Expected output',
            deliverable_files=['output.pdf'],
        )

        assert task.task_id == 'test_001'
        assert task.occupation == 'Engineer'
        assert task.sector == 'Finance'
        assert task.deliverable_text == 'Expected output'
        assert task.deliverable_files == ['output.pdf']


# ─── Integration Tests (실제 HuggingFace 연결) ───────────────────────────

@pytest.mark.integration
class TestGDPValDataLoaderIntegration:
    """실제 HuggingFace API를 사용하는 통합 테스트

    실행 전:
        export HF_TOKEN="hf_xxxxxxxxxxxx"
        pytest -m integration -v

    주의: 첫 실행 시 ~100MB 다운로드
    """

    @pytest.fixture(scope="class")
    def real_snapshot_path(self, tmp_path_factory):
        """Create temporary path for real snapshot (shared across tests)"""
        return tmp_path_factory.mktemp("gdpval-snapshot")

    @pytest.fixture(scope="class")
    def real_loader(self, real_snapshot_path):
        """Create loader with real snapshot download"""
        loader = GDPValDataLoader(local_path=str(real_snapshot_path))
        return loader

    @pytest.fixture(scope="class")
    def real_tasks(self, real_loader):
        """Download and load real tasks (cached for all tests)"""
        print("\n📥 Downloading real GDPVal snapshot (first time only)...")
        tasks = real_loader.load()
        return tasks

    def test_real_download_snapshot(self, real_loader, real_snapshot_path):
        """실제 데이터셋 다운로드 테스트"""
        result = real_loader.download_snapshot()
        assert result == real_snapshot_path
        assert real_snapshot_path.exists()

        # Check snapshot info
        info = real_loader.get_snapshot_info()
        assert info['exists'] is True
        assert info['size_mb'] > 0
        print(f"\n  Snapshot size: {info['size_mb']:.2f} MB")

    def test_real_load_returns_220_tasks(self, real_tasks):
        """실제 데이터셋에서 220개 태스크 로드 확인"""
        assert len(real_tasks) == EXPECTED_TASK_COUNT

        # Print occupation categories
        categories = {t.occupation for t in real_tasks}
        print(f"\n  Found {len(categories)} unique occupations")

    def test_real_tasks_are_gdpvaltask(self, real_tasks):
        """실제 데이터가 GDPValTask로 파싱되는지 확인"""
        assert all(isinstance(t, GDPValTask) for t in real_tasks)

    def test_real_task_fields_not_empty(self, real_tasks):
        """실제 태스크의 필수 필드가 비어있지 않은지 확인"""
        for task in real_tasks[:5]:
            assert task.task_id, "task_id is empty"
            assert task.occupation, "occupation is empty"
            assert task.sector, "sector is empty"
            assert task.prompt, "prompt is empty"

    def test_real_tasks_have_unique_ids(self, real_tasks):
        """실제 데이터의 task_id 중복 없는지 확인"""
        ids = [t.task_id for t in real_tasks]
        assert len(ids) == len(set(ids)), "Duplicate task_ids found"

    def test_real_sector_count_is_9(self, real_tasks):
        """정확히 9개 섹터가 존재하는지 확인"""
        sectors = {t.sector for t in real_tasks}
        assert len(sectors) == EXPECTED_SECTOR_COUNT, f"Expected {EXPECTED_SECTOR_COUNT} sectors, got {len(sectors)}"
        print(f"\n  Sectors: {sorted(sectors)}")

    def test_real_deliverable_fields_exist(self, real_tasks):
        """실제 데이터에 deliverable 필드가 존재하는지 확인"""
        task = real_tasks[0]

        assert hasattr(task, 'deliverable_text')
        assert hasattr(task, 'deliverable_files')
        assert isinstance(task.deliverable_text, str)
        assert isinstance(task.deliverable_files, list)

        print(f"\n  Sample deliverable_text length: {len(task.deliverable_text)} chars")
        print(f"  Sample deliverable_files count: {len(task.deliverable_files)}")

    def test_real_sector_names_match(self, real_tasks):
        """섹터명이 기대값과 일치하는지 확인"""
        actual_sectors = {t.sector for t in real_tasks}
        assert actual_sectors == EXPECTED_SECTORS, (
            f"Sector mismatch.\n"
            f"  Missing: {EXPECTED_SECTORS - actual_sectors}\n"
            f"  Unexpected: {actual_sectors - EXPECTED_SECTORS}"
        )

    def test_real_sector_task_distribution(self, real_tasks):
        """각 섹터별 과제 수가 기대값과 일치하는지 확인"""
        from collections import Counter

        actual = Counter(t.sector for t in real_tasks)

        print("\n  Sector distribution:")
        for sector, expected_count in sorted(EXPECTED_SECTOR_DISTRIBUTION.items()):
            actual_count = actual.get(sector, 0)
            status = "✅" if actual_count == expected_count else "❌"
            print(f"    {status} {sector}: {actual_count} (expected {expected_count})")

        for sector, expected_count in EXPECTED_SECTOR_DISTRIBUTION.items():
            assert actual.get(sector, 0) == expected_count, (
                f"{sector}: expected {expected_count}, got {actual.get(sector, 0)}"
            )

    def test_real_reload_from_snapshot(self, real_snapshot_path):
        """스냅샷에서 재로드 테스트 (다운로드 없이)"""
        # Create new loader pointing to same snapshot
        loader2 = GDPValDataLoader(local_path=str(real_snapshot_path))

        # Should load without downloading
        tasks = loader2.load()
        assert len(tasks) == EXPECTED_TASK_COUNT
        print("\n  ✓ Successfully reloaded from existing snapshot")
