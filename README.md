
<div align="center">

# SoundpadBotForTwitch
[![Versão](https://img.shields.io/badge/Versão-1.0-brightgreen)]()
[![Licença](https://img.shields.io/badge/Licença-GPL--3.0-blue)]()
[![Status](https://img.shields.io/badge/Status-Ativo-success)]()

[🇧🇷 Versão em Português](#-versão-em-português) • [🇺🇸 English Version](#-english-version)

</div>

---

## 🇧🇷 Versão em Português

Bot local em Python que integra resgates de Pontos de Canal da Twitch ao Soundpad via Named Pipe, com fila dinâmica de reprodução, buscador por texto e pop-up em tempo real para OBS Studio.

### 🚀 Funcionalidades

- **Controle Direto via Memória**: Comunicação local via canal IPC do Soundpad (`sp_remote_control`), funcionando independente da pasta ou disco onde o software esteja instalado.
- **Fila Real de Áudios (Sound Queue)**: Detecta o término do áudio e só libera o próximo som da fila quando o anterior acabar.
- **Detecção de Parada Manual**: Se o streamer parar o som manualmente no Soundpad, o bot detecta e avança a fila imediatamente.
- **Buscador de Memes por Texto**: O viewer pode resgatar digitando uma palavra-chave; o bot busca na biblioteca e executa o som mais próximo.
- **Anti-Spam / Cooldown Individual**: Impede que um único viewer esvazie seus pontos acumulados spammando áudios em sequência.
- **Comandos de Chat para Moderadores**:
  - `!parar`, `!skip`, `!proximo`: Pula o som atual e avança a fila.
  - `!limpar`, `!limparfila`: Pára o som atual e esvazia toda a fila de espera.
- **Overlay no OBS**: Gera o arquivo `obs_tocando_agora.txt`, exibindo pop-up temporário na transmissão com o áudio atual e o autor do resgate.

---

### 📦 Pré-requisitos

1. **Python 3.8+** instalado no Windows (com a opção *Add Python to PATH* marcada).
2. **Soundpad** instalado e em execução.
3. Instalar as dependências via terminal:
   ```bash
   pip install websockets requests
   ```
4. Git pra clonar o projeto (Opcional)

---

### 🛠️ Passo a Passo: Como Configurar e Rodar o Bot

#### 1. Clonar o repositório e instalar dependências
Baixe o Zip do projeto no botão "< > CODE" acima **OU**

Abra o terminal (CMD ou PowerShell) na pasta onde deseja salvar o projeto:
```bash
git clone https://github.com/Y4SH1R01/SoundpadBotForTwitch.git
cd SoundpadBotForTwitch
pip install websockets requests
```

#### 2. Obter as credenciais da Twitch
1. Acesse o [twitchtokengenerator.com](https://twitchtokengenerator.com).
2. Marque exatamente estes 3 escopos:
   - `channel:read:redemptions`
   - `user:write:chat`
   - `user:read:chat`
3. Clique em **Generate Token** e autorize com a sua conta da Twitch.
4. Abra o arquivo `bot_soundpad.py` no Notepad++ e cole seu **Client ID** e **Access Token** no topo:
   ```python
   CLIENT_ID = "SEU_CLIENT_ID_AQUI"
   ACCESS_TOKEN = "SEU_ACCESS_TOKEN_AQUI"
   ```

#### 3. Criar os Resgates de Pontos na Twitch
No seu Painel de Criador da Twitch (*Recompensas de Espectador ➔ Pontos do Canal ➔ Gerenciar Recompensas*), crie os seguintes resgates:
- **`Som Aleatório`**: Resgate padrão comum.
- **`Buscar Meme`**: Marque a opção **"Exigir que o espectador insira texto"** (o viewer digita o nome do meme).
- **`Parar Som`**: Resgate padrão para pular o áudio atual.
  - **Sons Específicos** *(Opcional)*: Se quiser criar resgates fixos para memes específicos, use na Twitch o **mesmo nome** cadastrado no `REWARDS_MAP` do script, apontando para o número do ID no Soundpad.  
  Exemplo de configuração no `bot_soundpad.py` (cada som em sua própria linha):
  ```python
  REWARDS_MAP = {
      "Nome Exato 1": 123,
      "Nome Exato 2": 456,
  }
    
#### 4. Configurar o Pop-up no OBS Studio **(Opcional, só pra ter algo na tela da Stream caso vc prefire, isso vai ser uma opção futuramente entre aparecer no chat e na tela da stream.)**
1. No OBS, adicione uma fonte de **Texto (GDI+)** na sua cena.
2. Marque a caixa **Ler do arquivo** (*Read from file*).
3. Selecione o arquivo `obs_tocando_agora.txt` que está dentro da pasta do bot.
4. Defina a fonte como **Segoe UI Emoji** (para os ícones não virarem quadrados xd).

#### 5. Iniciar o Bot
1. Abra o **Soundpad** (certifique-se de que a lista de sons esteja salva).
2. Dê dois cliques em **`iniciar_bot.bat`**.
3. Uma janela abrirá mostrando a quantidade de sons carregados e a conexão confirmada com a Twitch.

**Desenvolvido por Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) com ajuda da:**
* Versão 1.0: Gemini-3.8-Flash.

---

## 🇺🇸 English Version

A lightweight local Python bot integrating Twitch Channel Point rewards with Soundpad via Named Pipes, featuring real audio playback queues, keyword meme search, and real-time pop-up overlays for OBS Studio.

### 🚀 Features

- **Direct Memory IPC**: Direct communication using Soundpad's local named pipe (`sp_remote_control`), working regardless of installation folder or drive letter.
- **True Sound Queue**: Detects exact audio length and only starts the next sound after the current one finishes.
- **Manual Stop Detection**: If the broadcaster stops playback manually within Soundpad, the bot detects it immediately and advances the queue.
- **Meme Search by Keyword**: Viewers can redeem with user input; the bot scans the library and plays the closest match.
- **Per-User Anti-Spam / Cooldown**: Prevents point-rich viewers from rapid-fire redeeming sounds consecutively.
- **Moderator Chat Commands**:
  - `!parar`, `!skip`, `!proximo`: Skips current sound and advances to the next queued item.
  - `!limpar`, `!limparfila`: Stops playback immediately and clears the entire queue.
- **OBS Studio Overlay**: Outputs to `obs_tocando_agora.txt`, creating a temporary pop-up on stream showing the current sound and redeemer.

---

### 📦 Prerequisites

1. **Python 3.8+** installed on Windows (ensure *Add Python to PATH* is checked).
2. **Soundpad** installed and running.
3. Install dependencies via terminal/command prompt:
   ```bash
   pip install websockets requests
   ```

---

### 🛠️ Step-by-Step Setup & Usage Guide

#### 1. Clone the Repository & Install Dependencies
Open your terminal (Command Prompt or PowerShell) where you want to keep the bot:
```bash
git clone https://github.com/Y4SH1R01/SoundpadBotForTwitch.git
cd SoundpadBotForTwitch
pip install websockets requests
```

#### 2. Generate Twitch API Credentials
1. Visit [twitchtokengenerator.com](https://twitchtokengenerator.com).
2. Select these 3 required scopes:
   - `channel:read:redemptions`
   - `user:write:chat`
   - `user:read:chat`
3. Click **Generate Token** and authorize with your broadcaster Twitch account.
4. Open `bot_soundpad.py` in your text editor and paste your credentials at the top:
   ```python
   CLIENT_ID = "YOUR_CLIENT_ID_HERE"
   ACCESS_TOKEN = "YOUR_ACCESS_TOKEN_HERE"
   ```

#### 3. Create Twitch Channel Point Rewards
In your Twitch Creator Dashboard (*Viewer Rewards ➔ Channel Points ➔ Manage Rewards*), create:
- **`Rnadom Sound`**: Standard custom reward.
- **`Search Meme`**: Check **"Require Viewer to Enter Text"** (viewers type the meme keyword).
- **`Stop Sound`**: Standard custom reward to skip current playback.
  - **Specific Sounds** *(Optional)*: To create fixed rewards for specific sounds, make sure the reward title on Twitch matches the **exact name** defined in the `REWARDS_MAP` dictionary, mapped to its Soundpad index.  
  Configuration example in `bot_soundpad.py` (each entry on its own line):
  ```python
  REWARDS_MAP = {
      "Exact Title 1": 123,
      "Exact Title 2": 456,
  }

#### 4. Configure the OBS Studio Pop-up Overlay **(Currently Optional, will add a option for this or chat notifs later)**
1. In OBS Studio, add a **Text (GDI+)** source to your active scene.
2. Check the **Read from file** box.
3. Browse and select `obs_tocando_agora.txt` (located in the bot root folder).
4. Select **Segoe UI Emoji** as the font to ensure proper emoji rendering.

#### 5. Run the Bot
1. Open **Soundpad** (ensure your sound list is saved).
2. Double-click **`iniciar_bot.bat`**.
3. A terminal window will open confirming the loaded sound count and Twitch WebSocket connection.

---

⚠️⚠️⚠️ WARNING:

- Support for English commands and renaming of files is almost not existent in the current version. IDK if it would be viable to add support for renaming but I will probably put more commands and make the AI add a English version of it for convenience. That's it for now.

**Dev'd by Mateus ([Y4SH1R01](https://github.com/Y4SH1R01)) with the help of:**
* Version 1.0: Gemini-3.8-Flash.

[Voltar ao topo / Back to top](#soundpadbotfortwitch)
