<div align="center">

# SoundpadBotForTwitch
[![Versão](https://img.shields.io/badge/Versão-1.0.1-brightgreen)]()
[![Licença](https://img.shields.io/badge/Licença-GPL--3.0-blue)]()
[![Status](https://img.shields.io/badge/Status-Ativo-success)]()

[🇧🇷 Versão em Português](#-versão-em-português) • [🇺🇸 English Version](#-english-version)

</div>

---

## 🇧🇷 Versão em Português

Bot local em Python que integra resgates de Pontos de Canal da Twitch ao Soundpad via Named Pipe, com fila dinâmica de reprodução por duração de áudio, estorno automático de pontos, buscador por texto e pop-up sincronizado para OBS Studio.

### 🚀 Funcionalidades

- **Controle Direto via Memória**: Comunicação local via canal IPC do Soundpad (`sp_remote_control`), funcionando independente da pasta ou disco onde o software esteja instalado.
- **Suporte a Caminho Personalizado**: Permite apontar diretamente para listas personalizadas ou backups (ex: `CUSTOM_SPL_PATH`), além da detecção automática padrão.
- **Fila Real de Áudios (Sound Queue)**: Detecta o término exato do áudio e só libera o próximo som da fila quando o anterior acabar.
- **Detecção de Parada Manual**: Se o streamer parar o som manualmente no Soundpad, o bot detecta instantaneamente e avança para o próximo som da fila.
- **Buscador de Memes por Texto**: O viewer resgata digitando uma palavra-chave; o bot busca na biblioteca e executa o som mais próximo.
- **Estorno Automático de Pontos**: Devolve os pontos do canal do viewer automaticamente se o termo buscado não existir ou se tentarem usar o *Parar Som* sem nada tocando.
- **Anti-Spam / Cooldown Individual**: Impede que um único viewer esvazie seus pontos acumulados spammando áudios em sequência.
- **Resiliência de Rede**: Requisições assíncronas com timeout contra travamentos em caso de oscilações de roteador ou internet.
- **Pop-up Dinâmico no OBS**: Atualiza o arquivo `obs_tocando_agora.txt` exibindo o som na tela pela duração exata do áudio, sumindo na hora se o som acabar ou for parado.
- **Alternância de Chat**: Opção dinâmica (`ENABLE_CHAT_ANNOUNCEMENTS`) e comando para ligar/desligar anúncios de texto no chat caso prefira apenas o pop-up na tela.
- **Comandos de Chat para Moderadores** (1 variante PT-BR e 1 EN-US):
  - `!pular` / `!skip`: Pula o som atual e avança para o próximo da fila.
  - `!limpar` / `!clear`: Silencia tudo e apaga toda a fila de espera.
  - `!recarregar` / `!reload`: Recarrega a lista do Soundpad na memória sem reiniciar o bot.
  - `!chat` / `!togglechat`: Ativa ou desativa as mensagens de anúncio de som no chat.

---

### 📦 Pré-requisitos

1. **Python 3.8+** instalado no Windows (com a opção *Add Python to PATH* marcada).
2. **Soundpad** instalado e em execução.
3. Instalar as dependências via terminal:
   ```bash
   pip install websockets requests
   ```
4. Git para clonar o projeto (Opcional).

---

### 🛠️ Passo a Passo: Como Configurar e Rodar o Bot

#### 1. Clonar o repositório e instalar dependências
Baixe o Zip do projeto no botão "< > CODE" acima **OU** abra o terminal (CMD ou PowerShell) na pasta desejada:
```bash
git clone https://github.com/Y4SH1R01/SoundpadBotForTwitch.git
cd SoundpadBotForTwitch
pip install websockets requests
```

#### 2. Obter as credenciais da Twitch
1. Acesse o [twitchtokengenerator.com](https://twitchtokengenerator.com).
2. Marque exatamente estes 4 escopos:
   - `channel:read:redemptions` (ouvir resgates)
   - `channel:manage:redemptions` (necessário para o estorno automático de pontos)
   - `user:write:chat` (enviar anúncios no chat)
   - `user:read:chat` (ouvir comandos dos moderadores)
3. Clique em **Generate Token** e autorize com a sua conta da Twitch.
4. Abra o arquivo `bot_soundpad.py` no Notepad++ e cole seu **Client ID** e **Access Token** no topo:
   ```python
   CLIENT_ID = "SEU_CLIENT_ID_AQUI"
   ACCESS_TOKEN = "SEU_ACCESS_TOKEN_AQUI"
   ```

#### 3. Configurar os Resgates de Pontos na Twitch
* **Recompensas Automáticas gerenciadas pela API**: Ao iniciar o script pela primeira vez com o token configurado, o próprio bot cria as recompensas `Buscar Meme` (200 pts) e `Parar Som` (1000 pts) na Twitch para garantir permissão de estorno automático. *(Caso já as tenha criado manualmente antes pelo site da Twitch, exclua-as pelo painel para que o bot possa recriá-las via API).*
   - *(Opcional)*: Você pode personalizar a quantidade de pontos dessas recompensas alterando as variáveis `SEARCH_REWARD_COST` e `STOP_REWARD_COST` no início do `bot_soundpad.py`.
* **`Som Aleatório`**: Crie como resgate padrão comum no painel da Twitch.
* **Sons Específicos** *(Opcional)*: Se quiser criar resgates fixos para memes específicos, use na Twitch o **mesmo nome** cadastrado no `REWARDS_MAP` do script, apontando para o número do ID no Soundpad.  
  Exemplo de configuração no `bot_soundpad.py` (cada som em sua própria linha):
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

#### 5. Iniciar o Bot
1. Abra o **Soundpad** (certifique-se de que a lista de sons esteja salva).
2. Dê dois cliques em **`iniciar_bot.bat`**.
3. Uma janela abrirá mostrando a quantidade de sons carregados, as recompensas gerenciadas verificadas e a conexão confirmada com a Twitch.

**Desenvolvido por Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) com ajuda de:**
* Versão 1.0 e 1.0.1: Gemini-3.8-Flash.

---

## 🇺🇸 English Version

A lightweight local Python bot integrating Twitch Channel Point rewards with Soundpad via Named Pipes, featuring real audio playback queues based on track length, automatic point refunds, keyword meme search, and real-time pop-up overlays for OBS Studio.

### 🚀 Features

- **Direct Memory IPC**: Direct communication using Soundpad's local named pipe (`sp_remote_control`), working regardless of installation folder or drive letter.
- **Custom Soundlist Path Support**: Allows directly targeting custom list locations or backup files (e.g., `CUSTOM_SPL_PATH`), alongside default auto-detection.
- **True Sound Queue**: Detects exact audio length and only starts the next sound after the current one finishes.
- **Manual Stop Detection**: If the broadcaster stops playback manually within Soundpad, the bot detects it immediately and advances the queue.
- **Meme Search by Keyword**: Viewers redeem with user input; the bot scans the library and plays the closest match.
- **Automatic Point Refunds**: Automatically cancels redemptions and refunds channel points if a searched meme is not found or if *Stop Sound* is used while nothing is playing.
- **Per-User Anti-Spam / Cooldown**: Prevents point-rich viewers from rapid-fire redeeming sounds consecutively.
- **Network Resilience**: Asynchronous network calls with socket timeouts to prevent freezing during internet or router hiccups.
- **Dynamic OBS Studio Overlay**: Outputs to `obs_tocando_agora.txt` matching the exact sound duration, clearing immediately when playback ends or is stopped.
- **Dynamic Chat Toggle**: Configuration flag (`ENABLE_CHAT_ANNOUNCEMENTS`) and chat command to toggle text notifications on/off if you prefer screen pop-ups only.
- **Moderator Chat Commands** (1 PT-BR and 1 EN-US pair per action):
  - `!pular` / `!skip`: Skips current sound and advances to the next queued item.
  - `!limpar` / `!clear`: Stops playback immediately and clears the entire queue.
  - `!recarregar` / `!reload`: Reloads the Soundpad library in memory without restarting the bot.
  - `!chat` / `!togglechat`: Toggles chat sound announcements on or off live.

---

### 📦 Prerequisites

1. **Python 3.8+** installed on Windows (ensure *Add Python to PATH* is checked).
2. **Soundpad** installed and running.
3. Install dependencies via terminal/command prompt:
   ```bash
   pip install websockets requests
   ```
4. Git to clone the repository (Optional).

---

### 🛠️ Step-by-Step Setup & Usage Guide

#### 1. Clone the Repository & Install Dependencies
Download the project Zip from the "< > CODE" button above **OR** open your terminal (Command Prompt or PowerShell) in your preferred folder:
```bash
git clone https://github.com/Y4SH1R01/SoundpadBotForTwitch.git
cd SoundpadBotForTwitch
pip install websockets requests
```

#### 2. Generate Twitch API Credentials
1. Visit [twitchtokengenerator.com](https://twitchtokengenerator.com).
2. Select these 4 required scopes:
   - `channel:read:redemptions` (listen to channel point redeems)
   - `channel:manage:redemptions` (required for automatic point refunds)
   - `user:write:chat` (send bot messages in chat)
   - `user:read:chat` (listen for mod chat commands)
3. Click **Generate Token** and authorize with your broadcaster Twitch account.
4. Open `bot_soundpad.py` in your text editor and paste your credentials at the top:
   ```python
   CLIENT_ID = "YOUR_CLIENT_ID_HERE"
   ACCESS_TOKEN = "YOUR_ACCESS_TOKEN_HERE"
   ```

#### 3. Setup Twitch Channel Point Rewards
* **Auto-Managed API Rewards**: On startup, the bot automatically creates the `Buscar Meme` (200 pts) and `Parar Som` (1000 pts) rewards on Twitch to ensure refund permissions. *(If you previously created rewards with these names manually on Twitch, delete them from your dashboard first so the bot can recreate them via API).*
   - *(Optional)*: You can customize the point cost of these rewards by editing `SEARCH_REWARD_COST` and `STOP_REWARD_COST` at the top of `bot_soundpad.py`.
* **`Som Aleatório`**: Create as a standard custom reward in your Twitch dashboard.
* **Specific Sounds** *(Optional)*: To create fixed rewards for specific sounds, make sure the reward title on Twitch matches the **exact name** defined in the `REWARDS_MAP` dictionary, mapped to its Soundpad index.  
  Configuration example in `bot_soundpad.py` (each entry on its own line):
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

#### 5. Run the Bot
1. Open **Soundpad** (ensure your sound list is saved).
2. Double-click **`iniciar_bot.bat`**.
3. A terminal window will open confirming the loaded sound count, verified managed rewards, and Twitch WebSocket connection.

---

**Dev'd by Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) with the help of:**
* Version 1.0 & 1.0.1: Gemini-3.8-Flash.

---

[Voltar ao topo / Back to top](#soundpadbotfortwitch)
