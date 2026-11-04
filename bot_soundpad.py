import asyncio
import json
import math
import os
import random
import re
import subprocess
import time
import urllib.parse
import requests
import websockets

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

# ================= CONFIGURAÇÃO =================
CLIENT_ID = "SEU_CLIENT_ID_AQUI"
ACCESS_TOKEN = "SEU_ACCESS_TOKEN_AQUI"
REFRESH_TOKEN = "SEU_REFRESH_TOKEN_AQUI"         # Cole o Refresh Token do TwitchTokenGenerator para renovar sozinho e nunca expirar
CLIENT_SECRET = ""                              # Opcional (deixe vazio se gerou o token pelo TwitchTokenGenerator)

# Nomes, custos e descrições dos Resgates de Pontos do Canal na Twitch (gerenciados pelo bot)
RANDOM_REWARD_NAME = "Som Aleatório"
RANDOM_REWARD_COST = 100                        # Custo em pontos do som aleatório
RANDOM_REWARD_PROMPT = "Toca um som totalmente aleatório da lista de memes no Soundpad."

SEARCH_REWARD_NAME = "Buscar Meme"
SEARCH_REWARD_COST = 150                        # Custo em pontos da busca
SEARCH_REWARD_PROMPT = "Digite o nome ou ID (#125) do áudio que deseja buscar."

STOP_REWARD_NAME = "Parar Som"                  # Interrompe o áudio atual (sem apagar a fila restante)
STOP_REWARD_COST = 500                         # Custo em pontos para parar o áudio atual
STOP_REWARD_PROMPT = "Interrompe a reprodução do áudio atual no Soundpad imediatamente."

# Configurações da Roleta Russa
ROULETTE_REWARD_NAME = "Roleta Russa"
ROULETTE_REWARD_COST = 50                       # Custo em pontos da roleta
ROULETTE_REWARD_PROMPT = "Gire a roleta! 70% de chance de tocar um meme aleatório, mas 30% de chance de cair na TRAP!"
ROULETTE_TRAP_CHANCE = 30                       # Chance em % de cair na Trap (30 = 30%)
ROULETTE_TRAP_SOUND_IDS = [1, 2, 3]             # IDs dos sons tocados quando cai na Trap (sorteia um aleatório entre eles)
ROULETTE_TIMEOUT_SECONDS = 60                   # Duração do timeout em segundos para quem cair na trap (0 = desativado)

# Categorias de memes para os comandos !categoria / !category
SOUND_CATEGORIES = {
    "anime": "anime",
    "scream": "scream",
    "meme": "meme",
    "musica": "musica",
}

# Caminho manual para a sua lista de sons (deixe "" para auto-detectar pelo AppData do Windows)
CUSTOM_SPL_PATH = ""

# Sons específicos (tocam direto sem poluir o chat/OBS)
REWARDS_MAP = {
    "Exemplo Som 1": 1,
    "Exemplo Som 2": 2,
    "Exemplo Som 3": 3,
}

# Configurações de Fila e Cooldown
USER_COOLDOWN_SECONDS = 0                       # Tempo em segundos de cooldown por viewer (0 = desativado)
QUEUE_DELAY_SECONDS = 1                         # Intervalo em segundos entre um som e outro na fila
ENABLE_CHAT_ANNOUNCEMENTS = True                # True = avisa no chat / False = apenas pop-up no OBS

# Configuração da Imagem de Memes
GENERATE_IMAGE_ON_STARTUP = True                # True = ativa a geração automática ao iniciar / False = só gera via comando no chat (!gerarimagem)
FORCE_REGENERATE_IMAGE = False                  # True = força nova imagem toda vez que ligar / False = reaproveita a que já estiver pronta
IMAGE_HOST_SERVICE = "imgur"                   # Provedor web: "imgur" (estável e sem conta), "tmpfiles" (sem conta, dura 1h) ou "puush" (requer conta)
PUUSH_API_KEY = ""                             # Obrigatório apenas se IMAGE_HOST_SERVICE for "puush"

# Caminhos
PIPE_PATH = r"\\.\pipe\sp_remote_control"
OBS_TEXT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "obs_tocando_agora.txt")
SOUNDS_IMAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lista_de_sons.png")
SOUNDS_URL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "link_memes.txt")
VIP_THEMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_themes.json")
TOKEN_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twitch_tokens.json")
# ===============================================

BROADCASTER_ID = None
BROADCASTER_NAME = ""
SOUND_LIST = []
SOUND_QUEUE = asyncio.Queue()
USER_COOLDOWNS = {}
PLAYED_ENTRANCE_USERS = set()
USER_THEMES = {}

CURRENT_PLAY_TASK = None
PENDING_SEARCH_CHOICES = {}
MEMES_IMAGE_URL = ""
LAST_PLAYED_SOUND = None

