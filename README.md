# Bot Seguidores Instagram

Bot para monitorar contagem de seguidores de perfis do Instagram usando Blastup, salvando os dados em formato Parquet particionado.

## 📋 Requisitos

- Python 3.8+
- Playwright (navegador Chromium)

## 🚀 Instalação

1. Clone o repositório:
```bash
git clone <seu-repositorio>
cd BOT-SEGUIDORES
```

2. Crie um ambiente virtual:
```bash
python -m venv venv
```

3. Ative o ambiente virtual:
- Windows: `venv\Scripts\activate`
- Linux/Mac: `source venv/bin/activate`

4. Instale as dependências:
```bash
pip install -r requirements.txt
```

5. Instale os navegadores do Playwright:
```bash
playwright install chromium
```

## 📝 Uso

Crie um arquivo `handles.txt` com os usernames do Instagram (um por linha, com ou sem @):

```
marciele.albuquerque
openai
nasa
```

Execute o bot:
```bash
python main.py --handles-file handles.txt --out-dir data_out --headless
```

### Opções disponíveis:

- `--handles-file`: Arquivo .txt com usernames (obrigatório)
- `--out-dir`: Pasta de saída dos parquets (padrão: `data_out`)
- `--sleep-between-cycles`: Pausa em segundos após finalizar a lista (padrão: 20)
- `--headless`: Rodar sem janela do navegador
- `--profile-dir`: Diretório do perfil persistente do Chromium (padrão: `user_data`)

### Exemplo com todas as opções:
```bash
python main.py --handles-file handles.txt --out-dir data_out --sleep-between-cycles 30 --headless
```

## 📊 Saída

Os dados são salvos em formato Parquet particionado:
```
data_out/
  perfil=<username>/
    data=YYYY-MM-DD.parquet
```

Cada arquivo contém colunas:
- `data_hora`: Timestamp ISO 8601
- `perfil`: Username do Instagram
- `seguidores`: Número de seguidores

## ⚠️ Notas

- Na primeira execução, pode aparecer um desafio do Cloudflare. Resolva manualmente na janela do navegador.
- O bot aguarda no mínimo 10 segundos entre cada perfil para evitar rate limiting.
- Use `Ctrl+C` para encerrar o bot.

## 🚀 Deploy no Render

Para fazer deploy no Render, configure:

1. **Build Command**: 
   ```bash
   pip install -r requirements.txt && playwright install chromium
   ```

2. **Start Command**:
   ```bash
   python main.py --handles-file handles.txt --headless --out-dir data_out
   ```

3. **Variáveis de Ambiente** (se necessário):
   - Configure conforme suas necessidades

4. **Tipo de Serviço**: Web Service ou Background Worker (dependendo se você quer que rode continuamente)
