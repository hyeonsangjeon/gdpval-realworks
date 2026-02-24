"""Tests for prepare_dataset.py CLI interface

Usage:
    pytest tests/test_prepare_dataset.py -v
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Import the module
sys.path.insert(0, str(Path(__file__).parent.parent))
from prepare_dataset import GDPValDataset, main
from core.config import DATASET_ID, EXPECTED_TASK_COUNT


@pytest.fixture
def temp_snapshot_path(tmp_path):
    """Create temporary directory for testing"""
    return tmp_path / "test-snapshot"


@pytest.fixture
def mock_dataset_for_cli():
    """Create mock dataset for CLI tests"""
    mock_ds = MagicMock()
    mock_ds.__getitem__ = Mock(return_value={'train': [{'task_id': f'task_{i}'} for i in range(EXPECTED_TASK_COUNT)]})
    mock_ds.__len__ = Mock(return_value=EXPECTED_TASK_COUNT)
    mock_ds.save_to_disk = Mock()
    return mock_ds


class TestPrepareDatasetCLI:
    """Test suite for prepare_dataset.py CLI interface"""

    def test_main_default_download(self, temp_snapshot_path, mock_dataset_for_cli):
        """Test main() with default arguments (download)"""
        test_args = ['prepare_dataset.py', '--path', str(temp_snapshot_path)]

        with patch.object(sys, 'argv', test_args):
            with patch('prepare_dataset.snapshot_download'):
                with patch('prepare_dataset.load_dataset', return_value=mock_dataset_for_cli):
                    with patch.object(GDPValDataset, '_add_deliverable_columns', return_value=mock_dataset_for_cli):
                        with patch('sys.stdout', new=StringIO()) as fake_out:
                            result = main()

                            assert result == 0
                            output = fake_out.getvalue()
                            assert 'GDPVal Dataset Preparation' in output
                            assert 'Dataset preparation completed' in output

    def test_main_info_flag(self, temp_snapshot_path):
        """Test main() with --info flag"""
        # Create fake snapshot
        temp_snapshot_path.mkdir(parents=True)
        (temp_snapshot_path / "dataset_dict.json").write_text("{}")

        test_args = ['prepare_dataset.py', '--info', '--path', str(temp_snapshot_path)]

        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new=StringIO()) as fake_out:
                result = main()

                assert result == 0
                output = fake_out.getvalue()
                assert 'GDPVal Dataset Snapshot Info' in output
                assert 'Dataset ID' in output
                assert 'Local Path' in output

    def test_main_force_flag(self, temp_snapshot_path, mock_dataset_for_cli):
        """Test main() with --force flag"""
        # Create existing snapshot
        temp_snapshot_path.mkdir(parents=True)
        (temp_snapshot_path / "dataset_dict.json").write_text("{}")

        test_args = ['prepare_dataset.py', '--force', '--path', str(temp_snapshot_path)]

        with patch.object(sys, 'argv', test_args):
            with patch('prepare_dataset.snapshot_download'):
                with patch('prepare_dataset.load_dataset', return_value=mock_dataset_for_cli):
                    with patch.object(GDPValDataset, '_add_deliverable_columns', return_value=mock_dataset_for_cli):
                        with patch('sys.stdout', new=StringIO()):
                            result = main()
                            assert result == 0

    def test_main_custom_path(self, tmp_path, mock_dataset_for_cli):
        """Test main() with custom --path"""
        custom_path = tmp_path / "custom" / "snapshot"
        test_args = ['prepare_dataset.py', '--path', str(custom_path)]

        with patch.object(sys, 'argv', test_args):
            with patch('prepare_dataset.snapshot_download'):
                with patch('prepare_dataset.load_dataset', return_value=mock_dataset_for_cli):
                    with patch.object(GDPValDataset, '_add_deliverable_columns', return_value=mock_dataset_for_cli):
                        with patch('sys.stdout', new=StringIO()):
                            result = main()
                            assert result == 0

    def test_main_error_handling(self, temp_snapshot_path):
        """Test main() error handling"""
        test_args = ['prepare_dataset.py', '--path', str(temp_snapshot_path)]

        with patch.object(sys, 'argv', test_args):
            with patch('prepare_dataset.snapshot_download', side_effect=Exception("Network error")):
                with patch('sys.stdout', new=StringIO()) as fake_out:
                    result = main()

                    assert result == 1
                    output = fake_out.getvalue()
                    assert 'Error' in output
                    assert 'Network error' in output


class TestGDPValDatasetPrintInfo:
    """Test suite for print_info() method"""

    def test_print_info_when_not_exists(self, temp_snapshot_path):
        """Test print_info() when snapshot doesn't exist"""
        dataset = GDPValDataset(local_path=str(temp_snapshot_path))

        with patch('sys.stdout', new=StringIO()) as fake_out:
            dataset.print_info()
            output = fake_out.getvalue()

            assert 'GDPVal Dataset Snapshot Info' in output
            assert 'Exists:        ✗ No' in output
            assert 'Valid:         ✗ No' in output

    def test_print_info_when_exists(self, temp_snapshot_path):
        """Test print_info() when valid snapshot exists"""
        # Create valid snapshot
        temp_snapshot_path.mkdir(parents=True)
        (temp_snapshot_path / "dataset_dict.json").write_text("{}")
        (temp_snapshot_path / "data.txt").write_bytes(b"test" * 1000)

        dataset = GDPValDataset(local_path=str(temp_snapshot_path))

        with patch('sys.stdout', new=StringIO()) as fake_out:
            dataset.print_info()
            output = fake_out.getvalue()

            assert 'GDPVal Dataset Snapshot Info' in output
            assert 'Exists:        ✓ Yes' in output
            assert 'Valid:         ✓ Yes' in output
            assert 'Size:' in output


