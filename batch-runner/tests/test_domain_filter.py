"""Tests for Domain Filter

Usage:
    pytest                          # mock only (CI default)
    pytest -m integration           # real HF API only (needs HF_TOKEN)
    pytest -m ""                    # all tests
"""

import pytest
from core.domain_filter import DomainFilter
from core.data_loader import GDPValTask, GDPValDataLoader
from core.config import (
    EXPECTED_SECTOR_COUNT,
    EXPECTED_SECTORS,
    EXPECTED_SECTOR_DISTRIBUTION,
    EXPECTED_TASK_COUNT,
)


@pytest.fixture
def sample_tasks():
    """Create sample tasks for testing"""
    return [
        GDPValTask(
            task_id=f'task_{i:03d}',
            occupation='Engineer' if i < 5 else 'Analyst',
            sector='Finance' if i < 3 else 'Healthcare' if i < 7 else 'Manufacturing',
            prompt=f'Task {i}',
            reference_files=[],
            reference_file_urls=[],
            reference_file_hf_uris=[],
            deliverable_text=f'Deliverable {i}',
            deliverable_files=[]
        )
        for i in range(10)
    ]


class TestDomainFilter:
    """Test suite for DomainFilter"""

    def test_by_sector_returns_filtered(self, sample_tasks):
        """Test that by_sector filters correctly"""
        filter = DomainFilter(sample_tasks)
        result = filter.by_sector("Finance")
        assert len(result) == 3
        assert all(t.sector == "Finance" for t in result)

    def test_by_sector_case_insensitive(self, sample_tasks):
        """Test that by_sector is case-insensitive"""
        filter = DomainFilter(sample_tasks)
        result = filter.by_sector("finance")
        assert len(result) == 3
        assert all(t.sector == "Finance" for t in result)

    def test_by_occupation_returns_filtered(self, sample_tasks):
        """Test that by_occupation filters correctly"""
        filter = DomainFilter(sample_tasks)
        result = filter.by_occupation("Engineer")
        assert len(result) == 5
        assert all(t.occupation == "Engineer" for t in result)

    def test_by_occupation_case_insensitive(self, sample_tasks):
        """Test that by_occupation is case-insensitive"""
        filter = DomainFilter(sample_tasks)
        result = filter.by_occupation("engineer")
        assert len(result) == 5
        assert all(t.occupation == "Engineer" for t in result)

    def test_sample_returns_n_tasks(self, sample_tasks):
        """Test that sample returns exactly n tasks"""
        filter = DomainFilter(sample_tasks)
        result = filter.sample(5, seed=42)
        assert len(result) == 5

    def test_sample_with_seed_is_reproducible(self, sample_tasks):
        """Test that sample with same seed produces same results"""
        filter = DomainFilter(sample_tasks)
        result1 = filter.sample(5, seed=42)
        result2 = filter.sample(5, seed=42)
        assert [t.task_id for t in result1] == [t.task_id for t in result2]

    def test_sample_respects_max_size(self, sample_tasks):
        """Test that sample doesn't exceed available tasks"""
        filter = DomainFilter(sample_tasks)
        result = filter.sample(100, seed=42)
        assert len(result) == len(sample_tasks)

    def test_get_sectors(self, sample_tasks):
        """Test that get_sectors returns unique sectors"""
        filter = DomainFilter(sample_tasks)
        sectors = filter.get_sectors()
        assert sectors == ['Finance', 'Healthcare', 'Manufacturing']

    def test_get_occupations(self, sample_tasks):
        """Test that get_occupations returns unique occupations"""
        filter = DomainFilter(sample_tasks)
        occupations = filter.get_occupations()
        assert occupations == ['Analyst', 'Engineer']

    def test_count_by_sector(self, sample_tasks):
        """Test that count_by_sector returns correct counts"""
        filter = DomainFilter(sample_tasks)
        counts = filter.count_by_sector()
        assert counts == {
            'Finance': 3,
            'Healthcare': 4,
            'Manufacturing': 3
        }

    def test_count_by_occupation(self, sample_tasks):
        """Test that count_by_occupation returns correct counts"""
        filter = DomainFilter(sample_tasks)
        counts = filter.count_by_occupation()
        assert counts == {
            'Engineer': 5,
            'Analyst': 5
        }

    def test_filter_empty_result(self, sample_tasks):
        """Test filtering with non-existent sector returns empty list"""
        filter = DomainFilter(sample_tasks)
        result = filter.by_sector("NonExistent")
        assert result == []

    def test_filter_with_empty_tasks(self):
        """Test filter works with empty task list"""
        filter = DomainFilter([])
        assert filter.by_sector("Finance") == []
        assert filter.get_sectors() == []
        assert filter.count_by_sector() == {}


# ─── Integration Tests (실제 HuggingFace 연결) ───────────────────────────

