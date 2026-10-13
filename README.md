# Cria Studio — Personagem IA

Aplicação web em português para gerar **imagens por texto** e criar clipes curtos com personagem de referência e vídeo de movimento. As gerações usam a API externa deAPI e são acompanhadas até o resultado ficar pronto.

## Importante sobre o funcionamento e o plano gratuito

- A API deAPI oferece **US$ 5 em créditos iniciais** para novas contas, segundo o site oficial; são créditos limitados, não uma API gratuita ilimitada.
- O usuário que configurar a chave `DEAPI_API_KEY` no Render é quem paga o consumo de todas as pessoas que usarem a aplicação. A interface apresenta uma estimativa do custo antes de criar cada tarefa, mas o custo final pode variar se o provedor marcar o valor como estimado.
- A antiga rota dedicada de substituição integral de personagem não tem um modelo ativo no momento. Esta integração usa o MiniMax H3 de Video Animation com uma imagem e um vídeo de referência. Ela **gera um novo clipe guiado** pelo personagem e pelo movimento; não garante uma substituição perfeita pixel a pixel.
- A API aceita vídeos de referência de aproximadamente **2 a 5 segundos** neste fluxo. O resultado MiniMax H3 suporta **3 a 10 segundos** (72–240 quadros a 24 fps) conforme a opção escolhida. Não é um fluxo de 15–30 segundos.
- O modo de imagem gera artes a partir de texto com o modelo Flux.1 Schnell. A imagem pode ser baixada e enviada depois como referência para o modo de vídeo.
- A imagem de personagem recomendada mostra o corpo inteiro. O modelo de vídeo pode reinterpretar roupa, rosto, movimento, ambiente ou áudio; revise o resultado antes de publicar.
- O áudio original não é garantido na saída. A geração pode produzir outro áudio ou alterar a cena.

## Privacidade e uso responsável

Os arquivos são enviados ao deAPI para processamento. Consulte os [termos](https://deapi.ai/terms-of-service) e a [política de privacidade](https://deapi.ai/privacy-policy) do fornecedor antes de usar. O deAPI informa que, fora de infraestrutura dedicada, pode haver processamento em computadores de terceiros; declara também que os arquivos gerados são removidos no máximo 24 horas após a criação do trabalho. A interface exige confirmação de direito/autorização sobre a imagem e o vídeo. Use somente conteúdo próprio ou autorizado; não use para enganar, assediar ou criar conteúdo íntimo sem consentimento.

## Rodar localmente

Requisitos: Python 3.11+, FFmpeg/ffprobe e fontes do sistema.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DEAPI_API_KEY="sua-chave-deapi"
python app.py
```

Abra `http://localhost:10000`.

## Publicar no GitHub e Render

1. Crie uma conta no [deAPI](https://app.deapi.ai/register), resgate os créditos de teste se disponíveis e gere uma API key no painel. Não compartilhe essa chave no chat, no repositório ou no navegador.
2. Envie os arquivos deste projeto para seu repositório GitHub.
3. No Render, use **New + → Blueprint** e conecte o repositório, ou crie um Web Service com runtime Docker.
4. No painel do serviço Render, abra **Environment** e adicione `DEAPI_API_KEY` com a chave do deAPI. Salve para o Render fazer novo deploy.
5. Acesse a URL `.onrender.com` e confira `/health`. `provider_configured` deve aparecer como `true`.

O `render.yaml` inclui um blueprint com `plan: free`. O Render pode suspender serviços gratuitos inativos; arquivos locais são efêmeros. Não use o disco do servidor para guardar os vídeos como biblioteca.

## Limites da aplicação

- Foto: JPG, JPEG, PNG, WebP, GIF ou BMP; 1 KB a 10 MB.
- Vídeo: MP4, MOV, AVI, MPEG, MKV ou WebM; 1 KB a 80 MB e duração de 2 a 5 segundos.
- A duração do vídeo de referência é de 2 a 5 segundos. A duração de saída selecionável é 3, 4, 5, 6, 8 ou 10 segundos.
- Formatos de saída: vertical, horizontal ou quadrado.
- O orçamento consultado não inicia nem cobra uma geração. A tarefa só começa quando a pessoa confirma o botão de geração.
- Metadados de jobs ficam apenas na memória do processo; reinicializações do Render podem perder o acompanhamento das tarefas ativas. Configure o Render para um worker Gunicorn.
- Resultado temporário é baixado através do servidor, que mantém a chave deAPI fora do navegador.

## Rotas

- `GET /` — interface.
- `GET /health` — estado do servidor, configuração deAPI e ffprobe.
- `POST /api/quote` e `POST /api/image/quote` — estimam preço, sem iniciar tarefa.
- `POST /api/replace` — valida os arquivos e inicia a tarefa após a confirmação de autorização.
- `POST /api/image/generate` — cria imagem por texto após confirmação do orçamento.
- `GET /api/jobs/<id>` — consulta o andamento.
- `GET /api/jobs/<id>/download` — baixa o MP4 final.

## Referências técnicas

- [deAPI Image Generation](https://docs.deapi.ai/api/v2/images/generations)
- [deAPI Video Animation](https://docs.deapi.ai/api/v2/videos/animations)
- [deAPI Model Selection](https://docs.deapi.ai/api/v2/utilities/models)
- [deAPI Image Price Calculation](https://docs.deapi.ai/api/v2/images/generations-price)
- [deAPI Animation Price Calculation](https://docs.deapi.ai/api/v2/videos/animations-price)
- [deAPI Get Job Results](https://docs.deapi.ai/api/v2/utilities/jobs)
- [deAPI Pricing](https://deapi.ai/pricing)
