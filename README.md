<div align="center">

# SoundpadBotForTwitch
[![Versão](https://img.shields.io/badge/Versão-1.2-brightgreen)]()
[![Licença](https://img.shields.io/badge/Licença-GPL--3.0-blue)]()
[![Status](https://img.shields.io/badge/Status-Ativo-success)]()

[🇧🇷 Versão em Português](#-versão-em-português) • [🇺🇸 English Version](#-english-version)

</div>

---

## 🇧🇷 Versão em Português

Bot local em Python que integra resgates de Pontos de Canal da Twitch ao Soundpad via Named Pipe, com fila dinâmica de reprodução por duração de áudio, estorno automático e conclusão de resgates automático, buscador interativo com sugestões, uma feature de "Roleta Russa progressiva", gerador de catálogo em imagem sincronizado com a lista de sons, sistema de entradas VIP e pop-up em tempo real para OBS Studio.

### 🚀 Funcionalidades

- **Controle Direto via Memória e Ping Preventivo**: Comunicação local via canal IPC do Soundpad (`sp_remote_control`), funcionando independente da pasta ou disco onde o software esteja instalado. Verifica se o Soundpad está aberto antes de aceitar qualquer resgate, estornando os pontos caso esteja offline.
- **Auto-Reload Passivo & Caminho Personalizado**: Suporte a caminhos customizados (`CUSTOM_SPL_PATH`) ou detecção automática pelo Windows, além de verificação periódica de alterações no `.spl` (`SPL_AUTO_RELOAD_INTERVAL`) para carregar novos áudios durante a live sem precisar reiniciar o bot.
- **Credenciais Externas e Logs em Arquivo**: Suporte nativo para guardar tokens fora do script em `config.json` ou `.env` (com geração automática de `config.example.json`) e registro rotativo de todas as atividades e erros em `bot.log`.
- **Auto-Renovação de Credenciais e Migração de Sessão**: Validação automática via API com detecção de Client-ID, renovação em runtime em caso de token expirado (`401`) com cache inteligente (`twitch_tokens.json`), suporte a `session_reconnect` da Twitch EventSub e watchdog de keepalive.
- **Fila Real de Áudios, Limite e Pausa (`!fila` / `!pausar`)**: Detecta o término exato do áudio, respeita `QUEUE_DELAY_SECONDS`, permite consultar os próximos sons e tempo restante (`!fila`), pausar/retomar a fila (`!pausar`) e limitar o tamanho máximo (`MAX_QUEUE_SIZE`, estornando excessos).
- **Detecção de Parada Manual**: Se o streamer parar o som manualmente no Soundpad, o bot detecta instantaneamente e avança para o próximo som da fila.
- **Buscador Inteligente (Sem Acentos, ID ou Sugestões Fuzzy)**: Viewers podem buscar por texto (ignorando acentos/cedilha) ou ID direto (ex: `#125`). Se houver múltiplos resultados, abre menu numerado de 30s no chat (estornando buscas antigas caso o mesmo viewer abra outra); se não houver correspondência exata, sugere os 3 nomes mais parecidos antes de estornar.
- **Estorno Automático e Conclusão de Resgates**: Marca automaticamente resgates tocados como `FULFILLED` (mantendo o painel da Twitch limpo) e devolve os pontos (`CANCELED`) se o áudio não existir, se o Soundpad estiver offline, se a fila estiver cheia, se o tempo de escolha acabar ou se usarem *Parar Som* sem nada tocando.
- **Roleta Russa Progressiva com Trap & Timeout**: Começa com **5% de chance** de cair na Trap, aumentando **+5%** a cada sobrevivente e resetando para 5% quando alguém cai (com timeout configurável e imunidade automática para streamer e moderadores).
- **Anti-Repetição no RNG (`NO_REPEAT_LAST_N`)**: Impede que o *Som Aleatório*, a *Roleta Russa* e o *Som por Categoria* repitam em sequência os últimos áudios sorteados.
- **Resgate Pago por Categoria (`Som por Categoria`)**: Viewers podem resgatar pontos escolhendo uma categoria temática (ex: `anime`, `scream`, `meme`), evitando reprodução gratuita direta pelo chat (o comando `!cat` no chat fica restrito a Mods/Host).
- **Catálogo em Imagem Sincronizado com a Lista (Pillow)**: Gera `lista_de_sons.png` (até 5000px, com ajuste automático para bibliotecas com mais de 1.000 áudios) e verifica alterações na lista de sons (`lista_de_sons.sig`) *antes* de consultar ou enviar o link (**Imgur**, **Tmpfiles** ou **Puush**), atualizando a imagem automaticamente sempre que novos áudios forem adicionados.
- **Sons de Entrada VIP (`user_themes.json`)**: VIPs, Subs e Moderadores podem definir (`!settema <ID>`), consultar (`!meusom`) ou remover (`!limpartema`) um som pessoal que toca na primeira mensagem da live.
- **Aviso de Bot Online & Encerramento Limpo pelo Terminal**: Avisa no chat quando o bot entra no ar (`ANNOUNCE_BOT_ONLINE`), exibe lembrete periódico a cada 300s no console e permite encerrar com segurança digitando `sair` (ou `exit`) diretamente no terminal.
- **Pop-up Dinâmico no OBS & Controle de Chat**: Atualiza `obs_tocando_agora.txt` pelo tempo exato do áudio e permite alternar anúncios no chat (`!chat`) sem desligar o overlay na tela.
- **Comandos de Chat Bilingues com Pseudônimos Curtos** (PT-BR e EN-US):
  - `!comandos` (`!cmd`) / `!commands` (`!cmds`): Lista todos os comandos separados entre **Todos** e **Mod/Streamer**.
  - `!imagem` (`!img`) / `!image` (`!sounds`): Envia no chat o link atualizado da imagem completa de áudios.
  - `!gerarimagem` (`!gimg`) / `!generateimage` (`!genimg`): Força a regerar e reenviar a imagem da biblioteca (Mods/Host).
  - `!categorias` (`!cats`) / `!categories`: Lista as categorias temáticas disponíveis para resgate.
  - `!categoria <nome>` (`!cat <nome>`) / `!category <name>`: Sorteia um som da categoria escolhida (Mods/Host).
  - `!som` (`!usom`) / `!sound` (`!ls`) (ou `!ultimosom` / `!lastsound`): Consulta o último som reproduzido.
  - `!fila` (`!q`) / `!queue`: Exibe o som atual, próximos da fila e tempo restante estimado.
  - `!settema <ID>` (`!tema`) / `!settheme <ID>` (`!theme`): Define o som de entrada VIP do usuário.
  - `!meusom` (`!msom`) / `!mysound` (`!ms`): Consulta seu som de entrada atual.
  - `!limpartema` (`!ltema`) / `!cleartheme` (`!ctheme`): Remove seu som de entrada VIP.
  - `!pausar` (`!retomar`) / `!pause` (`!resume`): Pausa ou retoma a fila de sons sem apagar os resgates (Mods/Host).
  - `!pular` (`!pul`) / `!skip` (`!sk`): Pula o som atual e avança para o próximo da fila (Mods/Host).
  - `!limpar` (`!lmp`) / `!clear` (`!cls`): Silencia tudo e apaga toda a fila de espera (Mods/Host).
  - `!recarregar` (`!rec`) / `!reload` (`!rel`): Recarrega a biblioteca do Soundpad e atualiza a imagem sem reiniciar o bot (Mods/Host).
  - `!chat` (`!tc`) / `!togglechat`: Ativa ou desativa as mensagens de anúncio de som no chat (Mods/Host).

---

### 📦 Pré-requisitos

1. **Python 3.9+** instalado no Windows (com a opção *Add Python to PATH* marcada).
2. **Soundpad** instalado e em execução.
3. Instalar as dependências via terminal:
   ```bash
   pip install websockets requests pillow
   ```
4. Git para clonar o projeto (Opcional).

---

### 🛠️ Passo a Passo: Como Configurar e Rodar o Bot

#### 1. Clonar o repositório e instalar dependências
Baixe o Zip do projeto no botão "< > CODE" acima **OU** abra o terminal (CMD ou PowerShell) na pasta desejada:
```bash
git clone https://github.com/Y4SH1R01/SoundpadBotForTwitch.git
cd SoundpadBotForTwitch
pip install websockets requests pillow
```

#### 2. Obter as credenciais da Twitch
1. Acesse o [twitchtokengenerator.com](https://twitchtokengenerator.com).
2. Marque estes escopos:
   - `channel:read:redemptions` (ouvir resgates)
   - `channel:manage:redemptions` (necessário para criar recompensas, concluir e estornar pontos)
   - `user:write:chat` (enviar anúncios e links no chat)
   - `user:read:chat` (ouvir comandos e escolhas de busca no chat)
   - `moderator:manage:banned_users` (necessário caso queira a punição de timeout na Roleta Russa)
   - *(Opcional)* `moderation:read` (para carregar previamente todos os moderadores do canal e garantir imunidade na Roleta desde a inicialização)
3. Clique em **Generate Token** e autorize com a sua conta da Twitch.
4. Cole seu **Client ID**, **Access Token** e **Refresh Token** no topo do `bot_soundpad.py` **ou** crie um arquivo `config.json` (usando o `config.example.json` gerado automaticamente como modelo):
   ```json
   {
     "CLIENT_ID": "SEU_CLIENT_ID_AQUI",
     "ACCESS_TOKEN": "SEU_ACCESS_TOKEN_AQUI",
     "REFRESH_TOKEN": "SEU_REFRESH_TOKEN_AQUI",
     "CLIENT_SECRET": "",
     "PUUSH_API_KEY": ""
   }
   ```

#### 3. Configurar os Resgates de Pontos na Twitch
* **Recompensas Automáticas gerenciadas pela API**: Ao iniciar o script com o token configurado, o próprio bot cria e sincroniza as recompensas gerenciáveis na Twitch com direito a estorno automático:
   - `Som Aleatório` (100 pts)
   - `Buscar Meme` (150 pts)
   - `Som por Categoria` (120 pts)
   - `Parar Som` (500 pts)
   - `Roleta Russa` (50 pts — progressiva a partir de 5%)
* *(Você pode personalizar os nomes, custos e textos descritivos diretamente nas variáveis de configuração no início do `bot_soundpad.py` — o bot atualiza na Twitch via API automaticamente).*
* **Sons Específicos** *(Opcional)*: Se quiser criar resgates fixos para memes específicos, use na Twitch o **mesmo nome** cadastrado no `REWARDS_MAP` do script, apontando para o número do ID no Soundpad.  
  Exemplo de configuração no `bot_soundpad.py`:
  ```python
  REWARDS_MAP = {
      "Exemplo Som 1": 1,
      "Exemplo Som 2": 2,
  }
  ```

#### 4. Configurar o Pop-up no OBS Studio *(Opcional)*
1. No OBS, adicione uma fonte de **Texto (GDI+)** na sua cena.
2. Marque a caixa **Ler do arquivo** (*Read from file*).
3. Selecione o arquivo `obs_tocando_agora.txt` que está dentro da pasta do bot.
4. Defina a fonte como **Segoe UI Emoji** (para ícones e notas musicais renderizarem perfeitamente).
5. *(Opcional)* Adicione uma fonte de **Imagem** apontando para `lista_de_sons.png` caso queira exibir o catálogo gráfico de sons na tela.

#### 5. Iniciar (e Encerrar) o Bot
1. Abra o **Soundpad** (certifique-se de que a lista de sons esteja salva).
2. Dê dois cliques em **`iniciar_bot.bat`** (ou execute `python bot_soundpad.py`).
3. Uma janela abrirá validando os tokens, sincronizando as recompensas e confirmando a conexão com a Twitch.
4. Para encerrar o bot com segurança a qualquer momento, basta digitar `sair` (ou `exit`) no terminal e apertar **Enter**.

---

**Desenvolvido por Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) com ajuda de:**
* Versão 1.0 e 1.0.1: Gemini-3.8-Flash.
* Versão 1.1: Gemini-3.8-Flash.
* Versão 1.2: Gemini-4-Hydrogen.

**Última atualização:** 25 de novembro de 2026.

---

## 🇺🇸 English Version

A lightweight local Python bot integrating Twitch Channel Point rewards with Soundpad via Named Pipes, featuring real audio playback queues based on track length, automatic point refunds and redemption fulfillment (`FULFILLED`), accent-insensitive interactive search with fuzzy suggestions, progressive Russian Roulette, auto-synced high-definition sound catalogs, VIP entrance themes, and real-time overlays for OBS Studio.

### 🚀 Features

- **Direct Memory IPC & Preventive Soundpad Ping**: Direct communication using Soundpad's local named pipe (`sp_remote_control`), working regardless of installation folder or drive letter. Automatically verifies if Soundpad is running before accepting redemptions, refunding points immediately if offline.
- **Passive Auto-Reload & Custom Soundlist Path**: Supports custom list locations (`CUSTOM_SPL_PATH`) or automatic Windows detection, plus periodic `.spl` modification monitoring (`SPL_AUTO_RELOAD_INTERVAL`) to pick up newly added sounds mid-stream without restarting.
- **External Credentials & File Logging**: Supports storing credentials safely outside the script in `config.json` or `.env` (automatically creating `config.example.json`), plus rotating log output in `bot.log`.
- **Automatic Token Refresh & Seamless Session Migration**: Auto-detects the matching Client-ID, refreshes expired tokens in runtime (`401` retry with thread lock) caching them in `twitch_tokens.json`, handles Twitch EventSub `session_reconnect` seamlessly, and monitors connection health with a keepalive watchdog.
- **True Sound Queue, Max Limit & Pause (`!queue` / `!pause`)**: Tracks exact audio duration, respects `QUEUE_DELAY_SECONDS`, lets chat check upcoming sounds and remaining wait time (`!queue`), allows mods to pause/resume (`!pause`), and caps queue size (`MAX_QUEUE_SIZE`, refunding overflow).
- **Manual Stop Detection**: If the broadcaster stops playback manually within Soundpad, the bot detects it immediately and advances the queue.
- **Smart Interactive Search (Accent-Insensitive, ID, or Fuzzy Suggestions)**: Viewers can search by keywords (ignoring accents) or direct sound IDs (e.g., `#125`). Multiple matches open a 30-second numbered chat menu (auto-refunding stale searches if the same viewer starts a new one); if no exact match exists, up to 3 fuzzy suggestions are shown before refunding.
- **Automatic Refunds & Redemption Fulfillment**: Automatically marks played redemptions as `FULFILLED` to keep the creator dashboard clean, and cancels/refunds (`CANCELED`) if a sound isn't found, Soundpad is offline, the queue is full, selection times out, or *Stop Sound* is triggered when idle.
- **Progressive Russian Roulette with Trap & Timeout**: Starts at a **5% trap chance**, climbs **+5%** with each survivor, and resets to 5% when someone hits a Trap Troll audio + temporary chat timeout (broadcaster and moderators are automatically detected as immune).
- **RNG No-Repeat Protection (`NO_REPEAT_LAST_N`)**: Prevents *Random Sound*, *Russian Roulette*, and *Category Sound* from repeating the last N randomly selected tracks in a row.
- **Paid Category Redemption (`Som por Categoria`)**: Viewers can spend Channel Points to roll a random track from a chosen category (while direct chat `!cat` is restricted to Mods/Host).
- **Auto-Synced High-Definition Sound Catalog (Pillow)**: Renders `lista_de_sons.png` (up to 5000px wide, scaling dynamically for 1,000+ track libraries) and checks soundlist changes (`lista_de_sons.sig`) *before* serving or uploading links (**Imgur**, **Tmpfiles**, or **Puush**), refreshing the image automatically whenever new sounds are added.
- **VIP Entrance Sounds (`user_themes.json`)**: VIPs, Subscribers, and Moderators can set (`!settheme <ID>`), check (`!mysound`), or clear (`!cleartheme`) a personal entrance theme played on their first chat message of the session.
- **Online Chat Announcement & Clean Terminal Shutdown**: Announces when the bot comes online (`ANNOUNCE_BOT_ONLINE`), displays a periodic terminal reminder every 300s, and lets you cleanly stop the bot by typing `exit` (or `sair`) directly in the terminal.
- **Dynamic OBS Overlay & Chat Toggle**: Outputs to `obs_tocando_agora.txt` for the exact track duration and lets mods toggle chat notifications (`!togglechat`) without disabling the screen overlay.
- **Bilingual Chat Commands with Short Aliases** (PT-BR and EN-US):
  - `!comandos` (`!cmd`) / `!commands` (`!cmds`): Lists all commands separated into **Everyone** and **Mod/Streamer**.
  - `!imagem` (`!img`) / `!image` (`!sounds`): Posts the up-to-date catalog image link in chat.
  - `!gerarimagem` (`!gimg`) / `!generateimage` (`!genimg`): Forces regeneration and re-upload of the catalog image (Mods/Host).
  - `!categorias` (`!cats`) / `!categories`: Lists all available thematic categories for redemption.
  - `!categoria <nome>` (`!cat <nome>`) / `!category <name>`: Rolls a random sound from the selected category (Mods/Host).
  - `!som` (`!usom`) / `!sound` (`!ls`) (or `!ultimosom` / `!lastsound`): Shows the last played audio.
  - `!fila` (`!q`) / `!queue`: Displays currently playing track, queued sounds, and estimated wait time.
  - `!settema <ID>` (`!tema`) / `!settheme <ID>` (`!theme`): Sets the user's personal VIP entrance theme.
  - `!meusom` (`!msom`) / `!mysound` (`!ms`): Displays the user's currently configured entrance sound.
  - `!limpartema` (`!ltema`) / `!cleartheme` (`!ctheme`): Removes your VIP entrance theme.
  - `!pausar` (`!retomar`) / `!pause` (`!resume`): Pauses or resumes the queue without losing queued redemptions (Mods/Host).
  - `!pular` (`!pul`) / `!skip` (`!sk`): Skips current sound and advances to the next queued item (Mods/Host).
  - `!limpar` (`!lmp`) / `!clear` (`!cls`): Stops playback immediately and clears the entire queue (Mods/Host).
  - `!recarregar` (`!rec`) / `!reload` (`!rel`): Reloads the Soundpad library and updates the image without restarting the bot (Mods/Host).
  - `!chat` (`!tc`) / `!togglechat`: Toggles chat sound announcements on or off live (Mods/Host).

---

### 📦 Prerequisites

1. **Python 3.9+** installed on Windows (ensure *Add Python to PATH* is checked).
2. **Soundpad** installed and running.
3. Install dependencies via terminal/command prompt:
   ```bash
   pip install websockets requests pillow
   ```
4. Git to clone the repository (Optional).

---

### 🛠️ Step-by-Step Setup & Usage Guide

#### 1. Clone the Repository & Install Dependencies
Download the project Zip from the "< > CODE" button above **OR** open your terminal (Command Prompt or PowerShell) in your preferred folder:
```bash
git clone https://github.com/Y4SH1R01/SoundpadBotForTwitch.git
cd SoundpadBotForTwitch
pip install websockets requests pillow
```

#### 2. Generate Twitch API Credentials
1. Visit [twitchtokengenerator.com](https://twitchtokengenerator.com).
2. Select these scopes:
   - `channel:read:redemptions` (listen to channel point redeems)
   - `channel:manage:redemptions` (required to create rewards, fulfill, and refund points)
   - `user:write:chat` (send bot messages and links in chat)
   - `user:read:chat` (listen for chat commands and interactive search inputs)
   - `moderator:manage:banned_users` (required if using the Russian Roulette timeout feature)
   - *(Optional)* `moderation:read` (preload all channel moderators on startup for Roulette timeout immunity)
3. Click **Generate Token** and authorize with your broadcaster Twitch account.
4. Paste your **Client ID**, **Access Token**, and **Refresh Token** at the top of `bot_soundpad.py` **or** create a `config.json` file (using the auto-generated `config.example.json` as a template):
   ```json
   {
     "CLIENT_ID": "YOUR_CLIENT_ID_HERE",
     "ACCESS_TOKEN": "YOUR_ACCESS_TOKEN_HERE",
     "REFRESH_TOKEN": "YOUR_REFRESH_TOKEN_HERE",
     "CLIENT_SECRET": "",
     "PUUSH_API_KEY": ""
   }
   ```

#### 3. Setup Twitch Channel Point Rewards
* **Auto-Managed API Rewards**: On startup, the bot automatically creates and synchronizes managed rewards on Twitch with refund support:
   - `Som Aleatório` (100 pts)
   - `Buscar Meme` (150 pts)
   - `Som por Categoria` (120 pts)
   - `Parar Som` (500 pts)
   - `Roleta Russa` (50 pts — progressive starting at 5%)
* *(You can customize titles, point costs, and prompt descriptions directly in the configuration block at the top of `bot_soundpad.py` — the bot updates them on Twitch via API automatically).*
* **Specific Sounds** *(Optional)*: To create fixed rewards for specific sounds, make sure the reward title on Twitch matches the **exact name** defined in the `REWARDS_MAP` dictionary, mapped to its Soundpad index.  
  Configuration example in `bot_soundpad.py`:
  ```python
  REWARDS_MAP = {
      "Exemplo Som 1": 1,
      "Exemplo Som 2": 2,
  }
  ```

#### 4. Configure the OBS Studio Pop-up Overlay *(Optional)*
1. In OBS Studio, add a **Text (GDI+)** source to your active scene.
2. Check the **Read from file** box.
3. Browse and select `obs_tocando_agora.txt` (located in the bot root folder).
4. Select **Segoe UI Emoji** as the font to ensure proper emoji rendering.
5. *(Optional)* Add an **Image** source pointing to `lista_de_sons.png` to display the visual sound catalog on stream.

#### 5. Run (and Stop) the Bot
1. Open **Soundpad** (ensure your sound list is saved).
2. Double-click **`iniciar_bot.bat`** (or run `python bot_soundpad.py`).
3. A terminal window will open validating credentials, synchronizing managed rewards, and confirming the Twitch WebSocket connection.
4. To safely shut down the bot at any time, simply type `exit` (or `sair`) in the terminal and press **Enter**.

---

**Dev'd by Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) with the help of:**
* Version 1.0 & 1.0.1: Gemini-3.8-Flash.
* Version 1.1: Gemini-3.8-Flash.
* Version 1.2: Gemini-4-Hydrogen.

**Last updated:** November 25, 2026.

---

[Voltar ao topo / Back to top](#soundpadbotfortwitch)
