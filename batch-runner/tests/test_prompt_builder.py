"""Tests for Prompt Builder

Usage:
    pytest                          # mock only (CI default)
    pytest -m integration           # real HF API only (needs HF_TOKEN)
    pytest -m ""                    # all tests
"""

import pytest
from core.prompt_builder import PromptBuilder, PromptConfig
from core.data_loader import GDPValTask, GDPValDataLoader
from core.config import DEFAULT_SYSTEM_PROMPT, HF_DATASET_URI_PREFIX


@pytest.fixture
def sample_task():
    """Create a sample task for testing"""
    return GDPValTask(
        task_id='task_001',
        occupation='Financial Analyst',
        sector='Finance and Insurance',
        prompt='Calculate the annual revenue growth rate.',
        reference_files=['data.csv'],
        reference_file_urls=['https://example.com/data.csv'],
        reference_file_hf_uris=[f'{HF_DATASET_URI_PREFIX}/data.csv'],
        deliverable_text='Expected output text',
        deliverable_files=['output.pdf']
    )


class TestPromptConfig:
    """Test suite for PromptConfig dataclass"""

    def test_config_creation_minimal(self):
        """Test creating config with minimal fields"""
        config = PromptConfig(name="test")
        assert config.name == "test"
        assert config.system_prompt is None
        assert config.prefix is None
        assert config.suffix is None

    def test_config_creation_full(self):
        """Test creating config with all fields"""
        config = PromptConfig(
            name="test",
            system_prompt="System prompt",
            prefix="Prefix",
            suffix="Suffix"
        )
        assert config.name == "test"
        assert config.system_prompt == "System prompt"
        assert config.prefix == "Prefix"
        assert config.suffix == "Suffix"


