#!/usr/bin/env python3
"""
Script para unificar equipos que sufrieron un cambio de nombre durante la temporada.
Renombra todas las referencias y consolida las estadísticas de jugadores duplicados.

Uso: python join_same_teams.py
"""

import os
import pandas as pd
from pathlib import Path
import shutil
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== CONFIGURACIÓN =====
OLD_TEAM_NAME = "UEMC CBC VALLADOLID"
NEW_TEAM_NAME = "UEMC BALONCESTO VALLADOLID"
DATA_FOLDER = Path("data/2FEB_25_26")

# Columnas que deben sumarse (totales)
SUM_COLUMNS = [
    'MINUTOS JUGADOS', 'PUNTOS', 'T2 CONVERTIDO', 'T2 INTENTADO',
    'T3 CONVERTIDO', 'T3 INTENTADO', 'TL CONVERTIDOS', 'TL INTENTADOS',
    'REB OFFENSIVO', 'REB DEFENSIVO', 'ASISTENCIAS', 'RECUPEROS',
    'PERDIDAS', 'FaltasCOMETIDAS', 'FaltasRECIBIDAS',
    'PUNTOS +', 'PUNTOS -'
]

# Columnas que deben promediarse (porcentajes y ratios)
# PER y PACE se revisan como coincidencia exacta para evitar match con PERDIDAS/RECUPEROS
AVERAGE_COLUMNS_EXACT = ['PER', 'PACE']

AVERAGE_COLUMNS_CONTAINS = [
    '%REB', '%OREB', '%DREB', 'PPP', 'PPP OPP', 
    'OFFRTG', 'DEFRTG', 'NETRTG', 'TS%', 'EFG%', 'TOV%', 
    '%AST', 'USG%', 'FG%', '2P%', '3P%', 'FT%', 
    'ORB%', 'DRB%', 'TRB%', 'AST%', 'STL%', 'BLK%'
]


def backup_folder(folder_path: Path) -> Path:
    """Crea un backup de la carpeta antes de modificar."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = folder_path.parent / f"{folder_path.name}_backup_{timestamp}"
    
    logger.info(f"📦 Creando backup: {backup_path}")
    shutil.copytree(folder_path, backup_path)
    return backup_path


def rename_team_in_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Renombra todas las referencias del equipo antiguo al nuevo.
    Retorna el dataframe modificado y el número de cambios realizados.
    """
    changes = 0
    
    # Buscar columnas que contengan nombres de equipos
    team_columns = []
    for col in df.columns:
        if 'EQUIPO' in col.upper() or 'LOCAL' in col.upper() or 'RIVAL' in col.upper():
            team_columns.append(col)
    
    # Renombrar en cada columna encontrada
    for col in team_columns:
        if col in df.columns:
            mask = df[col] == OLD_TEAM_NAME
            if mask.any():
                df.loc[mask, col] = NEW_TEAM_NAME
                count = mask.sum()
                changes += count
                logger.info(f"  ✏️  Columna '{col}': {count} cambios")
    
    return df, changes


def consolidate_duplicate_players(df: pd.DataFrame, file_type: str) -> pd.DataFrame:
    """
    Consolida jugadores/equipos duplicados que aparecen bajo ambos nombres de equipo.
    Suma estadísticas totales y promedia porcentajes.
    """
    # Para archivos de equipos (teams), consolidar por EQUIPO
    if 'EQUIPO' in df.columns and 'JUGADOR' not in df.columns:
        return consolidate_duplicate_teams(df)
    
    # Para archivos de jugadores, consolidar por JUGADOR
    if 'JUGADOR' not in df.columns or 'EQUIPO' not in df.columns:
        return df
    
    # Identificar columnas de agrupación
    group_cols = ['JUGADOR']
    if 'FASE' in df.columns:
        group_cols.append('FASE')
    
    # Verificar si hay jugadores duplicados (mismo nombre, diferentes equipos Valladolid)
    valladolid_mask = df['EQUIPO'].isin([OLD_TEAM_NAME, NEW_TEAM_NAME])
    valladolid_df = df[valladolid_mask]
    
    if len(valladolid_df) == 0:
        return df
    
    # Contar duplicados
    duplicates = valladolid_df.groupby(group_cols).size()
    duplicates = duplicates[duplicates > 1]
    
    if len(duplicates) == 0:
        logger.info(f"  ℹ️  No se encontraron jugadores duplicados")
        return df
    
    logger.info(f"  🔄 Consolidando {len(duplicates)} jugadores duplicados...")
    
    # Separar jugadores de Valladolid de otros
    non_valladolid_df = df[~valladolid_mask].copy()
    
    # Identificar columnas numéricas
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    # Remover columnas de grupo de las numéricas
    numeric_cols = [col for col in numeric_cols if col not in group_cols]
    
    # Crear diccionario de agregación
    agg_dict = {}
    
    for col in numeric_cols:
        # Determinar si es suma o promedio
        # Usar coincidencia exacta para PER/PACE, substring para otros
        should_average = (col in AVERAGE_COLUMNS_EXACT or 
                        any(pattern in col for pattern in AVERAGE_COLUMNS_CONTAINS))
        
        if should_average:
            agg_dict[col] = 'mean'
        else:
            agg_dict[col] = 'sum'
    
    # Agregar columna EQUIPO (tomar el nuevo nombre)
    agg_dict['EQUIPO'] = lambda x: NEW_TEAM_NAME
    
    # Columnas no numéricas, no de grupo
    other_cols = [col for col in valladolid_df.columns 
                  if col not in group_cols and col not in numeric_cols and col != 'EQUIPO']
    for col in other_cols:
        agg_dict[col] = 'first'
    
    # Agregar jugadores de Valladolid
    consolidated_valladolid = valladolid_df.groupby(group_cols, as_index=False).agg(agg_dict)
    
    # Combinar con otros equipos
    result_df = pd.concat([non_valladolid_df, consolidated_valladolid], ignore_index=True)
    
    logger.info(f"  ✅ Consolidación completa: {len(valladolid_df)} → {len(consolidated_valladolid)} filas")
    
    return result_df