def load_user_themes() -> dict:
    """Carrega os temas de entrada salvos dos viewers."""
    if os.path.exists(VIP_THEMES_FILE):
        try:
            with open(VIP_THEMES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Erro ao carregar temas VIP: {e}")
    return {}

def save_user_themes():
    """Salva os temas de entrada dos viewers no arquivo JSON."""
    try:
        with open(VIP_THEMES_FILE, "w", encoding="utf-8") as f:
            json.dump(USER_THEMES, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] Erro ao salvar temas VIP: {e}")

def normalize_text(text: str) -> str:
    return text.replace("–", "-").replace("—", "-").strip().lower()

def send_soundpad(command: str):
    """Envia o comando direto pela memória do Soundpad."""
    try:
        with open(PIPE_PATH, "r+b", buffering=0) as pipe:
            pipe.write(command.encode("utf-8"))
            return True
    except Exception as e:
        print(f"[!] Erro no Soundpad: {e}")
        return False

def play_sound(sound_id: int):
    print(f" -> 🔊 Tocando som #{sound_id} no Soundpad...")
    send_soundpad(f"DoPlaySoundFromCategory(-1,{sound_id})")

def stop_sound():
    print(" -> ⏹️ Parando reprodução...")
    send_soundpad("DoStopSound()")

def is_soundpad_playing() -> bool:
    """Verifica diretamente no Soundpad se ainda há áudio tocando."""
    try:
        with open(PIPE_PATH, "r+b", buffering=0) as pipe:
            pipe.write(b"GetPlayStatus()")
            res = pipe.read(64).decode("utf-8", errors="replace")
            return "PLAYING" in res
    except Exception:
        return False

def update_obs_text(text: str):
    """Escreve no arquivo lido pelo OBS."""
    try:
        with open(OBS_TEXT_FILE, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"[OBS] Erro ao gravar arquivo: {e}")

def skip_current_sound():
    """Pula apenas o áudio atual e força a fila a avançar para o próximo som."""
    global CURRENT_PLAY_TASK
    if CURRENT_PLAY_TASK and not CURRENT_PLAY_TASK.done():
        CURRENT_PLAY_TASK.cancel()
    stop_sound()
    update_obs_text("")

def clear_queue_and_stop():
    """Cancela toda a fila e cala o áudio imediatamente."""
    global CURRENT_PLAY_TASK
    while not SOUND_QUEUE.empty():
        try:
            SOUND_QUEUE.get_nowait()
            SOUND_QUEUE.task_done()
        except Exception:
            break
    if CURRENT_PLAY_TASK and not CURRENT_PLAY_TASK.done():
        CURRENT_PLAY_TASK.cancel()
    stop_sound()
    update_obs_text("")

def check_user_cooldown(user: str):
    """Retorna (True, 0) se puder resgatar, ou (False, remaining) se estiver em cooldown."""
    if USER_COOLDOWN_SECONDS <= 0 or user.lower() == BROADCASTER_NAME.lower():
        return True, 0

    now = time.time()
    last_time = USER_COOLDOWNS.get(user.lower(), 0)
    remaining = int(USER_COOLDOWN_SECONDS - (now - last_time))

    if remaining > 0:
        return False, remaining

    USER_COOLDOWNS[user.lower()] = now
    return True, 0

def _sync_refund_redemption(broadcaster_id: str, reward_id: str, redemption_id: str):
    """Cancela o resgate via API da Twitch para devolver os pontos ao viewer."""
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()
    url = f"https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions?broadcaster_id={broadcaster_id}&reward_id={reward_id}&id={redemption_id}"
    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json"
    }
    body = {"status": "CANCELED"}
    try:
        r = requests.patch(url, headers=headers, json=body, timeout=5)
        if r.status_code == 200:
            print("[Twitch] Pontos estornados com sucesso ao viewer!")
        else:
            print(f"[!] Falha ao estornar pontos ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[!] Erro de conexão no estorno: {e}")

async def refund_redemption(broadcaster_id: str, reward_id: str, redemption_id: str):
    await asyncio.to_thread(_sync_refund_redemption, broadcaster_id, reward_id, redemption_id)

def _sync_timeout_user(broadcaster_id: str, target_user_id: str, duration: int, reason: str):
    """Aplica timeout em um usuário via API da Twitch (requer escopo moderator:manage:banned_users)."""
    if not target_user_id or target_user_id == broadcaster_id or duration <= 0:
        return
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()
    url = f"https://api.twitch.tv/helix/moderator/bans?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}"
    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json"
    }
    body = {
        "data": {
            "user_id": target_user_id,
            "duration": duration,
            "reason": reason
        }
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=5)
        if r.status_code in (200, 204):
            print(f"[Twitch] Timeout de {duration}s aplicado com sucesso no viewer ID {target_user_id}!")
        elif r.status_code == 403:
            print(f"[!] Falha no timeout (403): O token precisa do escopo 'moderator:manage:banned_users'!")
        else:
            print(f"[!] Falha ao aplicar timeout ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[!] Erro de conexão no timeout: {e}")

async def timeout_user(broadcaster_id: str, target_user_id: str, duration: int, reason: str):
    await asyncio.to_thread(_sync_timeout_user, broadcaster_id, target_user_id, duration, reason)

def ensure_managed_rewards(broadcaster_id: str):
    """Cria e atualiza automaticamente as recompensas gerenciáveis via API com base nas configurações."""
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()
    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json"
    }

    url_rewards = f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={broadcaster_id}"
    url_get = f"{url_rewards}&only_manageable_rewards=true"
    try:
        r = requests.get(url_get, headers=headers, timeout=5)
        manageable_map = {}
        if r.status_code == 200:
            rewards = r.json().get("data", [])
            for rw in rewards:
                manageable_map[normalize_text(rw.get("title", ""))] = rw

        rewards_to_ensure = [
            {
                "title": RANDOM_REWARD_NAME,
                "cost": RANDOM_REWARD_COST,
                "is_user_input_required": False,
                "prompt": RANDOM_REWARD_PROMPT
            },
            {
                "title": SEARCH_REWARD_NAME,
                "cost": SEARCH_REWARD_COST,
                "is_user_input_required": True,
                "prompt": SEARCH_REWARD_PROMPT
            },
            {
                "title": STOP_REWARD_NAME,
                "cost": STOP_REWARD_COST,
                "is_user_input_required": False,
                "prompt": STOP_REWARD_PROMPT
            },
            {
                "title": ROULETTE_REWARD_NAME,
                "cost": ROULETTE_REWARD_COST,
                "is_user_input_required": False,
                "prompt": ROULETTE_REWARD_PROMPT
            }
        ]

        for rw in rewards_to_ensure:
            norm_title = normalize_text(rw["title"])
            if norm_title in manageable_map:
                existing = manageable_map[norm_title]
                reward_id = existing["id"]

                needs_update = (
                    existing.get("prompt", "") != rw["prompt"]
                    or existing.get("cost", 0) != rw["cost"]
                    or existing.get("is_user_input_required", False) != rw["is_user_input_required"]
                )

                if needs_update:
                    patch_url = f"{url_rewards}&id={reward_id}"
                    r_patch = requests.patch(patch_url, headers=headers, json=rw, timeout=5)
                    if r_patch.status_code == 200:
                        print(f"[✓] Recompensa '{rw['title']}' atualizada na Twitch com a nova descrição/custo!")
                    else:
                        print(f"[!] Falha ao atualizar recompensa '{rw['title']}' ({r_patch.status_code}): {r_patch.text}")
                else:
                    print(f"[✓] Recompensa gerenciável '{rw['title']}' verificada (estorno e descrição ativos)!")
                continue

            r_post = requests.post(url_rewards, headers=headers, json=rw, timeout=5)
            if r_post.status_code in (200, 201):
                print(f"[✓] Recompensa '{rw['title']}' criada via API (estorno ativo)!")
            elif r_post.status_code == 400 and "already exists" in r_post.text.lower():
                print(f"[!] AVISO: Apague a recompensa '{rw['title']}' antiga do site da Twitch para o bot poder recriá-la com direito a estorno.")
            else:
                print(f"[!] Erro ao registrar recompensa '{rw['title']}' ({r_post.status_code}): {r_post.text}")
    except Exception as e:
        print(f"[!] Erro ao checar recompensas gerenciadas: {e}")

