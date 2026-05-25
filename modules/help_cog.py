# -*- coding: utf-8 -*-
"""Golden IQ — Modernized help system.

Highlights:
    * Hybrid command: works as both ``/help`` (slash) and ``{prefix}help``.
    * Bilingual UI (Khmer + English) across labels, hints, and category names.
    * Lists slash commands alongside prefix commands so users discover both.
    * Category quick-link buttons in addition to the dropdown.
    * Built-in search modal — find a command without scrolling pages.
    * Brand-gold visuals via ``utils.music.ui.theme.BRAND_GOLD``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, Union

import disnake
from disnake.ext import commands

from utils.others import select_bot_pool  # used for slash-side resolution

from utils.music.errors import GenericError
from utils.music.ui.emoji_set import e
from utils.music.ui.theme import BRAND_GOLD, BRAND_GOLD_DEEP
from utils.others import CustomContext

if TYPE_CHECKING:
    from utils.client import BotCore


# --- Bilingual label registry --------------------------------------------------
#
# Most user-facing strings live here so a future translator can flip a single
# language flag instead of grep-replacing across the cog.
#
# Convention used throughout the embed text:  "ខ្មែរ / English"

L = {
    "menu_title":        "ឧបករណ៍ជំនួយ Golden IQ  /  Golden IQ Help",
    "categories":        "ប្រភេទពាក្យបញ្ជា / Categories",
    "tip":               "💡 **ព័ត៌មាន / Tip**",
    "tip_prefix":        "ប្រើ `{prefix}{cmd} <command>` ដើម្បីមើលលម្អិត។\n"
                         "Use `{prefix}{cmd} <command>` to view details.",
    "tip_slash":         "ឬប្រើ `/help` ដើម្បីបើកវាជា slash command។\n"
                         "Or use `/help` to open this as a slash command.",
    "tip_search":        "ចុចប៊ូតុង 🔍 **ស្វែងរក / Search** ខាងក្រោម។\n"
                         "Click the 🔍 **Search** button below.",
    "select_placeholder": "ជ្រើសរើសប្រភេទមួយ / Choose a category…",
    "btn_back":          "ត្រឡប់ / Back",
    "btn_search":        "ស្វែងរក / Search",
    "btn_close":         "បិទ / Close",
    "modal_search":      "ស្វែងរកពាក្យបញ្ជា / Search a command",
    "modal_search_lbl":  "វាយឈ្មោះពាក្យបញ្ជា / Type the command name",
    "no_results":        "រកមិនឃើញពាក្យបញ្ជានេះទេ / Command not found.",
    "cmd_details":       "ព័ត៌មានពាក្យបញ្ជា / Command Details",
    "aliases":           "ឈ្មោះក្រៅ / Aliases",
    "subcommands":       "ពាក្យបញ្ជារង / Subcommands",
    "how_to_use":        "របៀបប្រើ / How to Use",
    "flags":             "Flags",
    "available_as":      "មាននៅ / Available as",
    "slash":             "Slash",
    "prefix":            "Prefix",
    "owner_restricted":  "សម្រាប់ម្ចាស់ Bot តែប៉ុណ្ណោះ / Owner-only",
    "no_description":    "មិនមានការពិពណ៌នាទេ / No description.",
    "category_emoji":    "ប្រភេទ / Category",
    "page":              "ទំព័រ / Page",
    "of":                "នៃ / of",
    "only_user_can_use": "មានតែ {user} ទេដែលអាចប្រើជម្រើសទាំងនេះ / Only {user} can use these options.",
    "search_no_match":   "រកមិនឃើញពាក្យបញ្ជា **{query}** / Command **{query}** not found.",
}

CATEGORY_ICONS = {}


# --- Helpers ------------------------------------------------------------------

def _is_visible(cmd: commands.Command, owner_ok: bool) -> bool:
    """Hidden/owner commands shouldn't leak to regular users."""
    try:
        if cmd.hidden and not owner_ok:
            return False
    except AttributeError:
        return False
    return True


async def _filter_visible(ctx, cmds: Iterable[commands.Command]) -> List[commands.Command]:
    owner_ok = await ctx.bot.is_owner(ctx.author)
    return [c for c in cmds if _is_visible(c, owner_ok)]


def _has_slash(bot, cmd: commands.Command) -> bool:
    """True if a slash variant of ``cmd`` exists.

    Pattern used across the project: a prefix-side ``@commands.command``
    wrapper named ``<name>_legacy`` calls the real ``@commands.slash_command``
    body, so they share a name and behavior.
    """
    if bot.get_slash_command(cmd.qualified_name):
        return True
    return False


