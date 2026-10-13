from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from threading import Lock

import requests
from flask import Flask, jsonify, render_template, request, send_file
from PIL import Image

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

DEAPI_BASE = "https://api.deapi.ai/api/v2"
MODEL = "MiniMaxH3_33B_Turbo_INT8"
IMAGE_MODEL = "Flux1schnell"
FPS = 24
MAX_VIDEO_BYTES = 80 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_VIDEO = {".mp4", ".mov", ".avi", ".mpeg", ".mpg", ".mkv", ".webm"}
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
JOBS: dict[str, dict] = {}
JOBS_LOCK = Lock()


def api_key() -> str:
    return (os.environ.get("DEAPI_API_KEY") or "").strip()


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key()}", "Accept": "application/json"}


def api_error_message(response: requests.Response) -> str:
    try:
        data = response.json()
        message = data.get("message") or data.get("error") or data.get("detail")
        if isinstance(message, dict):
            message = message.get("en") or next(iter(message.values()), None)
        if isinstance(message, str) and message.strip():
            return message[:500]
    except Exception:
        pass
    return f"O provedor respondeu com o código {response.status_code}."


def probe_video(path: str) -> tuple[float, int, int]:
    if not shutil.which("ffprobe"):
        raise RuntimeError("O ffprobe do FFmpeg não está disponível no servidor.")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json", path],
        capture_output=True, text=True, timeout=20, check=True,
    )
    import json
    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration", 0))
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if "width" in s and "height" in s), None)
    if not video_stream:
        raise ValueError("Não encontrei uma faixa de vídeo válida nesse arquivo.")
    return duration, int(video_stream["width"]), int(video_stream["height"])


def valid_output_seconds(value: int) -> bool:
    # MiniMax H3 accepts 56–243 frames at 24 fps (about 2.3–10.1 seconds).
    return value in (3, 4, 5, 6, 8, 10)


def clean_old_jobs() -> None:
    cutoff = time.time() - 60 * 60
    with JOBS_LOCK:
        expired = [key for key, value in JOBS.items() if value.get("created", 0) < cutoff]
        for key in expired:
            job = JOBS.pop(key, {})
            folder = job.get("folder")
            if folder:
                shutil.rmtree(folder, ignore_errors=True)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/health")
def health():
    configured = bool(api_key())
    return jsonify({"ok": True, "provider_configured": configured, "ffprobe": bool(shutil.which("ffprobe"))}), 200


@app.post("/api/quote")
def quote():
    if not api_key():
        return jsonify(error="O servidor ainda não foi configurado. Adicione DEAPI_API_KEY nas variáveis do Render."), 503
    body = request.get_json(silent=True) or {}
    try:
        seconds = int(body.get("seconds", 5))
    except (ValueError, TypeError):
        return jsonify(error="Duração inválida."), 400
    if not valid_output_seconds(seconds):
        return jsonify(error="Escolha uma duração de saída entre 3 e 10 segundos."), 400
    ratio = body.get("ratio", "portrait")
    sizes = {"portrait": (512, 768), "landscape": (768, 512), "square": (640, 640)}
    width, height = sizes.get(ratio, sizes["portrait"])
    payload = {
        "model": MODEL,
        "width": width,
        "height": height,
        "frames": seconds * FPS,
        "fps": FPS,
        "ref_images_count": 1,
        "ref_videos_count": 1,
    }
    try:
        response = requests.post(f"{DEAPI_BASE}/videos/animations/price", headers={**auth_headers(), "Content-Type": "application/json"}, json=payload, timeout=30)
        if not response.ok:
            return jsonify(error=api_error_message(response)), response.status_code if response.status_code < 500 else 502
        data = response.json().get("data", {})
        price = data.get("price")
        if price is None:
            return jsonify(error="Não foi possível obter um orçamento válido. Nenhum clipe foi enviado."), 502
        return jsonify({
            "price": price,
            "currency": "créditos da deAPI",
            "estimated": bool(data.get("is_estimated", True)),
            "basis": data.get("estimate_basis"),
            "seconds": seconds,
            "width": width,
            "height": height,
            "model": MODEL,
        })
    except requests.RequestException:
        app.logger.exception("Falha ao consultar orçamento deAPI")
        return jsonify(error="Não consegui consultar o orçamento agora. Tente novamente."), 502