async def sound_queue_worker():
    """Worker que monitora o áudio e sincroniza o pop-up com a duração real."""
    global CURRENT_PLAY_TASK, LAST_PLAYED_SOUND
    while True:
        item = await SOUND_QUEUE.get()
        try:
            LAST_PLAYED_SOUND = item
            play_sound(item["id"])
            duration = item.get("duration", 3.0)

            if item.get("show_popup"):
                sound_name = item["name"]
                user = item["user"]
                update_obs_text(f"🎵 {sound_name} (por @{user})")

                chat_msg = item.get("chat_message")
                if chat_msg:
                    await send_twitch_chat(chat_msg)
                elif not item.get("suppress_chat"):
                    if item.get("is_search"):
                        query = item.get("query", "")
                        await send_twitch_chat(f"🔎 @{user} buscou \"{query}\" e tocou: \"{sound_name}\" (ID #{item['id']})")
                    else:
                        await send_twitch_chat(f"🎲 @{user} tirou um som aleatório: \"{sound_name}\" (ID #{item['id']})")

                timeout_uid = item.get("timeout_user_id")
                timeout_dur = item.get("timeout_duration", 0)
                if timeout_uid and timeout_dur > 0 and BROADCASTER_ID:
                    asyncio.create_task(timeout_user(BROADCASTER_ID, timeout_uid, timeout_dur, "Caiu na Trap da Roleta Russa!"))

            async def _wait_playback():
                await asyncio.sleep(0.4)
                start_time = time.time()
                while time.time() - start_time < duration:
                    await asyncio.sleep(0.3)
                    if not is_soundpad_playing():
                        break

            CURRENT_PLAY_TASK = asyncio.create_task(_wait_playback())
            try:
                await CURRENT_PLAY_TASK
            except asyncio.CancelledError:
                pass

        except Exception as e:
            print(f"[!] Erro na fila: {e}")
        finally:
            update_obs_text("")
            SOUND_QUEUE.task_done()
            if QUEUE_DELAY_SECONDS > 0:
                await asyncio.sleep(QUEUE_DELAY_SECONDS)