def _category_for(cmd: commands.Command) -> Tuple[str, str]:
    """Return ``(category_name, emoji)`` for a command using either an
    explicit ``cmd.category`` attribute or the cog's emoji/name pair."""
    if hasattr(cmd, "category") and cmd.category:
        return cmd.category, CATEGORY_ICONS.get(cmd.category, "📁")

    cog = cmd.cog
    if not cog or not hasattr(cog, "name") or len(cog.get_commands()) < 2:
        return "Miscellaneous", "🔰"

    emoji = getattr(cog, "emoji", None) or "📁"
    return cog.name, emoji


# --- Views --------------------------------------------------------------------

class SearchModal(disnake.ui.Modal):
    """Modal letting the user type a command name without scrolling pages."""

    def __init__(self, parent_view: "ViewHelp"):
        self.parent_view = parent_view
        super().__init__(
            title=L["modal_search"],
            custom_id=f"help_search_{parent_view.ctx.author.id}",
            components=[
                disnake.ui.TextInput(
                    label=L["modal_search_lbl"],
                    custom_id="cmd_name",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=64,
                    placeholder="play, queue, volume…",
                ),
            ],
        )

    async def callback(self, interaction: disnake.ModalInteraction):
        query = interaction.text_values["cmd_name"].strip().lower()
        cmd = self.parent_view.bot.get_command(query)
        if not cmd:
            slash = self.parent_view.bot.get_slash_command(query)
            if slash:
                cmd = self.parent_view.bot.get_command(slash.qualified_name) or cmd
        if not cmd or not _is_visible(cmd, await self.parent_view.bot.is_owner(self.parent_view.ctx.author)):
            await interaction.response.send_message(
                L["search_no_match"].format(query=query), ephemeral=True
            )
            return

        category, emoji = _category_for(cmd)
        # Make sure the chosen command's category is now selected so prev/next work.
        if category in self.parent_view.cmd_list:
            self.parent_view.category = category
            cmds = self.parent_view.cmd_list[category]["cmds"]
            try:
                self.parent_view.page_index = cmds.index(cmd)
            except ValueError:
                self.parent_view.page_index = 0
        else:
            self.parent_view.category = category
            self.parent_view.cmd_list[category] = {"emoji": emoji, "cmds": [cmd]}
            self.parent_view.page_index = 0

        self.parent_view.clear_items()
        self.parent_view.process_buttons()

        embed = await self.parent_view.get_cmd(
            ctx=self.parent_view.ctx,
            cmds=self.parent_view.cmd_list[category]["cmds"],
            index=self.parent_view.page_index,
            category=category,
            emoji=emoji,
        )
        self.parent_view.main_embed = embed
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class ViewHelp(disnake.ui.View):

    def __init__(self, ctx, items, *, bot, get_cmd, main_embed, cmd_list,
                 category_cmd=None, timeout=180):
        self.message: Optional[disnake.Message] = None
        self.page_index = 0
        self.cmd_list = cmd_list
        self.category = category_cmd
        self.get_cmd = get_cmd
        self.items = items
        self.ctx = ctx
        self.bot = bot
        self.main_embed = main_embed
        self.first_embed = main_embed
        super().__init__(timeout=timeout)
        self.process_buttons()

    async def interaction_check(self, interaction: disnake.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                L["only_user_can_use"].format(user=self.ctx.author.mention),
                ephemeral=True,
            )
            return False
        return True

    # --- UI assembly ---------------------------------------------------------

    def process_buttons(self):
        options = []
        for category, emoji in self.items:
            options.append(disnake.SelectOption(
                label=category[:80],
                value=category[:100],
                emoji=emoji,
                default=category == self.category,
                description="មើលពាក្យបញ្ជា / View commands"[:100],
            ))

        if options:
            sel = disnake.ui.Select(
                placeholder=L["select_placeholder"], options=options[:25],
                custom_id="help_category_select",
            )
            sel.callback = self.callback_help
            self.add_item(sel)

        if self.category:
            cmd_count = len(self.cmd_list[self.category]["cmds"])
            if cmd_count > 1:
                left = disnake.ui.Button(
                    style=disnake.ButtonStyle.secondary,
                    emoji=e("prev"), custom_id="help_prev",
                )
                left.callback = self.callback_left
                self.add_item(left)

                right = disnake.ui.Button(
                    style=disnake.ButtonStyle.secondary,
                    emoji=e("next"), custom_id="help_next",
                )
                right.callback = self.callback_right
                self.add_item(right)

            back = disnake.ui.Button(
                style=disnake.ButtonStyle.primary,
                emoji=e("back"), label=L["btn_back"],
                custom_id="help_back",
            )
            back.callback = self.callback_back
            self.add_item(back)

        # Always-on search + close (consistent footer row).
        search = disnake.ui.Button(
            style=disnake.ButtonStyle.success,
            emoji="🔍", label=L["btn_search"],
            custom_id="help_search",
        )
        search.callback = self.callback_search
        self.add_item(search)

        close = disnake.ui.Button(
            style=disnake.ButtonStyle.danger,
            emoji="✖", label=L["btn_close"],
            custom_id="help_close",
        )
        close.callback = self.callback_close
        self.add_item(close)

    async def _refresh(self, interaction: disnake.MessageInteraction):
        if not self.category and not self.page_index:
            self.clear_items()
            self.process_buttons()

        self.main_embed = await self.get_cmd(
            ctx=self.ctx,
            index=self.page_index,
            cmds=self.cmd_list[self.category]["cmds"],
            emoji=self.cmd_list[self.category]["emoji"],
            category=self.category,
        )
        await interaction.response.edit_message(embed=self.main_embed, view=self)

    # --- Callbacks -----------------------------------------------------------

    async def callback_left(self, interaction):
        count = len(self.cmd_list[self.category]["cmds"])
        self.page_index = (self.page_index - 1) % count
        await self._refresh(interaction)

    async def callback_right(self, interaction):
        count = len(self.cmd_list[self.category]["cmds"])
        self.page_index = (self.page_index + 1) % count
        await self._refresh(interaction)

    async def callback_back(self, interaction):
        self.page_index = 0
        self.category = None
        self.clear_items()
        self.process_buttons()
        await interaction.response.edit_message(embed=self.first_embed, view=self)

    async def callback_help(self, interaction: disnake.MessageInteraction):
        self.category = interaction.data.values[0]
        self.page_index = 0
        self.clear_items()
        self.process_buttons()
        self.main_embed = await self.get_cmd(
            ctx=self.ctx,
            index=self.page_index,
            cmds=self.cmd_list[self.category]["cmds"],
            emoji=self.cmd_list[self.category]["emoji"],
            category=self.category,
        )
        await interaction.response.edit_message(embed=self.main_embed, view=self)

    async def callback_search(self, interaction: disnake.MessageInteraction):
        await interaction.response.send_modal(SearchModal(self))

    async def callback_close(self, interaction: disnake.MessageInteraction):
        for child in self.children:
            if isinstance(child, (disnake.ui.Button, disnake.ui.Select)):
                child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except disnake.HTTPException:
            pass
        self.stop()


