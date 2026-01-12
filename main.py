#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
    path.parent.mkdir(parents=True, exist_ok=True)

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
    df.to_parquet(path, engine="pyarrow", compression="snappy", index=False)
    return path


# ---------------- MAIN ---------------- #

def main():
    ap = argparse.ArgumentParser(description="Monitor de seguidores (Blastup) salvando em Parquet particionado.")
    ap.add_argument("--handles-file", required=True, help="Arquivo .txt com @/usernames (1 por linha).")
    ap.add_argument("--out-dir", default="data_out", help="Pasta de saída dos parquets.")
    ap.add_argument("--sleep-between-cycles", type=int, default=20, help="Pausa após finalizar a lista toda.")
    ap.add_argument("--headless", action="store_true", help="Rodar sem janela do navegador.")
    ap.add_argument("--profile-dir", default="user_data", help="Perfil persistente do Chromium (cookies/sessão).")
    args = ap.parse_args()

    usernames = load_usernames(args.handles_file)
    if not usernames:
        print("Nenhum @ válido encontrado.")
        return

    print(f"Monitorando {len(usernames)} perfis. Saída Parquet em: {args.out_dir}")
    print("Se aparecer Cloudflare, resolva manualmente na 1ª execução (janela do navegador).\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=args.profile_dir,
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        try:
            while True:
                for i, perfil in enumerate(usernames, start=1):
                    url = BLASTUP_URL.format(perfil)
                    ts = datetime.now(timezone.utc).isoformat()

                    print(f"[{i}/{len(usernames)}] @{perfil}")

                    try:
                        page.goto(url, wait_until="domcontentloaded")
                    except PWTimeoutError:
                        print("   ✖ Timeout ao carregar a página")
                        time.sleep(random.uniform(2.0, 4.0))
                        continue

                    # espera mínima obrigatória
                    time.sleep(MIN_WAIT_PER_PROFILE)

                    seguidores = extract_followers_from_page(page)

                    # retry leve (sem gambiarra)
                    if seguidores is None:
                        time.sleep(3)
                        seguidores = extract_followers_from_page(page)

                    if seguidores is not None:
                        out_path = append_parquet_partitioned(args.out_dir, ts, perfil, seguidores)
                        print(f"   ✔ Seguidores: {seguidores} | salvo em: {out_path}")
                    else:
                        print("   ✖ Não foi possível extrair seguidores (provável challenge/estrutura diferente)")

                    time.sleep(random.uniform(1.5, 3.0))

                print(f"\nCiclo completo. Aguardando {args.sleep_between_cycles}s para reiniciar...\n")
                time.sleep(args.sleep_between_cycles)

        except KeyboardInterrupt:
            print("\nEncerrado pelo usuário.")
        finally:
            context.close()


if __name__ == "__main__":
    main()
