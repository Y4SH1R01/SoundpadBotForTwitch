import asyncio
from collections import deque
import difflib
import hashlib
import html
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
import random
import re
import sys
import threading
import time
import unicodedata
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

CATEGORY_REWARD_NAME = "Som por Categoria"
CATEGORY_REWARD_COST = 120                      # Custo em pontos para sortear um som de uma categoria
CATEGORY_REWARD_PROMPT = "Digite o nome da categoria desejada (ex: anime, scream, meme). Use !cats no chat para ver todas."

STOP_REWARD_NAME = "Parar Som"                  # Interrompe o áudio atual (sem apagar a fila restante)
STOP_REWARD_COST = 500                          # Custo em pontos para parar o áudio atual
STOP_REWARD_PROMPT = "Interrompe a reprodução do áudio atual no Soundpad imediatamente."

# Configurações da Roleta Russa Progressiva
ROULETTE_REWARD_NAME = "Roleta Russa"
ROULETTE_REWARD_COST = 50                       # Custo em pontos da roleta
ROULETTE_REWARD_PROMPT = "Gire a roleta! Começa com 5% de chance de TRAP e sobe +5% a cada sobrevivente!"
ROULETTE_TRAP_CHANCE = 5                        # Chance inicial em % de cair na Trap (5 = 5%)
ROULETTE_PROGRESSIVE_STEP = 5                   # Quanto % a chance aumenta a cada viewer que sobrevive
ROULETTE_TRAP_SOUND_IDS = [1, 2, 3]             # IDs dos sons tocados quando cai na Trap (sorteia um aleatório entre eles)
ROULETTE_TIMEOUT_SECONDS = 60                   # Duração do timeout em segundos para quem cair na trap (0 = desativado)

# Categorias de memes para o resgate "Som por Categoria" e comando !cat (Mod)
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

# Configurações de Fila, Cooldown e Monitoramento
USER_COOLDOWN_SECONDS = 0                       # Tempo em segundos de cooldown por viewer (0 = desativado)
QUEUE_DELAY_SECONDS = 1                         # Intervalo em segundos entre um som e outro na fila
MAX_QUEUE_SIZE = 10                             # Máximo de áudios esperando na fila (0 = ilimitado)
NO_REPEAT_LAST_N = 15                           # Evita repetir os últimos N sons sorteados no RNG (0 = desativado)
SPL_AUTO_RELOAD_INTERVAL = 15                   # Intervalo mínimo em segundos para checar alterações no .spl automaticamente
ENABLE_CHAT_ANNOUNCEMENTS = True                # True = avisa no chat / False = apenas pop-up no OBS
ANNOUNCE_BOT_ONLINE = True                      # True = envia aviso no chat quando o bot ficar online

# Configuração da Imagem de Memes
GENERATE_IMAGE_ON_STARTUP = True                # True = ativa a geração automática ao iniciar / False = só gera via comando no chat (!gerarimagem)
FORCE_REGENERATE_IMAGE = False                  # True = força nova imagem toda vez que ligar / False = reaproveita a que já estiver pronta
IMAGE_HOST_SERVICE = "imgur"                    # Provedor web: "imgur" (estável e sem conta), "tmpfiles" (sem conta, dura 1h) ou "puush" (requer conta)
PUUSH_API_KEY = ""                              # Obrigatório apenas se IMAGE_HOST_SERVICE for "puush"

# Caminhos
PIPE_PATH = r"\\.\pipe\sp_remote_control"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OBS_TEXT_FILE = os.path.join(BASE_DIR, "obs_tocando_agora.txt")
SOUNDS_IMAGE_FILE = os.path.join(BASE_DIR, "lista_de_sons.png")
SOUNDS_URL_FILE = os.path.join(BASE_DIR, "link_memes.txt")
SOUNDS_SIG_FILE = os.path.join(BASE_DIR, "lista_de_sons.sig")
VIP_THEMES_FILE = os.path.join(BASE_DIR, "user_themes.json")
TOKEN_CACHE_FILE = os.path.join(BASE_DIR, "twitch_tokens.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONFIG_EXAMPLE_FILE = os.path.join(BASE_DIR, "config.example.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")
LOG_FILE = os.path.join(BASE_DIR, "bot.log")
# ===============================================

# ==================== LOGS EM ARQUIVO E CREDENCIAIS EXTERNAS ====================
class _DualStream:
    def __init__(self, stream, logger, level):
        self.stream = stream
        self.logger = logger
        self.level = level
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, message):
        with self._lock:
            if self.stream:
                try:
                    self.stream.write(message)
                except UnicodeEncodeError:
                    self.stream.write(message.encode("ascii", errors="replace").decode("ascii"))
            self._buffer += message
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                stripped = line.rstrip("\r")
                if stripped:
                    self.logger.log(self.level, stripped)

    def flush(self):
        with self._lock:
            if self.stream:
                self.stream.flush()
            if self._buffer.strip():
                self.logger.log(self.level, self._buffer.rstrip("\r\n"))
                self._buffer = ""

    def isatty(self):
        return bool(self.stream and self.stream.isatty())

def setup_logging():
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    file_logger = logging.getLogger("soundpad_bot")
    file_logger.setLevel(logging.INFO)
    file_logger.propagate = False

    if not file_logger.handlers:
        handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        file_logger.addHandler(handler)

    if not isinstance(sys.stdout, _DualStream):
        sys.stdout = _DualStream(sys.stdout, file_logger, logging.INFO)
    if not isinstance(sys.stderr, _DualStream):
        sys.stderr = _DualStream(sys.stderr, file_logger, logging.ERROR)