# --- Cog ----------------------------------------------------------------------

class HelpCog(commands.Cog, name="Help"):

    emoji = "📖"
    name = "Help"

    def __init__(self, bot: BotCore):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.remove_command("help")
        self.task_users = {}

    # ------------------------------------------------------------------
    # Embed builders
    # ------------------------------------------------------------------

    def _owner(self):
        appinfo = self.bot.appinfo
        try:
            return appinfo.team.owner
        except AttributeError:
            return appinfo.owner

    async def get_cmd(self, ctx, cmds, index=0, category=None, emoji=None):
        cmd = cmds[index]
        prefix = ctx.prefix if str(ctx.me.id) not in ctx.prefix else f"@{ctx.me.display_name} "

        description = cmd.description or L["no_description"]
        embed = disnake.Embed(color=BRAND_GOLD)

        # --- Header ---
        title_line = f"## {emoji or '⌨️'} `{prefix}{cmd.qualified_name}`"
        body = [title_line, f"> {description}", ""]

        # --- Availability badge ---
        availability_parts = [f"`{L['prefix']}`"]
        if _has_slash(self.bot, cmd):
            availability_parts.insert(0, f"`/{L['slash']}`")
        body.append(f"> **{L['available_as']}:** " + " ⬩ ".join(availability_parts))

        # --- Aliases ---
        if cmd.aliases:
            aliases = " ⬩ ".join(f"`{prefix}{a}`" for a in cmd.aliases)
            body.append(f"> 🔄 **{L['aliases']}:** {aliases}")

        # --- Subcommands ---
        if hasattr(cmd, "commands"):
            sub_cmds = await _filter_visible(ctx, cmd.commands)
            if sub_cmds:
                subs = " ⬩ ".join(f"`{c.name}`" for c in sub_cmds)
                body.append(
                    f"> 🔢 **{L['subcommands']}:** {subs}\n"
                    f"> -# `{prefix}help {cmd.qualified_name} <subcommand>`"
                )

        # --- Usage block ---
        if cmd.usage:
            usage = (cmd.usage
                     .replace("{prefix}", prefix)
                     .replace("{cmd}", cmd.name)
                     .replace("{parent}", cmd.full_parent_name or "")
                     .replace(f"<@!{ctx.bot.user.id}>", f"@{ctx.me.name}")
                     .replace(f"<@{ctx.bot.user.id}>", f"@{ctx.me.name}"))
            body.append(f"\n### 📘 {L['how_to_use']}\n```\n{usage}```\n"
                        f"> -# `[]` = ត្រូវការ / Required  ⬩  `<>` = មិនបង្ខំ / Optional")

        # --- Flags ---
        flags = cmd.extras.get("flags") if cmd.extras else None
        if flags and (actions := getattr(flags, "_actions", None)):
            rendered = []
            for a in actions:
                if not a.help or not a.option_strings:
                    continue
                rendered.append(f"[{' '.join(a.option_strings)}] {a.help}")
            if rendered:
                body.append(f"\n### 🚩 {L['flags']}\n```ini\n" + "\n".join(rendered) + "\n```")

        embed.description = "\n".join(body)
        embed.set_author(
            name=L["cmd_details"],
            icon_url=self.bot.user.display_avatar.url,
        )

        owner = self._owner()
        footer_parts = []
        max_pages = len(cmds)
        if max_pages > 1:
            footer_parts.append(f"{L['page']} {index + 1}/{max_pages}")
        if category:
            footer_parts.append(f"{L['category_emoji']}: {category}")
        embed.set_footer(
            icon_url=owner.display_avatar.replace(static_format="png"),
            text=" • ".join(footer_parts) if footer_parts else f"Owner: {owner}",
        )
        return embed

    def _build_main_embed(self, ctx, cmd_lst_new) -> Tuple[disnake.Embed, List[Tuple[str, str]]]:
        lines: List[str] = []
        btn_id: List[Tuple[str, str]] = []

        for category, data in sorted(cmd_lst_new.items()):
            btn_id.append((category, data["emoji"]))
            sample = sorted(data["cmds"], key=lambda c: c.name)
            cmds_str = " ⬩ ".join(f"`{c.name}`" for c in sample)
            lines.append(
                f"### {data['emoji']} {category} ({len(sample)})\n> {cmds_str}"
            )

        tip = "\n".join([
            "",
            f"{L['tip']}",
            f"> • " + L["tip_prefix"].format(prefix=ctx.prefix, cmd=ctx.invoked_with or "help").replace("\n", "\n> "),
            f"> • " + L["tip_slash"].replace("\n", "\n> "),
            f"> • " + L["tip_search"].replace("\n", "\n> "),
        ])

        body = "\n".join(lines) + tip
        body = (body
                .replace(ctx.me.mention, f"@{ctx.me.display_name}")
                .replace(f"<@!{ctx.bot.user.id}>", f"@{ctx.me.display_name}"))

        embed = disnake.Embed(description=body, color=BRAND_GOLD)
        embed.set_author(
            name=L["menu_title"],
            icon_url=self.bot.user.display_avatar.replace(static_format="png").url,
        )

        owner = self._owner()
        total_cmds = sum(len(d["cmds"]) for d in cmd_lst_new.values())
        embed.set_footer(
            icon_url=owner.display_avatar.replace(static_format="png").url,
            text=f"Golden IQ • {total_cmds} commands • Owner: {owner}",
        )
        return embed, btn_id

    async def _collect_commands(self, ctx):
        cmdlst = {}
        owner_ok = await ctx.bot.is_owner(ctx.author)

        for cmd in sorted(ctx.bot.commands, key=lambda c: c.name):
            if not _is_visible(cmd, owner_ok):
                continue
            category, emoji = _category_for(cmd)
            bucket = cmdlst.setdefault(emoji, (category, []))
            bucket[1].append(cmd)

        cmd_lst_new = {}
        for icon, (category, cmds) in cmdlst.items():
            cmd_lst_new[category] = {"emoji": icon, "cmds": cmds}
        return cmd_lst_new

    # ------------------------------------------------------------------
    # Command entrypoint (hybrid: works as both /help and {prefix}help)
    # ------------------------------------------------------------------

    help_cd = commands.CooldownMapping.from_cooldown(2, 5, commands.BucketType.user)
    help_mc = commands.MaxConcurrency(1, per=commands.BucketType.user, wait=False)

    async def _run_help(self, ctx: CustomContext, command: Optional[str]):
        if command:
            await self.parse_direct(ctx, command.split())
            return

        cmd_lst_new = await self._collect_commands(ctx)
        embed, btn_id = self._build_main_embed(ctx, cmd_lst_new)

        view = ViewHelp(
            ctx, btn_id, bot=self.bot, get_cmd=self.get_cmd,
            cmd_list=cmd_lst_new, category_cmd=None,
            main_embed=embed, timeout=180,
        )
        view.message = await ctx.send(embed=embed, mention_author=False, view=view)
        await view.wait()

        for item in view.children:
            if isinstance(item, (disnake.ui.Button, disnake.ui.Select)):
                item.disabled = True
        try:
            await view.message.edit(view=view)
        except disnake.NotFound:
            pass

    @commands.command(
        name="help",
        aliases=["h", "commands", "cmds"],
        description="បើកម៉ឺនុយជំនួយ / Open the interactive help menu.",
        cooldown=help_cd,
        max_concurrency=help_mc,
    )
    async def help_legacy(self, ctx: CustomContext, *, command: Optional[str] = None):
        await self._run_help(ctx, command)

    @commands.slash_command(
        name="help",
        description="បើកម៉ឺនុយជំនួយ / Open the interactive help menu.",
        cooldown=help_cd,
        max_concurrency=help_mc,
        extras={"allow_private": True},
    )
    async def help_slash(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        command: Optional[str] = commands.Param(
            default=None,
            name="command",
            description="ឈ្មោះពាក្យបញ្ជា (មិនបង្ខំ) / Command name (optional)",
        ),
    ):
        inter, bot = await select_bot_pool(interaction, first=True)
        if not bot:
            return

        # Attach the handful of Context-only attributes the embed builder and
        # ViewHelp expect. We're intentionally not creating a full Context
        # because the slash path doesn't need most of it — just prefix display
        # and a couple of mentions.
        if not hasattr(inter, "prefix"):
            inter.prefix = "/"
        if not hasattr(inter, "invoked_with"):
            inter.invoked_with = "help"
        if not hasattr(inter, "me"):
            inter.me = inter.guild.me if inter.guild else inter.bot.user

        await self._run_help(inter, command)

    async def parse_direct(self, ctx: CustomContext, cmd_name: List[str]):
        cmd: Union[commands.Command, commands.Group, None] = None
        for cname in cmd_name:
            if cmd:
                if hasattr(cmd, "commands"):
                    nxt = cmd.get_command(cname)
                    if not nxt:
                        break
                    cmd = nxt
            else:
                cmd = ctx.bot.get_command(cname)
                if not hasattr(cmd, "commands"):
                    break

        if not cmd or not _is_visible(cmd, await ctx.bot.is_owner(ctx.author)):
            joined = " ".join(cmd_name)
            raise GenericError(
                L["search_no_match"].format(query=joined)
            )

        category, emoji = _category_for(cmd)
        cog = cmd.cog
        if cog:
            cmds = [c for c in sorted(cog.get_commands(), key=lambda cm: cm.name)
                    if _is_visible(c, await ctx.bot.is_owner(ctx.author))]
            try:
                index = cmds.index(cmd)
            except ValueError:
                cmds, index = [cmd], 0
        else:
            cmds, index = [cmd], 0

        embed = await self.get_cmd(
            ctx=ctx, cmds=cmds, index=index, category=category, emoji=emoji,
        )
        # Both CustomContext.reply and ApplicationCommandInteraction.send work;
        # we prefer reply for the prefix path (replies to the user's message)
        # and fall back to send for slash interactions.
        if hasattr(ctx, "reply") and not isinstance(ctx, disnake.Interaction):
            await ctx.reply(
                ctx.author.mention, embed=embed,
                mention_author=False, fail_if_not_exists=False,
            )
        else:
            await ctx.send(ctx.author.mention, embed=embed)

    def cog_unload(self):
        self.bot.help_command = self._original_help_command


def setup(bot: BotCore):
    bot.add_cog(HelpCog(bot))
