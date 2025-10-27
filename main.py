#!/usr/bin/env python3
"""
Cucumber Repository Analyzer
Analisa repositórios que usam Cucumber com funil de filtragem otimizado
"""

import os
import sys
import argparse
import logging
from pathlib import Path

from src.config import Config
from src.dataset_manager import DatasetManager
from src.repository_cloner import RepositoryCloner
from src.feature_analyzer import FeatureAnalyzer
from src.cucumber_library_analyzer import CucumberLibraryAnalyzer
from src.output_generator import OutputGenerator
from src.utils.logger import setup_logger


def main():
    parser = argparse.ArgumentParser(description='Cucumber Repository Analyzer')
    parser.add_argument('--input', '-i', required=True, 
                       help='Caminho para o dataset JSON de entrada')
    parser.add_argument('--output-dir', '-o', default='./output',
                       help='Diretório de saída (padrão: ./output)')
    parser.add_argument('--repos-dir', '-r', default='./repositories',
                       help='Diretório para clonar repositórios (padrão: ./repositories)')
    parser.add_argument('--max-repos', '-m', type=int, default=None,
                       help='Número máximo de repositórios para processar')
    parser.add_argument('--languages', '-l', nargs='+', 
                       default=['nodejs', 'java', 'ruby', 'kotlin', 'go', 'scala', 'cpp', 'lua', 'ocaml'],
                       help='Linguagens para analisar')
    parser.add_argument('--skip-clone', action='store_true',
                       help='Pular etapa de clonagem (usar repositórios existentes)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Log verboso')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logger(log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize configuration
        config = Config(
            input_file=args.input,
            output_dir=Path(args.output_dir),
            repos_dir=Path(args.repos_dir),
            max_repos=args.max_repos,
            target_languages=set(args.languages),
            skip_clone=args.skip_clone
        )
        
        # Create output directories
        config.output_dir.mkdir(parents=True, exist_ok=True)
        config.repos_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("=" * 80)
        logger.info("🚀 INICIANDO ANÁLISE DE REPOSITÓRIOS CUCUMBER COM FUNIL DE FILTRAGEM")
        logger.info("=" * 80)
        logger.info(f"📁 Input: {config.input_file}")
        logger.info(f"📁 Output: {config.output_dir}")
        logger.info(f"📁 Repos: {config.repos_dir}")
        logger.info("=" * 80)
        
        # ========================================================================
        # ETAPA 1: Carregar dataset inicial
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("📊 ETAPA 1/5: CARREGAMENTO DO DATASET")
        logger.info("=" * 80)
        
        dataset_manager = DatasetManager(config)
        all_repositories = dataset_manager.load_and_filter_repositories()
        
        if not all_repositories:
            logger.error("❌ Nenhum repositório encontrado para processar")
            return 1
        
        logger.info(f"✅ Total de repositórios carregados: {len(all_repositories)}")
        
        # ========================================================================
        # ETAPA 2: Clonar repositórios (se necessário)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("📊 ETAPA 2/5: CLONAGEM DE REPOSITÓRIOS")
        logger.info("=" * 80)
        
        if not config.skip_clone:
            cloner = RepositoryCloner(config)
            cloner.clone_repositories(all_repositories)
        else:
            logger.info("⏭️  Clonagem pulada (usando repositórios existentes)")
        
        # ========================================================================
        # ETAPA 3: PRÉ-FILTRAGEM - Repositórios com arquivos .feature
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("📊 ETAPA 3/5: PRÉ-FILTRAGEM - REPOSITÓRIOS COM .FEATURE")
        logger.info("=" * 80)
        logger.info(f"🔍 Analisando {len(all_repositories)} repositórios...")
        
        feature_analyzer = FeatureAnalyzer(config)
        
        # Coletar estatísticas pré-filtragem (rápida, só verifica existência)
        repos_with_features = feature_analyzer.quick_filter_repos_with_features(all_repositories)
        
        logger.info(f"✅ Repositórios com arquivos .feature: {len(repos_with_features)}")
        logger.info(f"❌ Repositórios sem .feature: {len(all_repositories) - len(repos_with_features)}")
        logger.info(f"📊 Taxa de retenção: {len(repos_with_features)/len(all_repositories)*100:.1f}%")
        
        if not repos_with_features:
            logger.error("❌ Nenhum repositório com arquivos .feature encontrado")
            return 1
        
        # ========================================================================
        # ETAPA 4: ANÁLISE DE FEATURES VÁLIDAS (apenas repos com .feature)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("📊 ETAPA 4/5: ANÁLISE DE FEATURES VÁLIDAS")
        logger.info("=" * 80)
        logger.info(f"🔍 Analisando {len(repos_with_features)} repositórios com .feature...")
        
        # Agora sim, análise profunda apenas dos repositórios com .feature
        feature_analysis_results = feature_analyzer.analyze_repositories(repos_with_features)
        
        # Filtrar apenas repositórios válidos (features válidas em inglês)
        valid_feature_repos = [
            repo for repo in repos_with_features
            if feature_analysis_results.get(repo.name) and 
               feature_analysis_results[repo.name].is_valid_cucumber_repo
        ]
        
        logger.info(f"✅ Repositórios com features válidas: {len(valid_feature_repos)}")
        logger.info(f"❌ Repositórios com features inválidas: {len(repos_with_features) - len(valid_feature_repos)}")
        logger.info(f"📊 Taxa de retenção: {len(valid_feature_repos)/len(repos_with_features)*100:.1f}%")
        
        if not valid_feature_repos:
            logger.error("❌ Nenhum repositório com features válidas encontrado")
            return 1
        
        # ========================================================================
        # ETAPA 5: ANÁLISE DE BIBLIOTECA OFICIAL (apenas repos válidos)
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("📊 ETAPA 5/5: ANÁLISE DE BIBLIOTECA OFICIAL")
        logger.info("=" * 80)
        logger.info(f"🔍 Analisando {len(valid_feature_repos)} repositórios válidos...")
        
        library_analyzer = CucumberLibraryAnalyzer(config)
        library_analysis_results = library_analyzer.analyze_repositories(valid_feature_repos)
        
	        # Filtrar apenas repositórios com biblioteca oficial
        final_repos = [
            repo for repo in valid_feature_repos
            if library_analysis_results.get(repo.name) and
                library_analysis_results[repo.name].uses_official_cucumber
        ]
	        
        # Adicionar ordenação final para garantir determinismo
        final_repos.sort(key=lambda r: r.name)
        
        logger.info(f"✅ Repositórios com biblioteca oficial: {len(final_repos)}")
        logger.info(f"❌ Repositórios sem biblioteca oficial: {len(valid_feature_repos) - len(final_repos)}")
        logger.info(f"📊 Taxa de retenção: {len(final_repos)/len(valid_feature_repos)*100:.1f}%")
        
        # ========================================================================
        # GERAÇÃO DE RELATÓRIOS
        # ========================================================================
        logger.info("\n" + "=" * 80)
        logger.info("📊 GERANDO RELATÓRIOS")
        logger.info("=" * 80)
        
        output_generator = OutputGenerator(config)
        output_generator.generate_reports(
            all_repositories=all_repositories,
            repos_with_features=repos_with_features,
            valid_feature_repos=valid_feature_repos,
            final_repos=final_repos,
            feature_results=feature_analysis_results,
            library_results=library_analysis_results,
            feature_analyzer=feature_analyzer,
            dataset_manager=dataset_manager
        )
        
        # ========================================================================
        # RESUMO FINAL
        # ========================================================================
        
        # Calcular total de arquivos .feature em cada etapa
        total_files_with_features = feature_analyzer.get_pre_filter_statistics().get('total_feature_files', 0)
        
        total_files_valid = sum(
            result.valid_files 
            for repo in valid_feature_repos 
            if (result := feature_analysis_results.get(repo.name))
        )
        
        total_files_final = sum(
            sum(1 for f in result.feature_files if f.is_valid and f.is_english)
            for repo in final_repos 
            if (result := feature_analysis_results.get(repo.name))
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMO DO FUNIL DE FILTRAGEM")
        logger.info("=" * 80)
        logger.info(f"1️⃣  Repositórios iniciais:          {len(all_repositories):>6} repos")
        logger.info(f"2️⃣  Com arquivos .feature:          {len(repos_with_features):>6} repos ({len(repos_with_features)/len(all_repositories)*100:>5.1f}%) | {total_files_with_features:>6} arquivos")
        logger.info(f"3️⃣  Com features válidas:           {len(valid_feature_repos):>6} repos ({len(valid_feature_repos)/len(repos_with_features)*100:>5.1f}%) | {total_files_valid:>6} arquivos")
        logger.info(f"4️⃣  Com biblioteca oficial:        {len(final_repos):>6} repos ({len(final_repos)/len(valid_feature_repos)*100:>5.1f}%) | {total_files_final:>6} arquivos")
        logger.info("=" * 80)
        logger.info(f"📈 Taxa de sucesso global: {len(final_repos)/len(all_repositories)*100:.2f}%")
        logger.info(f"📁 Total de arquivos .feature no dataset final: {total_files_final}")
        logger.info("=" * 80)
        
        # Estatísticas de linguagens
        language_stats = feature_analyzer.get_language_statistics()
        logger.info("\n📊 Top 10 linguagens detectadas nos arquivos .feature:")
        for lang_code, count in sorted(language_stats['summary'].items(), key=lambda x: x[1], reverse=True)[:10]:
            lang_name = output_generator._get_language_name(lang_code)
            percentage = round((count / language_stats['total_feature_files_analyzed']) * 100, 2)
            logger.info(f"  • {lang_name:20} ({lang_code}): {count:>5} arquivos ({percentage:>5.2f}%)")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ ANÁLISE CONCLUÍDA COM SUCESSO!")
        logger.info(f"📁 Resultados salvos em: {config.output_dir}")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Erro durante a execução: {e}")
        if args.verbose:
            logger.exception("Detalhes do erro:")
        return 1


if __name__ == "__main__":
    sys.exit(main())