def load_external_credentials():
    """Carrega credenciais de config.json ou .env (se existirem) sem expor tokens no código."""
    global CLIENT_ID, ACCESS_TOKEN, REFRESH_TOKEN, CLIENT_SECRET, PUUSH_API_KEY

    if not os.path.exists(CONFIG_FILE) and not os.path.exists(CONFIG_EXAMPLE_FILE):
        try:
            with open(CONFIG_EXAMPLE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "CLIENT_ID": "SEU_CLIENT_ID_AQUI",
                    "ACCESS_TOKEN": "SEU_ACCESS_TOKEN_AQUI",
                    "REFRESH_TOKEN": "SEU_REFRESH_TOKEN_AQUI",
                    "CLIENT_SECRET": "",
                    "PUUSH_API_KEY": ""
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    loaded = {}

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if isinstance(cfg, dict):
                    loaded.update(cfg)
        except Exception as e:
            print(f"[!] Erro ao ler config.json: {e}")

    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    loaded[k] = v
        except Exception as e:
            print(f"[!] Erro ao ler .env: {e}")

    if loaded.get("CLIENT_ID"):
        CLIENT_ID = str(loaded["CLIENT_ID"]).strip()
    if loaded.get("ACCESS_TOKEN"):
        ACCESS_TOKEN = str(loaded["ACCESS_TOKEN"]).strip()
    if loaded.get("REFRESH_TOKEN"):
        REFRESH_TOKEN = str(loaded["REFRESH_TOKEN"]).strip()
    if "CLIENT_SECRET" in loaded:
        CLIENT_SECRET = str(loaded["CLIENT_SECRET"]).strip()
    if "PUUSH_API_KEY" in loaded:
        PUUSH_API_KEY = str(loaded["PUUSH_API_KEY"]).strip()

setup_logging()
load_external_credentials()
# ===============================================================================

INITIAL_ACCESS_TOKEN = ACCESS_TOKEN.replace("oauth:", "").strip()
INITIAL_REFRESH_TOKEN = REFRESH_TOKEN.strip()

BROADCASTER_ID = None
BROADCASTER_NAME = ""
SOUND_LIST = []
SOUND_BY_ID = {}
LAST_SPL_PATH = None
LAST_SPL_MTIME = None
LAST_SPL_CHECK_TIME = 0.0

SOUND_QUEUE = asyncio.Queue()
QUEUED_ITEMS = []
QUEUE_PAUSED = False
PAUSE_EVENT = None
CURRENT_PLAY_ITEM = None
CURRENT_PLAY_END_TIME = 0.0

USER_COOLDOWNS = {}
RECENT_RANDOM_IDS = deque(maxlen=NO_REPEAT_LAST_N if NO_REPEAT_LAST_N > 0 else 1)
CURRENT_ROULETTE_CHANCE = ROULETTE_TRAP_CHANCE
PLAYED_ENTRANCE_USERS = set()
KNOWN_MOD_IDS = set()
USER_THEMES = {}

CURRENT_PLAY_TASK = None
PENDING_SEARCH_CHOICES = {}
MEMES_IMAGE_URL = ""
LAST_PLAYED_SOUND = None

HTTP_SESSION = requests.Session()
TOKEN_LOCK = threading.Lock()
IMAGE_OP_LOCK = None
RECENT_BOT_MESSAGE_IDS = deque(maxlen=50)

def get_clean_token() -> str:
    return ACCESS_TOKEN.replace("oauth:", "").strip()

def load_user_themes() -> dict:
    """Carrega os temas de entrada salvos dos viewers."""
    if os.path.exists(VIP_THEMES_FILE):
        try:
            with open(VIP_THEMES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"[!] Erro ao carregar temas VIP: {e}")
    return {}

def save_user_themes(themes_snapshot: dict = None):
    """Salva os temas de entrada dos viewers no arquivo JSON."""
    payload = themes_snapshot if themes_snapshot is not None else USER_THEMES
    try:
        with open(VIP_THEMES_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Erro ao salvar temas VIP: {e}")

def normalize_text(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return no_accents.replace("–", "-").replace("—", "-").strip().lower()

def find_fuzzy_suggestions(query: str, limit: int = 3) -> list:
    if not SOUND_LIST or not query:
        return []
    scored = []
    for s in SOUND_LIST:
        norm = s["norm_name"]
        best_word = max(
            (difflib.SequenceMatcher(None, query, w).ratio() for w in norm.split() if len(w) >= 2),
            default=0.0
        )
        full_ratio = difflib.SequenceMatcher(None, query, norm).ratio()
        score = max(best_word, full_ratio)
        if score >= 0.62:
            scored.append((score, s["name"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [name for _, name in scored[:limit]]

def pick_non_repeating_sound(candidates: list):
    if not candidates:
        return None
    if NO_REPEAT_LAST_N > 0 and len(candidates) > 1:
        pool = [s for s in candidates if s["id"] not in RECENT_RANDOM_IDS]
        if not pool:
            last_id = RECENT_RANDOM_IDS[-1] if RECENT_RANDOM_IDS else None
            pool = [s for s in candidates if s["id"] != last_id] or candidates
        chosen = random.choice(pool)
    else:
        chosen = random.choice(candidates)

    if NO_REPEAT_LAST_N > 0:
        RECENT_RANDOM_IDS.append(chosen["id"])
    return chosen

def is_soundpad_connected() -> bool:
    """Verifica se o pipe do Soundpad está acessível antes de aceitar resgates."""
    try:
        with open(PIPE_PATH, "r+b", buffering=0) as pipe:
            pipe.write(b"GetPlayStatus()")
            pipe.read(64)
            return True
    except Exception:
        return False

def send_soundpad(command: str) -> bool:
    """Envia o comando direto pela memória do Soundpad."""
    try:
        with open(PIPE_PATH, "r+b", buffering=0) as pipe:
            pipe.write(command.encode("utf-8"))
            return True
    except Exception as e:
        print(f"[!] Erro no Soundpad: {e}")
        return False

def play_sound(sound_id: int) -> bool:
    print(f" -> 🔊 Tocando som #{sound_id} no Soundpad...")
    return send_soundpad(f"DoPlaySoundFromCategory(-1,{sound_id})")

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

def _twitch_request(method: str, url: str, json_data=None, timeout: int = 5) -> requests.Response:
    """Executa requisição à API Helix reutilizando sessão e renovando token em caso de 401."""
    token = get_clean_token()
    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    r = HTTP_SESSION.request(method, url, headers=headers, json=json_data, timeout=timeout)

    if r.status_code == 401:
        with TOKEN_LOCK:
            if get_clean_token() == token:
                print("\n[*] Token expirado durante operação (401). Tentando renovar...")
                refresh_access_token()
        new_token = get_clean_token()
        if new_token and new_token != token:
            headers["Authorization"] = f"Bearer {new_token}"
            r = HTTP_SESSION.request(method, url, headers=headers, json=json_data, timeout=timeout)

    return r

def _sync_update_redemption_status(broadcaster_id: str, reward_id: str, redemption_id: str, status: str):
    """Atualiza o status do resgate na Twitch ('CANCELED' = estorno, 'FULFILLED' = concluído)."""
    url = f"https://api.twitch.tv/helix/channel_points/custom_rewards/redemptions?broadcaster_id={broadcaster_id}&reward_id={reward_id}&id={redemption_id}"
    try:
        r = _twitch_request("PATCH", url, json_data={"status": status}, timeout=5)
        if r.status_code == 200:
            if status == "CANCELED":
                print("[Twitch] Pontos estornados com sucesso ao viewer!")
            elif status == "FULFILLED":
                print("[Twitch] Resgate marcado como concluído (FULFILLED)!")
        elif status == "FULFILLED" and r.status_code in (403, 404):
            pass
        else:
            print(f"[!] Falha ao atualizar resgate para {status} ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[!] Erro de conexão ao atualizar resgate ({status}): {e}")

async def refund_redemption(broadcaster_id: str, reward_id: str, redemption_id: str):
    await asyncio.to_thread(_sync_update_redemption_status, broadcaster_id, reward_id, redemption_id, "CANCELED")

async def fulfill_redemption(broadcaster_id: str, reward_id: str, redemption_id: str):
    await asyncio.to_thread(_sync_update_redemption_status, broadcaster_id, reward_id, redemption_id, "FULFILLED")

def _sync_timeout_user(broadcaster_id: str, target_user_id: str, duration: int, reason: str):
    """Aplica timeout em um usuário via API da Twitch (requer escopo moderator:manage:banned_users)."""
    if not target_user_id or target_user_id == broadcaster_id or duration <= 0:
        return
    url = f"https://api.twitch.tv/helix/moderator/bans?broadcaster_id={broadcaster_id}&moderator_id={broadcaster_id}"
    body = {
        "data": {
            "user_id": target_user_id,
            "duration": duration,
            "reason": reason
        }
    }
    try:
        r = _twitch_request("POST", url, json_data=body, timeout=5)
        if r.status_code in (200, 204):
            print(f"[Twitch] Timeout de {duration}s aplicado com sucesso no viewer ID {target_user_id}!")
        elif r.status_code == 400 and "moderator" in r.text.lower():
            KNOWN_MOD_IDS.add(target_user_id)
            print(f"[Twitch] Viewer ID {target_user_id} é moderador (imune a timeout).")
        elif r.status_code == 403:
            print("[!] Falha no timeout (403): O token precisa do escopo 'moderator:manage:banned_users'!")
        else:
            print(f"[!] Falha ao aplicar timeout ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[!] Erro de conexão no timeout: {e}")

async def timeout_user(broadcaster_id: str, target_user_id: str, duration: int, reason: str):
    await asyncio.to_thread(_sync_timeout_user, broadcaster_id, target_user_id, duration, reason)

def load_moderators(broadcaster_id: str):
    url = f"https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={broadcaster_id}&first=100"
    try:
        r = _twitch_request("GET", url, timeout=5)
        if r.status_code == 200:
            mods = r.json().get("data", [])
            for m in mods:
                uid = m.get("user_id")
                if uid:
                    KNOWN_MOD_IDS.add(uid)
    except Exception:
        pass

def ensure_managed_rewards(broadcaster_id: str):
    """Cria e atualiza automaticamente as recompensas gerenciáveis via API com base nas configurações."""
    url_rewards = f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={broadcaster_id}"
    url_get = f"{url_rewards}&only_manageable_rewards=true"
    try:
        r = _twitch_request("GET", url_get, timeout=5)
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
                "title": CATEGORY_REWARD_NAME,
                "cost": CATEGORY_REWARD_COST,
                "is_user_input_required": True,
                "prompt": CATEGORY_REWARD_PROMPT
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
                    (existing.get("prompt") or "") != rw["prompt"]
                    or existing.get("cost", 0) != rw["cost"]
                    or existing.get("is_user_input_required", False) != rw["is_user_input_required"]
                )

                if needs_update:
                    patch_url = f"{url_rewards}&id={reward_id}"
                    r_patch = _twitch_request("PATCH", patch_url, json_data=rw, timeout=5)
                    if r_patch.status_code == 200:
                        print(f"[✓] Recompensa '{rw['title']}' atualizada na Twitch com a nova descrição/custo!")
                    else:
                        print(f"[!] Falha ao atualizar recompensa '{rw['title']}' ({r_patch.status_code}): {r_patch.text}")
                else:
                    print(f"[✓] Recompensa gerenciável '{rw['title']}' verificada (estorno e descrição ativos)!")
                continue

            r_post = _twitch_request("POST", url_rewards, json_data=rw, timeout=5)
            if r_post.status_code in (200, 201):
                print(f"[✓] Recompensa '{rw['title']}' criada via API (estorno ativo)!")
            elif r_post.status_code == 400 and "already exists" in r_post.text.lower():
                print(f"[!] AVISO: Apague a recompensa '{rw['title']}' antiga do site da Twitch para o bot poder recriá-la com direito a estorno.")
            else:
                print(f"[!] Erro ao registrar recompensa '{rw['title']}' ({r_post.status_code}): {r_post.text}")
    except Exception as e:
        print(f"[!] Erro ao checar recompensas gerenciadas: {e}")

async def enqueue_sound(item: dict):
    QUEUED_ITEMS.append(item)
    await SOUND_QUEUE.put(item)

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
            queued = SOUND_QUEUE.get_nowait()
            if queued in QUEUED_ITEMS:
                QUEUED_ITEMS.remove(queued)
            SOUND_QUEUE.task_done()
        except Exception:
            break
    QUEUED_ITEMS.clear()
    if CURRENT_PLAY_TASK and not CURRENT_PLAY_TASK.done():
        CURRENT_PLAY_TASK.cancel()
    stop_sound()
    update_obs_text("")

def check_user_cooldown(user: str):
    """Apenas consulta o cooldown sem aplicar ainda. Retorna (True, 0) ou (False, remaining)."""
    if USER_COOLDOWN_SECONDS <= 0 or user.lower() == BROADCASTER_NAME.lower():
        return True, 0

    now = time.time()
    last_time = USER_COOLDOWNS.get(user.lower(), 0)
    remaining = int(USER_COOLDOWN_SECONDS - (now - last_time))

    if remaining > 0:
        return False, remaining
    return True, 0

def commit_user_cooldown(user: str):
    if USER_COOLDOWN_SECONDS <= 0 or user.lower() == BROADCASTER_NAME.lower():
        return
    now = time.time()
    USER_COOLDOWNS[user.lower()] = now
    if len(USER_COOLDOWNS) > 500:
        expired = [u for u, t in USER_COOLDOWNS.items() if now - t >= USER_COOLDOWN_SECONDS]
        for u in expired:
            USER_COOLDOWNS.pop(u, None)

async def sound_queue_worker():
    """Worker que monitora o áudio e sincroniza o pop-up com a duração real."""
    global CURRENT_PLAY_TASK, LAST_PLAYED_SOUND, CURRENT_PLAY_ITEM, CURRENT_PLAY_END_TIME
    while True:
        await PAUSE_EVENT.wait()
        item = await SOUND_QUEUE.get()
        try:
            if QUEUE_PAUSED:
                await PAUSE_EVENT.wait()

            if item in QUEUED_ITEMS:
                QUEUED_ITEMS.remove(item)

            played = await asyncio.to_thread(play_sound, item["id"])
            if not played:
                red_info = item.get("redemption_info")
                if red_info:
                    asyncio.create_task(refund_redemption(*red_info))
                continue

            red_info = item.get("redemption_info")
            if red_info:
                asyncio.create_task(fulfill_redemption(*red_info))

            LAST_PLAYED_SOUND = item
            duration = item.get("duration", 3.0)
            CURRENT_PLAY_ITEM = item
            CURRENT_PLAY_END_TIME = time.time() + duration

            if item.get("show_popup"):
                sound_name = item["name"]
                user = item["user"]
                await asyncio.to_thread(update_obs_text, f"🎵 {sound_name} (por @{user})")

                chat_msg = item.get("chat_message")
                if chat_msg:
                    asyncio.create_task(send_twitch_chat(chat_msg))
                elif not item.get("suppress_chat"):
                    if item.get("is_search"):
                        query = item.get("query", "")
                        asyncio.create_task(send_twitch_chat(f"🔎 @{user} buscou \"{query}\" e tocou: \"{sound_name}\" (ID #{item['id']})"))
                    else:
                        asyncio.create_task(send_twitch_chat(f"🎲 @{user} tirou um som aleatório: \"{sound_name}\" (ID #{item['id']})"))

                timeout_uid = item.get("timeout_user_id")
                timeout_dur = item.get("timeout_duration", 0)
                if timeout_uid and timeout_dur > 0 and BROADCASTER_ID:
                    asyncio.create_task(timeout_user(BROADCASTER_ID, timeout_uid, timeout_dur, "Caiu na Trap da Roleta Russa!"))

            async def _wait_playback():
                await asyncio.sleep(0.4)
                start_time = time.time()
                while time.time() - start_time < duration:
                    await asyncio.sleep(0.3)
                    if not await asyncio.to_thread(is_soundpad_playing):
                        break

            CURRENT_PLAY_TASK = asyncio.create_task(_wait_playback())
            try:
                await CURRENT_PLAY_TASK
            except asyncio.CancelledError:
                pass

        except Exception as e:
            print(f"[!] Erro na fila: {e}")
        finally:
            CURRENT_PLAY_ITEM = None
            CURRENT_PLAY_END_TIME = 0.0
            await asyncio.to_thread(update_obs_text, "")
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

# ==================== CHECAGEM DE ALTERAÇÕES NA LISTA ====================
def get_sounds_signature(sounds: list) -> dict:
    payload = json.dumps([[s["id"], s["name"]] for s in sounds], ensure_ascii=False)
    return {
        "count": len(sounds),
        "hash": hashlib.sha256(payload.encode("utf-8")).hexdigest()
    }

def load_sounds_signature() -> dict:
    if os.path.exists(SOUNDS_SIG_FILE):
        try:
            with open(SOUNDS_SIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "hash" in data:
                    return data
        except Exception:
            pass
    return None

def save_sounds_signature(sig: dict):
    try:
        with open(SOUNDS_SIG_FILE, "w", encoding="utf-8") as f:
            json.dump(sig, f, ensure_ascii=False)
    except Exception:
        pass

def is_sounds_image_outdated(sounds: list) -> bool:
    if not sounds:
        return False
    saved_sig = load_sounds_signature()
    if not saved_sig:
        return True
    return get_sounds_signature(sounds).get("hash") != saved_sig.get("hash")

def check_and_reload_sounds_if_changed() -> bool:
    global SOUND_LIST
    spl_path = find_spl_path()
    if not spl_path:
        return False
    try:
        mtime = os.path.getmtime(spl_path)
    except OSError:
        return False

    if spl_path != LAST_SPL_PATH or mtime != LAST_SPL_MTIME:
        new_list = load_soundpad_library(generate_image=False)
        if new_list:
            SOUND_LIST = new_list
            return True
    return False

def ensure_fresh_sound_library(force_check: bool = False) -> bool:
    global LAST_SPL_CHECK_TIME
    now = time.time()
    if not force_check and (now - LAST_SPL_CHECK_TIME) < SPL_AUTO_RELOAD_INTERVAL:
        return False
    LAST_SPL_CHECK_TIME = now
    changed = check_and_reload_sounds_if_changed()
    if changed:
        print(f"[✓] Lista de sons atualizada automaticamente ({len(SOUND_LIST)} áudios).")
    return changed
# =========================================================================

def load_soundpad_library(generate_image: bool = True):
    global SOUND_BY_ID, LAST_SPL_PATH, LAST_SPL_MTIME
    spl_path = find_spl_path()
    if not spl_path:
        SOUND_BY_ID = {}
        return []

    print(f"[✓] Arquivo de lista encontrado: {spl_path}")

    try:
        mtime = os.path.getmtime(spl_path)
        with open(spl_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        matches = re.findall(r'<Sound\b([^>]+)/?>', content, re.IGNORECASE)
        raw_sounds = []
        seen_urls = set()

        for m in matches:
            attrs = {k: html.unescape(v) for k, _, v in re.findall(r'(\w+)=(["\'])(.*?)\2', m)}
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

            if dur_seconds <= 0:
                dur_seconds = 3.0

            library.append({
                "id": i + 1,
                "name": name,
                "norm_name": normalize_text(name),
                "duration": dur_seconds
            })

        SOUND_BY_ID = {s["id"]: s for s in library}
        LAST_SPL_PATH = spl_path
        LAST_SPL_MTIME = mtime

        # Checa/carrega os sons ANTES de checar ou gerar a imagem
        if generate_image and GENERATE_IMAGE_ON_STARTUP:
            generate_sounds_image(library, force=FORCE_REGENERATE_IMAGE)
        return library
    except Exception as e:
        print(f"[!] Erro ao carregar biblioteca: {e}")
        if generate_image:
            SOUND_BY_ID = {}
        return []

def generate_sounds_image(library=None, force: bool = False) -> str:
    """Gera imagem ampla (até 5000x5000) com colunas largas de 480px para nomes longos não cortarem."""
    global MEMES_IMAGE_URL
    if Image is None:
        print("[!] Pillow não instalado. Execute 'pip install pillow' para gerar a imagem.")
        return None

    sounds = library if library is not None else SOUND_LIST
    if not sounds:
        return None

    current_sig = get_sounds_signature(sounds)
    saved_sig = load_sounds_signature()
    sounds_changed = (saved_sig is None) or (current_sig.get("hash") != saved_sig.get("hash"))

    if not force and os.path.exists(SOUNDS_IMAGE_FILE) and not sounds_changed:
        print(f"[✓] Imagem já existente em disco e lista sem alterações: {SOUNDS_IMAGE_FILE} (pulando geração).")

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

    if sounds_changed and not force and os.path.exists(SOUNDS_IMAGE_FILE):
        if saved_sig and isinstance(saved_sig.get("count"), int):
            old_count = saved_sig["count"]
            if len(sounds) > old_count:
                print(f"[*] Novos áudios encontrados na lista ({old_count} -> {len(sounds)}). Atualizando imagem...")
            else:
                print(f"[*] Alteração encontrada na lista de sons ({old_count} -> {len(sounds)}). Atualizando imagem...")
        else:
            print("[*] Sincronizando imagem com a lista atual de sons...")

    total = len(sounds)
    padding = 35
    header_height = 95
    row_height = 40
    max_rows_per_col = (5000 - header_height - padding) // row_height

    if total > 500:
        cols = max(10, math.ceil(total / max_rows_per_col))
    elif total > 100:
        cols = math.ceil(total / 50)
    else:
        cols = 4

    rows = math.ceil(total / cols)
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

    id_digits = max(3, len(str(total)))
    id_offset = 68 if id_digits >= 4 else 56
    max_text_w = col_width - id_offset - 12

    for i, s in enumerate(sounds):
        c = i // rows
        r = i % rows
        x = padding + c * col_width
        y = header_height + r * row_height

        draw.text((x, y), f"#{s['id']:0{id_digits}d}", fill=(145, 71, 255), font=font_id)

        name_x = x + id_offset
        name_text = s["name"]

        if draw.textlength(name_text, font=font_body) > max_text_w:
            while name_text and draw.textlength(name_text + "...", font=font_body) > max_text_w:
                name_text = name_text[:-1]
            name_text += "..."

        draw.text((name_x, y), name_text, fill=(235, 235, 238), font=font_body)

    try:
        img.save(SOUNDS_IMAGE_FILE, "PNG")
        save_sounds_signature(current_sig)
        print(f"[✓] Imagem gerada ({img_w}x{img_h}px): {SOUNDS_IMAGE_FILE}")

        MEMES_IMAGE_URL = ""
        save_image_url("")

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
        r = HTTP_SESSION.head(url, headers=headers, timeout=6, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False

def upload_temporary_image(filepath: str) -> str:
    """Faz upload no serviço selecionado em IMAGE_HOST_SERVICE ('imgur', 'tmpfiles' ou 'puush')."""
    if not os.path.exists(filepath):
        return ""

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
                r = HTTP_SESSION.post(url_imgur, headers=img_headers, files=files, timeout=30)
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
                r = HTTP_SESSION.post(url_tmp, files=files, headers=headers, timeout=30)
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
                r = HTTP_SESSION.post(url_puush, data=data, files=files, headers=headers, timeout=30)
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
    safe_msg = message if len(message) <= 500 else (message[:497] + "...")
    url = "https://api.twitch.tv/helix/chat/messages"
    body = {
        "broadcaster_id": BROADCASTER_ID,
        "sender_id": BROADCASTER_ID,
        "message": safe_msg
    }
    try:
        r = _twitch_request("POST", url, json_data=body, timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data and data[0].get("message_id"):
                RECENT_BOT_MESSAGE_IDS.append(data[0]["message_id"])
        else:
            print(f"[!] Falha ao enviar chat ({r.status_code}): {r.text}")
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
                source_access = data.get("source_access")
                source_refresh = data.get("source_refresh")
                if source_access is not None and (
                    source_access != INITIAL_ACCESS_TOKEN or source_refresh != INITIAL_REFRESH_TOKEN
                ):
                    return
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
            json.dump({
                "access_token": access,
                "refresh_token": refresh,
                "source_access": INITIAL_ACCESS_TOKEN,
                "source_refresh": INITIAL_REFRESH_TOKEN
            }, f, indent=2)
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
        r = HTTP_SESSION.get(url_ttg, timeout=10)
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
            r = HTTP_SESSION.post(url_twitch, data=payload, timeout=10)
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

def get_broadcaster_id():
    load_token_cache()
    clean_token = get_clean_token()

    if not clean_token or clean_token == "SEU_ACCESS_TOKEN_AQUI":
        print("\n[!] ERRO: Preencha seu ACCESS_TOKEN no topo do arquivo ou em config.json!")
        print(" -> Gere um token em: https://twitchtokengenerator.com/\n")
        raise SystemExit(1)

    val_res = HTTP_SESSION.get(
        "https://id.twitch.tv/oauth2/validate",
        headers={"Authorization": f"OAuth {clean_token}"},
        timeout=5
    )

    if val_res.status_code != 200:
        print("\n[*] ACCESS_TOKEN expirou! Tentando renovar com o Refresh Token...")
        with TOKEN_LOCK:
            new_token = refresh_access_token()
        if new_token:
            clean_token = new_token
            val_res = HTTP_SESSION.get(
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
    if token_client_id and CLIENT_ID != token_client_id:
        CLIENT_ID = token_client_id

    return user_id, login

def subscribe_eventsub(broadcaster_id: str, session_id: str):
    url = "https://api.twitch.tv/helix/eventsub/subscriptions"

    body_points = {
        "type": "channel.channel_points_custom_reward_redemption.add",
        "version": "1",
        "condition": {"broadcaster_user_id": broadcaster_id},
        "transport": {"method": "websocket", "session_id": session_id}
    }
    r_points = _twitch_request("POST", url, json_data=body_points, timeout=5)
    if r_points.status_code in (200, 202):
        print("[✓] Escuta de Pontos de Canal ativa!")
    else:
        print(f"[!] Erro ao registrar escuta de pontos ({r_points.status_code}): {r_points.text}")

    body_chat = {
        "type": "channel.chat.message",
        "version": "1",
        "condition": {
            "broadcaster_user_id": broadcaster_id,
            "user_id": broadcaster_id
        },
        "transport": {"method": "websocket", "session_id": session_id}
    }
    r_chat = _twitch_request("POST", url, json_data=body_chat, timeout=5)
    if r_chat.status_code in (200, 202):
        print("[✓] Escuta de Comandos de Chat ativa!")
    else:
        print(f"[!] Erro ao registrar escuta do chat ({r_chat.status_code}): {r_chat.text}")

async def handle_memes_image_command(chatter: str, cmd: str, is_mod_or_host: bool):
    """Checa os sons antes da imagem; !gerarimagem força nova geração e !imagem/!img consultam/atualizam se necessário."""
    global MEMES_IMAGE_URL
    async with IMAGE_OP_LOCK:
        await asyncio.to_thread(ensure_fresh_sound_library, True)
        sounds_outdated = await asyncio.to_thread(is_sounds_image_outdated, SOUND_LIST)

        if is_mod_or_host and cmd in ("!gerarimagem", "!generateimage", "!gimg", "!genimg"):
            img_path = await asyncio.to_thread(generate_sounds_image, SOUND_LIST, True)
            if img_path:
                msg_url = f": {MEMES_IMAGE_URL}" if MEMES_IMAGE_URL else "!"
                await send_twitch_chat(f"🖼️ @{chatter} Imagem atualizada{msg_url}", force=True)
                print(f"[MOD] @{chatter} gerou a imagem de sons.")
        else:
            if sounds_outdated and (GENERATE_IMAGE_ON_STARTUP or os.path.exists(SOUNDS_IMAGE_FILE)):
                await asyncio.to_thread(generate_sounds_image, SOUND_LIST, True)
            else:
                if not MEMES_IMAGE_URL and os.path.exists(SOUNDS_URL_FILE):
                    try:
                        with open(SOUNDS_URL_FILE, "r", encoding="utf-8") as f:
                            MEMES_IMAGE_URL = f.read().strip()
                    except Exception:
                        MEMES_IMAGE_URL = ""

                alive = bool(MEMES_IMAGE_URL) and await asyncio.to_thread(check_image_url_alive, MEMES_IMAGE_URL)
                if not alive:
                    if not os.path.exists(SOUNDS_IMAGE_FILE):
                        await asyncio.to_thread(generate_sounds_image, SOUND_LIST, True)
                    else:
                        new_url = await asyncio.to_thread(upload_temporary_image, SOUNDS_IMAGE_FILE)
                        if new_url:
                            MEMES_IMAGE_URL = new_url
                            await asyncio.to_thread(save_image_url, new_url)

            if MEMES_IMAGE_URL:
                msg_extra = " (Salve se quiser, o link expira em 1 hora!)" if IMAGE_HOST_SERVICE.lower().strip() == "tmpfiles" else ""
                await send_twitch_chat(f"🖼️ @{chatter} Lista de memes: {MEMES_IMAGE_URL}{msg_extra}", force=True)
            else:
                await send_twitch_chat(f"⚠️ @{chatter} Não foi possível obter o link da imagem agora. Tente novamente em instantes!", force=True)

async def listen_twitch():
    global BROADCASTER_ID, BROADCASTER_NAME, SOUND_LIST, ENABLE_CHAT_ANNOUNCEMENTS
    global USER_THEMES, IMAGE_OP_LOCK, PAUSE_EVENT, QUEUE_PAUSED, CURRENT_ROULETTE_CHANCE

    IMAGE_OP_LOCK = asyncio.Lock()
    PAUSE_EVENT = asyncio.Event()
    PAUSE_EVENT.set()

    user_id, user_name = await asyncio.to_thread(get_broadcaster_id)
    BROADCASTER_ID = user_id
    BROADCASTER_NAME = user_name
    USER_THEMES = await asyncio.to_thread(load_user_themes)

    queue_task = asyncio.create_task(sound_queue_worker())
    await asyncio.to_thread(update_obs_text, "")
    await asyncio.to_thread(ensure_managed_rewards, user_id)
    await asyncio.to_thread(load_moderators, user_id)

    print("=" * 60)
    print(f"[✓] Canal Conectado: {user_name} (ID: {user_id})")
    print(f"[✓] Soundpad: {len(SOUND_LIST)} sons carregados na memória!")
    print(f"[✓] Fila de reprodução ativa (Delay: {QUEUE_DELAY_SECONDS}s | Max: {MAX_QUEUE_SIZE})")
    print(f"[✓] Roleta Russa Progressiva ativa (Base: {ROULETTE_TRAP_CHANCE}% | +{ROULETTE_PROGRESSIVE_STEP}%)")
    print(f"[✓] Cooldown individual ativo ({USER_COOLDOWN_SECONDS}s)")
    print(f"[✓] Arquivo OBS pronto em: {OBS_TEXT_FILE}")
    print("=" * 60)

    normalized_rewards = {normalize_text(k): v for k, v in REWARDS_MAP.items()}
    normalized_categories = {normalize_text(k): v for k, v in SOUND_CATEGORIES.items()}
    ws_url = "wss://eventsub.wss.twitch.tv/ws"
    announced_online = False

    # ==================== COMANDO INTERNO DE ENCERRAMENTO ====================
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    active_ws = None
    reminder_task = None

    async def _safe_close_ws(sock):
        try:
            await sock.close()
        except Exception:
            pass

    def _request_shutdown():
        if not shutdown_event.is_set():
            print("\n[*] Comando de encerramento recebido no terminal. Desligando bot...")
            shutdown_event.set()
            if active_ws is not None:
                asyncio.create_task(_safe_close_ws(active_ws))

    def _terminal_command_listener():
        if not sys.stdin or sys.stdin.closed:
            return
        exit_cmds = {"sair", "exit", "quit", "fechar", "parar", "stop", "/exit", "!sair"}
        while not shutdown_event.is_set():
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd_in = line.strip().lower()
                if cmd_in in exit_cmds:
                    loop.call_soon_threadsafe(_request_shutdown)
                    break
                elif cmd_in in ("help", "ajuda", "?"):
                    print("[*] Comandos do terminal: sair, exit, quit, fechar, parar, stop")
            except Exception:
                break

    async def _terminal_reminder_loop():
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=300)
                break
            except asyncio.TimeoutError:
                if not shutdown_event.is_set():
                    print("[*] LEMBRETE: No Terminal, digite 'sair' (ou 'exit') e aperte Enter para encerrar.")

    threading.Thread(target=_terminal_command_listener, daemon=True).start()
    # =========================================================================

    try:
        while not shutdown_event.is_set():
            ws = None
            keepalive_timeout = 25
            try:
                print("[*] Conectando ao WebSocket da Twitch...")
                ws = await websockets.connect(ws_url)
                active_ws = ws

                while not shutdown_event.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=keepalive_timeout)
                    except asyncio.TimeoutError:
                        raise ConnectionError("Keepalive timeout da Twitch EventSub excedido.")

                    data = json.loads(msg)
                    metadata = data.get("metadata", {})
                    msg_type = metadata.get("message_type")
                    sub_type = metadata.get("subscription_type")

                    if msg_type == "session_welcome":
                        session_info = data.get("payload", {}).get("session", {})
                        session_id = session_info.get("id")
                        keepalive_timeout = (session_info.get("keepalive_timeout_seconds") or 10) + 15
                        await asyncio.to_thread(subscribe_eventsub, user_id, session_id)
                        print("[*] Bot pronto e aguardando interações!")

                        # ==================== AVISO DE BOT ONLINE NO CHAT ====================
                        if ANNOUNCE_BOT_ONLINE and not announced_online:
                            announced_online = True
                            await send_twitch_chat(
                                f"🤖 Bot Soundpad online! ({len(SOUND_LIST)} áudios carregados) • Use !comandos",
                                force=True
                            )
                        # =====================================================================

                        print("[*] LEMBRETE: No Terminal, digite 'sair' (ou 'exit') e aperte Enter para encerrar.")
                        if reminder_task is None or reminder_task.done():
                            reminder_task = asyncio.create_task(_terminal_reminder_loop())

                    elif msg_type == "notification":
                        event = data.get("payload", {}).get("event", {})

                        # ========================================================
                        # 1. COMANDOS DE CHAT (1 variante PT-BR e 1 EN-US por ação)
                        # ========================================================
                        if sub_type == "channel.chat.message":
                            if event.get("message_id") in RECENT_BOT_MESSAGE_IDS:
                                continue

                            chat_msg = event.get("message", {}).get("text", "").strip()
                            chatter = event.get("chatter_user_name", "")
                            chatter_id = event.get("chatter_user_id", "")
                            badges = event.get("badges", [])

                            is_mod_badge = any(b.get("set_id") in ("moderator", "broadcaster") for b in badges)
                            if is_mod_badge and chatter_id:
                                KNOWN_MOD_IDS.add(chatter_id)

                            is_mod_or_host = (chatter.lower() == BROADCASTER_NAME.lower()) or is_mod_badge
                            is_vip_or_sub = is_mod_or_host or any(b.get("set_id") in ("vip", "subscriber") for b in badges)

                            if is_vip_or_sub and chatter.lower() not in PLAYED_ENTRANCE_USERS:
                                PLAYED_ENTRANCE_USERS.add(chatter.lower())
                                if chatter.lower() in USER_THEMES:
                                    theme_id = USER_THEMES[chatter.lower()]
                                    theme_sound = SOUND_BY_ID.get(theme_id)
                                    if theme_sound:
                                        await enqueue_sound({
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

                                        commit_user_cooldown(chatter)
                                        await enqueue_sound({
                                            "id": chosen["id"],
                                            "name": chosen["name"],
                                            "duration": chosen.get("duration", 3.0),
                                            "user": chatter,
                                            "show_popup": True,
                                            "is_search": True,
                                            "query": pending["query"],
                                            "redemption_info": (user_id, pending["reward_id"], pending["redemption_id"])
                                        })
                                        print(f" -> [Fila] Escolha de @{chatter} -> #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")
                                        continue

                            if not chat_msg:
                                continue

                            cmd_parts = chat_msg.split()
                            cmd = cmd_parts[0].lower()

                            if cmd in ("!settema", "!settheme", "!tema", "!theme"):
                                if is_vip_or_sub:
                                    if len(cmd_parts) >= 2 and cmd_parts[1].lstrip("#").isdigit():
                                        chosen_id = int(cmd_parts[1].lstrip("#"))
                                        sound_match = SOUND_BY_ID.get(chosen_id)
                                        if sound_match:
                                            USER_THEMES[chatter.lower()] = chosen_id
                                            await asyncio.to_thread(save_user_themes, dict(USER_THEMES))
                                            await send_twitch_chat(f"✨ @{chatter} Seu som de entrada foi definido como: \"{sound_match['name']}\" (ID #{chosen_id})!")
                                        else:
                                            await send_twitch_chat(f"⚠️ @{chatter} Som ID #{chosen_id} não encontrado na lista!")
                                    else:
                                        await send_twitch_chat(f"⚠️ @{chatter} Use: !settema <ID> (ex: !settema 125)")
                                else:
                                    await send_twitch_chat(f"⚠️ @{chatter} Apenas VIPs, Subs e Moderadores podem ter som de entrada!")

                            elif cmd in ("!meusom", "!mysound", "!msom", "!ms"):
                                if chatter.lower() in USER_THEMES:
                                    t_id = USER_THEMES[chatter.lower()]
                                    t_sound = SOUND_BY_ID.get(t_id)
                                    name_label = f"\"{t_sound['name']}\" (ID #{t_id})" if t_sound else f"ID #{t_id}"
                                    await send_twitch_chat(f"🎵 @{chatter} Seu som de entrada atual é: {name_label}")
                                else:
                                    await send_twitch_chat(f"⚠️ @{chatter} Você ainda não configurou seu som de entrada! Use !settema <ID>")

                            elif cmd in ("!limpartema", "!cleartheme", "!ltema", "!ctheme"):
                                if chatter.lower() in USER_THEMES:
                                    del USER_THEMES[chatter.lower()]
                                    await asyncio.to_thread(save_user_themes, dict(USER_THEMES))
                                    await send_twitch_chat(f"🗑️ @{chatter} Seu som de entrada foi removido!", force=True)
                                else:
                                    await send_twitch_chat(f"⚠️ @{chatter} Você ainda não possui som de entrada configurado.", force=True)

                            elif cmd in ("!categorias", "!categories", "!cats"):
                                cat_list = ", ".join(SOUND_CATEGORIES.keys())
                                await send_twitch_chat(f"📂 Categorias disponíveis: {cat_list} (Resgate \"{CATEGORY_REWARD_NAME}\" nos Pontos do Canal!)", force=True)

                            elif cmd in ("!categoria", "!category", "!cat"):
                                if not is_mod_or_host:
                                    await send_twitch_chat(
                                        f"🎟️ @{chatter}, para sortear por categoria use o resgate \"{CATEGORY_REWARD_NAME}\" nos Pontos do Canal! (Veja opções com !cats)",
                                        force=True
                                    )
                                    continue

                                parts = chat_msg.split(maxsplit=1)
                                if len(parts) >= 2:
                                    cat_key = normalize_text(parts[1])
                                    if cat_key in normalized_categories:
                                        await asyncio.to_thread(ensure_fresh_sound_library)
                                        keyword = normalize_text(normalized_categories[cat_key])
                                        matched_sounds = [s for s in SOUND_LIST if keyword in s["norm_name"]]
                                        if matched_sounds:
                                            chosen = pick_non_repeating_sound(matched_sounds)
                                            await enqueue_sound({
                                                "id": chosen["id"],
                                                "name": chosen["name"],
                                                "duration": chosen.get("duration", 3.0),
                                                "user": chatter,
                                                "show_popup": True,
                                                "chat_message": f"📂 @{chatter} sorteou na categoria [{cat_key}]: \"{chosen['name']}\" (ID #{chosen['id']})",
                                                "is_search": False
                                            })
                                            print(f" -> [Categoria MOD] @{chatter} sorteou '{cat_key}' -> #{chosen['id']} ('{chosen['name']}')")
                                        else:
                                            await send_twitch_chat(f"⚠️ Nenhum som encontrado para a categoria '{cat_key}'!", force=True)
                                    else:
                                        cats = ", ".join(SOUND_CATEGORIES.keys())
                                        await send_twitch_chat(f"⚠️ Categoria desconhecida! Opções: {cats}", force=True)
                                else:
                                    cats = ", ".join(SOUND_CATEGORIES.keys())
                                    await send_twitch_chat(f"⚠️ Use: !cat <nome> (Opções: {cats})", force=True)

                            elif cmd in ("!som", "!ultimosom", "!usom", "!sound", "!lastsound", "!ls"):
                                if LAST_PLAYED_SOUND:
                                    await send_twitch_chat(f"🔊 Último som tocado: \"{LAST_PLAYED_SOUND['name']}\" (ID #{LAST_PLAYED_SOUND['id']}) — pedido por @{LAST_PLAYED_SOUND['user']}")
                                else:
                                    await send_twitch_chat("⚠️ Nenhum som foi reproduzido ainda nesta sessão!")

                            # ==================== FILA DE ÁUDIO (!fila / !pausar) ====================
                            elif cmd in ("!fila", "!queue", "!q"):
                                status_label = "⏸️ PAUSADA" if QUEUE_PAUSED else "▶️ Ativa"
                                total_items = len(QUEUED_ITEMS)
                                rem_current = max(0.0, CURRENT_PLAY_END_TIME - time.time()) if CURRENT_PLAY_ITEM else 0.0
                                rem_queue = sum(it.get("duration", 3.0) + QUEUE_DELAY_SECONDS for it in QUEUED_ITEMS)
                                total_secs = int(round(rem_current + rem_queue))

                                if not CURRENT_PLAY_ITEM and total_items == 0:
                                    await send_twitch_chat(f"🎶 Fila vazia! (Status: {status_label})", force=True)
                                else:
                                    preview = " | ".join([f"{idx+1}. {it['name'][:30]} (@{it['user']})" for idx, it in enumerate(QUEUED_ITEMS[:4])])
                                    extra = f" (+{total_items - 4} na espera)" if total_items > 4 else ""
                                    now_txt = f"Tocando: {CURRENT_PLAY_ITEM['name'][:30]}" if CURRENT_PLAY_ITEM else "Aguardando"
                                    queue_txt = f" • Próximos: {preview}{extra}" if preview else ""
                                    await send_twitch_chat(f"🎶 [{status_label}] {now_txt} ({total_items} na fila • ~{total_secs}s){queue_txt}", force=True)

                            elif cmd in ("!pausar", "!pause", "!retomar", "!resume"):
                                if is_mod_or_host:
                                    QUEUE_PAUSED = not QUEUE_PAUSED
                                    if QUEUE_PAUSED:
                                        PAUSE_EVENT.clear()
                                        await send_twitch_chat(f"⏸️ @{chatter} pausou a fila de sons! (Use !pausar para retomar)", force=True)
                                        print(f"[MOD] @{chatter} pausou a fila.")
                                    else:
                                        PAUSE_EVENT.set()
                                        await send_twitch_chat(f"▶️ @{chatter} retomou a fila de sons!", force=True)
                                        print(f"[MOD] @{chatter} retomou a fila.")
                            # =========================================================================

                            elif cmd in ("!sounds", "!imagem", "!image", "!img", "!gerarimagem", "!generateimage", "!gimg", "!genimg"):
                                asyncio.create_task(handle_memes_image_command(chatter, cmd, is_mod_or_host))

                            elif cmd in ("!pular", "!skip", "!pul", "!sk"):
                                if is_mod_or_host:
                                    skip_current_sound()
                                    await send_twitch_chat(f"⏭️ @{chatter} pulou para o próximo som da fila!")
                                    print(f"[MOD] @{chatter} pulou o som atual.")

                            elif cmd in ("!limpar", "!clear", "!lmp", "!cls"):
                                if is_mod_or_host:
                                    clear_queue_and_stop()
                                    await send_twitch_chat(f"⏹️ @{chatter} limpou toda a fila de sons!")
                                    print(f"[MOD] @{chatter} limpou a fila inteira.")

                            elif cmd in ("!recarregar", "!reload", "!rec", "!rel"):
                                if is_mod_or_host:
                                    SOUND_LIST = await asyncio.to_thread(load_soundpad_library, False)
                                    async with IMAGE_OP_LOCK:
                                        await asyncio.to_thread(generate_sounds_image, SOUND_LIST, True)
                                    await send_twitch_chat(f"🔄 @{chatter} recarregou o Soundpad: {len(SOUND_LIST)} sons e imagem atualizada!")
                                    print(f"[MOD] @{chatter} recarregou a biblioteca ({len(SOUND_LIST)} sons).")

                            elif cmd in ("!chat", "!togglechat", "!tc"):
                                if is_mod_or_host:
                                    ENABLE_CHAT_ANNOUNCEMENTS = not ENABLE_CHAT_ANNOUNCEMENTS
                                    estado = "ATIVADOS" if ENABLE_CHAT_ANNOUNCEMENTS else "DESATIVADOS"
                                    await send_twitch_chat(f"📢 Avisos de som no chat: {estado}!", force=True)
                                    print(f"[MOD] @{chatter} alterou avisos de chat para: {estado}.")

                            # ==================== LISTAR COMANDOS (PT-BR: !comandos/!cmd | EN-US: !commands/!cmds) ====================
                            elif cmd in ("!comandos", "!commands", "!cmd", "!cmds"):
                                if cmd in ("!commands", "!cmds"):
                                    await send_twitch_chat(
                                        "📋 Everyone: !commands (!cmds), !sounds, !image (!img), !categories (!cats), !sound (!ls), !queue (!q), !settheme (!theme) <ID> [VIP/Sub], !mysound (!ms), !cleartheme (!ctheme) | "
                                        "🛡️ Mod/Streamer: !cat <name>, !skip (!sk), !pause, !clear (!cls), !generateimage (!genimg), !reload (!rel), !chat (!tc)",
                                        force=True
                                    )
                                else:
                                    await send_twitch_chat(
                                        "📋 Todos: !comandos (!cmd), !imagem (!img), !categorias (!cats), !som (!usom), !fila (!q), !settema (!tema) <ID> [VIP/Sub], !meusom (!msom), !limpartema (!ltema) | "
                                        "🛡️ Mod/Streamer: !cat <nome>, !pular (!pul), !pausar, !limpar (!lmp), !gerarimagem (!gimg), !recarregar (!rec), !chat (!tc)",
                                        force=True
                                    )
                            # =========================================================================================================

                        # ========================================================
                        # 2. RESGATES DE PONTOS DE CANAL
                        # ========================================================
                        elif sub_type == "channel.channel_points_custom_reward_redemption.add":
                            redemption_id = event["id"]
                            reward_id = event["reward"]["id"]
                            reward_title = event["reward"]["title"]
                            user = event["user_name"]
                            viewer_id = event.get("user_id", "")
                            user_input = event.get("user_input", "").strip()
                            clean_title = normalize_text(reward_title)

                            print(f"\n[RESGATE] '{user}' resgatou: '{reward_title}'")

                            if clean_title == normalize_text(STOP_REWARD_NAME):
                                playing_now = await asyncio.to_thread(is_soundpad_playing)
                                is_active = playing_now or (CURRENT_PLAY_TASK and not CURRENT_PLAY_TASK.done())
                                if not is_active:
                                    await send_twitch_chat(f"⚠️ @{user}, nenhum áudio está tocando agora! Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                skip_current_sound()
                                asyncio.create_task(fulfill_redemption(user_id, reward_id, redemption_id))
                                await send_twitch_chat(f"⏹️ @{user} parou o áudio atual!")
                                continue

                            is_bot_reward = (
                                clean_title in (
                                    normalize_text(ROULETTE_REWARD_NAME),
                                    normalize_text(RANDOM_REWARD_NAME),
                                    normalize_text(SEARCH_REWARD_NAME),
                                    normalize_text(CATEGORY_REWARD_NAME)
                                )
                                or clean_title in normalized_rewards
                            )
                            if not is_bot_reward:
                                continue

                            can_redeem, remaining = check_user_cooldown(user)
                            if not can_redeem:
                                await send_twitch_chat(f"⏳ @{user}, aguarde {remaining}s para resgatar! Seus pontos foram devolvidos.", force=True)
                                await refund_redemption(user_id, reward_id, redemption_id)
                                continue

                            if not await asyncio.to_thread(is_soundpad_connected):
                                await send_twitch_chat(f"⚠️ @{user}, Soundpad offline no momento! Seus pontos foram devolvidos.", force=True)
                                await refund_redemption(user_id, reward_id, redemption_id)
                                continue

                            if MAX_QUEUE_SIZE > 0 and SOUND_QUEUE.qsize() >= MAX_QUEUE_SIZE:
                                await send_twitch_chat(f"⚠️ @{user}, a fila está cheia ({MAX_QUEUE_SIZE} áudios)! Tente em instantes — seus pontos foram devolvidos.", force=True)
                                await refund_redemption(user_id, reward_id, redemption_id)
                                continue

                            await asyncio.to_thread(ensure_fresh_sound_library)

                            if clean_title == normalize_text(CATEGORY_REWARD_NAME):
                                if not SOUND_LIST:
                                    await send_twitch_chat(f"⚠️ @{user}, Soundpad vazio! Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                cat_key = normalize_text(user_input)
                                if not cat_key or cat_key not in normalized_categories:
                                    cats = ", ".join(SOUND_CATEGORIES.keys())
                                    await send_twitch_chat(f"⚠️ @{user}, categoria \"{user_input}\" inválida! Opções: {cats} • Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                keyword = normalize_text(normalized_categories[cat_key])
                                matched_sounds = [s for s in SOUND_LIST if keyword in s["norm_name"]]
                                if not matched_sounds:
                                    await send_twitch_chat(f"⚠️ @{user}, nenhum som encontrado na categoria '{cat_key}'! Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                commit_user_cooldown(user)
                                chosen = pick_non_repeating_sound(matched_sounds)
                                await enqueue_sound({
                                    "id": chosen["id"],
                                    "name": chosen["name"],
                                    "duration": chosen.get("duration", 3.0),
                                    "user": user,
                                    "show_popup": True,
                                    "chat_message": f"📂 @{user} sorteou na categoria [{cat_key}]: \"{chosen['name']}\" (ID #{chosen['id']})",
                                    "is_search": False,
                                    "redemption_info": (user_id, reward_id, redemption_id)
                                })
                                print(f" -> [Fila] Categoria '{cat_key}' -> #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")

                            elif clean_title == normalize_text(ROULETTE_REWARD_NAME):
                                if not SOUND_LIST:
                                    await send_twitch_chat(f"⚠️ @{user}, Soundpad vazio! Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                commit_user_cooldown(user)
                                hit_chance = CURRENT_ROULETTE_CHANCE
                                is_trap = random.randint(1, 100) <= hit_chance

                                if is_trap:
                                    CURRENT_ROULETTE_CHANCE = ROULETTE_TRAP_CHANCE
                                    chosen_trap_id = random.choice(ROULETTE_TRAP_SOUND_IDS) if ROULETTE_TRAP_SOUND_IDS else 14
                                    trap_sound = SOUND_BY_ID.get(chosen_trap_id)
                                    trap_id = trap_sound["id"] if trap_sound else chosen_trap_id
                                    trap_name = trap_sound["name"] if trap_sound else "Trap Troll"
                                    trap_dur = trap_sound.get("duration", 3.0) if trap_sound else 3.0

                                    is_immune = (user.lower() == BROADCASTER_NAME.lower()) or (viewer_id == user_id) or (viewer_id in KNOWN_MOD_IDS)
                                    if is_immune:
                                        msg_chat = f"💀 @{user} caiu na TRAP ({hit_chance}%): \"{trap_name}\" (ID #{trap_id})! (Streamer/Mod é imune a timeout!) • 🔄 Chance resetada para {ROULETTE_TRAP_CHANCE}%."
                                        apply_timeout = False
                                    elif ROULETTE_TIMEOUT_SECONDS > 0:
                                        msg_chat = f"💀 @{user} deu azar na Roleta Russa ({hit_chance}%), caiu na TRAP: \"{trap_name}\" (ID #{trap_id}) e tomou {ROULETTE_TIMEOUT_SECONDS}s de timeout! • 🔄 Chance resetada para {ROULETTE_TRAP_CHANCE}%."
                                        apply_timeout = True
                                    else:
                                        msg_chat = f"💀 @{user} deu azar na Roleta Russa ({hit_chance}%) e caiu na TRAP: \"{trap_name}\" (ID #{trap_id})! • 🔄 Chance resetada para {ROULETTE_TRAP_CHANCE}%."
                                        apply_timeout = False

                                    await enqueue_sound({
                                        "id": trap_id,
                                        "name": f"💀 TRAP: {trap_name}",
                                        "duration": trap_dur,
                                        "user": user,
                                        "show_popup": True,
                                        "chat_message": msg_chat,
                                        "timeout_user_id": viewer_id if apply_timeout else None,
                                        "timeout_duration": ROULETTE_TIMEOUT_SECONDS,
                                        "is_search": False,
                                        "redemption_info": (user_id, reward_id, redemption_id)
                                    })
                                    print(f" -> [Fila] Adicionado Roleta (TRAP {hit_chance}%) #{trap_id} ('{trap_name}') [{trap_dur}s]")
                                else:
                                    CURRENT_ROULETTE_CHANCE = min(100, CURRENT_ROULETTE_CHANCE + ROULETTE_PROGRESSIVE_STEP)
                                    chosen = pick_non_repeating_sound(SOUND_LIST)
                                    await enqueue_sound({
                                        "id": chosen["id"],
                                        "name": chosen["name"],
                                        "duration": chosen.get("duration", 3.0),
                                        "user": user,
                                        "show_popup": True,
                                        "chat_message": f"🎰 @{user} sobreviveu à Roleta ({hit_chance}%) e tocou: \"{chosen['name']}\" (ID #{chosen['id']}) • ⚠️ Próxima TRAP: {CURRENT_ROULETTE_CHANCE}%!",
                                        "is_search": False,
                                        "redemption_info": (user_id, reward_id, redemption_id)
                                    })
                                    print(f" -> [Fila] Adicionado Roleta (Sobreviveu {hit_chance}% -> {CURRENT_ROULETTE_CHANCE}%) #{chosen['id']} ('{chosen['name']}')")

                            elif clean_title == normalize_text(RANDOM_REWARD_NAME):
                                if not SOUND_LIST:
                                    await send_twitch_chat(f"⚠️ @{user}, Soundpad vazio! Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                commit_user_cooldown(user)
                                chosen = pick_non_repeating_sound(SOUND_LIST)
                                await enqueue_sound({
                                    "id": chosen["id"],
                                    "name": chosen["name"],
                                    "duration": chosen.get("duration", 3.0),
                                    "user": user,
                                    "show_popup": True,
                                    "is_search": False,
                                    "redemption_info": (user_id, reward_id, redemption_id)
                                })
                                print(f" -> [Fila] Adicionado Aleatório #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")

                            elif clean_title == normalize_text(SEARCH_REWARD_NAME):
                                if not user_input:
                                    await send_twitch_chat(f"⚠️ @{user}, digite uma palavra ou ID para buscar o meme! Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                raw_id = user_input.lstrip("#").strip()
                                if raw_id.isdigit():
                                    target_id = int(raw_id)
                                    sound_by_id = SOUND_BY_ID.get(target_id)
                                    if sound_by_id:
                                        commit_user_cooldown(user)
                                        await enqueue_sound({
                                            "id": sound_by_id["id"],
                                            "name": sound_by_id["name"],
                                            "duration": sound_by_id.get("duration", 3.0),
                                            "user": user,
                                            "show_popup": True,
                                            "is_search": True,
                                            "query": f"#{target_id}",
                                            "redemption_info": (user_id, reward_id, redemption_id)
                                        })
                                        print(f" -> [Fila] Busca por ID #{target_id} -> '{sound_by_id['name']}' [{sound_by_id.get('duration', 3.0)}s]")
                                        continue
                                    else:
                                        await send_twitch_chat(f"⚠️ @{user}, nenhum som com o ID #{target_id}! Seus pontos foram devolvidos.", force=True)
                                        await refund_redemption(user_id, reward_id, redemption_id)
                                        continue

                                query = normalize_text(user_input)
                                matches = [s for s in SOUND_LIST if query in s["norm_name"]]

                                if not matches:
                                    suggestions = await asyncio.to_thread(find_fuzzy_suggestions, query)
                                    sug_txt = f" Você quis dizer: {', '.join(suggestions)}?" if suggestions else ""
                                    await send_twitch_chat(f"⚠️ @{user}, nenhum áudio com \"{user_input}\"!{sug_txt} Seus pontos foram devolvidos.", force=True)
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                if len(matches) == 1:
                                    commit_user_cooldown(user)
                                    chosen = matches[0]
                                    await enqueue_sound({
                                        "id": chosen["id"],
                                        "name": chosen["name"],
                                        "duration": chosen.get("duration", 3.0),
                                        "user": user,
                                        "show_popup": True,
                                        "is_search": True,
                                        "query": user_input,
                                        "redemption_info": (user_id, reward_id, redemption_id)
                                    })
                                    print(f" -> [Fila] Busca por '{user_input}' (único) -> #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")
                                else:
                                    options = matches[:5]
                                    user_key = user.lower()

                                    if user_key in PENDING_SEARCH_CHOICES:
                                        old_pending = PENDING_SEARCH_CHOICES.pop(user_key)
                                        old_pending["timer_task"].cancel()
                                        await refund_redemption(user_id, old_pending["reward_id"], old_pending["redemption_id"])

                                    async def search_choice_timeout(u_key, u_name, b_id, r_id, red_id):
                                        try:
                                            await asyncio.sleep(30)
                                            if u_key in PENDING_SEARCH_CHOICES and PENDING_SEARCH_CHOICES[u_key]["redemption_id"] == red_id:
                                                del PENDING_SEARCH_CHOICES[u_key]
                                                await refund_redemption(b_id, r_id, red_id)
                                                await send_twitch_chat(f"⏳ @{u_name}, tempo esgotado para escolher o som! Seus pontos foram devolvidos.", force=True)
                                        except asyncio.CancelledError:
                                            pass

                                    timeout_task = asyncio.create_task(search_choice_timeout(user_key, user, user_id, reward_id, redemption_id))
                                    PENDING_SEARCH_CHOICES[user_key] = {
                                        "options": options,
                                        "query": user_input,
                                        "reward_id": reward_id,
                                        "redemption_id": redemption_id,
                                        "timer_task": timeout_task
                                    }

                                    opts_text = " | ".join([f"[{i+1}] {s['name'][:65]}" for i, s in enumerate(options)])
                                    await send_twitch_chat(f"🔎 @{user}, escolha digitando o número (1 a {len(options)}) no chat em 30s: {opts_text}", force=True)
                                    print(f" -> [Busca] @{user} recebeu {len(options)} opções para '{user_input}'. Aguardando escolha...")

                            elif clean_title in normalized_rewards:
                                commit_user_cooldown(user)
                                sound_id = normalized_rewards[clean_title]
                                sound_info = SOUND_BY_ID.get(sound_id)
                                dur = sound_info.get("duration", 3.0) if sound_info else 3.0
                                await enqueue_sound({
                                    "id": sound_id,
                                    "name": reward_title,
                                    "duration": dur,
                                    "user": user,
                                    "show_popup": False,
                                    "redemption_info": (user_id, reward_id, redemption_id)
                                })
                                print(f" -> [Fila] Som Fixo #{sound_id} ('{reward_title}') adicionado silenciosamente [{dur}s].")

                    elif msg_type == "session_reconnect":
                        reconnect_url = data.get("payload", {}).get("session", {}).get("reconnect_url")
                        if reconnect_url:
                            print("[*] Twitch solicitou migração de sessão (session_reconnect). Transferindo conexão...")
                            new_ws = await websockets.connect(reconnect_url)
                            welcome_raw = await asyncio.wait_for(new_ws.recv(), timeout=15)
                            welcome_data = json.loads(welcome_raw)
                            session_info = welcome_data.get("payload", {}).get("session", {})
                            keepalive_timeout = (session_info.get("keepalive_timeout_seconds") or 10) + 15
                            await ws.close()
                            ws = new_ws
                            active_ws = ws
                            ws_url = "wss://eventsub.wss.twitch.tv/ws"
                            print("[✓] Sessão migrada sem perda de inscrições!")

                    elif msg_type == "session_keepalive":
                        pass

            except Exception as e:
                if shutdown_event.is_set():
                    break
                print(f"[!] Conexão caiu ({e}). Reconectando em 5 segundos...")
                ws_url = "wss://eventsub.wss.twitch.tv/ws"
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=5)
                    break
                except asyncio.TimeoutError:
                    pass
            finally:
                active_ws = None
                if ws is not None:
                    try:
                        await ws.close()
                    except Exception:
                        pass
    finally:
        queue_task.cancel()
        if reminder_task is not None:
            reminder_task.cancel()
        for pending in list(PENDING_SEARCH_CHOICES.values()):
            pending["timer_task"].cancel()
        PENDING_SEARCH_CHOICES.clear()

if __name__ == "__main__":
    update_obs_text("")
    SOUND_LIST = load_soundpad_library()
    try:
        asyncio.run(listen_twitch())
    except KeyboardInterrupt:
        print("\n[Encerrado pelo usuário]")
    finally:
        update_obs_text("")
        HTTP_SESSION.close()
        logging.shutdown()