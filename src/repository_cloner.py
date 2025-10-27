"""
Clonagem de repositórios
"""

import os
import subprocess
import logging
import shutil
from typing import List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .models import Repository
from .config import Config


class RepositoryCloner:
    """Gerencia a clonagem de repositórios"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def clone_repositories(self, repositories: List[Repository]) -> None:
        """Clona todos os repositórios"""
        self.logger.info(f"Iniciando clonagem de {len(repositories)} repositórios...")
        
        # Criar diretórios por linguagem
        for language in self.config.target_languages:
            lang_dir = self.config.repos_dir / language
            lang_dir.mkdir(exist_ok=True)
        
        # Clone em paralelo
        max_workers = min(4, len(repositories))  # Limite para não sobrecarregar
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(self._clone_repository, repo): repo 
                for repo in repositories
            }
            
            completed = 0
            for future in as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    success = future.result()
                    if success:
                        self.logger.debug(f"✓ Clonado: {repo.name}")
                    else:
                        self.logger.warning(f"✗ Falha: {repo.name}")
                except Exception as e:
                    self.logger.error(f"✗ Erro ao clonar {repo.name}: {e}")
                
                completed += 1
                if completed % 10 == 0:
                    self.logger.info(f"Progresso: {completed}/{len(repositories)} repositórios processados")
        
        self.logger.info("Clonagem concluída!")
    
    def _clone_repository(self, repo: Repository) -> bool:
        """Clona um repositório específico"""
        local_path = repo.get_local_path(self.config.repos_dir)
        
        # Verificar se já existe
        if local_path.exists():
            self.logger.debug(f"Repositório já existe: {local_path}")
            return True
        
        try:
            # Criar diretório pai
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Comando git clone
            cmd = [
                'git', 'clone',
                '--depth', '1',  # Clone superficial para economizar espaço
                '--single-branch',
                repo.url,
                str(local_path)
            ]
            
            # Executar clone com timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.clone_timeout
            )
            
            if result.returncode == 0:
                return True
            else:
                self.logger.warning(f"Erro git clone {repo.name}: {result.stderr}")
                # Limpar diretório parcial se existir
                if local_path.exists():
                    shutil.rmtree(local_path)
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout ao clonar {repo.name}")
            if local_path.exists():
                shutil.rmtree(local_path)
            return False
        except Exception as e:
            self.logger.warning(f"Erro ao clonar {repo.name}: {e}")
            if local_path.exists():
                shutil.rmtree(local_path)
            return False