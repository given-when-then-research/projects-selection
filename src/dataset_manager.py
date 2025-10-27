"""
Gerenciamento e carregamento do dataset de entrada
"""

import json
import logging
from typing import List, Dict, Any
from pathlib import Path

from .models import Repository
from .config import Config


class DatasetManager:
    """Gerencia o carregamento e filtragem do dataset"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.metadata_stats = {}
    
    def load_and_filter_repositories(self) -> List[Repository]:
        """Carrega e filtra repositórios do dataset"""
        self.logger.info(f"Carregando dataset: {self.config.input_file}")
        
        with open(self.config.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        repositories = []
        total_count = 0
        
        # Coletar metadados antes da filtragem
        self._collect_metadata_before_filtering(data)
        
        for language, repos_data in data.get('repositories', {}).items():
            if language not in self.config.target_languages:
                self.logger.debug(f"Ignorando linguagem: {language}")
                continue
                
            for repo_data in repos_data:
                total_count += 1
                
                try:
                    repo = Repository.from_dict(repo_data, language)
                    repositories.append(repo)
                    
                    if (self.config.max_repos and 
                        len(repositories) >= self.config.max_repos):
                        break
                        
                except Exception as e:
                    self.logger.warning(f"Erro ao processar repositório {repo_data.get('name', 'unknown')}: {e}")
                    continue
            
            if (self.config.max_repos and 
                len(repositories) >= self.config.max_repos):
                break
        
        # Adicionar ordenação para garantir determinismo
        repositories.sort(key=lambda r: r.name)
        
        self.logger.info(f"Carregados {len(repositories)} de {total_count} repositórios")
        return repositories
    
    def _collect_metadata_before_filtering(self, data: Dict[str, Any]) -> None:
        """Coleta metadados antes de aplicar filtros"""
        self.metadata_stats = {
            'total_repositories_by_language': {},
            'total_repositories': 0,
            'languages_found': set(),
            'repository_distribution': {}
        }
        
        for language, repos_data in data.get('repositories', {}).items():
            self.metadata_stats['languages_found'].add(language)
            repo_count = len(repos_data)
            self.metadata_stats['total_repositories_by_language'][language] = repo_count
            self.metadata_stats['total_repositories'] += repo_count
            
            # Estatísticas adicionais por linguagem
            self.metadata_stats['repository_distribution'][language] = {
                'total_repositories': repo_count,
                'repositories': [repo.get('name', 'unknown') for repo in repos_data],
                'total_stars': sum(repo.get('stars', 0) for repo in repos_data),
                'avg_stars': sum(repo.get('stars', 0) for repo in repos_data) / repo_count if repo_count > 0 else 0
            }
        
        # Converter set para list para serialização
        self.metadata_stats['languages_found'] = sorted(list(self.metadata_stats['languages_found']))
        
        self.logger.info(f"Metadados coletados: {len(self.metadata_stats['languages_found'])} linguagens, "
                        f"{self.metadata_stats['total_repositories']} repositórios totais")
    
    def get_metadata_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de metadados coletadas"""
        return self.metadata_stats