"""
Modelos de dados
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class Repository:
    """Modelo para repositório"""
    name: str
    url: str
    owner: str
    repo_name: str
    stars: int
    language: str
    found_in_languages: List[str]
    found_by_queries: int
    normalized_name: str
    normalized_owner: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], language: str) -> 'Repository':
        """Cria repositório a partir de dict"""
        name = data['name']
        owner, repo_name = name.split('/', 1)
        
        return cls(
            name=name,
            url=data['url'],
            owner=owner,
            repo_name=repo_name,
            stars=data.get('stars', 0),
            language=language,
            found_in_languages=data.get('found_in_languages', []),
            found_by_queries=data.get('found_by_queries', 0),
            normalized_name=cls._normalize_name(repo_name),
            normalized_owner=cls._normalize_name(owner)
        )
    
    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normaliza nome removendo caracteres especiais"""
        return re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())
    
    def get_local_path(self, base_dir: Path) -> Path:
        """Retorna caminho local do repositório"""
        return base_dir / self.language / f"{self.normalized_owner}_{self.normalized_name}"


@dataclass
class FeatureFile:
    """Modelo para arquivo .feature"""
    path: Path
    content: str
    is_valid: bool
    is_english: bool
    scenario_count: int
    step_count: int
    language_detected: str
    errors: List[str]


@dataclass
class FeatureAnalysisResult:
    """Resultado da análise de features"""
    repository: Repository
    feature_files: List[FeatureFile]
    total_files: int
    valid_files: int
    english_files: int
    total_scenarios: int
    total_steps: int
    is_valid_cucumber_repo: bool
    errors: List[str]


@dataclass
class CucumberLibrary:
    """Informações sobre biblioteca Cucumber"""
    name: str
    package_manager: str
    import_patterns: List[str]
    file_patterns: List[str]
    documentation_url: str


@dataclass
class LibraryAnalysisResult:
    """Resultado da análise de bibliotecas"""
    repository: Repository
    detected_libraries: List[CucumberLibrary]
    uses_official_cucumber: bool
    package_files_found: List[Path]
    import_files_found: List[Path]
    confidence_score: float