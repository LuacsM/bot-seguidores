"""
Módulo para salvar parquet files no AWS S3
"""
import io
import os
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

import pandas as pd


def get_s3_client():
    """Cria cliente S3 usando credenciais de variáveis de ambiente"""
    if not S3_AVAILABLE:
        raise ImportError("boto3 não está instalado. Execute: pip install boto3")
    
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )


def append_parquet_s3(
    bucket_name: str,
    s3_key: str,
    data_hora_iso: str,
    perfil: str,
    seguidores: int,
    log_print=print
) -> str:
    """
    Salva parquet no S3 com append.
    
    Args:
        bucket_name: Nome do bucket S3
        s3_key: Caminho no S3 (ex: 'data/perfil=openai/data=2026-01-12.parquet')
        data_hora_iso: Timestamp ISO
        perfil: Nome do perfil
        seguidores: Número de seguidores
        log_print: Função de log
    
    Returns:
        Caminho completo no S3 (s3://bucket/key)
    """
    date = data_hora_iso[:10]  # YYYY-MM-DD
    s3_path = f"{s3_key}/perfil={perfil}/data={date}.parquet"
    s3_uri = f"s3://{bucket_name}/{s3_path}"
    
    s3_client = get_s3_client()
    
    # Cria DataFrame com novo dado
    df_new = pd.DataFrame([{
        "data_hora": data_hora_iso,
        "perfil": perfil,
        "seguidores": int(seguidores),
    }])
    
    # Tenta ler arquivo existente do S3
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_path)
        df_old = pd.read_parquet(io.BytesIO(response['Body'].read()))
        df = pd.concat([df_old, df_new], ignore_index=True)
        log_print(f"   📥 Arquivo existente carregado do S3: {s3_path}")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            # Arquivo não existe, cria novo
            df = df_new
            log_print(f"   📝 Criando novo arquivo no S3: {s3_path}")
        elif error_code == 'AccessDenied':
            log_print(f"   ⚠️  Acesso negado ao ler do S3. Verifique as permissões IAM:")
            log_print(f"      - Precisa de: s3:GetObject no bucket {bucket_name}")
            log_print(f"      - Veja CORRIGIR-PERMISSOES-S3.md para instruções")
            df = df_new
        else:
            log_print(f"   ⚠️  Erro ao ler do S3 ({error_code}): {e}")
            df = df_new
    except Exception as e:
        log_print(f"   ⚠️  Erro ao processar arquivo do S3: {e}")
        df = df_new
    
    # Salva no buffer e faz upload para S3
    try:
        buffer = io.BytesIO()
        df.to_parquet(buffer, engine="pyarrow", compression="snappy", index=False)
        buffer.seek(0)
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_path,
            Body=buffer.getvalue(),
            ContentType='application/octet-stream'
        )
        
        size_kb = len(buffer.getvalue()) / 1024
        log_print(f"   💾 Arquivo salvo no S3: {s3_uri} ({size_kb:.2f} KB)")
        return s3_uri
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            log_print(f"   ✖ Acesso negado ao salvar no S3!")
            log_print(f"   📋 Permissões necessárias no IAM:")
            log_print(f"      - s3:PutObject no bucket {bucket_name}")
            log_print(f"      - s3:GetObject no bucket {bucket_name}")
            log_print(f"      - s3:ListBucket no bucket {bucket_name} (opcional)")
            log_print(f"   📖 Veja CORRIGIR-PERMISSOES-S3.md para instruções detalhadas")
        else:
            log_print(f"   ✖ Erro ao salvar no S3 ({error_code}): {e}")
        raise
    except Exception as e:
        log_print(f"   ✖ Erro ao salvar no S3: {e}")
        raise


def read_parquet_s3(bucket_name: str, s3_key: str) -> Optional[pd.DataFrame]:
    """
    Lê um arquivo parquet do S3.
    
    Args:
        bucket_name: Nome do bucket
        s3_key: Caminho completo no S3
    
    Returns:
        DataFrame ou None se não existir
    """
    s3_client = get_s3_client()
    
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        df = pd.read_parquet(io.BytesIO(response['Body'].read()))
        return df
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise
    except Exception as e:
        raise Exception(f"Erro ao ler do S3: {e}")
