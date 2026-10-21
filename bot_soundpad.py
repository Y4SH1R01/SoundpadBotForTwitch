import asyncio
import json
import os
import random
import re
import subprocess
import time
import urllib.parse
import requests
import websockets

# ================= CONFIGURAÇÃO =================
CLIENT_ID = "SEU_CLIENT_ID_AQUI"
ACCESS_TOKEN = "SEU_ACCESS_TOKEN_AQUI"

# Nomes dos Resgates de Pontos do Canal na Twitch
RANDOM_REWARD_NAME = "Som Aleatório"
SEARCH_REWARD_NAME = "Buscar Meme"
SEARCH_REWARD_COST = 200         # Custo em pontos da busca (criada via API)
STOP_REWARD_NAME = "Parar Som"   # Interrompe o áudio atual (sem apagar a fila restante)
STOP_REWARD_COST = 1000          # Custo em pontos para parar o áudio atual (criado via API)

# Caminho manual para a sua lista de sons (RECOMENDO BOTAR O SEU .spl AQUI, Caso contrário deixe "" para auto-detectar pelo AppData (não recomendável))
CUSTOM_SPL_PATH = ""

# Sons específicos (tocam direto sem poluir o chat/OBS)
REWARDS_MAP = {
    "Exemplo Som 1": 1,
    "Exemplo Som 2": 2,
    "Exemplo Som 3": 3,
}

# Configurações de Fila e Cooldown
USER_COOLDOWN_SECONDS = 0       # Tempo em segundos de cooldown por viewer (0 = desativado, AJUSTE!)
QUEUE_DELAY_SECONDS = 3         # Intervalo de segurança entre um som e outro na fila
ENABLE_CHAT_ANNOUNCEMENTS = True # True = avisa no chat / False = apenas pop-up no OBS (Comando !chat modifica isso)

# Caminhos
PIPE_PATH = r"\\.\pipe\sp_remote_control"
OBS_TEXT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "obs_tocando_agora.txt")
# ===============================================

BROADCASTER_ID = None
BROADCASTER_NAME = ""
SOUND_LIST = []
SOUND_QUEUE = asyncio.Queue()
USER_COOLDOWNS = {}
CURRENT_PLAY_TASK = None

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

def ensure_managed_rewards(broadcaster_id: str):
    """Cria as recompensas gerenciáveis via API para garantir permissão de estorno."""
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()
    headers = {
        "Client-Id": CLIENT_ID,
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json"
    }

    url_get = f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={broadcaster_id}&only_manageable_rewards=true"
    try:
        r = requests.get(url_get, headers=headers, timeout=5)
        manageable_titles = []
        if r.status_code == 200:
            rewards = r.json().get("data", [])
            manageable_titles = [normalize_text(rw.get("title", "")) for rw in rewards]

        rewards_to_ensure = [
            {
                "title": SEARCH_REWARD_NAME,
                "cost": SEARCH_REWARD_COST,
                "is_user_input_required": True,
                "prompt": "Digite o nome ou palavra do áudio que deseja buscar."
            },
            {
                "title": STOP_REWARD_NAME,
                "cost": STOP_REWARD_COST,
                "is_user_input_required": False,
                "prompt": ""
            }
        ]

        url_post = f"https://api.twitch.tv/helix/channel_points/custom_rewards?broadcaster_id={broadcaster_id}"
        for rw in rewards_to_ensure:
            norm_title = normalize_text(rw["title"])
            if norm_title in manageable_titles:
                print(f"[✓] Recompensa gerenciável '{rw['title']}' verificada (estorno ativo)!")
                continue

            r_post = requests.post(url_post, headers=headers, json=rw, timeout=5)
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
    global CURRENT_PLAY_TASK
    while True:
        item = await SOUND_QUEUE.get()
        try:
            play_sound(item["id"])
            duration = item.get("duration", 3.0)

            if item.get("show_popup"):
                sound_name = item["name"]
                user = item["user"]
                update_obs_text(f"🎵 {sound_name} (por @{user})")

                if item.get("is_search"):
                    query = item.get("query", "")
                    await send_twitch_chat(f"🔎 @{user} buscou \"{query}\" e tocou: \"{sound_name}\" (ID #{item['id']})")
                else:
                    await send_twitch_chat(f"🎲 @{user} girou a roleta e tocou: \"{sound_name}\" (ID #{item['id']})")

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

        return library
    except Exception as e:
        print(f"[!] Erro ao carregar biblioteca: {e}")
        return []

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

def get_broadcaster_id(client_id: str, token: str):
    clean_token = token.replace("oauth:", "").strip()
    headers = {
        "Client-Id": client_id,
        "Authorization": f"Bearer {clean_token}"
    }
    r = requests.get("https://api.twitch.tv/helix/users", headers=headers)
    if r.status_code != 200:
        raise Exception(f"Falha na autenticação da Twitch: {r.text}")
    data = r.json()["data"][0]
    return data["id"], data["display_name"]

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
        print("[✓] Escuta de Comandos de Chat (!parar, !limpar) ativa!")
    else:
        print(f"[!] Erro ao registrar escuta do chat ({r_chat.status_code}): {r_chat.text}")

async def listen_twitch():
    clean_token = ACCESS_TOKEN.replace("oauth:", "").strip()
    user_id, user_name = get_broadcaster_id(CLIENT_ID, clean_token)
    global BROADCASTER_ID, BROADCASTER_NAME, SOUND_LIST, ENABLE_CHAT_ANNOUNCEMENTS
    BROADCASTER_ID = user_id
    BROADCASTER_NAME = user_name

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

                            cmd = chat_msg.lower()

                            if cmd in ["!pular", "!skip"]:
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
                                    await send_twitch_chat(f"🔄 @{chatter} recarregou o Soundpad: {len(SOUND_LIST)} sons carregados!")
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

                            # Resgate: Parar Som (Interrompe o som atual sem apagar a fila restante)
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

                            if clean_title == normalize_text(RANDOM_REWARD_NAME):
                                if SOUND_LIST:
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
                                    await send_twitch_chat(f"⚠️ @{user}, digite uma palavra para buscar o meme! Seus pontos foram devolvidos.")
                                    await refund_redemption(user_id, reward_id, redemption_id)
                                    continue

                                query = normalize_text(user_input)
                                matches = [s for s in SOUND_LIST if query in normalize_text(s["name"])]

                                if matches:
                                    exact = [s for s in matches if normalize_text(s["name"]) == query]
                                    chosen = exact[0] if exact else min(matches, key=lambda s: len(s["name"]))
                                    await SOUND_QUEUE.put({
                                        "id": chosen["id"],
                                        "name": chosen["name"],
                                        "duration": chosen.get("duration", 3.0),
                                        "user": user,
                                        "show_popup": True,
                                        "is_search": True,
                                        "query": user_input
                                    })
                                    print(f" -> [Fila] Busca por '{user_input}' -> #{chosen['id']} ('{chosen['name']}') [{chosen.get('duration', 3.0)}s]")
                                else:
                                    await send_twitch_chat(f"⚠️ @{user}, nenhum áudio com \"{user_input}\"! Seus pontos foram devolvidos.")
                                    await refund_redemption(user_id, reward_id, redemption_id)

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
