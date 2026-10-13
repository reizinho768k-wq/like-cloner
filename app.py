from flask import Flask, request, jsonify, render_template_string
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Visual do Painel de Testes
HTML_VISUAL = """
<!DOCTYPE html>
<html lang="pt-PT">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel de Likes - Free Fire</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background-color: #0b0f19; color: #ffffff; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
        .container { width: 100%; max-width: 500px; background: #131b2e; border: 1px solid #1e293b; border-radius: 16px; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        h2 { font-size: 24px; margin-bottom: 8px; color: #f8fafc; }
        p.subtitle { color: #94a3b8; font-size: 14px; margin-bottom: 25px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; font-size: 13px; color: #cbd5e1; margin-bottom: 8px; font-weight: 600; text-transform: uppercase; }
        input { width: 100%; padding: 14px 16px; background: #0b0f19; border: 1px solid #334155; border-radius: 10px; color: #fff; font-size: 16px; outline: none; }
        input:focus { border-color: #3b82f6; }
        button { width: 100%; padding: 14px; background: linear-gradient(135deg, #2563eb, #1d4ed8); border: none; border-radius: 10px; color: white; font-size: 16px; font-weight: bold; cursor: pointer; }
        button:hover { opacity: 0.9; }
        .loading { display: none; text-align: center; margin-top: 20px; color: #38bdf8; font-size: 14px; }
        .spinner { width: 24px; height: 24px; border: 3px solid rgba(56, 189, 248, 0.3); border-radius: 50%; border-top-color: #38bdf8; animation: spin 0.8s linear infinite; margin: 10px auto; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .result-box { display: none; margin-top: 25px; background: #0b0f19; border: 1px solid #1e293b; border-radius: 12px; padding: 20px; font-size: 13px; color: #e2e8f0; white-space: pre-wrap; word-break: break-all; max-height: 250px; overflow-y: auto; }
        .status-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: bold; margin-bottom: 15px; }
        .status-success { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .status-error { background: rgba(239, 68, 68, 0.2); color: #f87171; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔥 Envio de Likes FF</h2>
        <p class="subtitle">Modo convidado 100% dinâmico e isolado</p>
        
        <div class="form-group">
            <label for="playerId">ID do Jogador</label>
            <input type="text" id="playerId" placeholder="Digite o ID do usuário" autocomplete="off">
        </div>

        <button id="btnEnviar" onclick="enviarLikes()">Enviar Likes</button>

        <div class="loading" id="loadingDiv">
            <div class="spinner"></div>
            Criando nova sessão de convidado e enviando para o ID...
        </div>

        <div class="result-box" id="resultBox"></div>
    </div>

    <script>
        async function enviarLikes() {
            const id = document.getElementById('playerId').value.trim();
            const btn = document.getElementById('btnEnviar');
            const loading = document.getElementById('loadingDiv');
            const resultBox = document.getElementById('resultBox');

            if (!id) {
                alert('Por favor, insira o ID do jogador!');
                return;
            }

            btn.disabled = true;
            loading.style.display = 'block';
            resultBox.style.display = 'none';
            resultBox.innerHTML = '';

            try {
                const response = await fetch('/enviar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: id })
                });

                const data = await response.json();
                
                loading.style.display = 'none';
                btn.disabled = false;
                resultBox.style.display = 'block';

                if (response.ok && data.status === 'sucesso') {
                    resultBox.innerHTML = `<span class="status-badge status-success">Sucesso! ID: ${data.id_enviado}</span>\n` + data.retorno_site;
                } else {
                    resultBox.innerHTML = `<span class="status-badge status-error">Erro</span>\n` + (data.mensagem || data.detalhes || 'Erro desconhecido');
                }
            } catch (error) {
                loading.style.display = 'none';
                btn.disabled = false;
                resultBox.style.display = 'block';
                resultBox.innerHTML = `<span class="status-badge status-error">Erro de Conexão</span>\n` + error.message;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_VISUAL)

@app.route('/enviar', methods=['POST'])
def enviar_likes():
    dados = request.json or {}
    player_id = dados.get('id')

    if not player_id:
        return jsonify({'status': 'erro', 'mensagem': 'ID não fornecido'}), 400

    try:
        with sync_playwright() as p:
            # Inicia o navegador sem proxies travados para garantir velocidade e estabilidade
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )

            # Cria um contexto totalmente novo e limpo a cada requisição (Gera um convidado novo por request)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()

            # 1. Acessa o site
            page.goto("https://freefirelikes.com", timeout=45000, wait_until="networkidle")

            # 2. Clica em "Entrar como convidado"
            botoes_convidado = page.locator("text=Entrar como convidado")
            if botoes_convidado.count() > 0:
                botoes_convidado.first.click()
                page.wait_for_timeout(1500)

            # 3. Confirma o modal se aparecer
            botao_continuar = page.locator("button:has-text('Continuar como Convidado'), a:has-text('Continuar como Convidado')")
            if botao_continuar.count() > 0:
                botao_continuar.first.click()
                page.wait_for_timeout(2000)

            # 4. Preenche o ID exato enviado pelo usuário
            page.wait_for_selector("input[placeholder*='123456789']", timeout=15000)
            campo_id = page.locator("input[placeholder*='123456789']").first
            campo_id.fill("")
            campo_id.type(str(player_id), delay=50)

            # 5. Envia os likes
            page.click("text=Enviar likes")

            # 6. Aguarda o retorno
            page.wait_for_selector("text=Envio feito, text=Likes do perfil, text=Gastou 1 uso", timeout=20000)
            page.wait_for_timeout(1500)

            texto_retorno = page.locator("body").inner_text()
            browser.close()

            return jsonify({
                'status': 'sucesso',
                'id_enviado': str(player_id),
                'mensagem': 'Envio processado com sucesso!',
                'retorno_site': texto_retorno[:600]
            })

    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': 'Falha no processamento ou tempo limite atingido.',
            'detalhes': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
