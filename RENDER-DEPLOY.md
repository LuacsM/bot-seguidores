# 🚀 Instruções de Deploy no Render

## ⚠️ PROBLEMA: "No open ports detected"

Se você está vendo esse erro, significa que o serviço foi criado como **Web Service** ao invés de **Background Worker**.

## ✅ SOLUÇÃO

### Passo 1: Delete o serviço atual
1. Vá no dashboard do Render
2. Encontre o serviço `bot-seguidores` (ou o nome que você deu)
3. Clique em **Settings** → **Delete Service**

### Passo 2: Crie um novo serviço como Background Worker

**Opção A: Usando render.yaml (Mais fácil)**

1. No dashboard do Render, clique em **"New +"** → **"Blueprint"**
2. Conecte seu repositório Git
3. O Render detectará automaticamente o `render.yaml` e criará como Background Worker
4. ✅ Pronto!

**Opção B: Manual**

1. No dashboard do Render, clique em **"New +"** → **"Background Worker"** ⚠️ (NÃO escolha Web Service!)
2. Conecte seu repositório Git
3. Configure:
   - **Name**: `bot-seguidores`
   - **Environment**: `Python 3`
   - **Region**: Escolha a mais próxima
   - **Branch**: `main` (ou a branch que você usa)
   - **Root Directory**: (deixe vazio)
   - **Build Command**: 
     ```bash
     pip install -r requirements.txt && playwright install chromium
     ```
   - **Start Command**:
     ```bash
     python main.py --handles-file handles.txt --headless --out-dir data_out
     ```
4. Clique em **"Create Background Worker"**

## 📝 Checklist

- [ ] Serviço criado como **Background Worker** (não Web Service)
- [ ] Arquivo `handles.txt` está no repositório Git
- [ ] Build Command inclui `playwright install chromium`
- [ ] Start Command está correto

## 🔍 Como verificar se está correto

- ✅ Background Worker: Não precisa de porta, roda continuamente
- ❌ Web Service: Precisa de porta, tenta detectar HTTP

Se você ver "No open ports detected", significa que está como Web Service. Delete e recrie como Background Worker.
