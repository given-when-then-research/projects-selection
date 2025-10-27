"""
Configurações do sistema
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Set, Optional


@dataclass
class Config:
    """Configurações principais do sistema"""
    input_file: str
    output_dir: Path
    repos_dir: Path
    max_repos: Optional[int] = None
    target_languages: Set[str] = None
    skip_clone: bool = False
    
    # Configurações de análise
    min_feature_files: int = 1
    clone_timeout: int = 1800  # 30 minutos => 30 * 60
    max_file_size: int = 1024 * 1024  # 1MB
    
    def __post_init__(self):
        if self.target_languages is None:
            self.target_languages = {
                'nodejs', 'java', 'ruby', 'kotlin', 
                'go', 'scala', 'cpp', 'lua', 'ocaml'
            }