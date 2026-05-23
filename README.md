# Golden IQ MUSIC

## A music bot written in Python featuring an interactive player, slash commands, [last.fm](https://www.last.fm/) integration, and much more.

### Some Previews:

- Player controller: normal/mini-player mode (skin: default) with [RPC (Rich Presence)](https://github.com/zRitsu/MuseHeart-MusicBot-RPC-app) support

[![](https://i.ibb.co/6tVbfFH/image.png)](https://i.ibb.co/6tVbfFH/image.png)

<details>
<summary>
More previews:
</summary>
<br>

- Slash commands

[![](https://i.ibb.co/nmhYWrK/muse-heart-slashcommands.png)](https://i.ibb.co/nmhYWrK/muse-heart-slashcommands.png)

- [last.fm](https://www.last.fm/) integration for scrobbles (more features coming soon).

[![](https://i.ibb.co/SXm608z/muse-heart-lastfm.png)](https://i.ibb.co/SXm608z/muse-heart-lastfm.png)

- Player controller: fixed/extended mode with song-request channel and chat (skin: default), configurable via the /setup command

[![](https://i.ibb.co/5cZ7JGs/image.png)](https://i.ibb.co/5cZ7JGs/image.png)

- Player controller: fixed/extended mode with a forum-based song-request channel with support for automatic status in voice and stage channels

[![](https://i.ibb.co/9Hm5cyG/playercontrollerforum.png)](https://i.ibb.co/9Hm5cyG/playercontrollerforum.png)

- There are many other skins available — see all of them with the /change_skin command (you can also create your own by using the default skins in the [skins](utils/music/skins/) folder as a reference: copy one, give it a new name, and modify it as you like).

</details>

---

<details>
<summary>
Hosting on your own PC/VPS (Windows/Linux)
</summary>
<br>

### Requirements:

- Python 3.9, 3.10, or 3.11<br/>
  [Download from the Microsoft Store](https://apps.microsoft.com/store/detail/9PJPW5LDXLZ5?hl=en-us&gl=US) (Recommended for Windows 10/11 users).<br/>
  [Direct download from the official site](https://www.python.org/downloads/release/python-3117/) (Check this option during installation: **Add python to the PATH**)
- [Git](https://git-scm.com/downloads) (Do not choose the portable version)</br>

- [JDK 17](https://www.azul.com/downloads) or higher (Not required to install manually on Windows and Linux — it is downloaded automatically)</br>

`Note: this source requires at least 512MB of RAM and 1GHz of CPU to run normally (when running Lavalink in the same instance as the bot, assuming the bot is private).`

### Starting the bot (quick guide):

- Download this source as a [zip](https://github.com/zRitsu/MuseHeart-MusicBot/archive/refs/heads/main.zip) and extract it (or use the command below in your terminal/cmd and open the folder):

```shell
git clone https://github.com/zRitsu/MuseHeart-MusicBot.git
```

- Double-click the file `source_setup.sh` (or just `setup` if Windows is hiding file extensions) and wait.</br>
  `If you are on Linux, run the following command in the terminal:`

```shell
bash source_setup.sh
```

- A file named **.env** will appear. Edit it and place the bot token in the appropriate field (you can also edit other settings in the same file to customize your bot).</br>
  `Note: If you haven't created a bot account,` [see this tutorial](https://www.youtube.com/watch?v=lfdmZQySTXE) `to create your bot and obtain the required token.`</br>`It is also highly recommended to use MongoDB — find the MONGO= field in the .env file and enter your MongoDB connection URL (if you don't have one,` [see this tutorial](https://www.youtube.com/watch?v=x1Gq5beRx9k)`).`
- To start the bot on Windows, double-click `source_start_win.bat`; on Linux, double-click `start.sh` or run:

```shell
bash source_start.sh
```

### Notes:

- To update your bot, double-click `update.sh` (Windows), or on Linux run:

```shell
bash source_update.sh
```

`When updating, there is a chance that any manual changes you have made will be lost (if this is not a fork of the original source).`<br/>

`Note: If running the source directly on a Windows machine (with Git installed), simply double-click the source_update.sh file.`

</details>

---

Note: there are more guides on the [wiki](https://github.com/zRitsu/MuseHeart-MusicBot/wiki).

### Important notes:

- You can use this source as a self-hosted alternative to run your own music bot for private use or for public servers you manage (where you have permission to add your own bot). However, distributing the bot publicly using this source is not recommended as it is not optimized to handle high server demand. If you choose to do so anyway, the bot must comply with the [license](/LICENSE) of the original source, and depending on where the bot is listed (e.g. bot lists), it may be flagged for using this source.

- It is recommended to use the current source without code modifications. If you want to make changes (especially adding new features), it is highly recommended that you have knowledge of Python, disnake, Lavalink, etc. If you also want to keep your modified source up to date with the base source, knowledge of Git (at least enough to perform a clean merge) is also recommended.

- Support will not be provided for modified versions of this source (except for custom skins), as it is updated frequently and modified versions tend to fall out of date quickly, making support difficult. Additionally, depending on the modification or implementation, unknown errors may be introduced, and the methods used to update the code typically undo those changes.

- If you want to post a video or tutorial using this source, you are completely free to do so as long as you comply with the terms mentioned in the paragraphs above.

---

### If you encounter any issues, please open an [issue](https://github.com/zRitsu/MuseHeart-MusicBot/issues) describing the problem.

## Special thanks and credits:

- [DisnakeDev](https://github.com/DisnakeDev) (disnake) and Rapptz for the original [discord.py](https://github.com/Rapptz/discord.py)
- [Pythonista Guild](https://github.com/PythonistaGuild) (wavelink)
- [Lavalink-Devs](https://github.com/lavalink-devs) (lavalink and lavaplayer)
- [DarrenOfficial](https://lavalink-list.darrennathanael.com/) Lavalink server list (Users who published their lavalink servers are listed in the about command along with their website/link).
- And to all members who helped greatly with bug reports (via [issues](https://github.com/zRitsu/MuseHeart-MusicBot/issues) and on the Discord server)
- Additional attributions can be found in the [dependency graph](https://github.com/zRitsu/MuseHeart-MusicBot/network/dependencies)