@app.post("/api/image/quote")
def image_quote():
    if not api_key():
        return jsonify(error="O servidor ainda não foi configurado. Adicione DEAPI_API_KEY nas variáveis do Render."), 503
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    if len(prompt) < 4 or len(prompt) > 700:
        return jsonify(error="Escreva uma descrição entre 4 e 700 caracteres."), 400
    sizes = {"square": (768, 768), "portrait": (512, 768), "landscape": (768, 512)}
    width, height = sizes.get(body.get("ratio", "square"), sizes["square"])
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "width": width, "height": height, "steps": 4, "seed": -1}
    try:
        response = requests.post(f"{DEAPI_BASE}/images/generations/price", headers={**auth_headers(), "Content-Type": "application/json"}, json=payload, timeout=30)
        if not response.ok:
            return jsonify(error=api_error_message(response)), response.status_code if response.status_code < 500 else 502
        data = response.json().get("data", {})
        if data.get("price") is None:
            return jsonify(error="Não foi possível obter o orçamento da imagem."), 502
        return jsonify({"price": data["price"], "currency": "créditos da deAPI", "estimated": bool(data.get("is_estimated", True)), "width": width, "height": height, "model": IMAGE_MODEL})
    except requests.RequestException:
        app.logger.exception("Falha ao consultar orçamento de imagem")
        return jsonify(error="Não consegui consultar o orçamento agora."), 502


@app.post("/api/image/generate")
def generate_image():
    if not api_key():
        return jsonify(error="O servidor ainda não foi configurado. Adicione DEAPI_API_KEY nas variáveis do Render."), 503
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    if len(prompt) < 4 or len(prompt) > 700:
        return jsonify(error="Escreva uma descrição entre 4 e 700 caracteres."), 400
    sizes = {"square": (768, 768), "portrait": (512, 768), "landscape": (768, 512)}
    width, height = sizes.get(body.get("ratio", "square"), sizes["square"])
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "width": width, "height": height, "steps": 4, "seed": -1}
    try:
        response = requests.post(f"{DEAPI_BASE}/images/generations", headers={**auth_headers(), "Content-Type": "application/json"}, json=payload, timeout=90)
        if not response.ok:
            return jsonify(error=api_error_message(response)), response.status_code if response.status_code < 500 else 502
        request_id = (response.json().get("data") or {}).get("request_id")
        if not request_id:
            return jsonify(error="O serviço não retornou um identificador de tarefa válido."), 502
        public_id = uuid.uuid4().hex
        folder = tempfile.mkdtemp(prefix="cria-imagem-")
        with JOBS_LOCK:
            JOBS[public_id] = {"provider_id": str(request_id), "folder": folder, "created": time.time(), "kind": "image", "original_name": "imagem-gerada.png"}
        return jsonify({"job_id": public_id, "status": "pending", "message": "Geração iniciada."}), 202
    except requests.RequestException:
        app.logger.exception("Falha ao enviar geração de imagem")
        return jsonify(error="Não consegui iniciar a geração de imagem."), 502


