"""
Analisador de arquivos .feature com funil de filtragem otimizado
"""

import re
import logging
from typing import List, Dict, Set, Counter
from pathlib import Path
import langdetect
from langdetect.lang_detect_exception import LangDetectException
from collections import Counter

from .models import Repository, FeatureFile, FeatureAnalysisResult
from .config import Config

# remove aleatorioedade
langdetect.DetectorFactory.seed = 0

class FeatureAnalyzer:
    """Analisa arquivos .feature nos repositórios com funil de filtragem"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Padrões de steps em inglês
        self.english_step_patterns = [
            r'\b(Given|When|Then|And|But)\b',
            r'\b(Background|Scenario|Feature|Rule|Example)\b'
        ]
        
        # Palavras-chave Gherkin em inglês
        self.english_keywords = {
            'feature', 'background', 'scenario', 'scenario outline',
            'given', 'when', 'then', 'and', 'but', 'examples',
            'rule', 'example'
        }
        
        # Contador global de linguagens detectadas
        self.language_statistics = Counter()
        self.language_details = {}
        
        # Estatísticas antes da filtragem
        self.pre_filter_stats = {}
    
    def quick_filter_repos_with_features(self, repositories: List[Repository]) -> List[Repository]:
        """
        PRÉ-FILTRAGEM RÁPIDA: Identifica repositórios que possuem arquivos .feature
        
        Esta é uma filtragem leve que apenas verifica a existência de arquivos .feature,
        sem analisar o conteúdo. É muito mais rápida que a análise completa.
        
        Returns:
            Lista de repositórios que possuem pelo menos um arquivo .feature
        """
        self.logger.info("🔍 Iniciando pré-filtragem rápida de repositórios com .feature...")
        
        repos_with_features = []
        
        # Estatísticas por linguagem
        self.pre_filter_stats = {
            'by_language': {},
            'total_repositories_with_features': 0,
            'total_feature_files': 0
        }
        
        for i, repo in enumerate(repositories, 1):
            local_path = repo.get_local_path(self.config.repos_dir)
            
            # Verificar se diretório existe
            if not local_path.exists():
                continue
            
            # Buscar arquivos .feature (sem analisar conteúdo)
            feature_files = list(local_path.rglob("*.feature")) + list(local_path.rglob("*.features"))
            
            if feature_files:
                repos_with_features.append(repo)
                
                # Atualizar estatísticas
                if repo.language not in self.pre_filter_stats['by_language']:
                    self.pre_filter_stats['by_language'][repo.language] = {
                        'repositories_with_features': 0,
                        'total_feature_files': 0,
                        'repositories': []
                    }
                
                lang_stats = self.pre_filter_stats['by_language'][repo.language]
                lang_stats['repositories_with_features'] += 1
                lang_stats['total_feature_files'] += len(feature_files)
                lang_stats['repositories'].append(repo.name)
                
                self.pre_filter_stats['total_feature_files'] += len(feature_files)
            
            # Log de progresso a cada 200 repos
            if i % 200 == 0:
                self.logger.info(f"  Progresso pré-filtragem: {i}/{len(repositories)} "
                               f"({len(repos_with_features)} com .feature)")
        
        self.pre_filter_stats['total_repositories_with_features'] = len(repos_with_features)
        
        self.logger.info(f"✅ Pré-filtragem concluída:")
        self.logger.info(f"   • {len(repos_with_features)} repositórios com .feature")
        self.logger.info(f"   • {self.pre_filter_stats['total_feature_files']} arquivos .feature encontrados")
        
        # Log por linguagem
        for language, stats in sorted(self.pre_filter_stats['by_language'].items()):
            self.logger.info(f"   • {language}: {stats['repositories_with_features']} repos, "
                           f"{stats['total_feature_files']} arquivos")
        
        return repos_with_features
    
    def analyze_repositories(self, repositories: List[Repository]) -> Dict[str, FeatureAnalysisResult]:
        """
        ANÁLISE PROFUNDA: Analisa conteúdo dos arquivos .feature
        
        Esta função só deve ser chamada com repositórios que JÁ POSSUEM arquivos .feature
        (após a pré-filtragem com quick_filter_repos_with_features)
        """
        self.logger.info(f"🔍 Iniciando análise profunda de {len(repositories)} repositórios...")
        
        # Resetar estatísticas de análise profunda
        self.language_statistics.clear()
        self.language_details.clear()
        
        results = {}
        
        for i, repo in enumerate(repositories, 1):
            try:
                result = self._analyze_repository(repo)
                results[repo.name] = result
                
                # Coletar estatísticas de linguagem
                self._collect_language_statistics(repo, result)
                
                if i % 100 == 0:
                    self.logger.info(f"  Progresso análise profunda: {i}/{len(repositories)}")
                    
            except Exception as e:
                self.logger.error(f"Erro ao analisar {repo.name}: {e}")
                results[repo.name] = FeatureAnalysisResult(
                    repository=repo,
                    feature_files=[],
                    total_files=0,
                    valid_files=0,
                    english_files=0,
                    total_scenarios=0,
                    total_steps=0,
                    is_valid_cucumber_repo=False,
                    errors=[str(e)]
                )
        
        self.logger.info(f"✅ Análise profunda concluída para {len(results)} repositórios")
        self.logger.info(f"   • Linguagens detectadas: {len(self.language_statistics)}")
        
        return results
    
    def get_pre_filter_statistics(self) -> Dict:
        """Retorna estatísticas pré-filtragem"""
        return self.pre_filter_stats
    
    def get_language_statistics(self) -> Dict:
        """Retorna estatísticas detalhadas das linguagens detectadas"""
        return {
            'summary': dict(self.language_statistics),
            'details': self.language_details,
            'total_languages_detected': len(self.language_statistics),
            'total_feature_files_analyzed': sum(self.language_statistics.values())
        }
    
    def _collect_language_statistics(self, repo: Repository, result: FeatureAnalysisResult) -> None:
        """Coleta estatísticas de linguagem para um repositório"""
        for feature_file in result.feature_files:
            if feature_file.language_detected and feature_file.language_detected != "no_text":
                lang = feature_file.language_detected
                
                # Incrementar contador
                self.language_statistics[lang] += 1
                
                # Coletar detalhes
                if lang not in self.language_details:
                    self.language_details[lang] = {
                        'total_files': 0,
                        'valid_files': 0,
                        'repositories': set(),
                        'scenarios': 0,
                        'steps': 0,
                        'sample_files': []
                    }
                
                details = self.language_details[lang]
                details['total_files'] += 1
                details['repositories'].add(repo.name)
                details['scenarios'] += feature_file.scenario_count
                details['steps'] += feature_file.step_count
                
                if feature_file.is_valid:
                    details['valid_files'] += 1
                
                # Adicionar arquivo de exemplo (máximo 5 por linguagem)
                if len(details['sample_files']) < 5:
                    details['sample_files'].append({
                        'repository': repo.name,
                        'file_path': str(feature_file.path),
                        'is_valid': feature_file.is_valid,
                        'scenarios': feature_file.scenario_count,
                        'steps': feature_file.step_count
                    })
    
    def _analyze_repository(self, repo: Repository) -> FeatureAnalysisResult:
        """Analisa um repositório específico"""
        local_path = repo.get_local_path(self.config.repos_dir)
        
        if not local_path.exists():
            return FeatureAnalysisResult(
                repository=repo,
                feature_files=[],
                total_files=0,
                valid_files=0,
                english_files=0,
                total_scenarios=0,
                total_steps=0,
                is_valid_cucumber_repo=False,
                errors=["Repositório não encontrado localmente"]
            )
        
        # Encontrar arquivos .feature
        feature_files = list(local_path.rglob("*.feature")) + list(local_path.rglob("*.features"))
        
        # Adicionar ordenação para garantir determinismo
        feature_files.sort()
        
        analyzed_features = []
        total_scenarios = 0
        total_steps = 0
        valid_count = 0
        english_count = 0
        errors = []
        
        for feature_path in feature_files:
            try:
                # Verificar tamanho do arquivo
                if feature_path.stat().st_size > self.config.max_file_size:
                    self.logger.warning(f"Arquivo muito grande: {feature_path}")
                    continue
                
                feature_analysis = self._analyze_feature_file(feature_path)
                analyzed_features.append(feature_analysis)
                
                if feature_analysis.is_valid:
                    valid_count += 1
                    total_scenarios += feature_analysis.scenario_count
                    total_steps += feature_analysis.step_count
                
                if feature_analysis.is_english:
                    english_count += 1
                    
            except Exception as e:
                error_msg = f"Erro ao analisar {feature_path}: {e}"
                errors.append(error_msg)
                self.logger.warning(error_msg)
        
        # Determinar se é um repositório Cucumber válido
        is_valid_repo = (
            len(analyzed_features) >= self.config.min_feature_files and
            valid_count > 0 and
            english_count > 0
        )
        
        return FeatureAnalysisResult(
            repository=repo,
            feature_files=analyzed_features,
            total_files=len(analyzed_features),
            valid_files=valid_count,
            english_files=english_count,
            total_scenarios=total_scenarios,
            total_steps=total_steps,
            is_valid_cucumber_repo=is_valid_repo,
            errors=errors
        )
    
    def _analyze_feature_file(self, file_path: Path) -> FeatureFile:
        """Analisa um arquivo .feature específico"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return FeatureFile(
                path=file_path,
                content="",
                is_valid=False,
                is_english=False,
                scenario_count=0,
                step_count=0,
                language_detected="unknown",
                errors=[f"Erro ao ler arquivo: {e}"]
            )
        
        # Verificar se arquivo está vazio ou só tem comentários
        is_valid = self._is_valid_feature_content(content)
        
        # Detectar idioma
        is_english, detected_lang = self._detect_language(content)
        
        # Contar cenários e steps
        scenario_count = self._count_scenarios(content)
        step_count = self._count_steps(content)
        
        return FeatureFile(
            path=file_path,
            content=content,
            is_valid=is_valid,
            is_english=is_english,
            scenario_count=scenario_count,
            step_count=step_count,
            language_detected=detected_lang,
            errors=[]
        )
    
    def _is_valid_feature_content(self, content: str) -> bool:
        """Verifica se o conteúdo do feature é válido"""
        if not content.strip():
            return False
        
        # Remover comentários
        lines = [line.strip() for line in content.split('\n') 
                if line.strip() and not line.strip().startswith('#')]
        
        if not lines:
            return False
        
        # Verificar se tem pelo menos uma palavra-chave Gherkin
        content_lower = content.lower()
        has_gherkin = any(keyword in content_lower for keyword in self.english_keywords)
        
        return has_gherkin
    
    def _detect_language(self, content: str) -> tuple[bool, str]:
        """Detecta o idioma do conteúdo"""
        # Extrair apenas o texto dos steps para análise
        step_text = self._extract_step_text(content)
        
        if not step_text:
            return False, "no_text"
        
        try:
            # Usar langdetect para detectar idioma
            detected = langdetect.detect(step_text)
            is_english = detected == 'en'
            
            # Double check: verificar padrões em inglês
            if is_english:
                english_pattern_count = sum(
                    len(re.findall(pattern, content, re.IGNORECASE))
                    for pattern in self.english_step_patterns
                )
                # Se não encontrou padrões suficientes, pode não ser inglês
                if english_pattern_count < 3:
                    is_english = False
            
            return is_english, detected
            
        except LangDetectException:
            return False, "detection_failed"
    
    def _extract_step_text(self, content: str) -> str:
        """Extrai texto dos steps para análise de idioma"""
        step_lines = []
        
        for line in content.split('\n'):
            line = line.strip()
            # Pular comentários e linhas vazias
            if not line or line.startswith('#'):
                continue
            
            # Procurar por linhas que começam com palavras-chave de step
            if re.match(r'^\s*(Given|When|Then|And|But)\s+', line, re.IGNORECASE):
                # Remover a palavra-chave e pegar só o texto
                text = re.sub(r'^\s*(Given|When|Then|And|But)\s+', '', line, flags=re.IGNORECASE)
                step_lines.append(text)
        
        return ' '.join(step_lines)
    
    def _count_scenarios(self, content: str) -> int:
        """Conta número de cenários"""
        pattern = r'^\s*(Scenario|Scenario Outline):'
        return len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))
    
    def _count_steps(self, content: str) -> int:
        """Conta número de steps"""
        pattern = r'^\s*(Given|When|Then|And|But)\s+'
        return len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))