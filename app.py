from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import random

app = Flask(__name__)

# Lista de Proxies para alterar o IP a cada envio.
# Você pode adicionar mais proxies HTTP/HTTPS no formato "http://ip:porta"
PROXIES = [
    # Exemplo: "http://185.200.118.38:8080",
]

# Caso não queira fornecer proxies manuais, o script usará proxies públicos aleatórios da Web
PROXIES_PUBLICOS = [
    "http://185.200.118.38:8080",
    "http://51.159.65.65:80",
    "http://162.223.94.164:80",
    "http://198.23.239.134:6543",
    "http://207.244.217.165:6712"
]

def obter_proxy_aleatorio():
    lista = PROXIES if PROXIES else PROXIES_PUBLICOS
    return random.choice(lista)

@app.route('/enviar', methods=['POST'])
def enviar_likes():
    dados = request.json or {}
    player_id = dados.get('id')

    if not player_id:
        return jsonify({'status': 'erro', 'mensagem': 'ID não fornecido'}), 400

    proxy_ip = obter_proxy_aleatorio()

    try:
        with sync_playwright() as p:
            # Lança o navegador Chromium com proxy aleatório
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox'],
                proxy={'server': proxy_ip} if proxy_ip else None
            )

            # Cria um contexto do zero sem histórico/cookies acumulados
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()

            # 1. Acessa o site oficial de Free Fire Likes
            page.goto("https://freefirelikes.com", timeout=60000, wait_until="networkidle")

            # 2. Clica em "Entrar como convidado"
            botoes_convidado = page.locator("text=Entrar como convidado")
            if botoes_convidado.count() > 0:
                botoes_convidado.first.click()
                page.wait_for_timeout(2000)

            # 3. Confirma o modal "Continuar como Convidado..." se ele aparecer
            botao_continuar = page.locator("button:has-text('Continuar como Convidado'), a:has-text('Continuar como Convidado')")
            if botao_continuar.count() > 0:
                botao_continuar.first.click()
                page.wait_for_timeout(3000)

            # 4. Aguarda carregar o campo do ID do jogador e digita o ID recebido
            page.wait_for_selector("input[placeholder*='123456789']", timeout=15000)
            campo_id = page.locator("input[placeholder*='123456789']").first
            campo_id.fill("")
            campo_id.type(str(player_id), delay=100)

            # 5. Clica no botão "Enviar likes"
            page.click("text=Enviar likes")

            # 6. Aguarda o modal/caixa de resultado do envio aparecer
            page.wait_for_selector("text=Envio feito, text=Likes do perfil, text=Gastou 1 uso", timeout=20000)
            page.wait_for_timeout(2000)

            # Extrai os dados do painel de retorno para enviar ao usuário
            resultado_elemento = page.locator("body")
            texto_retorno = resultado_elemento.inner_text()

            # Fecha o navegador e descarta o contexto
            browser.close()

            return jsonify({
                'status': 'sucesso',
                'id_enviado': player_id,
                'mensagem': 'Envio processado com sucesso!',
                'retorno_site': texto_retorno[:600]
            })

    except Exception as e:
        return jsonify({
            'status': 'erro',
            'mensagem': 'Falha no envio ou tempo limite atingido.',
            'detalhes': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
