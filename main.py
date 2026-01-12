#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Força flush imediato para logs aparecerem no Render
def log_print(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


BLASTUP_URL = "https://blastup.com/instagram-follower-count?{}"
MIN_WAIT_PER_PROFILE = 10  # espera mínima obrigatória por perfil (segundos)


# ---------------- UTIL ---------------- #

def normalize_username(u: str) -> str:
    u = u.strip()
    if u.startswith("@"):
        u = u[1:]
    return re.sub(r"\s+", "", u)


def load_usernames(handles_file: str) -> list[str]:
    p = Path(handles_file)
    if not p.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {handles_file}")

    users: list[str] = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        u = normalize_username(line)
        if u:
            users.append(u)

    # remove duplicados mantendo ordem
    return list(dict.fromkeys(users))


def looks_like_challenge(text: str) -> Optional[str]:
    s = (text or "").lower()
    for key, msg in [
        ("cloudflare", "Cloudflare"),
        ("verify you are human", "Verificação humana"),
        ("captcha", "CAPTCHA"),
        ("please enable javascript", "Exige JavaScript"),
        ("attention required", "Challenge"),
    ]:
        if key in s:
            return msg
    return None


# ---------------- EXTRAÇÃO ---------------- #

def extract_followers_from_page(page) -> Optional[int]:
    # detecta challenge
    try:
        body_text = page.locator("body").inner_text(timeout=2000)[:800]
        if looks_like_challenge(body_text):
            return None
    except Exception:
        pass

    odo = page.locator("#odometer")
    if odo.count() == 0:
        return None

    # 1) tenta texto direto
    try:
        text = odo.inner_text(timeout=2000)
        digits = re.sub(r"[^\d]", "", text)
        if digits.isdigit():
            return int(digits)
    except Exception:
        pass

    # 2) tenta spans
    try:
        spans = odo.locator(".odometer-value")
        if spans.count() > 0:
            parts = []
            for i in range(min(spans.count(), 60)):
                parts.append(spans.nth(i).inner_text(timeout=2000))
            digits = re.sub(r"[^\d]", "", "".join(parts))
            if digits.isdigit():
                return int(digits)
    except Exception:
        pass

    return None


# ---------------- PARQUET (append particionado) ---------------- #

def append_parquet_partitioned(out_dir: str, data_hora_iso: str, perfil: str, seguidores: int) -> Path:
    """
    Salva em: out_dir/perfil=<perfil>/data=<YYYY-MM-DD>.parquet
    Append lendo o parquet do dia (arquivo pequeno) e sobrescrevendo.
    """
    date = data_hora_iso[:10]  # YYYY-MM-DD

    base = Path(out_dir)
    path = base / f"perfil={perfil}" / f"data={date}.parquet"
    
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        log_print(f"   📁 Diretório criado/verificado: {path.parent}")
    except Exception as e:
        log_print(f"   ✖ Erro ao criar diretório {path.parent}: {e}")
        raise

    df_new = pd.DataFrame([{
        "data_hora": data_hora_iso,
        "perfil": perfil,
        "seguidores": int(seguidores),
    }])

    if path.exists() and path.stat().st_size > 0:
        try:
            df_old = pd.read_parquet(path)
            df = pd.concat([df_old, df_new], ignore_index=True)
        except Exception:
            # se der ruim lendo (arquivo corrompido), cria um backup e recomeça o dia
            bak = path.with_suffix(path.suffix + ".bak")
            try:
                path.replace(bak)
            except Exception:
                pass
            df = df_new
    else:
        df = df_new

    # compressão snappy: ótima e rápida
    try:
        df.to_parquet(path, engine="pyarrow", compression="snappy", index=False)
        log_print(f"   💾 Arquivo salvo: {path} ({path.stat().st_size} bytes)")
        return path
    except Exception as e:
        log_print(f"   ✖ Erro ao salvar parquet {path}: {e}")
        raise


# ---------------- MAIN ---------------- #

def main():
    # Logs imediatos para debug no Render
    log_print("=" * 60)
    log_print("🚀 Bot Seguidores Instagram - Iniciando...")
    log_print("=" * 60)
    log_print(f"📅 Data/Hora: {datetime.now(timezone.utc).isoformat()}")
    log_print(f"🐍 Python: {sys.version}")
    log_print(f"📂 Diretório de trabalho: {Path.cwd()}")
    log_print("=" * 60)
    
    try:
        ap = argparse.ArgumentParser(description="Monitor de seguidores (Blastup) salvando em Parquet particionado.")
        ap.add_argument("--handles-file", required=True, help="Arquivo .txt com @/usernames (1 por linha).")
        ap.add_argument("--out-dir", default="data_out", help="Pasta de saída dos parquets.")
        ap.add_argument("--sleep-between-cycles", type=int, default=20, help="Pausa após finalizar a lista toda.")
        ap.add_argument("--headless", action="store_true", help="Rodar sem janela do navegador.")
        ap.add_argument("--profile-dir", default="user_data", help="Perfil persistente do Chromium (cookies/sessão).")
        args = ap.parse_args()
        
        log_print("✅ Argumentos parseados com sucesso")
        log_print(f"   --handles-file: {args.handles_file}")
        log_print(f"   --out-dir: {args.out_dir}")
        log_print(f"   --headless: {args.headless}")
    except Exception as e:
        log_print(f"✖ Erro ao parsear argumentos: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    log_print("📖 Carregando arquivo de handles...")
    try:
        usernames = load_usernames(args.handles_file)
        log_print(f"✅ Arquivo {args.handles_file} carregado")
    except Exception as e:
        log_print(f"✖ Erro ao carregar {args.handles_file}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    if not usernames:
        log_print("✖ Nenhum @ válido encontrado.")
        sys.exit(1)

    log_print(f"✅ {len(usernames)} perfis carregados: {', '.join(usernames)}")
    log_print(f"📂 Diretório de saída: {args.out_dir}")
    log_print(f"🌐 Modo headless: {args.headless}")
    log_print(f"⏱️  Espera entre ciclos: {args.sleep_between_cycles}s")
    log_print("=" * 60)
    log_print("Se aparecer Cloudflare, resolva manualmente na 1ª execução (janela do navegador).\n")

    log_print("🎭 Inicializando Playwright...")
    try:
        with sync_playwright() as p:
            log_print("✅ Playwright iniciado")
            
            log_print("🌐 Lançando navegador Chromium...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=args.profile_dir,
                headless=args.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            log_print("✅ Navegador lançado")
            
            page = context.new_page()
            page.set_default_timeout(30000)
            log_print("✅ Página criada, iniciando loop principal...")
            log_print("=" * 60)

            try:
                while True:
                    for i, perfil in enumerate(usernames, start=1):
                        url = BLASTUP_URL.format(perfil)
                        ts = datetime.now(timezone.utc).isoformat()

                        log_print(f"[{i}/{len(usernames)}] @{perfil}")

                        try:
                            log_print(f"   🌐 Acessando: {url}")
                            page.goto(url, wait_until="domcontentloaded")
                            log_print("   ✅ Página carregada")
                        except PWTimeoutError:
                            log_print("   ✖ Timeout ao carregar a página")
                            time.sleep(random.uniform(2.0, 4.0))
                            continue
                        except Exception as e:
                            log_print(f"   ✖ Erro ao carregar página: {e}")
                            time.sleep(random.uniform(2.0, 4.0))
                            continue

                        # espera mínima obrigatória
                        log_print(f"   ⏳ Aguardando {MIN_WAIT_PER_PROFILE}s...")
                        time.sleep(MIN_WAIT_PER_PROFILE)

                        log_print("   🔍 Extraindo número de seguidores...")
                        seguidores = extract_followers_from_page(page)

                        # retry leve (sem gambiarra)
                        if seguidores is None:
                            log_print("   🔄 Retry: tentando novamente...")
                            time.sleep(3)
                            seguidores = extract_followers_from_page(page)

                        if seguidores is not None:
                            log_print(f"   ✅ Seguidores encontrados: {seguidores}")
                            out_path = append_parquet_partitioned(args.out_dir, ts, perfil, seguidores)
                            log_print(f"   ✔ Seguidores: {seguidores} | salvo em: {out_path}")
                        else:
                            log_print("   ✖ Não foi possível extrair seguidores (provável challenge/estrutura diferente)")

                        time.sleep(random.uniform(1.5, 3.0))

                    log_print(f"\n✅ Ciclo completo. Aguardando {args.sleep_between_cycles}s para reiniciar...\n")
                    time.sleep(args.sleep_between_cycles)

            except KeyboardInterrupt:
                log_print("\n⚠️  Encerrado pelo usuário.")
            except Exception as e:
                log_print(f"\n✖ Erro inesperado: {e}")
                import traceback
                traceback.print_exc()
            finally:
                log_print("\n🛑 Fechando navegador...")
                try:
                    context.close()
                    log_print("✅ Navegador fechado.")
                except:
                    pass
    except Exception as e:
        log_print(f"✖ Erro ao iniciar Playwright: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
