"""Domain Filter for GDPVal Tasks

Filters tasks by sector, occupation, or random sampling.
"""

from typing import List, Optional
from .data_loader import GDPValTask


class DomainFilter:
    """산업/직업별 태스크 필터"""

    def __init__(self, tasks: List[GDPValTask]):
        self.tasks = tasks

    def by_sector(self, sector: str) -> List[GDPValTask]:
        """Filter tasks by sector (case-insensitive)

        Args:
            sector: Sector name to filter by

        Returns:
            List of tasks matching the sector
        """
        return [t for t in self.tasks if t.sector.lower() == sector.lower()]

    def by_occupation(self, occupation: str) -> List[GDPValTask]:
        """Filter tasks by occupation (case-insensitive)

        Args:
            occupation: Occupation name to filter by

        Returns:
            List of tasks matching the occupation
        """
        return [t for t in self.tasks if t.occupation.lower() == occupation.lower()]

    def sample(self, n: int, seed: Optional[int] = None) -> List[GDPValTask]:
        """Randomly sample n tasks

        Args:
            n: Number of tasks to sample
            seed: Random seed for reproducibility

        Returns:
            List of randomly sampled tasks (up to n or len(tasks), whichever is smaller)
        """
        import random
        if seed is not None:
            random.seed(seed)
        return random.sample(self.tasks, min(n, len(self.tasks)))

    def get_sectors(self) -> List[str]:
        """Get list of unique sectors in the dataset

        Returns:
            Sorted list of unique sector names
        """
        return sorted(set(t.sector for t in self.tasks))

    def get_occupations(self) -> List[str]:
        """Get list of unique occupations in the dataset

        Returns:
            Sorted list of unique occupation names
        """
        return sorted(set(t.occupation for t in self.tasks))

    def count_by_sector(self) -> dict:
        """Count tasks per sector

        Returns:
            Dictionary mapping sector names to task counts
        """
        from collections import Counter
        return dict(Counter(t.sector for t in self.tasks))

    def count_by_occupation(self) -> dict:
        """Count tasks per occupation

        Returns:
            Dictionary mapping occupation names to task counts
        """
        from collections import Counter
        return dict(Counter(t.occupation for t in self.tasks))