class TestGDPValDatasetDirectImport:
    """Test importing and using GDPValDataset directly"""

    def test_direct_import_and_usage(self, temp_snapshot_path, mock_dataset_for_cli):
        """Test using GDPValDataset directly (not through data_loader)"""
        with patch('prepare_dataset.snapshot_download'):
            with patch('prepare_dataset.load_dataset', return_value=mock_dataset_for_cli):
                with patch.object(GDPValDataset, '_add_deliverable_columns', return_value=mock_dataset_for_cli):
                    # Direct import usage
                    dataset = GDPValDataset(local_path=str(temp_snapshot_path))

                    # Test download
                    result = dataset.download()
                    assert result == temp_snapshot_path

    def test_direct_import_get_info(self, temp_snapshot_path):
        """Test get_info() through direct import"""
        dataset = GDPValDataset(local_path=str(temp_snapshot_path))
        info = dataset.get_info()

        assert 'exists' in info
        assert 'valid' in info
        assert 'path' in info
        assert 'size_mb' in info
        assert 'task_count' in info
        assert 'dataset_id' in info
        assert info['dataset_id'] == DATASET_ID


class TestCLIArgumentParsing:
    """Test CLI argument parsing"""

    def test_help_message(self):
        """Test --help flag"""
        test_args = ['prepare_dataset.py', '--help']

        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_default_arguments(self, mock_dataset_for_cli):
        """Test running with no arguments (defaults)"""
        test_args = ['prepare_dataset.py']

        with patch.object(sys, 'argv', test_args):
            with patch('prepare_dataset.snapshot_download'):
                with patch('prepare_dataset.load_dataset', return_value=mock_dataset_for_cli):
                    with patch.object(GDPValDataset, '_add_deliverable_columns', return_value=mock_dataset_for_cli):
                        with patch('sys.stdout', new=StringIO()):
                            # Should use default path
                            result = main()
                            assert result == 0


class TestBackwardCompatibility:
    """Test backward compatibility with data_loader.py"""

    def test_import_from_data_loader(self):
        """Test that GDPValDataLoader is available from data_loader"""
        from core.data_loader import GDPValDataLoader, GDPValDataset, GDPValTask

        # Should be the same class
        assert GDPValDataLoader == GDPValDataset

    def test_data_loader_wrapper_works(self, temp_snapshot_path):
        """Test that data_loader wrapper maintains functionality"""
        from core.data_loader import GDPValDataLoader

        loader = GDPValDataLoader(local_path=str(temp_snapshot_path), auto_download=False)

        # Should have same methods
        assert hasattr(loader, 'download')
        assert hasattr(loader, 'download_snapshot')  # backward compat
        assert hasattr(loader, 'load')
        assert hasattr(loader, 'get_info')
        assert hasattr(loader, 'get_snapshot_info')  # backward compat