@pytest.mark.integration
class TestDomainFilterIntegration:
    """실제 HuggingFace API를 사용하는 통합 테스트

    실행 전 HF_TOKEN 환경변수 필요:
        export HF_TOKEN="hf_xxxxxxxxxxxx"
        pytest -m integration
    """

    @pytest.fixture
    def real_tasks(self):
        """Load real tasks from HuggingFace (fixture는 클래스 내에서 재사용)"""
        loader = GDPValDataLoader()
        return loader.load()

    def test_real_get_sectors_returns_9(self, real_tasks):
        """실제 데이터에서 9개 섹터 확인"""
        filter = DomainFilter(real_tasks)
        sectors = filter.get_sectors()
        assert len(sectors) == EXPECTED_SECTOR_COUNT, f"Expected {EXPECTED_SECTOR_COUNT} sectors, got {len(sectors)}: {sectors}"

    def test_real_sector_names_match(self, real_tasks):
        """실제 섹터명이 기대값과 일치하는지 확인"""
        filter = DomainFilter(real_tasks)
        actual_sectors = set(filter.get_sectors())
        assert actual_sectors == EXPECTED_SECTORS, (
            f"Sector mismatch.\n"
            f"  Missing: {EXPECTED_SECTORS - actual_sectors}\n"
            f"  Unexpected: {actual_sectors - EXPECTED_SECTORS}"
        )

    def test_real_by_sector_filter(self, real_tasks):
        """실제 데이터에서 섹터 필터링 동작 확인"""
        filter = DomainFilter(real_tasks)
        finance = filter.by_sector("Finance and Insurance")
        assert len(finance) == 25, f"Expected 25 Finance tasks, got {len(finance)}"
        assert all(t.sector == "Finance and Insurance" for t in finance)

    def test_real_by_sector_case_insensitive(self, real_tasks):
        """실제 데이터에서 대소문자 무시 확인"""
        filter = DomainFilter(real_tasks)
        result1 = filter.by_sector("Finance and Insurance")
        result2 = filter.by_sector("finance and insurance")
        result3 = filter.by_sector("FINANCE AND INSURANCE")
        assert len(result1) == len(result2) == len(result3) == 25

    def test_real_count_by_sector(self, real_tasks):
        """실제 데이터의 섹터별 분포 확인"""
        filter = DomainFilter(real_tasks)
        actual = filter.count_by_sector()

        print("\n  Sector distribution:")
        for sector, expected_count in sorted(EXPECTED_SECTOR_DISTRIBUTION.items()):
            actual_count = actual.get(sector, 0)
            status = "✅" if actual_count == expected_count else "❌"
            print(f"    {status} {sector}: {actual_count} (expected {expected_count})")

        assert actual == EXPECTED_SECTOR_DISTRIBUTION

    def test_real_get_occupations(self, real_tasks):
        """실제 데이터의 직업 종류 확인"""
        filter = DomainFilter(real_tasks)
        occupations = filter.get_occupations()
        assert len(occupations) > 0, "No occupations found"
        print(f"\n  Found {len(occupations)} unique occupations")
        for occ in occupations[:10]:  # 처음 10개만 출력
            print(f"    - {occ}")

    def test_real_by_occupation_filter(self, real_tasks):
        """실제 데이터에서 직업 필터링 동작 확인"""
        filter = DomainFilter(real_tasks)
        occupations = filter.get_occupations()

        # 첫 번째 직업으로 필터링
        first_occupation = occupations[0]
        filtered = filter.by_occupation(first_occupation)

        assert len(filtered) > 0, f"No tasks for {first_occupation}"
        assert all(t.occupation == first_occupation for t in filtered)
        print(f"\n  {first_occupation}: {len(filtered)} tasks")

    def test_real_sample_reproducibility(self, real_tasks):
        """실제 데이터에서 샘플링 재현성 확인"""
        filter = DomainFilter(real_tasks)

        sample1 = filter.sample(10, seed=42)
        sample2 = filter.sample(10, seed=42)

        assert len(sample1) == len(sample2) == 10
        assert [t.task_id for t in sample1] == [t.task_id for t in sample2]

    def test_real_sample_size_constraints(self, real_tasks):
        """실제 데이터에서 샘플 크기 제약 확인"""
        filter = DomainFilter(real_tasks)

        # 전체보다 큰 샘플 요청 시 전체 반환
        large_sample = filter.sample(1000, seed=42)
        assert len(large_sample) == EXPECTED_TASK_COUNT

        # 정확한 크기 요청
        small_sample = filter.sample(50, seed=42)
        assert len(small_sample) == 50

    def test_real_filter_chain(self, real_tasks):
        """실제 데이터에서 필터 체이닝 확인"""
        # 섹터 필터링 후 다시 필터링
        filter1 = DomainFilter(real_tasks)
        finance_tasks = filter1.by_sector("Finance and Insurance")

        # 금융 섹터 내에서 직업별 필터링
        filter2 = DomainFilter(finance_tasks)
        occupations = filter2.get_occupations()

        assert len(occupations) > 0
        print(f"\n  Finance sector has {len(occupations)} occupations")

        # 각 직업별 태스크 수 확인
        counts = filter2.count_by_occupation()
        total = sum(counts.values())
        assert total == 25, f"Total tasks should be 25, got {total}"