def find_spl_path() -> str:
    if CUSTOM_SPL_PATH and os.path.exists(CUSTOM_SPL_PATH):
        return CUSTOM_SPL_PATH

    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")

    candidates = [
        os.path.join(appdata, "Leppsoft", "soundlist.spl"),
        os.path.join(localappdata, "Leppsoft", "soundlist.spl"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    lepp_dir = os.path.join(appdata, "Leppsoft")
    if os.path.exists(lepp_dir):
        for root, _, files in os.walk(lepp_dir):
            for f in files:
                if f.endswith(".spl") and "stats" not in f.lower():
                    return os.path.join(root, f)
    return None

def load_soundpad_library():
    spl_path = find_spl_path()
    if not spl_path:
        return []

    print(f"[✓] Arquivo de lista encontrado: {spl_path}")

    try:
        with open(spl_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        matches = re.findall(r'<Sound\b([^>]+)/?>', content, re.IGNORECASE)
        raw_sounds = []
        seen_urls = set()

        for m in matches:
            attrs = dict(re.findall(r'(\w+)=["\']([^"\']*)["\']', m))
            url = attrs.get("url") or attrs.get("URL") or attrs.get("path") or ""
            if url and url not in seen_urls:
                seen_urls.add(url)
                raw_sounds.append(attrs)

        raw_sounds.sort(key=lambda s: s.get("addedOn") or s.get("addedon") or "")

        library = []
        for i, s in enumerate(raw_sounds):
            url = s.get("url") or s.get("URL") or s.get("path") or ""
            clean_url = urllib.parse.unquote(url)
            filename = clean_url.replace("\\", "/").split("/")[-1]
            name = filename.rsplit(".", 1)[0]

            dur_str = s.get("duration") or s.get("Duration") or ""
            dur_seconds = 3.0
            if dur_str:
                parts = dur_str.strip().split(":")
                try:
                    if len(parts) == 2:
                        dur_seconds = int(parts[0]) * 60 + float(parts[1])
                    elif len(parts) == 3:
                        dur_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
                    else:
                        dur_seconds = float(dur_str)
                except Exception:
                    dur_seconds = 3.0

            library.append({
                "id": i + 1,
                "name": name,
                "duration": dur_seconds
            })

        if GENERATE_IMAGE_ON_STARTUP:
            generate_sounds_image(library, force=FORCE_REGENERATE_IMAGE)
        return library
    except Exception as e:
        print(f"[!] Erro ao carregar biblioteca: {e}")
        return []

def generate_sounds_image(library=None, force: bool = False) -> str:
    """Gera imagem ampla (até 5000x5000) com colunas largas de 480px para nomes longos não cortarem."""
    global MEMES_IMAGE_URL
    if Image is None:
        print("[!] Pillow não instalado. Execute 'pip install pillow' para gerar a imagem.")
        return None

    if not force and os.path.exists(SOUNDS_IMAGE_FILE):
        print(f"[✓] Imagem já existente em disco: {SOUNDS_IMAGE_FILE} (pulando geração).")

        if not MEMES_IMAGE_URL and os.path.exists(SOUNDS_URL_FILE):
            try:
                with open(SOUNDS_URL_FILE, "r", encoding="utf-8") as f:
                    MEMES_IMAGE_URL = f.read().strip()
            except Exception:
                MEMES_IMAGE_URL = ""

        if MEMES_IMAGE_URL and check_image_url_alive(MEMES_IMAGE_URL):
            print(f"[✓] Link web verificado no servidor e ainda ativo: {MEMES_IMAGE_URL}")
            return SOUNDS_IMAGE_FILE

        print("[*] Link web expirou ou não encontrado. Enviando imagem existente para a web...")
        uploaded_url = upload_temporary_image(SOUNDS_IMAGE_FILE)
        if uploaded_url:
            MEMES_IMAGE_URL = uploaded_url
            save_image_url(uploaded_url)
            print(f"[✓] Novo link web gerado: {MEMES_IMAGE_URL}")
        return SOUNDS_IMAGE_FILE

    sounds = library if library is not None else SOUND_LIST
    if not sounds:
        return None

    total = len(sounds)
    cols = 10 if total > 500 else (math.ceil(total / 50) if total > 100 else 4)
    rows = math.ceil(total / cols)

    padding = 35
    header_height = 95
    row_height = 40
    col_width = min(480, (5000 - padding * 2) // cols)

    img_w = padding * 2 + cols * col_width
    img_h = header_height + rows * row_height + padding

    img = Image.new("RGB", (img_w, img_h), (18, 18, 22))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 32)
        font_body = ImageFont.truetype("arial.ttf", 17)
        font_id = ImageFont.truetype("arialbd.ttf", 18)
    except Exception:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_id = ImageFont.load_default()

    draw.text((padding, 26), f"SOUNDPAD - LISTA DE MEMES ({total} áudios)", fill=(169, 112, 255), font=font_title)
    draw.line([(padding, 76), (img_w - padding, 76)], fill=(45, 45, 55), width=2)

    for c_idx in range(1, cols):
        sep_x = padding + c_idx * col_width - 12
        draw.line([(sep_x, header_height - 12), (sep_x, img_h - padding)], fill=(32, 32, 40), width=1)

    max_text_w = col_width - 64

    for i, s in enumerate(sounds):
        c = i // rows
        r = i % rows
        x = padding + c * col_width
        y = header_height + r * row_height

        draw.text((x, y), f"#{s['id']:03d}", fill=(145, 71, 255), font=font_id)

        name_x = x + 56
        name_text = s["name"]

        if draw.textlength(name_text, font=font_body) > max_text_w:
            while name_text and draw.textlength(name_text + "...", font=font_body) > max_text_w:
                name_text = name_text[:-1]
            name_text += "..."

        draw.text((name_x, y), name_text, fill=(235, 235, 238), font=font_body)

    try:
        img.save(SOUNDS_IMAGE_FILE, "PNG")
        print(f"[✓] Imagem gerada com colunas largas ({img_w}x{img_h}px): {SOUNDS_IMAGE_FILE}")

        uploaded_url = upload_temporary_image(SOUNDS_IMAGE_FILE)
        if uploaded_url:
            MEMES_IMAGE_URL = uploaded_url
            save_image_url(uploaded_url)
            print(f"[✓] Link web ativo gerado: {MEMES_IMAGE_URL}")

        return SOUNDS_IMAGE_FILE
    except OSError:
        print(f"[!] AVISO: Não foi possível sobrescrever '{SOUNDS_IMAGE_FILE}'. O arquivo está aberto no visualizador do Windows ou no OBS! Feche o visualizador e use !gerarimagem.")
        return None

def save_image_url(url: str):
    """Salva a última URL válida em arquivo de texto para persistir entre reinicializações."""
    try:
        with open(SOUNDS_URL_FILE, "w", encoding="utf-8") as f:
            f.write(url)
    except Exception:
        pass

def check_image_url_alive(url: str) -> bool:
    """Verifica se a imagem ainda existe e está acessível no servidor de upload."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.head(url, headers=headers, timeout=6, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False

def upload_temporary_image(filepath: str) -> str:
    """Faz upload no serviço selecionado em IMAGE_HOST_SERVICE ('imgur', 'tmpfiles' ou 'puush')."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    service = IMAGE_HOST_SERVICE.lower().strip()

    if service == "imgur":
        try:
            url_imgur = "https://api.imgur.com/3/image"
            img_headers = {
                "Authorization": "Client-ID 1ceddedc03a5d71",
                "User-Agent": headers["User-Agent"]
            }
            with open(filepath, "rb") as f:
                files = {"image": f}
                r = requests.post(url_imgur, headers=img_headers, files=files, timeout=30)
            if r.status_code == 200:
                link = r.json().get("data", {}).get("link", "")
                if link:
                    return link
            print(f"[!] Imgur retornou status {r.status_code}.")
        except Exception as e:
            print(f"[!] Erro no upload Imgur: {e}")

    elif service == "tmpfiles":
        try:
            url_tmp = "https://tmpfiles.org/api/v1/upload"
            with open(filepath, "rb") as f:
                files = {"file": (os.path.basename(filepath), f, "image/png")}
                r = requests.post(url_tmp, files=files, headers=headers, timeout=30)
            if r.status_code == 200:
                res = r.json()
                raw_url = res.get("data", {}).get("url", "")
                if raw_url:
                    return raw_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            print(f"[!] Tmpfiles retornou status {r.status_code}.")
        except Exception as e:
            print(f"[!] Erro no upload Tmpfiles: {e}")

    elif service == "puush":
        if not PUUSH_API_KEY:
            print("[!] ERRO: Puush exige conta! Preencha PUUSH_API_KEY ou altere IMAGE_HOST_SERVICE para 'imgur' ou 'tmpfiles'.")
            return ""
        try:
            url_puush = "https://puush.me/api/up"
            data = {"k": PUUSH_API_KEY, "z": "poop"}
            with open(filepath, "rb") as f:
                files = {"f": (os.path.basename(filepath), f, "image/png")}
                r = requests.post(url_puush, data=data, files=files, headers=headers, timeout=30)
            if r.status_code == 200 and "puu.sh" in r.text:
                parts = r.text.strip().split(",")
                if len(parts) >= 2 and parts[1].startswith("http"):
                    return parts[1].replace("http://", "https://")
            print(f"[!] Puush recusou o upload: {r.text.strip()[:60]}")
        except Exception as e:
            print(f"[!] Erro no upload Puush: {e}")

    else:
        print(f"[!] Serviço '{IMAGE_HOST_SERVICE}' desconhecido. Use 'imgur', 'tmpfiles' ou 'puush'.")

    return ""

def _sync_send_twitch_chat(message: str, force: bool = False):
    if not BROADCASTER_ID or (not ENABLE_CHAT_ANNOUNCEMENTS and not force):
        return
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()
    url = "https://api.twitch.tv/helix/chat/messages"
    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json"
    }
    body = {
        "broadcaster_id": BROADCASTER_ID,
        "sender_id": BROADCASTER_ID,
        "message": message
    }
    try:
        requests.post(url, headers=headers, json=body, timeout=5)
    except Exception as e:
        print(f"[!] Erro de conexão no chat: {e}")

async def send_twitch_chat(message: str, force: bool = False):
    await asyncio.to_thread(_sync_send_twitch_chat, message, force)

def load_token_cache():
    """Carrega tokens renovados anteriormente do arquivo de cache."""
    global ACCESS_TOKEN, REFRESH_TOKEN
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cached_access = data.get("access_token")
                cached_refresh = data.get("refresh_token")
                if cached_access:
                    ACCESS_TOKEN = cached_access
                if cached_refresh:
                    REFRESH_TOKEN = cached_refresh
        except Exception:
            pass

def save_token_cache(access: str, refresh: str):
    """Salva novos tokens no cache local após a renovação automática."""
    try:
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"access_token": access, "refresh_token": refresh}, f, indent=2)
    except Exception:
        pass

