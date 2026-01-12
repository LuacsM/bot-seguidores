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

### ⚠️ IMPORTANTE: Use Background Worker, não Web Service!

Este bot **NÃO precisa de porta** porque é um processo em background. Configure como **Background Worker**.

### Opção 1: Usando render.yaml (Recomendado)

1. Conecte seu repositório Git no Render
2. O Render detectará automaticamente o arquivo `render.yaml` e criará o serviço como Background Worker
3. Certifique-se de que o arquivo `handles.txt` está no repositório

### Opção 2: Configuração Manual

1. No dashboard do Render, clique em **"New +"** → **"Background Worker"** (NÃO escolha Web Service!)

2. Configure:
   - **Name**: `bot-seguidores`
   - **Environment**: `Python 3`
   - **Build Command**: 
     ```bash
     pip install -r requirements.txt && playwright install chromium
     ```
   - **Start Command**:
     ```bash
     python main.py --handles-file handles.txt --headless --out-dir data_out
     ```

3. **Variáveis de Ambiente** (se necessário):
   - Configure conforme suas necessidades

### 🔧 Solução para erro de porta

Se você ver o erro "No open ports detected":
- **Delete o serviço atual** (se foi criado como Web Service)
- **Crie um novo serviço** selecionando **"Background Worker"** (não Web Service)
- Ou use o arquivo `render.yaml` que já está configurado corretamente

### 💾 Persistência de Dados no Render

⚠️ **IMPORTANTE**: O Render tem sistema de arquivos **efêmero** - arquivos criados são perdidos quando o serviço reinicia.

**Solução: AWS S3** ⭐

O bot está configurado para salvar automaticamente no **AWS S3** quando as credenciais estiverem configuradas.

**Configuração:**
1. Adicione as variáveis de ambiente no Render (veja `CONFIGURAR-S3.md`)
2. O bot detectará automaticamente e começará a salvar no S3
3. Os logs mostrarão: `💾 Storage: S3 (bucket: bot-seguidores-lucasm)`

📖 **Veja `CONFIGURAR-S3.md`** para instruções detalhadas de configuração.

**Sem S3 configurado:**
- Os dados serão salvos localmente (perdidos ao reiniciar)
- Útil apenas para testes