@app.post("/api/replace")
def replace_character():
    if not api_key():
        return jsonify(error="O servidor ainda não foi configurado. Adicione DEAPI_API_KEY nas variáveis do Render."), 503
    clean_old_jobs()
    if request.form.get("consent") != "yes":
        return jsonify(error="Confirme que tem autorização para usar os arquivos enviados."), 400

    character = request.files.get("character")
    source_video = request.files.get("video")
    if not character or not character.filename or not source_video or not source_video.filename:
        return jsonify(error="Envie uma imagem do personagem e um vídeo curto de referência."), 400

    image_ext = Path(character.filename).suffix.lower()
    video_ext = Path(source_video.filename).suffix.lower()
    if image_ext not in ALLOWED_IMAGE:
        return jsonify(error="A foto do personagem deve ser JPG, PNG, WebP, GIF ou BMP."), 400
    if video_ext not in ALLOWED_VIDEO:
        return jsonify(error="O vídeo deve ser MP4, MOV, AVI, MPEG, MKV ou WebM."), 400

    ratio = request.form.get("ratio", "portrait")
    sizes = {"portrait": (512, 768), "landscape": (768, 512), "square": (640, 640)}
    width, height = sizes.get(ratio, sizes["portrait"])
    try:
        seconds = int(request.form.get("seconds", "5"))
    except (ValueError, TypeError):
        return jsonify(error="Duração inválida."), 400
    if not valid_output_seconds(seconds):
        return jsonify(error="Escolha uma duração de saída entre 3 e 10 segundos."), 400

    prompt = (request.form.get("prompt") or "").strip()[:700]
    if not prompt:
        prompt = "Use the full-body character appearance from <Picture 1> as the main subject and transfer the movement, gestures, timing, and camera motion from <Video 1>. Preserve the scene composition and background as much as possible. Keep the same character design, clothing, colors, and proportions throughout. This is a creative AI-generated transformation."

    folder = tempfile.mkdtemp(prefix="cria-personagem-")
    image_path = os.path.join(folder, "character" + image_ext)
    video_path = os.path.join(folder, "motion" + video_ext)
    try:
        character.save(image_path)
        source_video.save(video_path)
        image_size = os.path.getsize(image_path)
        video_size = os.path.getsize(video_path)
        if image_size < 1024 or image_size > MAX_IMAGE_BYTES:
            raise ValueError("A imagem deve ter entre 1 KB e 10 MB.")
        if video_size < 1024 or video_size > MAX_VIDEO_BYTES:
            raise ValueError("O vídeo deve ter entre 1 KB e 80 MB.")
        with Image.open(image_path) as img:
            img.verify()
        with Image.open(image_path) as img:
            img_width, img_height = img.size
        if min(img_width, img_height) < 64 or max(img_width, img_height) > 5000:
            raise ValueError("A imagem deve ter entre 64 e 5000 pixels em cada lado.")
        image_ratio = img_width / img_height
        if image_ratio < 0.25 or image_ratio > 4:
            raise ValueError("A imagem de referência deve ter proporção entre 1:4 e 4:1.")
        duration, original_width, original_height = probe_video(video_path)
        if duration < 2 or duration > 5.05:
            raise ValueError(f"O vídeo de referência precisa ter entre 2 e 5 segundos; o arquivo tem {duration:.1f}s.")
    except ValueError as exc:
        shutil.rmtree(folder, ignore_errors=True)
        return jsonify(error=str(exc)), 400
    except subprocess.CalledProcessError:
        shutil.rmtree(folder, ignore_errors=True)
        return jsonify(error="Não consegui ler esse vídeo. Converta-o para MP4 H.264 e tente novamente."), 400
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        app.logger.exception("Falha ao validar os arquivos enviados")
        return jsonify(error="Não foi possível validar os arquivos. Confira os formatos e tente novamente."), 400

    files = {
        "ref_images[0]": (Path(character.filename).name, open(image_path, "rb"), character.mimetype or "application/octet-stream"),
        "ref_videos[0]": (Path(source_video.filename).name, open(video_path, "rb"), source_video.mimetype or "application/octet-stream"),
    }
    data = {
        "model": MODEL,
        "width": width,
        "height": height,
        "frames": seconds * FPS,
        "fps": FPS,
        "seed": -1,
        "prompt": prompt,
    }
    try:
        response = requests.post(f"{DEAPI_BASE}/videos/animations", headers=auth_headers(), files=files, data=data, timeout=(20, 180))
        for _field, file_tuple in files.items():
            file_tuple[1].close()
        if not response.ok:
            detail = api_error_message(response)
            shutil.rmtree(folder, ignore_errors=True)
            return jsonify(error=detail), response.status_code if response.status_code < 500 else 502
        payload = response.json()
        request_id = (payload.get("data") or {}).get("request_id") or payload.get("request_id")
        if not request_id:
            shutil.rmtree(folder, ignore_errors=True)
            return jsonify(error="O serviço não retornou um identificador de tarefa válido."), 502
        public_id = uuid.uuid4().hex
        with JOBS_LOCK:
            JOBS[public_id] = {
                "provider_id": str(request_id),
                "folder": folder,
                "created": time.time(),
                "original_name": "personagem-animado.mp4",
            }
        return jsonify({"job_id": public_id, "status": "pending", "message": "Geração iniciada."}), 202
    except requests.RequestException:
        for _field, file_tuple in files.items():
            try:
                file_tuple[1].close()
            except Exception:
                pass
        shutil.rmtree(folder, ignore_errors=True)
        app.logger.exception("Falha ao enviar tarefa para deAPI")
        return jsonify(error="Não consegui iniciar a tarefa. Confira a conexão e tente novamente."), 502
    except Exception:
        for _field, file_tuple in files.items():
            try:
                file_tuple[1].close()
            except Exception:
                pass
        shutil.rmtree(folder, ignore_errors=True)
        app.logger.exception("Erro inesperado ao iniciar tarefa")
        return jsonify(error="Não foi possível iniciar a tarefa."), 502


