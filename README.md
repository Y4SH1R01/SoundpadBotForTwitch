<div align="center">

# SoundpadBotForTwitch
[![Versão](https://img.shields.io/badge/Versão-1.1-brightgreen)]()
[![Licença](https://img.shields.io/badge/Licença-GPL--3.0-blue)]()
[![Status](https://img.shields.io/badge/Status-Ativo-success)]()

[🇧🇷 Versão em Português](#-versão-em-português) • [🇺🇸 English Version](#-english-version)

</div>

---

## 🇧🇷 Versão em Português

Bot local em Python que integra resgates de Pontos de Canal da Twitch ao Soundpad via Named Pipe, com fila dinâmica de reprodução por duração de áudio, estorno automático de pontos, buscador interativo por texto/ID, gerador de catálogo em imagem de alta definição, sistema de entradas VIP e pop-up sincronizado para OBS Studio.

### 🚀 Funcionalidades

- **Controle Direto via Memória**: Comunicação local via canal IPC do Soundpad (`sp_remote_control`), funcionando independente da pasta ou disco onde o software esteja instalado.
- **Suporte a Caminho Personalizado**: Permite apontar diretamente para listas personalizadas ou backups (ex: `CUSTOM_SPL_PATH`), além da detecção automática padrão.
- **Auto-Renovação de Credenciais (Refresh Token)**: Validação inteligente via API que detecta o Client-ID correto do token automaticamente e renova tokens expirados em segundo plano, salvando em cache (`twitch_tokens.json`).
- **Fila Real de Áudios (Sound Queue)**: Detecta o término exato do áudio e só libera o próximo som da fila quando o anterior acabar, respeitando o intervalo de segurança configurado (`QUEUE_DELAY_SECONDS`).
- **Detecção de Parada Manual**: Se o streamer parar o som manualmente no Soundpad, o bot detecta instantaneamente e avança para o próximo som da fila.
- **Buscador de Memes Interativo (Texto ou ID)**: Viewers podem resgatar digitando palavras-chave ou o ID direto (ex: `#125`). Se houver múltiplos resultados parecidos, o bot envia um menu no chat com 3 a 5 opções numeradas para escolha em até 30 segundos.
- **Estorno Automático de Pontos**: Devolve os pontos do canal do viewer automaticamente se o áudio não existir, se a biblioteca estiver vazia, se o viewer não responder ao menu de busca no tempo limite ou se tentarem usar o *Parar Som* sem nada tocando.
- **Roleta Russa com Trap & Timeout**: Recompensa configurável com chance de tocar um meme aleatório ou cair numa Trap Troll com sons selecionados e punição de timeout temporário no chat da Twitch (streamer e mods são imunes).
- **Gerador e Hospedagem da Lista de Memes (Pillow)**: Cria automaticamente uma imagem em alta resolução (`lista_de_sons.png`) em até 5000px com colunas largas e medição por pixel para evitar cortes. Faz upload automático para a web (**Imgur**, **Tmpfiles** ou **Puush**) para compartilhamento rápido no chat.
- **Sons de Entrada VIP (`user_themes.json`)**: VIPs, Subs e Moderadores podem cadastrar um som pessoal (`!settema <ID>`) que toca automaticamente na primeira mensagem enviada no chat durante a live.
- **Filtro e Sorteio por Categorias**: Permite sortear áudios dentro de temas ou personagens específicos cadastrados no bot (`!categoria <nome>`).
- **Consulta de Último Som Tocado**: Comando para informar no chat o nome, ID e autor do último meme executado.
- **Anti-Spam / Cooldown Individual**: Impede que um único viewer esvazie seus pontos acumulados spammando áudios em sequência.
- **Pop-up Dinâmico no OBS**: Atualiza o arquivo `obs_tocando_agora.txt` exibindo o som na tela pela duração exata do áudio, sumindo na hora se o som acabar ou for parado.
- **Alternância de Chat**: Opção dinâmica (`ENABLE_CHAT_ANNOUNCEMENTS`) e comando para ligar/desligar anúncios de texto no chat caso prefira apenas o pop-up na tela.
- **Comandos de Chat Bilingues** (1 variante PT-BR e 1 EN-US por ação):
  - `!som` / `!sound` (ou `!ultimosom` / `!lastsound`): Consulta o último som reproduzido.
  - `!memes` / `!sounds` (ou `!imagem` / `!image`): Envia o link da imagem da lista completa de memes no chat.
  - `!gerarimagem` / `!generateimage`: Força a regerar e reupar a imagem da biblioteca (Mods/Host).
  - `!settema <ID>` / `!settheme <ID>`: Define o som de entrada VIP do usuário.
  - `!meusom` / `!mysound`: Consulta o som de entrada atual configurado para você.
  - `!categorias` / `!categories`: Lista as categorias temáticas configuradas.
  - `!categoria <nome>` / `!category <name>`: Sorteia um som da categoria escolhida.
  - `!pular` / `!skip`: Pula o som atual e avança para o próximo da fila (Mods/Host).
  - `!limpar` / `!clear`: Silencia tudo e apaga toda a fila de espera (Mods/Host).
  - `!recarregar` / `!reload`: Recarrega a biblioteca do Soundpad na memória sem reiniciar o bot (Mods/Host).
  - `!chat` / `!togglechat`: Ativa ou desativa as mensagens de anúncio de som no chat (Mods/Host).

---

### 📦 Pré-requisitos

1. **Python 3.8+** instalado no Windows (com a opção *Add Python to PATH* marcada).
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
2. Marque exatamente estes escopos:
   - `channel:read:redemptions` (ouvir resgates)
   - `channel:manage:redemptions` (necessário para criar recompensas e estornar pontos)
   - `user:write:chat` (enviar anúncios e links no chat)
   - `user:read:chat` (ouvir comandos e escolhas de busca no chat)
   - `moderator:manage:banned_users` (necessário caso queira a punição de timeout na Roleta Russa)
3. Clique em **Generate Token** e autorize com a sua conta da Twitch.
4. Abra o arquivo `bot_soundpad.py` em seu editor e cole seu **Client ID**, **Access Token** e o **Refresh Token** no topo:
   ```python
   CLIENT_ID = "SEU_CLIENT_ID_AQUI"
   ACCESS_TOKEN = "SEU_ACCESS_TOKEN_AQUI"
   REFRESH_TOKEN = "SEU_REFRESH_TOKEN_AQUI"
   ```

#### 3. Configurar os Resgates de Pontos na Twitch
* **Recompensas Automáticas gerenciadas pela API**: Ao iniciar o script com o token configurado, o próprio bot cria e sincroniza as recompensas gerenciáveis na Twitch com direito a estorno automático:
   - `Som Aleatório` (100 pts)
   - `Buscar Meme` (150 pts)
   - `Parar Som` (500 pts)
   - `Roleta Russa` (50 pts)
*   *(Você pode personalizar os nomes, custos e textos descritivos diretamente nas variáveis de configuração no início do `bot_soundpad.py` — o bot atualiza na Twitch via API automaticamente).*
* **Sons Específicos** *(Opcional)*: Se quiser criar resgates fixos para memes específicos, use na Twitch o **mesmo nome** cadastrado no `REWARDS_MAP` do script, apontando para o número do ID no Soundpad.  
  Exemplo de configuração no `bot_soundpad.py`:
  ```python
  REWARDS_MAP = {
      "Nome Exato 1": 123,
      "Nome Exato 2": 456,
  }
  ```

#### 4. Configurar o Pop-up no OBS Studio *(Opcional)*
1. No OBS, adicione uma fonte de **Texto (GDI+)** na sua cena.
2. Marque a caixa **Ler do arquivo** (*Read from file*).
3. Selecione o arquivo `obs_tocando_agora.txt` que está dentro da pasta do bot.
4. Defina a fonte como **Segoe UI Emoji** (para ícones e notas musicais renderizarem perfeitamente).
5. *(Opcional)* Adicione uma fonte de **Imagem** apontando para `lista_de_sons.png` caso queira exibir o catálogo gráfico de sons na tela.

#### 5. Iniciar o Bot
1. Abra o **Soundpad** (certifique-se de que a lista de sons esteja salva).
2. Dê dois cliques em **`iniciar_bot.bat`** (ou execute `python bot_soundpad.py`).
3. Uma janela abrirá validando os tokens, sincronizando as recompensas gerenciadas e confirmando a conexão com a Twitch.

---

**Desenvolvido por Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) com ajuda de:**
* Versão 1.0 e 1.0.1: Gemini-3.8-Flash.
* Versão 1.1: Gemini-3.8-Flash.

---

## 🇺🇸 English Version

A lightweight local Python bot integrating Twitch Channel Point rewards with Soundpad via Named Pipes, featuring real audio playback queues based on track length, automatic point refunds, interactive keyword/ID meme search, high-definition graphical sound catalogs, VIP entrance themes, and real-time pop-up overlays for OBS Studio.

### 🚀 Features

- **Direct Memory IPC**: Direct communication using Soundpad's local named pipe (`sp_remote_control`), working regardless of installation folder or drive letter.
- **Custom Soundlist Path Support**: Allows directly targeting custom list locations or backup files (e.g., `CUSTOM_SPL_PATH`), alongside default auto-detection.
- **Automatic Token Refresh**: Smart API validation that auto-detects the matching Client-ID and seamlessly refreshes expired tokens in the background via `REFRESH_TOKEN`, caching credentials in `twitch_tokens.json`.
- **True Sound Queue**: Detects exact audio length and only starts the next sound after the current one finishes, respecting the configured safety delay (`QUEUE_DELAY_SECONDS`).
- **Manual Stop Detection**: If the broadcaster stops playback manually within Soundpad, the bot detects it immediately and advances the queue.
- **Interactive Meme Search (Keyword or ID)**: Viewers can redeem using keywords or direct sound IDs (e.g., `#125`). If multiple matches exist, an interactive chat menu offers 3 to 5 numbered options with a 30-second response window.
- **Automatic Point Refunds**: Automatically cancels redemptions and refunds channel points if a searched meme is not found, if the library is empty, if the viewer times out during search selection, or if *Stop Sound* is used while nothing is playing.
- **Russian Roulette with Trap & Timeout**: Configurable gamble reward offering a chance for a random meme or a selected Trap Troll audio accompanied by a temporary Twitch chat timeout (broadcaster and mods are immune).
- **High-Definition Soundboard Image Catalog (Pillow)**: Renders a crystal-clear image (`lista_de_sons.png`) up to 5000px wide with wide columns and pixel-accurate clipping. Automatically uploads to image hosting (**Imgur**, **Tmpfiles**, or **Puush**) for quick link distribution in chat.
- **VIP Entrance Sounds (`user_themes.json`)**: VIPs, Subscribers, and Moderators can set a personal theme sound (`!settheme <ID>`) that plays automatically on their first chat message of the stream.
- **Category Filter & Rolls**: Allows rolling random sounds within specific custom-defined character or topic categories (`!category <name>`).
- **Last Sound Check**: Chat command to look up the title, ID, and author of the most recently played sound.
- **Per-User Anti-Spam / Cooldown**: Prevents point-rich viewers from rapid-fire redeeming sounds consecutively.
- **Dynamic OBS Studio Overlay**: Outputs to `obs_tocando_agora.txt` matching the exact sound duration, clearing immediately when playback ends or is stopped.
- **Dynamic Chat Toggle**: Configuration flag (`ENABLE_CHAT_ANNOUNCEMENTS`) and chat command to toggle text notifications on/off if you prefer screen pop-ups only.
- **Bilingual Chat Commands** (1 PT-BR and 1 EN-US pair per action):
  - `!som` / `!sound` (or `!ultimosom` / `!lastsound`): Shows the last played audio.
  - `!memes` / `!sounds` (or `!imagem` / `!image`): Posts the full sound list image link in chat.
  - `!gerarimagem` / `!generateimage`: Forces regeneration and re-upload of the catalog image (Mods/Host).
  - `!settema <ID>` / `!settheme <ID>`: Sets the user's personal VIP entrance theme.
  - `!meusom` / `!mysound`: Displays the user's currently configured entrance sound.
  - `!categorias` / `!categories`: Lists all available thematic categories.
  - `!categoria <nome>` / `!category <name>`: Rolls a random sound from the selected category.
  - `!pular` / `!skip`: Skips current sound and advances to the next queued item (Mods/Host).
  - `!limpar` / `!clear`: Stops playback immediately and clears the entire queue (Mods/Host).
  - `!recarregar` / `!reload`: Reloads the Soundpad library in memory without restarting the bot (Mods/Host).
  - `!chat` / `!togglechat`: Toggles chat sound announcements on or off live (Mods/Host).

---

### 📦 Prerequisites

1. **Python 3.8+** installed on Windows (ensure *Add Python to PATH* is checked).
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
2. Select these required scopes:
   - `channel:read:redemptions` (listen to channel point redeems)
   - `channel:manage:redemptions` (required to create rewards and refund points)
   - `user:write:chat` (send bot messages and links in chat)
   - `user:read:chat` (listen for chat commands and interactive search inputs)
   - `moderator:manage:banned_users` (required if using the Russian Roulette timeout feature)
3. Click **Generate Token** and authorize with your broadcaster Twitch account.
4. Open `bot_soundpad.py` in your text editor and paste your **Client ID**, **Access Token**, and **Refresh Token** at the top:
   ```python
   CLIENT_ID = "YOUR_CLIENT_ID_HERE"
   ACCESS_TOKEN = "YOUR_ACCESS_TOKEN_HERE"
   REFRESH_TOKEN = "YOUR_REFRESH_TOKEN_HERE"
   ```

#### 3. Setup Twitch Channel Point Rewards
* **Auto-Managed API Rewards**: On startup, the bot automatically creates and synchronizes managed rewards on Twitch with refund permissions:
   - `Som Aleatório` (100 pts)
   - `Buscar Meme` (150 pts)
   - `Parar Som` (500 pts)
   - `Roleta Russa` (50 pts)
 *  *(You can customize titles, point costs, and prompt descriptions directly in the configuration block at the top of `bot_soundpad.py` — the bot updates them on Twitch via API automatically).*
* **Specific Sounds** *(Optional)*: To create fixed rewards for specific sounds, make sure the reward title on Twitch matches the **exact name** defined in the `REWARDS_MAP` dictionary, mapped to its Soundpad index.  
  Configuration example in `bot_soundpad.py`:
  ```python
  REWARDS_MAP = {
      "Exact Title 1": 123,
      "Exact Title 2": 456,
  }
  ```

#### 4. Configure the OBS Studio Pop-up Overlay *(Optional)*
1. In OBS Studio, add a **Text (GDI+)** source to your active scene.
2. Check the **Read from file** box.
3. Browse and select `obs_tocando_agora.txt` (located in the bot root folder).
4. Select **Segoe UI Emoji** as the font to ensure proper emoji rendering.
5. *(Optional)* Add an **Image** source pointing to `lista_de_sons.png` to display the visual sound catalog on stream.

#### 5. Run the Bot
1. Open **Soundpad** (ensure your sound list is saved).
2. Double-click **`iniciar_bot.bat`** (or run `python bot_soundpad.py`).
3. A terminal window will open validating credentials, synchronizing managed rewards, and confirming the Twitch WebSocket connection.

---

**Dev'd by Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) with the help of:**
* Version 1.0 & 1.0.1: Gemini-3.8-Flash.
* Version 1.1: Gemini-3.8-Flash.

---

[Voltar ao topo / Back to top](#soundpadbotfortwitch)
