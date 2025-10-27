"""
Analisador de bibliotecas oficiais do Cucumber
"""

import re
import json
import logging
from typing import List, Dict, Set
from pathlib import Path

from .models import Repository, CucumberLibrary, LibraryAnalysisResult
from .config import Config


class CucumberLibraryAnalyzer:
    """Analisa uso de bibliotecas oficiais do Cucumber"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.libraries = self._initialize_cucumber_libraries()
    
    def _initialize_cucumber_libraries(self) -> Dict[str, List[CucumberLibrary]]:
        """Inicializa definições das bibliotecas oficiais do Cucumber"""
        return {
            'nodejs': [
                CucumberLibrary(
                    name='@cucumber/cucumber',
                    package_manager='npm',
                    import_patterns=[
                        r'require\(["\']@cucumber/cucumber["\']',
                        r'import.*from\s+["\']@cucumber/cucumber["\']',
                        r'import\s+.*@cucumber/cucumber'
                    ],
                    file_patterns=['package.json', 'package-lock.json'],
                    documentation_url='https://cucumber.io/docs/installation/javascript/'
                )
            ],
            'java': [
                CucumberLibrary(
                    name='io.cucumber',
                    package_manager='maven/gradle',
                    import_patterns=[
                        r'import\s+io\.cucumber\.',
                        r'@CucumberOptions',
                        r'@RunWith\(Cucumber\.class\)'
                    ],
                    file_patterns=['pom.xml', 'build.gradle', 'build.gradle.kts'],
                    documentation_url='https://cucumber.io/docs/installation/java/'
                )
            ],
            'ruby': [
                CucumberLibrary(
                    name='cucumber',
                    package_manager='gem',
                    import_patterns=[
                        r'require\s+["\']cucumber["\']',
                        r'gem\s+["\']cucumber["\']'
                    ],
                    file_patterns=['Gemfile', 'Gemfile.lock', '*.gemspec'],
                    documentation_url='https://cucumber.io/docs/installation/ruby/'
                )
            ],
            'kotlin': [
                CucumberLibrary(
                    name='io.cucumber',
                    package_manager='maven/gradle',
                    import_patterns=[
                        r'import\s+io\.cucumber\.',
                        r'@CucumberOptions',
                        r'@RunWith\(Cucumber::class\)'
                    ],
                    file_patterns=['pom.xml', 'build.gradle', 'build.gradle.kts'],
                    documentation_url='https://cucumber.io/docs/installation/kotlin/'
                )
            ],
            'go': [
                CucumberLibrary(
                    name='github.com/cucumber/godog',
                    package_manager='go mod',
                    import_patterns=[
                        r'import\s+.*github\.com/cucumber/godog',
                        r'"github\.com/cucumber/godog"'
                    ],
                    file_patterns=['go.mod', 'go.sum'],
                    documentation_url='https://cucumber.io/docs/installation/golang/'
                )
            ],
            'scala': [
                CucumberLibrary(
                    name='io.cucumber',
                    package_manager='sbt/maven',
                    import_patterns=[
                        r'import\s+io\.cucumber\.',
                        r'libraryDependencies.*cucumber'
                    ],
                    file_patterns=['build.sbt', 'pom.xml'],
                    documentation_url='https://cucumber.io/docs/installation/scala/'
                )
            ],
            'cpp': [
                CucumberLibrary(
                    name='cucumber-cpp',
                    package_manager='cmake/conan',
                    import_patterns=[
                        r'#include\s+<cucumber-cpp/',
                        r'GIVEN\s*\(',
                        r'WHEN\s*\(',
                        r'THEN\s*\('
                    ],
                    file_patterns=['CMakeLists.txt', 'conanfile.txt', 'conanfile.py'],
                    documentation_url='https://cucumber.io/docs/installation/cplusplus/'
                )
            ],
            'lua': [
                CucumberLibrary(
                    name='cucumber-lua',
                    package_manager='luarocks',
                    import_patterns=[
                        r'require\s*\(\s*["\']cucumber["\']',
                        r'cucumber\s*=\s*require'
                    ],
                    file_patterns=['*.rockspec', 'luarocks.cfg'],
                    documentation_url='https://cucumber.io/docs/installation/lua/'
                )
            ],
            'ocaml': [
                CucumberLibrary(
                    name='cucumber',
                    package_manager='opam',
                    import_patterns=[
                        r'open\s+Cucumber',
                        r'#require\s+"cucumber"'
                    ],
                    file_patterns=['dune-project', '*.opam', 'dune'],
                    documentation_url='https://cucumber.io/docs/installation/ocaml/'
                )
            ]
        }
    
    def analyze_repositories(self, repositories: List[Repository]) -> Dict[str, LibraryAnalysisResult]:
        """Analisa uso de bibliotecas em todos os repositórios"""
        self.logger.info("Iniciando análise de bibliotecas Cucumber...")
        
        results = {}
        
        # Adicionar ordenação para garantir determinismo
        repositories.sort(key=lambda r: r.name)
        
        for i, repo in enumerate(repositories, 1):
            try:
                self.logger.debug(f"Analisando bibliotecas {repo.name} ({i}/{len(repositories)})")
                result = self._analyze_repository(repo)
                results[repo.name] = result
                
                if i % 50 == 0:
                    self.logger.info(f"Progresso análise bibliotecas: {i}/{len(repositories)}")
                    
            except Exception as e:
                self.logger.error(f"Erro ao analisar bibliotecas {repo.name}: {e}")
                results[repo.name] = LibraryAnalysisResult(
                    repository=repo,
                    detected_libraries=[],
                    uses_official_cucumber=False,
                    package_files_found=[],
                    import_files_found=[],
                    confidence_score=0.0
                )
        
        self.logger.info(f"Análise de bibliotecas concluída para {len(results)} repositórios")
        return results
    
    def _analyze_repository(self, repo: Repository) -> LibraryAnalysisResult:
        """Analisa bibliotecas em um repositório específico"""
        local_path = repo.get_local_path(self.config.repos_dir)
        
        if not local_path.exists():
            return LibraryAnalysisResult(
                repository=repo,
                detected_libraries=[],
                uses_official_cucumber=False,
                package_files_found=[],
                import_files_found=[],
                confidence_score=0.0
            )
        
        # Obter bibliotecas para a linguagem do repositório
        language_libraries = self.libraries.get(repo.language, [])
        
        detected_libraries = []
        package_files_found = []
        import_files_found = []
        total_confidence = 0.0
        
        for library in language_libraries:
            detection_result = self._detect_library_usage(local_path, library)
            
            if detection_result['detected']:
                detected_libraries.append(library)
                package_files_found.extend(detection_result['package_files'])
                import_files_found.extend(detection_result['import_files'])
                total_confidence += detection_result['confidence']
        
        # Calcular confiança média
        avg_confidence = total_confidence / len(language_libraries) if language_libraries else 0.0
        
        uses_official = len(detected_libraries) > 0
        
        return LibraryAnalysisResult(
            repository=repo,
            detected_libraries=detected_libraries,
            uses_official_cucumber=uses_official,
            package_files_found=package_files_found,
            import_files_found=import_files_found,
            confidence_score=avg_confidence
        )
    
    def _detect_library_usage(self, repo_path: Path, library: CucumberLibrary) -> Dict:
        """Detecta uso de uma biblioteca específica"""
        package_files = []
        import_files = []
        confidence = 0.0
        
        # Buscar arquivos de configuração de pacotes
        for pattern in library.file_patterns:
            found_files = list(repo_path.rglob(pattern))
            package_files.extend(found_files)
        
        # Verificar conteúdo dos arquivos de pacote
        package_confidence = self._check_package_files(package_files, library)
        
        # Buscar padrões de import em arquivos de código
        import_confidence = self._check_import_patterns(repo_path, library)
        
        # Confiança total
        confidence = (package_confidence + import_confidence) / 2
        detected = confidence > 0.3  # Threshold para detecção
        
        return {
            'detected': detected,
            'confidence': confidence,
            'package_files': package_files,
            'import_files': import_files
        }
    
    def _check_package_files(self, package_files: List[Path], library: CucumberLibrary) -> float:
        """Verifica bibliotecas em arquivos de configuração"""
        if not package_files:
            return 0.0
        
        total_confidence = 0.0
        files_checked = 0
        
        for file_path in package_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                files_checked += 1
                
                # Buscar nome da biblioteca no conteúdo
                if library.name.lower() in content.lower():
                    total_confidence += 1.0
                elif any(part in content.lower() for part in library.name.split('.')):
                    total_confidence += 0.5
                    
            except Exception as e:
                self.logger.debug(f"Erro ao ler {file_path}: {e}")
                continue
        
        return total_confidence / files_checked if files_checked > 0 else 0.0
    
    def _check_import_patterns(self, repo_path: Path, library: CucumberLibrary) -> float:
        """Verifica padrões de import em arquivos de código"""
        # Extensões de arquivo por linguagem
        extensions_map = {
            'nodejs': ['.js', '.ts', '.mjs'],
            'java': ['.java'],
            'ruby': ['.rb'],
            'kotlin': ['.kt', '.kts'],
            'go': ['.go'],
            'scala': ['.scala'],
            'cpp': ['.cpp', '.cc', '.cxx', '.h', '.hpp'],
            'lua': ['.lua'],
            'ocaml': ['.ml', '.mli']
        }
        
        # Determinar extensões para buscar baseado na linguagem
        language = None
        for lang, libs in self.libraries.items():
            if library in libs:
                language = lang
                break
        
        if not language:
            return 0.0
        
        extensions = extensions_map.get(language, [])
        pattern_matches = 0
        files_checked = 0
        
        # Buscar arquivos com extensões relevantes
        for ext in extensions:
            code_files = list(repo_path.rglob(f"*{ext}"))
            
            for file_path in code_files:
                try:
                    # Limitar tamanho do arquivo para análise
                    if file_path.stat().st_size > self.config.max_file_size:
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    files_checked += 1
                    
                    # Verificar padrões de import
                    for pattern in library.import_patterns:
                        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                            pattern_matches += 1
                            break  # Um match por arquivo é suficiente
                            
                except Exception as e:
                    self.logger.debug(f"Erro ao ler {file_path}: {e}")
                    continue
        
        return pattern_matches / files_checked if files_checked > 0 else 0.0