def refresh_access_token() -> str:
    """Renova o ACCESS_TOKEN automaticamente usando o REFRESH_TOKEN."""
    global ACCESS_TOKEN, REFRESH_TOKEN
    clean_refresh = REFRESH_TOKEN.strip()
    if not clean_refresh or clean_refresh == "SEU_REFRESH_TOKEN_AQUI":
        return ""

    try:
        url_ttg = f"https://twitchtokengenerator.com/api/refresh/{clean_refresh}"
        r = requests.get(url_ttg, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                new_token = data.get("token")
                new_refresh = data.get("refresh")
                if new_token:
                    ACCESS_TOKEN = new_token
                    if new_refresh:
                        REFRESH_TOKEN = new_refresh
                    save_token_cache(ACCESS_TOKEN, REFRESH_TOKEN)
                    print("[✓] ACCESS_TOKEN renovado automaticamente com sucesso!")
                    return new_token
    except Exception as e:
        print(f"[!] Erro ao tentar renovar via TwitchTokenGenerator: {e}")

    if CLIENT_SECRET:
        try:
            url_twitch = "https://id.twitch.tv/oauth2/token"
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": clean_refresh,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            }
            r = requests.post(url_twitch, data=payload, timeout=10)
            if r.status_code == 200:
                data = r.json()
                new_token = data.get("access_token")
                new_refresh = data.get("refresh_token")
                if new_token:
                    ACCESS_TOKEN = new_token
                    if new_refresh:
                        REFRESH_TOKEN = new_refresh
                    save_token_cache(ACCESS_TOKEN, REFRESH_TOKEN)
                    print("[✓] ACCESS_TOKEN renovado automaticamente via Twitch!")
                    return new_token
        except Exception as e:
            print(f"[!] Erro ao renovar via Twitch: {e}")

    return ""

def get_broadcaster_id(client_id: str, token: str):
    load_token_cache()
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()

    if not clean_token or clean_token == "SEU_ACCESS_TOKEN_AQUI":
        print("\n[!] ERRO: Preencha seu ACCESS_TOKEN no topo do arquivo bot_soundpad.py!")
        print(" -> Gere um token em: https://twitchtokengenerator.com/\n")
        raise SystemExit(1)

    val_res = requests.get(
        "https://id.twitch.tv/oauth2/validate",
        headers={"Authorization": f"OAuth {clean_token}"},
        timeout=5
    )

    if val_res.status_code != 200:
        print("\n[*] ACCESS_TOKEN expirou! Tentando renovar com o Refresh Token...")
        new_token = refresh_access_token()
        if new_token:
            clean_token = new_token
            val_res = requests.get(
                "https://id.twitch.tv/oauth2/validate",
                headers={"Authorization": f"OAuth {clean_token}"},
                timeout=5
            )

    if val_res.status_code != 200:
        print("\n[!] ERRO DE AUTENTICAÇÃO: Não foi possível autenticar nem renovar o token!")
        print(" -> Gere um novo token em: https://twitchtokengenerator.com/\n")
        raise SystemExit(1)

    val_data = val_res.json()
    token_client_id = val_data.get("client_id")
    user_id = val_data.get("user_id")
    login = val_data.get("login")

    global CLIENT_ID
    if CLIENT_ID != token_client_id:
        CLIENT_ID = token_client_id

    return user_id, login

def subscribe_eventsub(client_id: str, token: str, broadcaster_id: str, session_id: str):
    clean_token = token.replace("oauth:", "").strip()
    headers = {
        "Client-Id": client_id,
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json"
    }
    
    body_points = {
        "type": "channel.channel_points_custom_reward_redemption.add",
        "version": "1",
        "condition": {"broadcaster_user_id": broadcaster_id},
        "transport": {"method": "websocket", "session_id": session_id}
    }
    r_points = requests.post("https://api.twitch.tv/helix/eventsub/subscriptions", headers=headers, json=body_points)
    if r_points.status_code in (200, 202):
        print("[✓] Escuta de Pontos de Canal ativa!")

    body_chat = {
        "type": "channel.chat.message",
        "version": "1",
        "condition": {
            "broadcaster_user_id": broadcaster_id,
            "user_id": broadcaster_id
        },
        "transport": {"method": "websocket", "session_id": session_id}
    }
    r_chat = requests.post("https://api.twitch.tv/helix/eventsub/subscriptions", headers=headers, json=body_chat)
    if r_chat.status_code in (200, 202):
        print("[✓] Escuta de Comandos de Chat ativa!")
    else:
        print(f"[!] Erro ao registrar escuta do chat ({r_chat.status_code}): {r_chat.text}")

async def listen_twitch():
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()
    user_id, user_name = get_broadcaster_id(CLIENT_ID, clean_token)
    global BROADCASTER_ID, BROADCASTER_NAME, SOUND_LIST, ENABLE_CHAT_ANNOUNCEMENTS, MEMES_IMAGE_URL, USER_THEMES
    BROADCASTER_ID = user_id
    BROADCASTER_NAME = user_name
    USER_THEMES = load_user_themes()

    asyncio.create_task(sound_queue_worker())
    update_obs_text("")
    ensure_managed_rewards(user_id)

    print("=" * 60)
    print(f"[✓] Canal Conectado: {user_name} (ID: {user_id})")
    print(f"[✓] Soundpad: {len(SOUND_LIST)} sons carregados na memória!")
    print(f"[✓] Fila de reprodução ativa (Delay: {QUEUE_DELAY_SECONDS}s)")
    print(f"[✓] Cooldown individual ativo ({USER_COOLDOWN_SECONDS}s)")
    print(f"[✓] Arquivo OBS pronto em: {OBS_TEXT_FILE}")
    print("=" * 60)

    normalized_rewards = {normalize_text(k): v for k, v in REWARDS_MAP.items()}
    ws_url = "wss://eventsub.wss.twitch.tv/ws"

    while True:
        try:
            print("[*] Conectando ao WebSocket da Twitch...")
            async with websockets.connect(ws_url) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    msg_type = data.get("metadata", {}).get("message_type")
                    sub_type = data.get("metadata", {}).get("subscription_type")

                    if msg_type == "session_welcome":
                        session_id = data["payload"]["session"]["id"]
                        subscribe_eventsub(CLIENT_ID, clean_token, user_id, session_id)
                        print("[*] Bot pronto e aguardando interações!")

                    elif msg_type == "notification":
                        event = data["payload"]["event"]

                        # ========================================================
                        # 1. COMANDOS DE CHAT (1 variante PT-BR e 1 EN-US por ação)
                        # ========================================================
                        if sub_type == "channel.chat.message":
                            chat_msg = event.get("message", {}).get("text", "").strip()
                            chatter = event.get("chatter_user_name", "")
                            badges = event.get("badges", [])
                            is_mod_or_host = (chatter.lower() == BROADCASTER_NAME.lower()) or any(b.get("set_id") in ["moderator", "broadcaster"] for b in badges)
                            is_vip_or_sub = is_mod_or_host or any(b.get("set_id") in ["vip", "subscriber"] for b in badges)

                            if is_vip_or_sub and chatter.lower() not in PLAYED_ENTRANCE_USERS:
                                PLAYED_ENTRANCE_USERS.add(chatter.lower())
                                if chatter.lower() in USER_THEMES:
                                    theme_id = USER_THEMES[chatter.lower()]
                                    theme_sound = next((s for s in SOUND_LIST if s["id"] == theme_id), None)
                                    if theme_sound:
                                        await SOUND_QUEUE.put({
                                            "id": theme_sound["id"],
                                            "name": f"✨ Entrada: {theme_sound['name']}",
                                            "duration": theme_sound.get("duration", 3.0),
                                            "user": chatter,
                                            "show_popup": True,
                                            "suppress_chat": True,
                                            "is_search": False
                                        })
                                        print(f" -> [Entrada VIP] @{chatter} tocou #{theme_id} ('{theme_sound['name']}')")

                            if chatter.lower() in PENDING_SEARCH_CHOICES:
                                clean_choice = chat_msg.lstrip("!").strip()
                                if clean_choice.isdigit():
                                    choice_num = int(clean_choice)
                                    pending = PENDING_SEARCH_CHOICES[chatter.lower()]
                                    if 1 <= choice_num <= len(pending["options"]):
                                        pending["timer_task"].cancel()
                                        chosen = pending["options"][choice_num - 1]
                                        del PENDING_SEARCH_CHOICES[chatter.lower()]

                                        await SOUND_QUEUE.put({
                                            "id": chosen["id"],
                                            "name": chosen["name"],
                                            "duration": chosen.get("duration", 3.0),
                                            "user": chatter,
                                            "show_popup": True,
                                            "is_search": True,
                                            "query": pending["query"]
                                        })
                                        print(f" -> [Fila] Escolha de @{chatter} -> #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")
                                        continue

                            cmd = chat_msg.lower()

                            if cmd.startswith("!settema") or cmd.startswith("!settheme"):
                                if is_vip_or_sub:
                                    parts = chat_msg.split()
                                    if len(parts) >= 2 and parts[1].lstrip("#").isdigit():
                                        chosen_id = int(parts[1].lstrip("#"))
                                        sound_match = next((s for s in SOUND_LIST if s["id"] == chosen_id), None)
                                        if sound_match:
                                            USER_THEMES[chatter.lower()] = chosen_id
                                            save_user_themes()
                                            await send_twitch_chat(f"✨ @{chatter} Seu som de entrada foi definido como: \"{sound_match['name']}\" (ID #{chosen_id})!")
                                        else:
                                            await send_twitch_chat(f"⚠️ @{chatter} Som ID #{chosen_id} não encontrado na lista!")
                                    else:
                                        await send_twitch_chat(f"⚠️ @{chatter} Use: !settema <ID> (ex: !settema 125)")
                                else:
                                    await send_twitch_chat(f"⚠️ @{chatter} Apenas VIPs, Subs e Moderadores podem ter som de entrada!")

                            elif cmd in ["!meusom", "!mysound"]:
                                if chatter.lower() in USER_THEMES:
                                    t_id = USER_THEMES[chatter.lower()]
                                    t_sound = next((s for s in SOUND_LIST if s["id"] == t_id), None)
                                    name_label = f"\"{t_sound['name']}\" (ID #{t_id})" if t_sound else f"ID #{t_id}"
                                    await send_twitch_chat(f"🎵 @{chatter} Seu som de entrada atual é: {name_label}")
                                else:
                                    await send_twitch_chat(f"⚠️ @{chatter} Você ainda não configurou seu som de entrada! Use !settema <ID>")

                            elif cmd in ["!categorias", "!categories"]:
                                cat_list = ", ".join(SOUND_CATEGORIES.keys())
                                await send_twitch_chat(f"📂 Categorias disponíveis: {cat_list} (Use !categoria <nome> para sortear)")

                            elif cmd.startswith("!categoria") or cmd.startswith("!category"):
                                parts = chat_msg.split(maxsplit=1)
                                if len(parts) >= 2:
                                    cat_key = parts[1].strip().lower()
                                    if cat_key in SOUND_CATEGORIES:
                                        can_redeem, remaining = check_user_cooldown(chatter)
                                        if not can_redeem:
                                            await send_twitch_chat(f"⏳ @{chatter}, aguarde {remaining}s para sortear de novo!")
                                            continue

                                        keyword = normalize_text(SOUND_CATEGORIES[cat_key])
                                        matched_sounds = [s for s in SOUND_LIST if keyword in normalize_text(s["name"])]
                                        if matched_sounds:
                                            chosen = random.choice(matched_sounds)
                                            await SOUND_QUEUE.put({
                                                "id": chosen["id"],
                                                "name": chosen["name"],
                                                "duration": chosen.get("duration", 3.0),
                                                "user": chatter,
                                                "show_popup": True,
                                                "chat_message": f"📂 @{chatter} sorteou na categoria [{cat_key}]: \"{chosen['name']}\" (ID #{chosen['id']})",
                                                "is_search": False
                                            })
                                            print(f" -> [Categoria] @{chatter} sorteou '{cat_key}' -> #{chosen['id']} ('{chosen['name']}')")
                                        else:
                                            await send_twitch_chat(f"⚠️ Nenhum som encontrado para a categoria '{cat_key}'!")
                                    else:
                                        cats = ", ".join(SOUND_CATEGORIES.keys())
                                        await send_twitch_chat(f"⚠️ Categoria desconhecida! Opções: {cats}")
                                else:
                                    cats = ", ".join(SOUND_CATEGORIES.keys())
                                    await send_twitch_chat(f"⚠️ Use: !categoria <nome> (Opções: {cats})")

                            elif cmd in ["!som", "!ultimosom", "!sound", "!lastsound"]:
                                if LAST_PLAYED_SOUND:
                                    await send_twitch_chat(f"🔊 Último som tocado: \"{LAST_PLAYED_SOUND['name']}\" (ID #{LAST_PLAYED_SOUND['id']}) — pedido por @{LAST_PLAYED_SOUND['user']}")
                                else:
                                    await send_twitch_chat("⚠️ Nenhum som foi reproduzido ainda nesta sessão!")

                            elif cmd in ["!memes", "!sounds", "!imagem", "!image", "!gerarimagem", "!generateimage"]:
                                if is_mod_or_host and cmd in ["!gerarimagem", "!generateimage", "!imagem", "!image"]:
                                    img_path = generate_sounds_image(force=True)
                                    if img_path:
                                        msg_url = f": {MEMES_IMAGE_URL}" if MEMES_IMAGE_URL else "!"
                                        await send_twitch_chat(f"🖼️ @{chatter} Imagem atualizada{msg_url}", force=True)
                                        print(f"[MOD] @{chatter} gerou a imagem de sons.")
                                elif cmd in ["!memes", "!sounds"]:
                                    if not MEMES_IMAGE_URL or not check_image_url_alive(MEMES_IMAGE_URL):
                                        new_url = upload_temporary_image(SOUNDS_IMAGE_FILE)
                                        if new_url:
                                            MEMES_IMAGE_URL = new_url
                                            save_image_url(new_url)

                                    if MEMES_IMAGE_URL:
                                        msg_extra = " (Salve se quiser, o link expira em 1 hora!)" if IMAGE_HOST_SERVICE.lower().strip() == "tmpfiles" else ""
                                        await send_twitch_chat(f"🖼️ @{chatter} Lista de memes: {MEMES_IMAGE_URL}{msg_extra}")
                                    else:
                                        await send_twitch_chat(f"⚠️ @{chatter} O link da imagem ainda está sendo gerado. Tente de novo em instantes!")

                            elif cmd in ["!pular", "!skip"]:
                                if is_mod_or_host:
                                    skip_current_sound()
                                    await send_twitch_chat(f"⏭️ @{chatter} pulou para o próximo som da fila!")
                                    print(f"[MOD] @{chatter} pulou o som atual.")

                            elif cmd in ["!limpar", "!clear"]:
                                if is_mod_or_host:
                                    clear_queue_and_stop()
                                    await send_twitch_chat(f"⏹️ @{chatter} limpou toda a fila de sons!")
                                    print(f"[MOD] @{chatter} limpou a fila inteira.")

                            elif cmd in ["!recarregar", "!reload"]:
                                if is_mod_or_host:
                                    SOUND_LIST = load_soundpad_library()
                                    generate_sounds_image(SOUND_LIST, force=True)
                                    await send_twitch_chat(f"🔄 @{chatter} recarregou o Soundpad: {len(SOUND_LIST)} sons e imagem atualizada!")
                                    print(f"[MOD] @{chatter} recarregou a biblioteca ({len(SOUND_LIST)} sons).")

                            elif cmd in ["!chat", "!togglechat"]:
                                if is_mod_or_host:
                                    ENABLE_CHAT_ANNOUNCEMENTS = not ENABLE_CHAT_ANNOUNCEMENTS
                                    estado = "ATIVADOS" if ENABLE_CHAT_ANNOUNCEMENTS else "DESATIVADOS"
                                    await send_twitch_chat(f"📢 Avisos de som no chat: {estado}!", force=True)
                                    print(f"[MOD] @{chatter} alterou avisos de chat para: {estado}.")

                        # ========================================================
                        # 2. RESGATES DE PONTOS DE CANAL
                        # ========================================================
                        elif sub_type == "channel.channel_points_custom_reward_redemption.add":
                            redemption_id = event["id"]
                            reward_id = event["reward"]["id"]
                            reward_title = event["reward"]["title"]
                            user = event["user_name"]
                            user_input = event.get("user_input", "").strip()
                            clean_title = normalize_text(reward_title)

                            print(f"\n[RESGATE] '{user}' resgatou: '{reward_title}'")

                            if clean_title == normalize_text(STOP_REWARD_NAME):
                                is_active = is_soundpad_playing() or not SOUND_QUEUE.empty() or (CURRENT_PLAY_TASK and not CURRENT_PLAY_TASK.done())
                                if not is_active:
                                    await send_twitch_chat(f"⚠️ @{user}, nenhum áudio está tocando agora! Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                skip_current_sound()
                                await send_twitch_chat(f"⏹️ @{user} parou o áudio atual!")
                                continue

                            can_redeem, remaining = check_user_cooldown(user)
                            if not can_redeem:
                                await send_twitch_chat(f"⏳ @{user}, aguarde {remaining}s para resgatar! Seus pontos foram devolvidos.")
                                await refund_redemption(user_id, reward_id, redemption_id)
                                continue

                            if clean_title == normalize_text(ROULETTE_REWARD_NAME):
                                if not SOUND_LIST:
                                    await send_twitch_chat(f"⚠️ @{user}, Soundpad vazio! Seus pontos foram devolvidos.")
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                viewer_id = event.get("user_id", "")
                                is_trap = random.randint(1, 100) <= ROULETTE_TRAP_CHANCE
                                if is_trap:
                                    chosen_trap_id = random.choice(ROULETTE_TRAP_SOUND_IDS) if ROULETTE_TRAP_SOUND_IDS else 14
                                    trap_sound = next((s for s in SOUND_LIST if s["id"] == chosen_trap_id), None)
                                    trap_id = trap_sound["id"] if trap_sound else chosen_trap_id
                                    trap_name = trap_sound["name"] if trap_sound else "Trap Troll"
                                    trap_dur = trap_sound.get("duration", 3.0) if trap_sound else 3.0

                                    is_streamer = (user.lower() == BROADCASTER_NAME.lower()) or (viewer_id == user_id)
                                    if is_streamer:
                                        msg_chat = f"💀 @{user} caiu na TRAP: \"{trap_name}\" (ID #{trap_id})! (Streamer/Mod é imune a timeout!)"
                                        apply_timeout = False
                                    elif ROULETTE_TIMEOUT_SECONDS > 0:
                                        msg_chat = f"💀 @{user} deu azar na Roleta Russa, caiu na TRAP: \"{trap_name}\" (ID #{trap_id}) e tomou {ROULETTE_TIMEOUT_SECONDS}s de timeout!"
                                        apply_timeout = True
                                    else:
                                        msg_chat = f"💀 @{user} deu azar na Roleta Russa e caiu na TRAP: \"{trap_name}\" (ID #{trap_id})!"
                                        apply_timeout = False

                                    await SOUND_QUEUE.put({
                                        "id": trap_id,
                                        "name": f"💀 TRAP: {trap_name}",
                                        "duration": trap_dur,
                                        "user": user,
                                        "show_popup": True,
                                        "chat_message": msg_chat,
                                        "timeout_user_id": viewer_id if apply_timeout else None,
                                        "timeout_duration": ROULETTE_TIMEOUT_SECONDS,
                                        "is_search": False
                                    })
                                    print(f" -> [Fila] Adicionado Roleta (TRAP) #{trap_id} ('{trap_name}') [{trap_dur}s]")
                                else:
                                    chosen = random.choice(SOUND_LIST)
                                    await SOUND_QUEUE.put({
                                        "id": chosen["id"],
                                        "name": chosen["name"],
                                        "duration": chosen.get("duration", 3.0),
                                        "user": user,
                                        "show_popup": True,
                                        "chat_message": f"🎰 @{user} sobreviveu à Roleta Russa e tocou: \"{chosen['name']}\" (ID #{chosen['id']})",
                                        "is_search": False
                                    })
                                    print(f" -> [Fila] Adicionado Roleta (Sobreviveu) #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")

                            elif clean_title == normalize_text(RANDOM_REWARD_NAME):
                                if not SOUND_LIST:
                                    await send_twitch_chat(f"⚠️ @{user}, Soundpad vazio! Seus pontos foram devolvidos.")
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                chosen = random.choice(SOUND_LIST)
                                await SOUND_QUEUE.put({
                                    "id": chosen["id"],
                                    "name": chosen["name"],
                                    "duration": chosen.get("duration", 3.0),
                                    "user": user,
                                    "show_popup": True,
                                    "is_search": False
                                })
                                print(f" -> [Fila] Adicionado Aleatório #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")

                            elif clean_title == normalize_text(SEARCH_REWARD_NAME):
                                if not user_input:
                                    await send_twitch_chat(f"⚠️ @{user}, digite uma palavra ou ID para buscar o meme! Seus pontos foram devolvidos.")
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                raw_id = user_input.lstrip("#").strip()
                                if raw_id.isdigit():
                                    target_id = int(raw_id)
                                    sound_by_id = next((s for s in SOUND_LIST if s["id"] == target_id), None)
                                    if sound_by_id:
                                        await SOUND_QUEUE.put({
                                            "id": sound_by_id["id"],
                                            "name": sound_by_id["name"],
                                            "duration": sound_by_id.get("duration", 3.0),
                                            "user": user,
                                            "show_popup": True,
                                            "is_search": True,
                                            "query": f"#{target_id}"
                                        })
                                        print(f" -> [Fila] Busca por ID #{target_id} -> '{sound_by_id['name']}' [{sound_by_id.get('duration', 3.0)}s]")
                                        continue
                                    else:
                                        await send_twitch_chat(f"⚠️ @{user}, nenhum som com o ID #{target_id}! Seus pontos foram devolvidos.")
                                        await refund_redemption(user_id, reward_id, redemption_id)
                                        continue

                                query = normalize_text(user_input)
                                matches = [s for s in SOUND_LIST if query in normalize_text(s["name"])]

                                if not matches:
                                    await send_twitch_chat(f"⚠️ @{user}, nenhum áudio com \"{user_input}\"! Seus pontos foram devolvidos.")
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                if len(matches) == 1:
                                    chosen = matches[0]
                                    await SOUND_QUEUE.put({
                                        "id": chosen["id"],
                                        "name": chosen["name"],
                                        "duration": chosen.get("duration", 3.0),
                                        "user": user,
                                        "show_popup": True,
                                        "is_search": True,
                                        "query": user_input
                                    })
                                    print(f" -> [Fila] Busca por '{user_input}' (único) -> #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")
                                else:
                                    options = matches[:5]
                                    user_key = user.lower()

                                    if user_key in PENDING_SEARCH_CHOICES:
                                        PENDING_SEARCH_CHOICES[user_key]["timer_task"].cancel()

                                    async def search_choice_timeout(u_key, b_id, r_id, red_id):
                                        await asyncio.sleep(30)
                                        if u_key in PENDING_SEARCH_CHOICES:
                                            del PENDING_SEARCH_CHOICES[u_key]
                                            await refund_redemption(b_id, r_id, red_id)
                                            await send_twitch_chat(f"⏳ @{user}, tempo esgotado para escolher o som! Seus pontos foram devolvidos.", force=True)

                                    timeout_task = asyncio.create_task(search_choice_timeout(user_key, user_id, reward_id, redemption_id))
                                    PENDING_SEARCH_CHOICES[user_key] = {
                                        "options": options,
                                        "query": user_input,
                                        "timer_task": timeout_task
                                    }

                                    opts_text = " | ".join([f"[{i+1}] {s['name']}" for i, s in enumerate(options)])
                                    await send_twitch_chat(f"🔎 @{user}, escolha digitando o número (1 a {len(options)}) no chat em 30s: {opts_text}", force=True)
                                    print(f" -> [Busca] @{user} recebeu {len(options)} opções para '{user_input}'. Aguardando escolha...")

                            elif clean_title in normalized_rewards:
                                sound_id = normalized_rewards[clean_title]
                                sound_info = next((s for s in SOUND_LIST if s["id"] == sound_id), None)
                                dur = sound_info.get("duration", 3.0) if sound_info else 3.0
                                await SOUND_QUEUE.put({
                                    "id": sound_id,
                                    "name": reward_title,
                                    "duration": dur,
                                    "user": user,
                                    "show_popup": False
                                })
                                print(f" -> [Fila] Som Fixo #{sound_id} ('{reward_title}') adicionado silenciosamente [{dur}s].")

                    elif msg_type == "session_reconnect":
                        ws_url = data["payload"]["session"]["reconnect_url"]
                        break

                    elif msg_type == "session_keepalive":
                        pass

        except Exception as e:
            print(f"[!] Conexão caiu ({e}). Reconectando em 5 segundos...")
            ws_url = "wss://eventsub.wss.twitch.tv/ws"
            await asyncio.sleep(5)

if __name__ == "__main__":
    update_obs_text("")
    SOUND_LIST = load_soundpad_library()
    try:
        asyncio.run(listen_twitch())
    except KeyboardInterrupt:
        update_obs_text("")
        print("\n[Encerrado pelo usuário]")