class TestPromptBuilder:
    """Test suite for PromptBuilder"""

    def test_builder_creation(self):
        """Test creating builder with custom config"""
        config = PromptConfig(name="test", system_prompt="Test")
        builder = PromptBuilder(config)
        assert builder.config.name == "test"

    def test_from_preset_baseline(self):
        """Test creating builder from baseline preset"""
        builder = PromptBuilder.from_preset("baseline")
        assert builder.config.name == "baseline"
        assert builder.config.system_prompt == DEFAULT_SYSTEM_PROMPT
        assert builder.config.prefix is None
        assert builder.config.suffix is None

    def test_from_preset_visual_inspection(self):
        """Test creating builder from visual_inspection preset"""
        builder = PromptBuilder.from_preset("visual_inspection")
        assert builder.config.name == "visual_inspection"
        assert "STEP 1" in builder.config.suffix
        assert "STEP 2" in builder.config.suffix
        assert "STEP 3" in builder.config.suffix

    def test_from_preset_reasoning_high(self):
        """Test creating builder from reasoning_high preset"""
        builder = PromptBuilder.from_preset("reasoning_high")
        assert builder.config.name == "reasoning_high"
        assert "step by step" in builder.config.system_prompt.lower()

    def test_from_preset_invalid(self):
        """Test that invalid preset raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            PromptBuilder.from_preset("invalid_preset")
        assert "Unknown preset" in str(exc_info.value)
        assert "invalid_preset" in str(exc_info.value)

    def test_get_preset_names(self):
        """Test getting list of preset names"""
        names = PromptBuilder.get_preset_names()
        assert "baseline" in names
        assert "visual_inspection" in names
        assert "reasoning_high" in names
        assert isinstance(names, list)

    def test_build_baseline(self, sample_task):
        """Test building prompt with baseline preset"""
        builder = PromptBuilder.from_preset("baseline")
        result = builder.build(sample_task)

        assert result["system"] == DEFAULT_SYSTEM_PROMPT
        assert result["user"].startswith(sample_task.prompt)
        # Reference files are always included (file not found is expected in test)
        assert "=== Reference Files ===" in result["user"]
        assert result["metadata"]["task_id"] == "task_001"
        assert result["metadata"]["prompt_config"] == "baseline"

    def test_build_with_suffix(self, sample_task):
        """Test building prompt with suffix"""
        builder = PromptBuilder.from_preset("visual_inspection")
        result = builder.build(sample_task)

        assert result["user"].startswith(sample_task.prompt)
        assert "STEP 1" in result["user"]
        assert result["metadata"]["prompt_config"] == "visual_inspection"

    def test_build_with_prefix(self, sample_task):
        """Test building prompt with prefix"""
        config = PromptConfig(
            name="custom",
            system_prompt="System",
            prefix="PREFIX:"
        )
        builder = PromptBuilder(config)
        result = builder.build(sample_task)

        assert result["user"].startswith("PREFIX:")
        assert sample_task.prompt in result["user"]

    def test_build_with_prefix_and_suffix(self, sample_task):
        """Test building prompt with both prefix and suffix"""
        config = PromptConfig(
            name="custom",
            system_prompt="System",
            prefix="PREFIX:",
            suffix="SUFFIX:"
        )
        builder = PromptBuilder(config)
        result = builder.build(sample_task)

        assert result["user"].startswith("PREFIX:")
        assert "SUFFIX:" in result["user"]
        assert sample_task.prompt in result["user"]

    def test_build_includes_metadata(self, sample_task):
        """Test that build includes task metadata"""
        builder = PromptBuilder.from_preset("baseline")
        result = builder.build(sample_task)

        assert result["metadata"]["task_id"] == sample_task.task_id
        assert result["metadata"]["sector"] == sample_task.sector
        assert result["metadata"]["occupation"] == sample_task.occupation
        assert result["metadata"]["prompt_config"] == "baseline"

    def test_build_batch(self, sample_task):
        """Test building prompts for multiple tasks"""
        tasks = [sample_task, sample_task, sample_task]
        builder = PromptBuilder.from_preset("baseline")
        results = builder.build_batch(tasks)

        assert len(results) == 3
        assert all(r["metadata"]["task_id"] == "task_001" for r in results)

    def test_build_batch_empty(self):
        """Test building batch with empty list"""
        builder = PromptBuilder.from_preset("baseline")
        results = builder.build_batch([])
        assert results == []

    def test_repr(self):
        """Test string representation"""
        builder = PromptBuilder.from_preset("baseline")
        assert "baseline" in repr(builder)


# ─── Integration Tests (실제 HuggingFace 연결) ───────────────────────────

@pytest.mark.integration
class TestPromptBuilderIntegration:
    """실제 HuggingFace API를 사용하는 통합 테스트

    실행 전 HF_TOKEN 환경변수 필요:
        export HF_TOKEN="hf_xxxxxxxxxxxx"
        pytest -m integration
    """

    @pytest.fixture
    def real_tasks(self):
        """Load real tasks from HuggingFace"""
        loader = GDPValDataLoader()
        tasks = loader.load()
        return tasks[:10]  # Use first 10 for testing

    def test_real_baseline_prompt(self, real_tasks):
        """실제 태스크로 baseline 프롬프트 생성"""
        builder = PromptBuilder.from_preset("baseline")
        result = builder.build(real_tasks[0])

        assert result["system"] == DEFAULT_SYSTEM_PROMPT
        assert result["user"] == real_tasks[0].prompt
        assert "task_id" in result["metadata"]
        print(f"\n  Task ID: {result['metadata']['task_id']}")
        print(f"  Prompt length: {len(result['user'])} chars")

    def test_real_visual_inspection_prompt(self, real_tasks):
        """실제 태스크로 visual inspection 프롬프트 생성"""
        builder = PromptBuilder.from_preset("visual_inspection")
        result = builder.build(real_tasks[0])

        assert "STEP 1" in result["user"]
        assert "STEP 2" in result["user"]
        assert "STEP 3" in result["user"]
        print(f"\n  Added visual inspection steps: {result['user'].count('STEP')} steps")

    def test_real_build_batch_all_presets(self, real_tasks):
        """모든 preset으로 배치 생성 테스트"""
        presets = PromptBuilder.get_preset_names()

        for preset_name in presets:
            builder = PromptBuilder.from_preset(preset_name)
            results = builder.build_batch(real_tasks)

            assert len(results) == len(real_tasks)
            assert all(r["metadata"]["prompt_config"] == preset_name for r in results)

        print(f"\n  Tested {len(presets)} presets with {len(real_tasks)} tasks each")

    def test_real_prompt_consistency(self, real_tasks):
        """같은 태스크로 여러 번 빌드 시 일관성 확인"""
        builder = PromptBuilder.from_preset("baseline")

        result1 = builder.build(real_tasks[0])
        result2 = builder.build(real_tasks[0])

        assert result1 == result2
        print("\n  Prompt generation is deterministic ✓")

    def test_real_metadata_completeness(self, real_tasks):
        """실제 태스크의 메타데이터가 모두 포함되는지 확인"""
        builder = PromptBuilder.from_preset("baseline")

        for task in real_tasks[:3]:
            result = builder.build(task)

            assert result["metadata"]["task_id"] == task.task_id
            assert result["metadata"]["sector"] == task.sector
            assert result["metadata"]["occupation"] == task.occupation
            assert result["metadata"]["prompt_config"] == "baseline"

        print(f"\n  Verified metadata for {3} tasks")

    def test_real_prompt_lengths(self, real_tasks):
        """각 preset별 프롬프트 길이 확인"""
        presets = PromptBuilder.get_preset_names()
        lengths = {}

        for preset_name in presets:
            builder = PromptBuilder.from_preset(preset_name)
            result = builder.build(real_tasks[0])
            lengths[preset_name] = len(result["user"])

        print("\n  Prompt lengths by preset:")
        for preset, length in sorted(lengths.items()):
            print(f"    {preset}: {length} chars")

        # Visual inspection should be longer due to added steps
        assert lengths["visual_inspection"] > lengths["baseline"]