def consolidate_duplicate_teams(df: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida filas duplicadas del mismo equipo (para archivos teams.xlsx).
    """
    # Verificar si hay filas de Valladolid
    valladolid_mask = df['EQUIPO'] == NEW_TEAM_NAME
    valladolid_df = df[valladolid_mask]
    
    if len(valladolid_df) <= 1:
        logger.info(f"  ℹ️  Solo hay {len(valladolid_df)} fila(s) del equipo, no requiere consolidación")
        return df
    
    logger.info(f"  🔄 Consolidando {len(valladolid_df)} filas del equipo...")
    
    # Separar Valladolid de otros equipos
    non_valladolid_df = df[~valladolid_mask].copy()
    
    # Identificar columnas de agrupación
    group_cols = ['EQUIPO']
    if 'FASE' in df.columns:
        group_cols.append('FASE')
    
    # Identificar columnas numéricas
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    numeric_cols = [col for col in numeric_cols if col not in group_cols]
    
    # Crear diccionario de agregación
    agg_dict = {}
    
    for col in numeric_cols:
        # Determinar si es suma o promedio
        # Usar coincidencia exacta para PER/PACE, substring para otros
        should_average = (col in AVERAGE_COLUMNS_EXACT or 
                        any(pattern in col for pattern in AVERAGE_COLUMNS_CONTAINS))
        
        if should_average:
            agg_dict[col] = 'mean'
        else:
            agg_dict[col] = 'sum'
    
    # Columnas no numéricas, no de grupo
    other_cols = [col for col in valladolid_df.columns 
                  if col not in group_cols and col not in numeric_cols]
    for col in other_cols:
        agg_dict[col] = 'first'
    
    # Agregar equipo de Valladolid
    consolidated_valladolid = valladolid_df.groupby(group_cols, as_index=False).agg(agg_dict)
    
    # Combinar con otros equipos
    result_df = pd.concat([non_valladolid_df, consolidated_valladolid], ignore_index=True)
    
    logger.info(f"  ✅ Consolidación de equipo completa: {len(valladolid_df)} → {len(consolidated_valladolid)} filas")
    
    return result_df


def process_excel_file(file_path: Path) -> bool:
    """
    Procesa un archivo Excel: renombra el equipo y consolida duplicados.
    Retorna True si se realizaron cambios.
    """
    logger.info(f"\n📄 Procesando: {file_path.name}")
    
    try:
        # Leer Excel
        df = pd.read_excel(file_path)
        original_rows = len(df)
        file_name = file_path.stem.lower()
        
        # 1. Renombrar referencias al equipo
        df, rename_changes = rename_team_in_dataframe(df)
        
        # 2. Consolidar jugadores/equipos duplicados
        # Para todos los archivos que tengan columna EQUIPO
        if 'EQUIPO' in df.columns:
            df = consolidate_duplicate_players(df, file_name)
        
        # 3. Guardar si hubo cambios
        final_rows = len(df)
        if rename_changes > 0 or original_rows != final_rows:
            df.to_excel(file_path, index=False)
            logger.info(f"  💾 Guardado: {rename_changes} renombres, {original_rows} → {final_rows} filas")
            return True
        else:
            logger.info(f"  ⏭️  Sin cambios")
            return False
            
    except Exception as e:
        logger.error(f"  ❌ Error procesando {file_path.name}: {e}")
        return False


def main():
    """Función principal."""
    logger.info("="*80)
    logger.info("🏀 Script de Unificación de Equipos Renombrados")
    logger.info("="*80)
    logger.info(f"📁 Carpeta: {DATA_FOLDER}")
    logger.info(f"🔄 Cambio: '{OLD_TEAM_NAME}' → '{NEW_TEAM_NAME}'")
    logger.info("="*80)
    
    # Verificar que existe la carpeta
    if not DATA_FOLDER.exists():
        logger.error(f"❌ No se encontró la carpeta: {DATA_FOLDER}")
        return
    
    # Crear backup
    backup_path = backup_folder(DATA_FOLDER)
    logger.info(f"✅ Backup creado: {backup_path.name}\n")
    
    # Buscar todos los archivos Excel
    excel_files = list(DATA_FOLDER.glob("*.xlsx"))
    
    if not excel_files:
        logger.warning(f"⚠️  No se encontraron archivos .xlsx en {DATA_FOLDER}")
        return
    
    logger.info(f"📊 Archivos encontrados: {len(excel_files)}\n")
    
    # Procesar cada archivo
    processed = 0
    modified = 0
    
    for excel_file in excel_files:
        if process_excel_file(excel_file):
            modified += 1
        processed += 1
    
    # Resumen
    logger.info("\n" + "="*80)
    logger.info("📋 RESUMEN")
    logger.info("="*80)
    logger.info(f"✅ Archivos procesados: {processed}")
    logger.info(f"📝 Archivos modificados: {modified}")
    logger.info(f"📦 Backup disponible en: {backup_path.name}")
    logger.info("="*80)
    logger.info("✨ Proceso completado\n")


if __name__ == "__main__":
    main()