@app.get("/api/jobs/<job_id>")
def job_status(job_id: str):
    clean_old_jobs()
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        return jsonify(error="Tarefa não encontrada ou expirada. Envie novamente."), 404
    try:
        response = requests.get(f"{DEAPI_BASE}/jobs/{job['provider_id']}", headers=auth_headers(), timeout=30)
        if not response.ok:
            return jsonify(error=api_error_message(response)), response.status_code if response.status_code < 500 else 502
        payload = response.json()
        result = payload.get("data") or {}
        status = result.get("status", "processing")
        out = {"status": status, "progress": result.get("progress")}
        if status == "done":
            result_url = result.get("result_url")
            if not result_url:
                return jsonify(error="A tarefa concluiu, mas não retornou o arquivo final."), 502
            with JOBS_LOCK:
                if job_id in JOBS:
                    JOBS[job_id]["result_url"] = result_url
                    JOBS[job_id]["price"] = result.get("price")
            out["download_url"] = f"/api/jobs/{job_id}/download"
            out["output_type"] = job.get("kind", "video")
            out["price"] = result.get("price")
        elif status == "error":
            out["error"] = result.get("error") or "A geração falhou no provedor."
        return jsonify(out)
    except requests.RequestException:
        app.logger.exception("Falha ao consultar status da tarefa")
        return jsonify(error="Não consegui consultar o andamento agora."), 502


@app.get("/api/jobs/<job_id>/download")
def download_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or not job.get("result_url"):
        return jsonify(error="O vídeo ainda não está pronto ou a tarefa expirou."), 404
    try:
        response = requests.get(job["result_url"], headers=auth_headers(), stream=True, timeout=(20, 120))
        if not response.ok:
            return jsonify(error="Não consegui baixar o resultado do provedor."), 502
        if job.get("kind") == "image":
            mime = response.headers.get("Content-Type", "image/png").split(";")[0]
            ext = {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
            filename = "imagem-gerada" + ext
        else:
            mime, filename, ext = "video/mp4", "personagem-animado.mp4", ".mp4"
        path = os.path.join(job["folder"], "final" + ext)
        with open(path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
        return send_file(path, mimetype=mime, as_attachment=False, download_name=filename)
    except requests.RequestException:
        app.logger.exception("Falha ao baixar o resultado")
        return jsonify(error="Falha temporária ao baixar o arquivo final."), 502


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Os arquivos excedem o limite total de 100 MB."), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
