import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select
import os, json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
GUILD = discord.Object(id=GUILD_ID)

# ================== Stockage des soldes ==================
if os.path.exists("users.json"):
    with open("users.json", "r") as f:
        users = json.load(f)
else:
    users = {}

def save_users():
    with open("users.json", "w") as f:
        json.dump(users, f, indent=4)

# ================== Message de bienvenue ==================
@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=f"Bienvenue {member.name} ! 🎉",
            description=f"Votre compte a été créé le {member.created_at.strftime('%d/%m/%Y')}\nNous sommes maintenant {member.guild.member_count} membres sur le serveur !",
            color=0x00ff00
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

# ================== Panel admin ==================
class ChannelSelect(Select):
    def __init__(self, channels):
        options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in channels]
        super().__init__(placeholder="Sélectionner un channel...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)
        perms = channel.overwrites_for(interaction.guild.default_role)
        if perms.send_messages is False:
            perms.send_messages = True
            msg = f"{channel.name} est maintenant déverrouillé ✅"
        else:
            perms.send_messages = False
            msg = f"{channel.name} est maintenant verrouillé 🔒"
        await channel.set_permissions(interaction.guild.default_role, overwrite=perms)
        await interaction.response.send_message(msg, ephemeral=True)

class AdminPanel(View):
    def __init__(self, guild):
        super().__init__(timeout=None)
        self.guild = guild
        self.add_item(ChannelSelect(guild.channels))

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban_button(self, interaction: discord.Interaction, button: Button):
        user_id = int(interaction.message.content.split("ID: ")[1].strip())
        member = self.guild.get_member(user_id)
        if member:
            await member.ban(reason="Action via panel")
            await interaction.response.send_message(f"{member} a été banni ✅", ephemeral=True)
        else:
            await interaction.response.send_message("Membre non trouvé.", ephemeral=True)

    @discord.ui.button(label="Unban", style=discord.ButtonStyle.success)
    async def unban_button(self, interaction: discord.Interaction, button: Button):
        user_id = int(interaction.message.content.split("ID: ")[1].strip())
        bans = await self.guild.bans()
        for ban_entry in bans:
            if ban_entry.user.id == user_id:
                await self.guild.unban(ban_entry.user)
                await interaction.response.send_message(f"{ban_entry.user} a été unbanni ✅", ephemeral=True)
                return
        await interaction.response.send_message("Membre non trouvé dans la liste des bans.", ephemeral=True)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger)
    async def kick_button(self, interaction: discord.Interaction, button: Button):
        user_id = int(interaction.message.content.split("ID: ")[1].strip())
        member = self.guild.get_member(user_id)
        if member:
            await member.kick(reason="Action via panel")
            await interaction.response.send_message(f"{member} a été expulsé ✅", ephemeral=True)
        else:
            await interaction.response.send_message("Membre non trouvé.", ephemeral=True)

    @discord.ui.button(label="Mute/Unmute", style=discord.ButtonStyle.secondary)
    async def mute_button(self, interaction: discord.Interaction, button: Button):
        user_id = int(interaction.message.content.split("ID: ")[1].strip())
        member = self.guild.get_member(user_id)
        if member:
            muted_role = discord.utils.get(self.guild.roles, name="Muted")
            if not muted_role:
                muted_role = await self.guild.create_role(name="Muted")
                for channel in self.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
            if muted_role in member.roles:
                await member.remove_roles(muted_role)
                await interaction.response.send_message(f"{member} a été unmuted ✅", ephemeral=True)
            else:
                await member.add_roles(muted_role)
                await interaction.response.send_message(f"{member} a été muted ✅", ephemeral=True)
        else:
            await interaction.response.send_message("Membre non trouvé.", ephemeral=True)

# ================== Commande /panel ==================
@bot.tree.command(name="panel", description="Ouvre le panel admin", guild=GUILD)
async def panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Vous devez être admin pour utiliser cette commande.", ephemeral=True)
        return
    embed = discord.Embed(title="Admin Panel", description="ID: `entrez l'ID d'un membre ici`", color=0x00ff00)
    view = AdminPanel(interaction.guild)
    await interaction.response.send_message(embed=embed, view=view)

# ================== Commande /solde ==================
@bot.tree.command(name="solde", description="Voir ton solde d'argent", guild=GUILD)
async def solde(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in users:
        users[user_id] = {"argent": 0, "last_retrait": None}
        save_users()
    argent = users[user_id]["argent"]
    last = users[user_id]["last_retrait"]
    now = datetime.now()
    can_withdraw = False
    if last:
        last_date = datetime.fromisoformat(last)
        if now - last_date >= timedelta(weeks=1):
            can_withdraw = True
    else:
        can_withdraw = True
    msg = f"💰 Solde cumulé : {argent}$\n"
    msg += "✅ Vous pouvez retirer votre argent !" if can_withdraw else "⏳ Retrait disponible dans 1 semaine."
    await interaction.response.send_message(msg, ephemeral=True)

# ================== Commande /retirer ==================
@bot.tree.command(name="retirer", description="Retirer ton argent si disponible", guild=GUILD)
async def retirer(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if user_id not in users:
        await interaction.response.send_message("Vous n'avez pas de solde.", ephemeral=True)
        return
    now = datetime.now()
    last = users[user_id]["last_retrait"]
    if last:
        last_date = datetime.fromisoformat(last)
        if now - last_date < timedelta(weeks=1):
            await interaction.response.send_message("⏳ Retrait disponible seulement 1 fois par semaine.", ephemeral=True)
            return
    argent = users[user_id]["argent"]
    if argent == 0:
        await interaction.response.send_message("Vous n'avez pas d'argent à retirer.", ephemeral=True)
        return
    users[user_id]["argent"] = 0
    users[user_id]["last_retrait"] = now.isoformat()
    save_users()
    await interaction.response.send_message(f"✅ Vous avez retiré {argent}$ ! Prochain retrait dans 1 semaine.", ephemeral=True)

# ================== Synchronisation ==================
@bot.event
async def on_ready():
    await bot.tree.sync(guild=GUILD)
    print(f"Connecté comme {bot.user} ✅")

bot.run(TOKEN)
