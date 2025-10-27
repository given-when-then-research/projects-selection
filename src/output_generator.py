"""
Gerador de relatórios e datasets de saída - com funil de filtragem
"""

import json
import csv
import logging
from typing import List, Dict, Set
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from .models import Repository, FeatureAnalysisResult, LibraryAnalysisResult
from .config import Config


class OutputGenerator:
    """Gera relatórios e datasets de saída"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.feature_results_cache = {}  # Cache para resultados de features
    
    def generate_reports(self, 
                        all_repositories: List[Repository],
                        repos_with_features: List[Repository],
                        valid_feature_repos: List[Repository],
                        final_repos: List[Repository],
                        feature_results: Dict[str, FeatureAnalysisResult],
                        library_results: Dict[str, LibraryAnalysisResult],
                        feature_analyzer=None,
                        dataset_manager=None) -> None:
        """Gera todos os relatórios com informações do funil de filtragem"""
        self.logger.info("📝 Gerando relatórios...")
        
        # Cachear feature_results para uso nos métodos
        self.feature_results_cache = feature_results
        
        # Gerar dataset de metadados com funil de filtragem
        if dataset_manager and feature_analyzer:
            self._generate_filtering_funnel_report(
                all_repositories,
                repos_with_features,
                valid_feature_repos,
                final_repos,
                dataset_manager,
                feature_analyzer
            )
        
        # Gerar dataset principal no novo formato (apenas com biblioteca oficial)
        self._generate_main_dataset_new_format(final_repos, feature_results, library_results)
        
        # Gerar dataset de linguagens detectadas
        if feature_analyzer:
            self._generate_language_detection_dataset(feature_analyzer)
        
        # Gerar relatório estatístico
        self._generate_statistics_report(all_repositories, feature_results, library_results)
        
        # Gerar relatório detalhado por linguagem
        self._generate_language_reports(final_repos, feature_results, library_results)
        
        # Gerar CSV para análise
        self._generate_csv_reports(final_repos, feature_results, library_results)
        
        self.logger.info(f"✅ Relatórios gerados em: {self.config.output_dir}")
    
    def _generate_filtering_funnel_report(self,
                                         all_repositories: List[Repository],
                                         repos_with_features: List[Repository],
                                         valid_feature_repos: List[Repository],
                                         final_repos: List[Repository],
                                         dataset_manager,
                                         feature_analyzer) -> None:
        """Gera relatório completo do funil de filtragem"""
        self.logger.info("📊 Gerando relatório do funil de filtragem...")
        
        metadata_stats = dataset_manager.get_metadata_stats()
        pre_filter_stats = feature_analyzer.get_pre_filter_statistics()
        
        # Calcular taxas de retenção
        retention_rates = {
            'stage_1_with_features': len(repos_with_features) / len(all_repositories) * 100 if all_repositories else 0,
            'stage_2_valid_features': len(valid_feature_repos) / len(repos_with_features) * 100 if repos_with_features else 0,
            'stage_3_official_lib': len(final_repos) / len(valid_feature_repos) * 100 if valid_feature_repos else 0,
            'overall': len(final_repos) / len(all_repositories) * 100 if all_repositories else 0
        }
        
        # Calcular total de arquivos .feature em cada etapa
        total_files_with_features = pre_filter_stats.get('total_feature_files', 0)
        
        # Arquivos válidos (apenas os que passaram na validação)
        total_files_valid = 0
        for repo in valid_feature_repos:
            if repo.name in self.feature_results_cache:
                result = self.feature_results_cache[repo.name]
                total_files_valid += result.valid_files
        
        # Arquivos finais (válidos E em inglês)
        total_files_final = 0
        for repo in final_repos:
            if repo.name in self.feature_results_cache:
                result = self.feature_results_cache[repo.name]
                total_files_final += sum(1 for f in result.feature_files if f.is_valid and f.is_english)
        
        # Estatísticas por linguagem em cada etapa
        stats_by_language = {}
        
        for language in self.config.target_languages:
            lang_all = [r for r in all_repositories if r.language == language]
            lang_with_features = [r for r in repos_with_features if r.language == language]
            lang_valid = [r for r in valid_feature_repos if r.language == language]
            lang_final = [r for r in final_repos if r.language == language]
            
            if lang_all:  # Só inclui linguagem se houver repositórios
                # Contar arquivos por linguagem
                lang_files_with_features = pre_filter_stats.get('by_language', {}).get(language, {}).get('total_feature_files', 0)
                
                lang_files_valid = sum(
                    self.feature_results_cache.get(r.name, type('obj', (), {'valid_files': 0})()).valid_files
                    for r in lang_valid
                )
                
                lang_files_final = sum(
                    sum(1 for f in self.feature_results_cache.get(r.name, type('obj', (), {'feature_files': []})()).feature_files 
                        if hasattr(f, 'is_valid') and f.is_valid and f.is_english)
                    for r in lang_final
                )
                
                stats_by_language[language] = {
                    'stage_0_initial': len(lang_all),
                    'stage_1_with_features': {
                        'repositories': len(lang_with_features),
                        'feature_files': lang_files_with_features
                    },
                    'stage_2_valid_features': {
                        'repositories': len(lang_valid),
                        'feature_files': lang_files_valid
                    },
                    'stage_3_official_library': {
                        'repositories': len(lang_final),
                        'feature_files': lang_files_final
                    },
                    'retention_rates': {
                        'to_stage_1': len(lang_with_features) / len(lang_all) * 100,
                        'to_stage_2': len(lang_valid) / len(lang_with_features) * 100 if lang_with_features else 0,
                        'to_stage_3': len(lang_final) / len(lang_valid) * 100 if lang_valid else 0,
                        'overall': len(lang_final) / len(lang_all) * 100
                    }
                }
        
        funnel_report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'Relatório completo do funil de filtragem de repositórios Cucumber',
                'user': 'lucianobajr',
                'version': '2.0.0'
            },
            'filtering_funnel': {
                'stage_0_initial_dataset': {
                    'description': 'Repositórios carregados do dataset inicial',
                    'total_repositories': len(all_repositories),
                    'repositories_by_language': {
                        lang: len([r for r in all_repositories if r.language == lang])
                        for lang in self.config.target_languages
                    }
                },
                'stage_1_with_feature_files': {
                    'description': 'Repositórios que possuem pelo menos um arquivo .feature',
                    'total_repositories': len(repos_with_features),
                    'total_feature_files': total_files_with_features,
                    'retention_rate': round(retention_rates['stage_1_with_features'], 2),
                    'repositories_by_language': {
                        lang: len([r for r in repos_with_features if r.language == lang])
                        for lang in self.config.target_languages
                    },
                    'feature_files_by_language': {
                        lang: pre_filter_stats.get('by_language', {}).get(lang, {}).get('total_feature_files', 0)
                        for lang in self.config.target_languages
                    }
                },
                'stage_2_valid_features': {
                    'description': 'Repositórios com features válidas em inglês',
                    'total_repositories': len(valid_feature_repos),
                    'total_feature_files': total_files_valid,
                    'retention_rate': round(retention_rates['stage_2_valid_features'], 2),
                    'repositories_by_language': {
                        lang: len([r for r in valid_feature_repos if r.language == lang])
                        for lang in self.config.target_languages
                    }
                },
                'stage_3_official_library': {
                    'description': 'Repositórios que usam biblioteca oficial do Cucumber',
                    'total_repositories': len(final_repos),
                    'total_feature_files': total_files_final,
                    'retention_rate': round(retention_rates['stage_3_official_lib'], 2),
                    'repositories_by_language': {
                        lang: len([r for r in final_repos if r.language == lang])
                        for lang in self.config.target_languages
                    }
                }
            },
            'retention_summary': {
                'overall_retention_rate': round(retention_rates['overall'], 2),
                'repositories_lost': {
                    'no_feature_files': len(all_repositories) - len(repos_with_features),
                    'invalid_features': len(repos_with_features) - len(valid_feature_repos),
                    'no_official_library': len(valid_feature_repos) - len(final_repos)
                },
                'feature_files_summary': {
                    'initial': total_files_with_features,
                    'valid': total_files_valid,
                    'final': total_files_final,
                    'files_lost': {
                        'invalid': total_files_with_features - total_files_valid,
                        'no_official_library': total_files_valid - total_files_final
                    }
                },
                'by_language': stats_by_language
            }
        }
        
        # Salvar relatório
        output_file = self.config.output_dir / 'filtering_funnel_report.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(funnel_report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"✅ Relatório do funil salvo: {output_file}")
    
    def _generate_metadata_dataset(self, dataset_manager, feature_analyzer) -> None:
        """Gera dataset de metadados antes das filtragens"""
        self.logger.info("Gerando dataset de metadados pré-filtragem...")
        
        metadata_stats = dataset_manager.get_metadata_stats()
        pre_filter_stats = feature_analyzer.get_pre_filter_statistics()
        
        metadata_dataset = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'Estatísticas dos repositórios e arquivos .feature antes da aplicação de filtros',
                'user': 'lucianobajr',
                'version': '1.0.0'
            },
            'repository_statistics': {
                'total_repositories': metadata_stats['total_repositories'],
                'total_languages': len(metadata_stats['languages_found']),
                'languages_found': metadata_stats['languages_found'],
                'repositories_by_language': metadata_stats['total_repositories_by_language']
            },
            'feature_files_statistics': {
                'total_repositories_with_features': pre_filter_stats.get('total_repositories_with_features', 0),
                'total_feature_files': pre_filter_stats.get('total_feature_files', 0),
                'feature_files_by_language': {}
            },
            'detailed_by_language': {}
        }
        
        # Estatísticas detalhadas por linguagem
        for language, repo_data in metadata_stats['repository_distribution'].items():
            feature_data = pre_filter_stats.get('by_language', {}).get(language, {})
            
            metadata_dataset['detailed_by_language'][language] = {
                'total_repositories': repo_data['total_repositories'],
                'repositories_with_features': feature_data.get('repositories_with_features', 0),
                'percentage_with_features': round(
                    (feature_data.get('repositories_with_features', 0) / repo_data['total_repositories']) * 100, 2
                ) if repo_data['total_repositories'] > 0 else 0,
                'total_feature_files': feature_data.get('total_feature_files', 0),
                'avg_feature_files_per_repo': round(
                    feature_data.get('total_feature_files', 0) / feature_data.get('repositories_with_features', 1), 2
                ) if feature_data.get('repositories_with_features', 0) > 0 else 0,
                'total_stars': repo_data['total_stars'],
                'avg_stars': round(repo_data['avg_stars'], 2),
                'sample_repositories': repo_data['repositories'][:10]  # Primeiros 10 como amostra
            }
            
            # Adicionar ao resumo
            metadata_dataset['feature_files_statistics']['feature_files_by_language'][language] = feature_data.get('total_feature_files', 0)
        
        # Salvar dataset de metadados
        output_file = self.config.output_dir / 'metadata_pre_filtering.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata_dataset, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Dataset de metadados salvo: {output_file}")
    
    def _generate_main_dataset_new_format(self, 
                                         repositories: List[Repository],
                                         feature_results: Dict[str, FeatureAnalysisResult],
                                         library_results: Dict[str, LibraryAnalysisResult]) -> None:
        """Gera dataset principal no novo formato para análise de pares - APENAS com biblioteca oficial"""
        self.logger.info("Gerando dataset principal no formato para análise de pares (apenas com biblioteca oficial)...")
        
        dataset = {}
        
        # Agrupar por linguagem
        by_language = defaultdict(list)
        for repo in repositories:
            by_language[repo.language].append(repo)
        
        # Contadores para estatísticas
        total_repos_processed = 0
        total_repos_with_features = 0
        total_repos_with_official_lib = 0
        total_repos_final = 0
        
        for language, repos in by_language.items():
            dataset[language] = []
            
            for repo in repos:
                total_repos_processed += 1
                
                feature_result = feature_results.get(repo.name)
                library_result = library_results.get(repo.name)
                
                # ✅ CRITÉRIO 1: Repositório deve ser válido (tem arquivos .feature válidos em inglês)
                if not feature_result or not feature_result.is_valid_cucumber_repo:
                    continue
                
                total_repos_with_features += 1
                
                # ✅ CRITÉRIO 2: Repositório deve usar biblioteca oficial do Cucumber
                if not library_result or not library_result.uses_official_cucumber:
                    continue
                
                total_repos_with_official_lib += 1
                
                # Coletar apenas arquivos válidos em inglês
                valid_feature_files = []
                directories = set()
                
                repo_base_path = repo.get_local_path(self.config.repos_dir)
                
                for feature_file in feature_result.feature_files:
                    if feature_file.is_valid and feature_file.is_english:
                        # Calcular caminho relativo do arquivo
                        try:
                            relative_path = feature_file.path.relative_to(repo_base_path)
                            valid_feature_files.append(str(relative_path))
                            
                            # Adicionar diretório
                            directory = str(relative_path.parent)
                            if directory != '.':
                                directories.add(directory)
                        except ValueError:
                            # Fallback se não conseguir calcular caminho relativo
                            valid_feature_files.append(str(feature_file.path))
                
                # Só incluir se tem arquivos válidos
                if valid_feature_files:
                    total_repos_final += 1
                    
                    repo_data = {
                        'name': repo.name,
                        'url': repo.url,
                        'count': len(valid_feature_files),
                        'feature_files': sorted(valid_feature_files),
                        'directories': sorted(list(directories)) if directories else ['.']
                    }
                    
                    dataset[language].append(repo_data)
            
            # Ordenar repositórios por número de arquivos (decrescente)
            dataset[language].sort(key=lambda x: x['count'], reverse=True)
        
        # Remover linguagens sem repositórios válidos
        dataset = {k: v for k, v in dataset.items() if v}
        
        # Adicionar metadados de filtragem
        dataset_with_metadata = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'user': 'lucianobajr',
                'description': 'Repositórios Cucumber válidos que usam bibliotecas oficiais - para análise de pares',
                'filtering_criteria': {
                    'requires_valid_feature_files': True,
                    'requires_english_content': True,
                    'requires_official_cucumber_library': True,
                    'min_feature_files': self.config.min_feature_files
                },
                'statistics': {
                    'total_repositories_processed': total_repos_processed,
                    'repositories_with_valid_features': total_repos_with_features,
                    'repositories_with_official_library': total_repos_with_official_lib,
                    'final_repositories_included': total_repos_final,
                    'filtering_rate': {
                        'feature_validation': round((total_repos_with_features / total_repos_processed) * 100, 2) if total_repos_processed > 0 else 0,
                        'library_validation': round((total_repos_with_official_lib / total_repos_with_features) * 100, 2) if total_repos_with_features > 0 else 0,
                        'overall_success_rate': round((total_repos_final / total_repos_processed) * 100, 2) if total_repos_processed > 0 else 0
                    }
                }
            },
            # 'repositories': dataset
        }
        
        # Salvar dataset metadata
        output_file_metadata = self.config.output_dir / 'projects_selection_metadata.json'
        with open(output_file_metadata, 'w', encoding='utf-8') as f:
            json.dump(dataset_with_metadata, f, indent=2, ensure_ascii=False)
            
        output_file = self.config.output_dir / 'projects_selection.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Dataset principal para análise de pares salvo: {output_file}")
        
        # Log estatísticas detalhadas do dataset final
        total_files = sum(sum(repo['count'] for repo in repos) for repos in dataset.values())
        
        self.logger.info("=" * 60)
        self.logger.info("📊 ESTATÍSTICAS DE FILTRAGEM")
        self.logger.info("=" * 60)
        self.logger.info(f"📂 Repositórios processados: {total_repos_processed}")
        self.logger.info(f"✅ Com features válidas: {total_repos_with_features} ({round((total_repos_with_features/total_repos_processed)*100, 1)}%)")
        self.logger.info(f"🔧 Com biblioteca oficial: {total_repos_with_official_lib} ({round((total_repos_with_official_lib/total_repos_with_features)*100, 1)}%)")
        self.logger.info(f"🎯 Dataset final: {total_repos_final} repositórios, {total_files} arquivos .feature")
        self.logger.info(f"📈 Taxa de sucesso geral: {round((total_repos_final/total_repos_processed)*100, 2)}%")
        self.logger.info("=" * 60)
        
        for language, repos in dataset.items():
            files_count = sum(repo['count'] for repo in repos)
            self.logger.info(f"  🔹 {language}: {len(repos)} repositórios, {files_count} arquivos .feature")
        
        self.logger.info("=" * 60)
    
    def _generate_language_detection_dataset(self, feature_analyzer) -> None:
        """Gera dataset com todas as linguagens detectadas nos arquivos .feature"""
        self.logger.info("Gerando dataset de detecção de linguagens...")
        
        language_stats = feature_analyzer.get_language_statistics()
        
        # Preparar dados para o dataset
        dataset = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'description': 'Linguagens detectadas em arquivos .feature usando langdetect',
                'total_languages_detected': language_stats['total_languages_detected'],
                'total_feature_files_analyzed': language_stats['total_feature_files_analyzed'],
                'methodology': {
                    'language_detection': 'langdetect library',
                    'text_extraction': 'Content from Given/When/Then/And/But steps',
                    'validation': 'Double-check with English Gherkin patterns'
                }
            },
            'language_summary': {},
            'detailed_statistics': {}
        }
        
        # Resumo das linguagens (ordenado por quantidade)
        sorted_languages = sorted(
            language_stats['summary'].items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for lang_code, count in sorted_languages:
            language_name = self._get_language_name(lang_code)
            dataset['language_summary'][lang_code] = {
                'language_name': language_name,
                'total_files': count,
                'percentage': round((count / language_stats['total_feature_files_analyzed']) * 100, 2)
            }
        
        # Estatísticas detalhadas
        for lang_code, details in language_stats['details'].items():
            # Converter set para list para serialização JSON
            repositories_list = sorted(list(details['repositories']))
            
            dataset['detailed_statistics'][lang_code] = {
                'language_name': self._get_language_name(lang_code),
                'statistics': {
                    'total_files': details['total_files'],
                    'valid_files': details['valid_files'],
                    'invalid_files': details['total_files'] - details['valid_files'],
                    'validity_percentage': round((details['valid_files'] / details['total_files']) * 100, 2) if details['total_files'] > 0 else 0,
                    'total_scenarios': details['scenarios'],
                    'total_steps': details['steps'],
                    'avg_scenarios_per_file': round(details['scenarios'] / details['total_files'], 2) if details['total_files'] > 0 else 0,
                    'avg_steps_per_file': round(details['steps'] / details['total_files'], 2) if details['total_files'] > 0 else 0
                },
                'repository_distribution': {
                    'total_repositories': len(repositories_list),
                    'repositories': repositories_list
                },
                'sample_files': details['sample_files']
            }
        
        # Gerar análise de distribuição
        dataset['distribution_analysis'] = self._generate_language_distribution_analysis(language_stats)
        
        # Salvar dataset
        output_file = self.config.output_dir / 'feature_language_detection.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Dataset de linguagens salvo: {output_file}")
        
        # Gerar CSV resumido das linguagens
        self._generate_language_detection_csv(language_stats)
    
    def _generate_language_detection_csv(self, language_stats: Dict) -> None:
        """Gera CSV com resumo das linguagens detectadas"""
        csv_dir = self.config.output_dir / 'csv'
        csv_dir.mkdir(exist_ok=True)
        
        # CSV principal de linguagens
        languages_csv = csv_dir / 'feature_languages_summary.csv'
        with open(languages_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Cabeçalho
            writer.writerow([
                'language_code', 'language_name', 'total_files', 'valid_files', 
                'invalid_files', 'validity_percentage', 'total_repositories', 
                'total_scenarios', 'total_steps', 'avg_scenarios_per_file', 
                'avg_steps_per_file', 'percentage_of_total'
            ])
            
            # Ordenar por quantidade de arquivos
            sorted_languages = sorted(
                language_stats['details'].items(),
                key=lambda x: x[1]['total_files'],
                reverse=True
            )
            
            total_files = language_stats['total_feature_files_analyzed']
            
            # Dados
            for lang_code, details in sorted_languages:
                language_name = self._get_language_name(lang_code)
                total_lang_files = details['total_files']
                valid_files = details['valid_files']
                invalid_files = total_lang_files - valid_files
                validity_pct = round((valid_files / total_lang_files) * 100, 2) if total_lang_files > 0 else 0
                percentage_total = round((total_lang_files / total_files) * 100, 2) if total_files > 0 else 0
                
                writer.writerow([
                    lang_code,
                    language_name,
                    total_lang_files,
                    valid_files,
                    invalid_files,
                    validity_pct,
                    len(details['repositories']),
                    details['scenarios'],
                    details['steps'],
                    round(details['scenarios'] / total_lang_files, 2) if total_lang_files > 0 else 0,
                    round(details['steps'] / total_lang_files, 2) if total_lang_files > 0 else 0,
                    percentage_total
                ])
        
        self.logger.info(f"CSV de linguagens salvo: {languages_csv}")
    
    def _generate_language_distribution_analysis(self, language_stats: Dict) -> Dict:
        """Gera análise de distribuição das linguagens"""
        total_files = language_stats['total_feature_files_analyzed']
        details = language_stats['details']
        
        # Categorizar linguagens por popularidade
        sorted_by_files = sorted(details.items(), key=lambda x: x[1]['total_files'], reverse=True)
        
        analysis = {
            'top_languages': {
                'top_5': [],
                'top_10': []
            },
            'quality_analysis': {
                'highest_validity': [],
                'lowest_validity': []
            },
            'content_richness': {
                'most_scenarios': [],
                'most_steps': []
            },
            'repository_spread': {
                'most_widespread': [],
                'least_widespread': []
            }
        }
        
        # Top 5 e 10 linguagens
        for i, (lang_code, data) in enumerate(sorted_by_files):
            lang_info = {
                'language_code': lang_code,
                'language_name': self._get_language_name(lang_code),
                'total_files': data['total_files'],
                'percentage': round((data['total_files'] / total_files) * 100, 2)
            }
            
            if i < 5:
                analysis['top_languages']['top_5'].append(lang_info)
            if i < 10:
                analysis['top_languages']['top_10'].append(lang_info)
        
        # Análise de qualidade (validade)
        sorted_by_validity = sorted(
            [(k, v) for k, v in details.items() if v['total_files'] >= 5],  # Mínimo 5 arquivos
            key=lambda x: (x[1]['valid_files'] / x[1]['total_files']) if x[1]['total_files'] > 0 else 0,
            reverse=True
        )
        
        for lang_code, data in sorted_by_validity[:5]:
            validity_pct = round((data['valid_files'] / data['total_files']) * 100, 2)
            analysis['quality_analysis']['highest_validity'].append({
                'language_code': lang_code,
                'language_name': self._get_language_name(lang_code),
                'validity_percentage': validity_pct,
                'valid_files': data['valid_files'],
                'total_files': data['total_files']
            })
        
        for lang_code, data in sorted_by_validity[-5:]:
            validity_pct = round((data['valid_files'] / data['total_files']) * 100, 2)
            analysis['quality_analysis']['lowest_validity'].append({
                'language_code': lang_code,
                'language_name': self._get_language_name(lang_code),
                'validity_percentage': validity_pct,
                'valid_files': data['valid_files'],
                'total_files': data['total_files']
            })
        
        return analysis
    
    def _get_language_name(self, lang_code: str) -> str:
        """Converte código de linguagem para nome legível"""
        language_names = {
            'en': 'English',
            'es': 'Spanish',
            'pt': 'Portuguese',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi',
            'nl': 'Dutch',
            'sv': 'Swedish',
            'da': 'Danish',
            'no': 'Norwegian',
            'fi': 'Finnish',
            'pl': 'Polish',
            'cs': 'Czech',
            'sk': 'Slovak',
            'hu': 'Hungarian',
            'ro': 'Romanian',
            'bg': 'Bulgarian',
            'hr': 'Croatian',
            'sl': 'Slovenian',
            'et': 'Estonian',
            'lv': 'Latvian',
            'lt': 'Lithuanian',
            'tr': 'Turkish',
            'el': 'Greek',
            'he': 'Hebrew',
            'th': 'Thai',
            'vi': 'Vietnamese',
            'id': 'Indonesian',
            'ms': 'Malay',
            'tl': 'Filipino',
            'uk': 'Ukrainian',
            'be': 'Belarusian',
            'mk': 'Macedonian',
            'sq': 'Albanian',
            'ca': 'Catalan',
            'eu': 'Basque',
            'gl': 'Galician',
            'cy': 'Welsh',
            'ga': 'Irish',
            'mt': 'Maltese',
            'is': 'Icelandic',
            'fo': 'Faroese',
            'detection_failed': 'Detection Failed',
            'no_text': 'No Text Content',
            'unknown': 'Unknown'
        }
        
        return language_names.get(lang_code, f'Unknown ({lang_code})')
    
    def _filter_valid_repositories(self, feature_results: Dict[str, FeatureAnalysisResult]) -> List[Repository]:
        """Filtra repositórios que atendem aos critérios"""
        valid_repos = []
        
        for repo_name, result in feature_results.items():
            if result.is_valid_cucumber_repo:
                valid_repos.append(result.repository)
        
        self.logger.info(f"Repositórios válidos: {len(valid_repos)}")
        return valid_repos
    
    def _generate_statistics_report(self, 
                                   repositories: List[Repository],
                                   feature_results: Dict[str, FeatureAnalysisResult],
                                   library_results: Dict[str, LibraryAnalysisResult]) -> None:
        """Gera relatório estatístico"""
        stats = {
            'summary': {
                'total_repositories_processed': len(repositories),
                'valid_cucumber_repositories': sum(1 for r in feature_results.values() if r.is_valid_cucumber_repo),
                'repositories_with_official_libraries': sum(1 for r in library_results.values() if r.uses_official_cucumber),
                'generated_at': datetime.now().isoformat()
            },
            'by_language': {},
            'feature_file_statistics': {
                'total_feature_files': sum(r.total_files for r in feature_results.values()),
                'valid_feature_files': sum(r.valid_files for r in feature_results.values()),
                'english_feature_files': sum(r.english_files for r in feature_results.values()),
                'total_scenarios': sum(r.total_scenarios for r in feature_results.values()),
                'total_steps': sum(r.total_steps for r in feature_results.values())
            },
            'library_usage': {}
        }
        
        # Estatísticas por linguagem
        by_language = {}
        for repo in repositories:
            lang = repo.language
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(repo)
        
        for language, repos in by_language.items():
            lang_stats = {
                'total_repositories': len(repos),
                'valid_repositories': 0,
                'with_official_libraries': 0,
                'total_stars': sum(r.stars for r in repos),
                'avg_stars': sum(r.stars for r in repos) / len(repos) if repos else 0,
                'feature_files': 0,
                'scenarios': 0,
                'steps': 0
            }
            
            for repo in repos:
                feature_result = feature_results.get(repo.name)
                library_result = library_results.get(repo.name)
                
                if feature_result and feature_result.is_valid_cucumber_repo:
                    lang_stats['valid_repositories'] += 1
                    lang_stats['feature_files'] += feature_result.total_files
                    lang_stats['scenarios'] += feature_result.total_scenarios
                    lang_stats['steps'] += feature_result.total_steps
                
                if library_result and library_result.uses_official_cucumber:
                    lang_stats['with_official_libraries'] += 1
            
            stats['by_language'][language] = lang_stats
        
        # Estatísticas de uso de bibliotecas
        library_usage = {}
        for result in library_results.values():
            for lib in result.detected_libraries:
                if lib.name not in library_usage:
                    library_usage[lib.name] = 0
                library_usage[lib.name] += 1
        
        stats['library_usage'] = library_usage
        
        # Salvar relatório
        output_file = self.config.output_dir / 'analysis_statistics.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Relatório estatístico salvo: {output_file}")
    
    def _generate_language_reports(self, 
                                  repositories: List[Repository],
                                  feature_results: Dict[str, FeatureAnalysisResult],
                                  library_results: Dict[str, LibraryAnalysisResult]) -> None:
        """Gera relatórios detalhados por linguagem"""
        language_dir = self.config.output_dir / 'by_language'
        language_dir.mkdir(exist_ok=True)
        
        # Agrupar por linguagem
        by_language = {}
        for repo in repositories:
            if repo.language not in by_language:
                by_language[repo.language] = []
            by_language[repo.language].append(repo)
        
        for language, repos in by_language.items():
            report = {
                'language': language,
                'total_repositories': len(repos),
                'repositories': []
            }
            
            for repo in repos:
                feature_result = feature_results.get(repo.name)
                library_result = library_results.get(repo.name)
                
                repo_detail = {
                    'name': repo.name,
                    'url': repo.url,
                    'stars': repo.stars,
                    'feature_files': [],
                    'detected_libraries': [],
                    'analysis_summary': {
                        'is_valid_cucumber_repo': feature_result.is_valid_cucumber_repo if feature_result else False,
                        'uses_official_libraries': library_result.uses_official_cucumber if library_result else False,
                        'confidence_score': library_result.confidence_score if library_result else 0.0
                    }
                }
                
                # Detalhes dos arquivos feature
                if feature_result:
                    for feature_file in feature_result.feature_files:
                        if feature_file.is_valid and feature_file.is_english:
                            repo_detail['feature_files'].append({
                                'path': str(feature_file.path),
                                'scenarios': feature_file.scenario_count,
                                'steps': feature_file.step_count,
                                'language_detected': feature_file.language_detected
                            })
                
                # Bibliotecas detectadas
                if library_result:
                    repo_detail['detected_libraries'] = [
                        {
                            'name': lib.name,
                            'documentation_url': lib.documentation_url
                        }
                        for lib in library_result.detected_libraries
                    ]
                
                report['repositories'].append(repo_detail)
            
            # Salvar relatório da linguagem
            output_file = language_dir / f'{language}_detailed_report.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Relatório {language} salvo: {output_file}")
    
    def _generate_csv_reports(self, 
                             repositories: List[Repository],
                             feature_results: Dict[str, FeatureAnalysisResult],
                             library_results: Dict[str, LibraryAnalysisResult]) -> None:
        """Gera relatórios CSV para análise"""
        csv_dir = self.config.output_dir / 'csv'
        csv_dir.mkdir(exist_ok=True)
        
        # CSV principal
        main_csv = csv_dir / 'cucumber_repositories_analysis.csv'
        with open(main_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Cabeçalho
            writer.writerow([
                'repository_name', 'owner', 'repo_name', 'url', 'stars', 'language',
                'total_feature_files', 'valid_feature_files', 'english_feature_files',
                'total_scenarios', 'total_steps', 'is_valid_cucumber_repo',
                'uses_official_cucumber', 'detected_libraries', 'confidence_score'
            ])
            
            # Dados
            for repo in repositories:
                feature_result = feature_results.get(repo.name)
                library_result = library_results.get(repo.name)
                
                writer.writerow([
                    repo.name,
                    repo.owner,
                    repo.repo_name,
                    repo.url,
                    repo.stars,
                    repo.language,
                    feature_result.total_files if feature_result else 0,
                    feature_result.valid_files if feature_result else 0,
                    feature_result.english_files if feature_result else 0,
                    feature_result.total_scenarios if feature_result else 0,
                    feature_result.total_steps if feature_result else 0,
                    feature_result.is_valid_cucumber_repo if feature_result else False,
                    library_result.uses_official_cucumber if library_result else False,
                    ';'.join(lib.name for lib in library_result.detected_libraries) if library_result else '',
                    library_result.confidence_score if library_result else 0.0
                ])
        
        self.logger.info(f"CSV principal salvo: {main_csv}")