from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import time

app = Flask(__name__)

@app.route('/enviar', methods=['POST'])
data = request.json
player_id = data.get('id')

if not player_id:
    return jsonify({'erro': 'ID não fornecido'}), 400

    try:
        with sync_playwright() as p:
            # Inicia o navegador em modo headless (invisível)
            browser = p.chromium.launch(headless=True)
            
            # Cria um contexto novo (simula um IP/sessão limpa a cada requisição)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # 1. Acessa o site
            page.goto("https://freefirelikes.com", timeout=60000)
            
            # 2. Clica no botão "Entrar como convidado"
            # Ajuste o seletor conforme o botão real da página
            page.click("text=Entrar como convidado")
            
            # Aguarda carregar o painel interno
            page.wait_for_load_state("networkidle")
            
            # 3. Preenche o ID do jogador no campo correspondente
            # Substitua '#input-id' pelo seletor CSS real do campo de ID do site
            page.fill("input[placeholder*='123456789']", str(player_id))
            
            # 4. Clica no botão de enviar likes
            page.click("text=Enviar likes")
            
            # 5. Aguarda o resultado aparecer na tela
            # Aguarda o elemento de resposta carregar
            page.wait_for_selector(".swal2-popup, .result-class, text=Envio feito", timeout=15000)
            
            # Captura o texto do resultado/mensagem gerada
            # Tente pegar o texto da caixa de aviso ou status
            resultado_texto = page.inner_text("body") # ou um seletor específico da mensagem

            browser.close()

            return jsonify({
                'status': 'sucesso',
                'mensagem': 'Likes enviados com sucesso!',
                'detalhes': resultado_texto[:500] # Retorna um resumo do resultado
            })

    except Exception as e:
        return jsonify({'status': 'erro', 'detalhes': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
