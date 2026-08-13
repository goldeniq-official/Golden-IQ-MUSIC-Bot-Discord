# -*- coding: utf-8 -*-
"""Player controller dispatch — the button and select handlers.

Extracted verbatim from modules/music/__init__.py, which had grown past
7,900 lines. This is the code path behind every player button, so isolating
it makes the part users touch most the part easiest to read.

PlayerControllerMixin is mixed into the Music cog. disnake collects
@Cog.listener across the MRO, so the listeners here register exactly as they
did when defined directly on the cog.
"""
from __future__ import annotations

import asyncio
from typing import Optional, Union

import disnake
from disnake.ext import commands

import wavelink
from utils.client import BotCore
from utils.db import DBModel
from utils.music.checks import can_connect, check_player_perm, is_dj
from utils.music.converters import URL_REG, fix_characters, time_format
from utils.music.errors import GenericError
from utils.music.interactions import SelectInteraction
from utils.music.models import LavalinkPlayer
from utils.others import PlayerControls, check_cmd, music_source_emoji_url, send_idle_embed


class PlayerControllerMixin:
    """Button, select, and dispatch handling for the music player."""

    async def process_player_interaction(
            self,
            interaction: Union[disnake.MessageInteraction, disnake.ModalInteraction],
            command: Optional[disnake.ApplicationCommandInteraction],
            kwargs: dict
    ):

        if not command:
            raise GenericError("command not found/implemented.")

        try:
            interaction.application_command = command
            await command._max_concurrency.acquire(interaction)
        except AttributeError:
            pass

        await check_cmd(command, interaction)

        await command(interaction, **kwargs)

        try:
            await command._max_concurrency.release(interaction)
        except:
            pass

        try:
            player: LavalinkPlayer = self.bot.music.players[interaction.guild_id]
            player.interaction_cooldown = True
            await asyncio.sleep(1)
            player.interaction_cooldown = False
        except (KeyError, AttributeError):
            pass
    @commands.Cog.listener("on_dropdown")
    async def player_dropdown_event(self, interaction: disnake.MessageInteraction):

        if interaction.data.custom_id == "musicplayer_queue_dropdown":
            await self.process_player_interaction(
                interaction=interaction, command=self.bot.get_slash_command("skipto"),
                kwargs={"query": interaction.values[0][3:], "case_sensitive": True}
            )
            return

        if not interaction.data.custom_id.startswith("musicplayer_dropdown_"):
            return

        if not interaction.values:
            await interaction.response.defer()
            return

        await self.player_controller(interaction, interaction.values[0])
    @commands.Cog.listener("on_button_click")
    async def player_button_event(self, interaction: disnake.MessageInteraction):

        if not interaction.data.custom_id.startswith("musicplayer_"):
            return

        await self.player_controller(interaction, interaction.data.custom_id)
    async def check_stage_title(self, inter, bot: BotCore, player: LavalinkPlayer):

        time_limit = 30 if isinstance(player.guild.me.voice.channel, disnake.VoiceChannel) else 120

        if player.stage_title_event and (time_:=int((disnake.utils.utcnow() - player.start_time).total_seconds())) < time_limit and not (await bot.is_owner(inter.author)):
            raise GenericError(
                f"**You will have to wait {time_format((time_limit - time_) * 1000, use_names=True)} to use this function "
                f"with the automatic stage announcement active...**"
            )
    async def player_controller(self, interaction: disnake.MessageInteraction, control: str, **kwargs):

        if not self.bot.bot_ready or not self.bot.is_ready():
            await interaction.send("I'm still initializing...", ephemeral=True)
            return

        if not interaction.guild_id:
            await interaction.response.edit_message(components=None)
            return

        cmd_kwargs = {}

        cmd: Optional[disnake.ApplicationCommandInteraction] = None

        if control in (
                PlayerControls.embed_forceplay,
                PlayerControls.embed_enqueue_track,
                PlayerControls.embed_enqueue_playlist,
        ):

            try:
                # Resolve the track URL from the source embed. Every failure
                # path here must tell the user something: returning silently
                # leaves the interaction unacknowledged, and Discord shows
                # "This interaction failed" after 3 seconds (or the button
                # simply looks dead). Reachable in normal use when the embed
                # was edited, has no description, or the message lost its
                # embeds entirely.
                try:
                    embed = interaction.message.embeds[0]
                except (IndexError, AttributeError):
                    raise GenericError(
                        "**រកមិនឃើញព័ត៌មានបទចម្រៀងក្នុងសារនេះទេ សូមព្យាយាមម្ដងទៀត។ / "
                        "The track information is missing from this message — please try again.**"
                    )

                url = getattr(embed.author, "url", None)

                if not url:
                    matches = URL_REG.findall(embed.description or "")
                    if not matches:
                        raise GenericError(
                            "**រកមិនឃើញតំណបទចម្រៀងក្នុងសារនេះទេ។ / "
                            "No track link was found in this message.**"
                        )
                    url = matches[0].split(">")[0]

                try:
                    await self.player_interaction_concurrency.acquire(interaction)
                except:
                    raise GenericError("A song is currently being processed...")

                bot: Optional[BotCore] = None
                player: Optional[LavalinkPlayer] = None
                channel: Union[disnake.TextChannel, disnake.VoiceChannel, disnake.StageChannel, disnake.Thread] = None
                author: Optional[disnake.Member] = None

                for b in sorted(self.bot.pool.get_guild_bots(interaction.guild_id), key=lambda b: b.identifier, reverse=True):

                    try:
                        p = b.music.players[interaction.guild_id]
                    except KeyError:
                        if c := b.get_channel(interaction.channel_id):
                            bot = b
                            channel = c
                            author = c.guild.get_member(interaction.author.id)
                        continue

                    if p.guild.me.voice and interaction.author.id in p.guild.me.voice.channel.voice_states:

                        if p.locked:
                            raise GenericError(
                                "**It is not possible to perform this action while the song is being processed "
                                "(please wait a few more seconds and try again).**")

                        player = p
                        bot = b
                        channel = player.text_channel
                        author = p.guild.get_member(interaction.author.id)
                        break

                if not channel:
                    raise GenericError("There are no bots available at the moment.")

                if not author.voice:
                    raise GenericError("You must join a voice channel to use this button....")

                try:
                    node = player.node
                except:
                    node: Optional[wavelink.Node] = None

                try:
                    interaction.author = author
                except AttributeError:
                    pass

                await check_player_perm(inter=interaction, bot=bot, channel=interaction.channel)

                vc_id: int = author.voice.channel.id

                can_connect(channel=author.voice.channel, guild=channel.guild)

                await interaction.response.defer()

                if control == PlayerControls.embed_enqueue_playlist:

                    if (retry_after := self.bot.pool.enqueue_playlist_embed_cooldown.get_bucket(interaction).update_rate_limit()):
                        raise GenericError(
                            f"**You will have to wait {(rta:=int(retry_after))} second{'s'[:rta^1]} to add a playlist to the current player.**")

                    if not player:
                        player = await self.create_player(inter=interaction, bot=bot, guild=channel.guild,
                                                          channel=channel, node=node)

                    await self.check_player_queue(interaction.author, bot, interaction.guild_id)
                    result, node = await self.get_tracks(url, interaction, author, source=False, node=player.node, bot=bot)
                    result = await self.check_player_queue(interaction.author, bot, interaction.guild_id, tracks=result)
                    player.queue.extend(result.tracks)
                    await interaction.send(f"{interaction.author.mention}, the playlist [`{result.name}`](<{url}>) was added successfully!{player.controller_link}", ephemeral=True)

                    if not player.is_connected:
                        await player.connect(vc_id)

                    try:
                        vc = interaction.author.voice.channel
                    except AttributeError:
                        vc = player.bot.get_channel(vc_id)

                    if isinstance(vc, disnake.StageChannel):

                        retries = 5

                        while retries > 0:

                            await asyncio.sleep(1)

                            if not player.guild.me.voice:
                                retries -= 1
                                continue

                            break

                        if player.guild.me not in vc.speakers:
                            stage_perms = vc.permissions_for(player.guild.me)
                            if stage_perms.manage_permissions:
                                await asyncio.sleep(1.5)
                                await player.guild.me.edit(suppress=False)

                    if not player.current:
                        await player.process_next()

                else:

                    track = []
                    seek_status = False

                    if player:

                        if control == PlayerControls.embed_forceplay and player.current and (player.current.uri.startswith(url) or url.startswith(player.current.uri)):
                            await self.check_stage_title(inter=interaction, bot=bot, player=player)
                            await player.seek(0)
                            player.set_command_log("went back to the beginning of the song.", emoji="⏪")
                            await asyncio.sleep(3)
                            await player.update_stage_topic()
                            await asyncio.sleep(7)
                            seek_status = True

                        else:

                            for t in list(player.queue):
                                if t.uri.startswith(url) or url.startswith(t.uri):
                                    track = [t]
                                    player.queue.remove(t)
                                    break

                            if not track:
                                for t in list(player.played):
                                    if t.uri.startswith(url) or url.startswith(t.uri):
                                        track = [t]
                                        player.played.remove(t)
                                        break

                                if not track:

                                    for t in list(player.failed_tracks):
                                        if t.uri.startswith(url) or url.startswith(t.uri):
                                            track = [t]
                                            player.failed_tracks.remove(t)
                                            break

                    if not seek_status:

                        if not track:

                            if (retry_after := self.bot.pool.enqueue_track_embed_cooldown.get_bucket(interaction).update_rate_limit()):
                                raise GenericError(
                                    f"**You will have to wait {(rta:=int(retry_after))} segundo{'s'[:rta^1]} to add a new song to the queue.**")

                            if control == PlayerControls.embed_enqueue_track:
                                await self.check_player_queue(interaction.author, bot, interaction.guild_id)

                            result, node = await self.get_tracks(url, interaction, author, source=False, node=node, bot=bot)

                            track = result

                        if control == PlayerControls.embed_enqueue_track:

                            if not player:
                                player = await self.create_player(inter=interaction, bot=bot, guild=channel.guild,
                                                                  channel=channel, node=node)
                            await self.check_player_queue(interaction.author, bot, interaction.guild_id)
                            player.update = True
                            if isinstance(track, list):
                                t = track[0]
                                player.queue.append(t)
                                await interaction.send(
                                    f"{author.mention}, song [`{t.title}`](<{t.uri}>) was added to the queue.{player.controller_link}",
                                    ephemeral=True)
                            else:
                                player.queue.extend(track.tracks)
                                await interaction.send(
                                    f"{author.mention}, a playlist [`{track.name}`](<{track.url}>) foi adicionada na fila.{player.controller_link}",
                                    ephemeral=True)
                            if not player.is_connected:
                                await player.connect(vc_id)
                            if not player.current:
                                await player.process_next()

                        else:
                            if not player:
                                player = await self.create_player(inter=interaction, bot=bot, guild=channel.guild,
                                                                  channel=channel, node=node)
                            else:
                                await self.check_stage_title(inter=interaction, bot=bot, player=player)

                            if isinstance(track, list):
                                player.queue.insert(0, track[0])
                            else:
                                index = len(player.queue)
                                player.queue.extend(track.tracks)
                                if index:
                                    player.queue.rotate(index * -1)
                            if not player.is_connected:
                                await player.connect(vc_id)
                            await self.process_music(inter=interaction, player=player, force_play="yes")

            except Exception as e:
                self.bot.dispatch('interaction_player_error', interaction, e)
                if not isinstance(e, GenericError):
                    await asyncio.sleep(5)
            try:
                await self.player_interaction_concurrency.release(interaction)
            except:
                pass
            return

        if control == PlayerControls.embed_add_fav:

            try:
                embed = interaction.message.embeds[0]
            except IndexError:
                await interaction.send("The message embed was removed...", ephemeral=True)
                return

            if (retry_after := self.bot.pool.add_fav_embed_cooldown.get_bucket(interaction).update_rate_limit()):
                await interaction.send(
                    f"**You will have to wait {(rta:=int(retry_after))} segundo{'s'[:rta^1]} to add a new favorite.**",
                    ephemeral=True)
                return

            await interaction.response.defer()

            user_data = await self.bot.get_global_data(interaction.author.id, db_name=DBModel.users)

            if self.bot.config["MAX_USER_FAVS"] > 0 and not (await self.bot.is_owner(interaction.author)):

                if (current_favs_size := len(user_data["fav_links"])) > self.bot.config["MAX_USER_FAVS"]:
                    await interaction.edit_original_message(f"The number of items in your favorites file exceeds "
                                                            f"the maximum allowed amount ({self.bot.config['MAX_USER_FAVS']}).")
                    return

                if (current_favs_size + (user_favs := len(user_data["fav_links"]))) > self.bot.config["MAX_USER_FAVS"]:
                    await interaction.edit_original_message(
                        "You don't have enough space to add all the favorites from your file...\n"
                        f"Current limit: {self.bot.config['MAX_USER_FAVS']}\n"
                        f"Number of saved favorites: {user_favs}\n"
                        f"You need: {(current_favs_size + user_favs) - self.bot.config['MAX_USER_FAVS']}")
                    return

            fav_name = embed.author.name[1:]

            user_data["fav_links"][fav_name] = embed.author.url

            await self.bot.update_global_data(interaction.author.id, user_data, db_name=DBModel.users)

            global_data = await self.bot.get_global_data(interaction.guild_id, db_name=DBModel.guilds)

            try:
                cmd = f"</play:" + str(self.bot.get_global_command_named("play",
                                                                                             cmd_type=disnake.ApplicationCommandType.chat_input).id) + ">"
            except AttributeError:
                cmd = "/play"

            try:
                interaction.message.embeds[0].fields[0].value = f"{interaction.author.mention} " + \
                                                                interaction.message.embeds[0].fields[0].value.replace(
                                                                    interaction.author.mention, "")
            except IndexError:
                interaction.message.embeds[0].add_field(name="**Members who favorited the link:**",
                                                        value=interaction.author.mention)

            await interaction.send(embed=disnake.Embed(
                description=f"[`{fav_name}`](<{embed.author.url}>) **was added to your favorites!**\n\n"
                            "**How to use?**\n"
                            f"* Using the command {cmd} (selecting the favorite in the search autocomplete)\n"
                            "* Clicking the play favorite/integration button/select in the player.\n"
                            f"* Using the command {global_data['prefix'] or self.bot.default_prefix}{self.play_legacy.name} without including a song name or link.\n"


            ).set_footer(text=f"To see all your favorites use the command {global_data['prefix'] or self.bot.default_prefix}{self.fav_manager_legacy.name}"), ephemeral=True)

            if not interaction.message.flags.ephemeral:
                if not interaction.guild:
                    await (await interaction.original_response()).edit(embed=interaction.message.embeds[0])
                else:
                    await interaction.message.edit(embed=interaction.message.embeds[0])
            return

        if not interaction.guild:
            await interaction.response.edit_message(components=None)
            return

        try:

            if control == "musicplayer_request_channel":
                cmd = self.bot.get_slash_command("setup")
                cmd_kwargs = {"target": interaction.channel}
                await self.process_player_interaction(interaction, cmd, cmd_kwargs)
                return

            if control == PlayerControls.fav_manager:

                if str(interaction.user.id) not in interaction.message.content:
                    await interaction.send("You cannot interact here!", ephemeral=True)
                    return

                cmd = self.bot.get_slash_command("fav_manager")
                await self.process_player_interaction(interaction, cmd, cmd_kwargs)
                return

            if control in (PlayerControls.add_song, PlayerControls.enqueue_fav):

                if not interaction.user.voice:
                    raise GenericError("**You must join a voice channel to use this button.**")

                user_data = await self.bot.get_global_data(id_=interaction.user.id, db_name=DBModel.users)

                modal_components = []

                if user_data["fav_links"]:

                    fav_opts = []

                    for k, v in list(user_data["fav_links"].items())[:25]:
                        emoji, platform = music_source_emoji_url(v)
                        fav_opts.append(
                            disnake.SelectOption(
                                label=fix_characters(k, 35),
                                value=f"> fav: {k}",
                                description=f"⭐ -> {platform}",
                                emoji=emoji
                            )
                        )

                    modal_components.append(
                        disnake.ui.Label(
                            text="⭐⠂Favorites:",
                            component=disnake.ui.StringSelect(
                                options=fav_opts, required=False, min_values=0, custom_id="fav_links"
                            )
                        ),
                    )

                if user_data["integration_links"]:

                    integration_opts = []

                    update = False

                    for k, v in list(user_data["integration_links"].items())[:25]:

                        if not isinstance(v, dict):
                            v = {"url": v, "avatar": None}
                            user_data["integration_links"][k] = v
                            update = True

                        emoji, platform = music_source_emoji_url(v["url"])

                        integration_opts.append(
                            disnake.SelectOption(
                                label=fix_characters(k[6:], 35),
                                value=f"> itg: {k}",
                                description=f"💠 -> {platform}",
                                emoji=emoji
                            )
                        )

                    modal_components.append(
                        disnake.ui.Label(
                            text="💠⠂Integrations:",
                            component=disnake.ui.StringSelect(
                                options=integration_opts, required=False, min_values=0, custom_id="integration_links"
                            )
                        )
                    )

                    if update:
                        await self.bot.update_global_data(interaction.author.id, user_data, db_name=DBModel.users)

                modal_components = [
                   disnake.ui.Label(
                       text="Song name or link (YT/Spotify/SoundCloud)",
                       component=disnake.ui.TextInput(
                           custom_id="song_input", max_length=150, required=not modal_components
                       )
                   ),
                   disnake.ui.Label(
                       text="Queue position (number).",
                       component=disnake.ui.TextInput(
                           custom_id="song_position", max_length=3, required=False
                       )
                   )
                ] + modal_components

                await interaction.response.send_modal(
                    title="Request a song",
                    custom_id="modal_add_song" + (f"_{interaction.message.id}" if interaction.message.thread else ""),
                    components=modal_components
                )

                return

            if control == PlayerControls.lastfm_scrobble:
                await interaction.response.defer(ephemeral=True, with_message=True)
                user_data = await self.bot.get_global_data(interaction.author.id, db_name=DBModel.users)

                if not user_data["lastfm"]["sessionkey"]:
                    try:
                        cmd = f"</lastfm:" + str(self.bot.get_global_command_named("lastfm",
                                                                                 cmd_type=disnake.ApplicationCommandType.chat_input).id) + ">"
                    except AttributeError:
                        cmd = "/lastfm"

                    await interaction.edit_original_message(
                        content=f"You do not have a Last.fm account linked in my data. "
                                f"You can link a Last.fm account using the command {cmd}."
                    )
                    return

                user_data["lastfm"]["scrobble"] = not user_data["lastfm"]["scrobble"]
                self.bot.pool.lastfm_sessions[interaction.author.id] = user_data["lastfm"]
                await self.bot.update_global_data(interaction.author.id, user_data, db_name=DBModel.users)
                await interaction.edit_original_message(
                    embed=disnake.Embed(
                        description=f'**Song scrobbling has been {"enabled" if user_data["lastfm"]["scrobble"] else "disabled"} for the account: [{user_data["lastfm"]["username"]}](<https://www.last.fm/user/{user_data["lastfm"]["username"]}>).**',
                        color=self.bot.get_color()
                    )
                )
                return

            try:
                player: LavalinkPlayer = self.bot.music.players[interaction.guild_id]
            except KeyError:
                await interaction.send("There is no active player on the server...", ephemeral=True)
                await send_idle_embed(interaction.message, bot=self.bot)
                return

            if interaction.message != player.message:
                if control != PlayerControls.queue:
                    return

            if player.interaction_cooldown:
                raise GenericError("The player is on cooldown, please try again shortly.")

            try:
                vc = player.guild.me.voice.channel
            except AttributeError:
                await player.destroy(force=True)
                return

            if control == PlayerControls.help_button:
                embed = disnake.Embed(
                    description="📘 **BUTTON INFORMATION** 📘\n\n"
                                "⏯️ `= Pause/Resume the song.`\n"
                                "⏮️ `= Go back to the previously played song.`\n"
                                "⏭️ `= Skip to the next song.`\n"
                                "🔀 `= Shuffle the songs in the queue.`\n"
                                "🎶 `= Add song/playlist/favorite.`\n"
                                "⏹️ `= Stop the player and disconnect me from the channel.`\n"
                                "📑 `= Display the music queue.`\n"
                                "🛠️ `= Change some player settings:`\n"
                                "`volume / nightcore effect / loop / restricted mode.`\n",
                    color=self.bot.get_color(interaction.guild.me)
                )

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if not interaction.author.voice or interaction.author.voice.channel != vc:
                raise GenericError(f"You must be in channel <#{vc.id}> to use the player buttons.")

            if control == PlayerControls.miniqueue:
                await is_dj().predicate(interaction)
                player.mini_queue_enabled = not player.mini_queue_enabled
                player.set_command_log(
                    emoji="📑",
                    text=f"{interaction.author.mention} {'enabled' if player.mini_queue_enabled else 'disabled'} "
                         f"the player's mini-queue."
                )
                await player.invoke_np(interaction=interaction)
                return

            if control != PlayerControls.queue:
                try:
                    await self.player_interaction_concurrency.acquire(interaction)
                except commands.MaxConcurrencyReached:
                    raise GenericError(
                        "**You have an open interaction!**\n`If it's a hidden message, avoid clicking \"dismiss\".`")

            if control == PlayerControls.add_favorite:

                if not player.current:
                    await interaction.send("**There is no song playing currently...**", ephemeral=True)
                    return

                choices = {}
                msg = ""

                if player.current.uri:
                    choices["Track"] = {
                        "name": player.current.title,
                        "url": player.current.uri,
                        "emoji": "🎵"
                    }
                    msg += f"**Song:** [`{player.current.title}`]({player.current.uri})\n"

                if player.current.album_url:
                    choices["Album"] = {
                        "name": player.current.album_name,
                        "url": player.current.album_url,
                        "emoji": "💽"
                    }
                    msg += f"**Album:** [`{player.current.album_name}`]({player.current.album_url})\n"

                if player.current.playlist_url:
                    choices["Playlist"] = {
                        "name": player.current.playlist_name,
                        "url": player.current.playlist_url,
                        "emoji": e("queue")
                    }
                    msg += f"**Playlist:** [`{player.current.playlist_name}`]({player.current.playlist_url})\n"

                if not choices:
                    try:
                        await self.player_interaction_concurrency.release(interaction)
                    except:
                        pass
                    await interaction.send(
                        embed=disnake.Embed(
                            color=self.bot.get_color(interaction.guild.me),
                            description="### There are no items to favorite from the current song."
                        ), ephemeral=True
                    )
                    return

                if len(choices) == 1:
                    select_type, info = list(choices.items())[0]

                else:
                    view = SelectInteraction(
                        user=interaction.author, timeout=30,
                        opts=[disnake.SelectOption(label=k, description=v["name"][:50], emoji=v["emoji"]) for k,v in choices.items()]
                    )

                    await interaction.send(
                        embed=disnake.Embed(
                            color=self.bot.get_color(interaction.guild.me),
                            description=f"### Select an item from the current song to add to your favorites:"
                                        f"\n\n{msg}"
                        ), view=view, ephemeral=True
                    )

                    await view.wait()

                    select_interaction = view.inter

                    if not select_interaction or view.selected is False:
                        try:
                            await self.player_interaction_concurrency.release(interaction)
                        except:
                            pass
                        await interaction.edit_original_message(
                            embed=disnake.Embed(
                                color=self.bot.get_color(interaction.guild.me),
                                description="### Operation cancelled!"
                            ), view=None
                        )
                        return

                    interaction = select_interaction

                    select_type = view.selected
                    info = choices[select_type]

                await interaction.response.defer()

                user_data = await self.bot.get_global_data(interaction.author.id, db_name=DBModel.users)

                if self.bot.config["MAX_USER_FAVS"] > 0 and not (await self.bot.is_owner(interaction.author)):

                    if len(user_data["fav_links"]) >= self.bot.config["MAX_USER_FAVS"]:
                        await interaction.edit_original_message(
                            embed=disnake.Embed(
                                color=self.bot.get_color(interaction.guild.me),
                                description="You don't have enough space to add all the favorites from your file...\n"
                                            f"Current limit: {self.bot.config['MAX_USER_FAVS']}"
                            ), view=None)
                        return

                user_data["fav_links"][fix_characters(info["name"], self.bot.config["USER_FAV_MAX_URL_LENGTH"])] = info["url"]

                await self.bot.update_global_data(interaction.author.id, user_data, db_name=DBModel.users)

                self.bot.dispatch("fav_add", interaction.user, user_data, f"[`{info['name']}`]({info['url']})")

                global_data = await self.bot.get_global_data(interaction.author.id, db_name=DBModel.guilds)

                try:
                    slashcmd = f"</play:" + str(self.bot.get_global_command_named("play", cmd_type=disnake.ApplicationCommandType.chat_input).id) + ">"
                except AttributeError:
                    slashcmd = "/play"

                await interaction.edit_original_response(
                    embed=disnake.Embed(
                        color=self.bot.get_color(interaction.guild.me),
                        description="### Item added/edited successfully in your favorites:\n\n"
                                    f"**{select_type}:** [`{info['name']}`]({info['url']})\n\n"
                                    f"### How to use?\n"
                                    f"* Using the command {slashcmd} (in the search autocomplete)\n"
                                    f"* Clicking the play favorite/integration button/select in the player.\n"
                                    f"* Using the command {global_data['prefix'] or self.bot.default_prefix}{self.play_legacy.name} without including a song/video name or link."
                    ), view=None
                )

                try:
                    await self.player_interaction_concurrency.release(interaction)
                except:
                    pass

                return

            if control == PlayerControls.lyrics:
                if not player.current:
                    try:
                        await self.player_interaction_concurrency.release(interaction)
                    except:
                        pass
                    await interaction.send("**I am not playing anything at the moment...**", ephemeral=True)
                    return

                if not player.current.ytid:
                    try:
                        await self.player_interaction_concurrency.release(interaction)
                    except:
                        pass
                    await interaction.send("Only YouTube songs are supported at the moment.", ephemeral=True)
                    return

                not_found_msg = "There are no lyrics available for the current song..."

                await interaction.response.defer(ephemeral=True, with_message=True)

                if player.current.info["extra"].get("lyrics") is None:
                    lyrics_data = await player.node.fetch_ytm_lyrics(player.current.ytid)
                    player.current.info["extra"]["lyrics"] = {} if lyrics_data.get("track") is None else lyrics_data

                elif not player.current.info["extra"]["lyrics"]:
                    try:
                        await self.player_interaction_concurrency.release(interaction)
                    except:
                        pass
                    await interaction.edit_original_message(f"**{not_found_msg}**")
                    return

                if not player.current.info["extra"]["lyrics"]:
                    try:
                        await self.player_interaction_concurrency.release(interaction)
                    except:
                        pass
                    await interaction.edit_original_message(f"**{not_found_msg}**")
                    return

                album_art = player.current.info["extra"]["lyrics"]["track"].get("albumArt")
                if album_art:
                    player.current.info["extra"]["lyrics"]["track"]["albumArt"] = album_art[:-1]

                try:
                    lyrics_string = "\n".join([d['line'] for d in  player.current.info["extra"]["lyrics"]['lines']])
                except KeyError:
                    lyrics_string = player.current.info["extra"]["lyrics"]["text"]

                try:
                    await self.player_interaction_concurrency.release(interaction)
                except:
                    pass

                # Discord caps embed description at 4096 characters; lyrics
                # routinely exceed that. Paginate into ~900-char chunks at
                # blank-line boundaries so each page reads cleanly on mobile.
                color = self.bot.get_color(player.guild.me)
                header = f"### Song lyrics: [{player.current.title}](<{player.current.uri}>)"

                LYRIC_PAGE_TARGET = 900
                if len(lyrics_string) <= LYRIC_PAGE_TARGET:
                    pages = [lyrics_string]
                else:
                    pages = []
                    current = []
                    current_len = 0
                    for paragraph in lyrics_string.split("\n\n"):
                        if current_len + len(paragraph) + 2 > LYRIC_PAGE_TARGET and current:
                            pages.append("\n\n".join(current))
                            current = [paragraph]
                            current_len = len(paragraph)
                        else:
                            current.append(paragraph)
                            current_len += len(paragraph) + 2
                    if current:
                        pages.append("\n\n".join(current))

                lyric_embeds = []
                for n, page in enumerate(pages, 1):
                    embed_desc = f"{header}\n{page}"
                    if len(pages) > 1:
                        embed_desc += f"\n\n-# Page {n} / {len(pages)}"
                    lyric_embeds.append(disnake.Embed(description=embed_desc, color=color))

                if len(lyric_embeds) == 1:
                    await interaction.edit_original_message(embed=lyric_embeds[0])
                else:
                    from utils.music.ui.components import Paginator
                    view = Paginator(interaction.author, embeds=lyric_embeds, timeout=300)
                    msg = await interaction.edit_original_message(embed=lyric_embeds[0], view=view)
                    view.message = msg
                return

            if control == PlayerControls.volume:
                cmd_kwargs = {"value": None}

            elif control == PlayerControls.queue:
                cmd = self.bot.get_slash_command("queue").children.get("display")

            elif control == PlayerControls.shuffle:
                cmd = self.bot.get_slash_command("queue").children.get("shuffle")

            elif control == PlayerControls.seek_to_start:
                cmd = self.bot.get_slash_command("seek")
                cmd_kwargs = {"position": "0"}

            elif control == PlayerControls.pause_resume:
                control = PlayerControls.pause if not player.paused else PlayerControls.resume

            elif control == PlayerControls.loop_mode:

                if player.loop == "current":
                    cmd_kwargs['mode'] = 'queue'
                elif player.loop == "queue":
                    cmd_kwargs['mode'] = 'off'
                else:
                    cmd_kwargs['mode'] = 'current'

            elif control == PlayerControls.skip:
                cmd_kwargs = {"query": None, "play_only": "no"}

            if not cmd:
                cmd = self.bot.get_slash_command(control[12:])

            await self.process_player_interaction(
                interaction=interaction,
                command=cmd,
                kwargs=cmd_kwargs
            )

            try:
                await self.player_interaction_concurrency.release(interaction)
            except:
                pass

        except Exception as e:
            try:
                await self.player_interaction_concurrency.release(interaction)
            except:
                pass
            self.bot.dispatch('interaction_player_error', interaction, e)
