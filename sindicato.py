import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View, Button, Modal, TextInput
import asyncio 
import json 
import os 
from flask import Flask
from threading import Thread

# --- ⚠️ CONFIGURAÇÕES OBRIGATÓRIAS ⚠️ ---
# O Render vai buscar isso nas "Environment Variables"
TOKEN_DO_BOT = os.environ.get('DISCORD_TOKEN')

# --- Sistema de Verificação ---
ID_CANAL_ADMIN_VERIFICACAO = 1439358728078889001 
NOME_CARGO_NAO_IDENTIFICADO = "『 ✗ ┇ Não identificado"
NOME_CARGO_IDENTIFICADO = "『 ✓ ┇ Identificado"
NOME_CARGO_MEMBRO = "『 👤 ┇Membro"
NOME_CARGO_AFILIADO = "『 🤝 ┇Afiliado"

# --- Sistema de Alvos ---
ID_CANAL_REQUISITAR_ALVOS = 123456789012345678 
ID_CANAL_ALVOS = 1439454702101205032 

# --- Sistema de Cofre ---
NOME_CANAL_COFRE = "📦﹒cofre"
VAULT_FILE = "vault.json" 

# --- Sistema de Setar Cargo ---
NOME_CANAL_SETAR_CARGO = "🔖﹒setar-cargo"

# --- Nomes dos Cargos ---
ROLE_SINDICATO = "『 🛠️ ┇ Sindicato"
ROLE_HYDRA = "『 🐉 ┇ Hydra"

ROLES_SINDICATO_SUB = [
    "『 ⌖ ┇ Associados",
    "『 🕶️┇ Vígias",
    "『 📋┇ Capataz",
    "『 ❖ ┇ Sub-Comandante"
]
ROLES_HYDRA_SUB = [
    "『 ⌖ ┇ Associados",
    "『 ❖ ┇ Sub-Comandante"
]

ROLES_STATIC_HIERARQUIA = [
    "⎯⎯⎯⎯ Hierarquia ⎯⎯⎯⎯",
    "⎯⎯⎯⎯ Designação ⎯⎯⎯⎯",
    "⎯⎯⎯⎯ Identificação ⎯⎯⎯⎯",
    "⎯⎯⎯⎯ Situacional ⎯⎯⎯⎯"
]

# --- SERVIDOR WEB (FLASK) PARA UPTIMEROBOT ---
app = Flask('')

@app.route('/')
def home():
    return "Estou vivo e operante!"

def run_web_server():
    # Roda na porta 8080 ou na porta que o Render fornecer
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    server_thread = Thread(target=run_web_server)
    server_thread.start()
# ---------------------------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# --- FUNÇÕES AUXILIARES ---
async def get_role(guild: discord.Guild, role_name: str):
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        print(f"AVISO: O cargo '{role_name}' não foi encontrado.")
    return role

def load_vault():
    if not os.path.exists(VAULT_FILE): return {"message_id": None, "items": []}
    try:
        with open(VAULT_FILE, 'r') as f: return json.load(f)
    except json.JSONDecodeError: return {"message_id": None, "items": []}

def save_vault(data):
    with open(VAULT_FILE, 'w') as f: json.dump(data, f, indent=4)

async def update_vault_embed(guild):
    vault_data = load_vault()
    if not vault_data["message_id"]: return
    try:
        channel = discord.utils.get(guild.channels, name=NOME_CANAL_COFRE)
        if not channel: return
        message = await channel.fetch_message(vault_data["message_id"])
        item_list_str = "\n".join(f"• {item}" for item in vault_data["items"]) if vault_data["items"] else "O cofre está vazio."
        embed = discord.Embed(title="📦 Cofre do Sindicato", description=item_list_str, color=discord.Color.dark_grey())
        embed.set_footer(text="Use 'Colocar: <item>' ou 'Remover: <item>'")
        await message.edit(embed=embed)
    except Exception as e: print(f"Erro ao atualizar o cofre: {e}")

# --- VIEWS E CLASSES (Setar Cargo) ---
class RoleApprovalView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success, custom_id="role_admin_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        try:
            original_embed = interaction.message.embeds[0]
            footer_text = original_embed.footer.text
            member_id = int(footer_text.split(";")[0].split(":")[1])
            group_role_name = footer_text.split(";")[1].split(":")[1]
            sub_role_name = footer_text.split(";")[2].split(":")[1]
            guild = interaction.guild
            member = guild.get_member(member_id)
            if member is None: await interaction.response.send_message("Erro: Membro não encontrado.", ephemeral=True); return
            roles_to_give_names = [group_role_name, sub_role_name] + ROLES_STATIC_HIERARQUIA
            roles_to_give_objects = []
            for role_name in roles_to_give_names:
                role = await get_role(guild, role_name)
                if role: roles_to_give_objects.append(role)
            await member.add_roles(*roles_to_give_objects, reason="Bot Aprovação")
            new_embed = original_embed; new_embed.title = "✅ Cargo APROVADO"; new_embed.color = discord.Color.green()
            new_embed.set_field_at(0, name="Status", value=f"Aprovado por {interaction.user.mention}")
            await interaction.response.edit_message(embed=new_embed, view=None)
            try: await member.send(f"🎉 Seus cargos foram aprovados em **{guild.name}**!")
            except: pass
        except Exception as e: await interaction.response.send_message(f"Erro: {e}", ephemeral=True)

    @discord.ui.button(label="Negar", style=discord.ButtonStyle.danger, custom_id="role_admin_deny")
    async def deny_button(self, interaction: discord.Interaction, button: Button):
        try:
            original_embed = interaction.message.embeds[0]
            new_embed = original_embed; new_embed.title = "❌ Cargo NEGADO"; new_embed.color = discord.Color.red()
            new_embed.set_field_at(0, name="Status", value=f"Negado por {interaction.user.mention}")
            await interaction.response.edit_message(embed=new_embed, view=None)
        except Exception as e: print(f"Erro negar: {e}")

class SubRoleSelect(Select):
    def __init__(self, group_role_name: str, sub_role_names: list):
        self.group_role_name = group_role_name
        options = [discord.SelectOption(label=name) for name in sub_role_names]
        super().__init__(placeholder="Passo 2: Escolha seu cargo...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        sub_role_name = self.values[0]
        admin_channel = interaction.client.get_channel(ID_CANAL_ADMIN_VERIFICACAO)
        if not admin_channel: await interaction.response.edit_message(content="Erro admin channel.", view=None); return
        embed = discord.Embed(title="🔔 Novo Pedido de Cargo", description=f"{interaction.user.mention} pediu cargos:", color=discord.Color.blue())
        embed.add_field(name="Grupo", value=self.group_role_name, inline=False); embed.add_field(name="Cargo", value=sub_role_name, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"UserID:{interaction.user.id};GroupRole:{self.group_role_name};SubRole:{sub_role_name}")
        await admin_channel.send(embed=embed, view=RoleApprovalView())
        await interaction.response.edit_message(content="✅ Pedido enviado para aprovação.", view=None)

class GroupSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=ROLE_SINDICATO, emoji="🛠️"), discord.SelectOption(label=ROLE_HYDRA, emoji="🐉")]
        super().__init__(placeholder="Passo 1: Escolha sua facção...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        chosen = self.values[0]
        subs = ROLES_SINDICATO_SUB if chosen == ROLE_SINDICATO else ROLES_HYDRA_SUB
        view = View(timeout=None); view.add_item(SubRoleSelect(chosen, subs))
        await interaction.response.edit_message(content="Passo 2: Escolha seu cargo específico:", view=view)

class RoleRequestStartView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Requisitar Cargo", style=discord.ButtonStyle.primary, custom_id="role_req_start", emoji="🔖")
    async def start_button(self, interaction: discord.Interaction, button: Button):
        view = View(timeout=None); view.add_item(GroupSelect())
        await interaction.response.send_message(content="Iniciando...", view=view, ephemeral=True)

@bot.command(name="setarcargo_setup")
@commands.has_permissions(administrator=True)
async def setarcargo_setup_cmd(ctx: commands.Context):
    if ctx.channel.name != NOME_CANAL_SETAR_CARGO: await ctx.message.delete(); return
    embed = discord.Embed(title="Requisitar Cargos", description="Clique abaixo para pedir seus cargos.", color=discord.Color.blue())
    await ctx.send(embed=embed, view=RoleRequestStartView()); await ctx.message.delete()

# --- VIEWS E CLASSES (Verificação) ---
class AdminActionViewVerify(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success, custom_id="verify_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        try:
            orig_embed = interaction.message.embeds[0]; footer = orig_embed.footer.text
            mem_id = int(footer.split(";")[0].split(":")[1]); role_n = footer.split(";")[1].split(":")[1]
            member = interaction.guild.get_member(mem_id)
            if not member: return
            r_give = await get_role(interaction.guild, role_n); r_id = await get_role(interaction.guild, NOME_CARGO_IDENTIFICADO); r_un = await get_role(interaction.guild, NOME_CARGO_NAO_IDENTIFICADO)
            if r_give and r_id and r_un:
                await member.add_roles(r_give, r_id); await member.remove_roles(r_un)
                orig_embed.title = "✅ VERIFICADO"; orig_embed.color = discord.Color.green()
                await interaction.response.edit_message(embed=orig_embed, view=None)
                try: await member.send(f"Você foi verificado em {interaction.guild.name}!")
                except: pass
        except Exception as e: print(e)

    @discord.ui.button(label="Negar", style=discord.ButtonStyle.danger, custom_id="verify_deny")
    async def deny_button(self, interaction: discord.Interaction, button: Button):
        orig_embed = interaction.message.embeds[0]; orig_embed.title = "❌ NEGADO"; orig_embed.color = discord.Color.red()
        await interaction.response.edit_message(embed=orig_embed, view=None)

class VerificationDropdown(Select):
    def __init__(self):
        options = [discord.SelectOption(label="Membro", value=NOME_CARGO_MEMBRO, emoji="👤"), discord.SelectOption(label="Afiliado", value=NOME_CARGO_AFILIADO, emoji="🤝")]
        super().__init__(placeholder="Quem é você?", min_values=1, max_values=1, custom_id="verify_drop")
    async def callback(self, interaction: discord.Interaction):
        role_name = self.values[0]
        adm_ch = interaction.client.get_channel(ID_CANAL_ADMIN_VERIFICACAO)
        if not adm_ch: await interaction.response.send_message("Erro admin channel", ephemeral=True); return
        embed = discord.Embed(title="🔔 Verificação Pendente", description=f"{interaction.user.mention}", color=discord.Color.orange())
        embed.add_field(name="Escolha", value=role_name)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID:{interaction.user.id};Role:{role_name}")
        await adm_ch.send(embed=embed, view=AdminActionViewVerify())
        await interaction.response.send_message("Enviado para análise.", ephemeral=True)

class VerificationView(View):
    def __init__(self): super().__init__(timeout=None); self.add_item(VerificationDropdown())

@bot.event
async def on_member_join(member: discord.Member):
    role = await get_role(member.guild, NOME_CARGO_NAO_IDENTIFICADO)
    if role: await member.add_roles(role)
    embed = discord.Embed(title=f"Bem-vindo ao {member.guild.name}", description="Identifique-se abaixo.", color=discord.Color.blue())
    try: await member.send(embed=embed, view=VerificationView())
    except: print(f"Erro DM {member.name}")

# --- ALVOS ---
class TargetModal(Modal, title="Designar Alvo"):
    def __init__(self, bot): super().__init__(); self.bot = bot
    nome = TextInput(label="Nome", style=discord.TextStyle.short)
    grupo = TextInput(label="Grupo", style=discord.TextStyle.short)
    motivo = TextInput(label="Motivo", style=discord.TextStyle.paragraph)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Verifique sua DM.", ephemeral=True)
        try: dm = await interaction.user.create_dm(); await dm.send("Envie a **FOTO** do alvo agora (5 min).")
        except: return
        def check(m): return m.author == interaction.user and m.channel == dm and m.attachments
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=300)
            url = msg.attachments[0].url
            ch = self.bot.get_channel(ID_CANAL_ALVOS)
            if ch:
                emb = discord.Embed(title="🎯 Novo Alvo", color=discord.Color.red())
                emb.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
                emb.add_field(name="Nome", value=self.nome.value); emb.add_field(name="Grupo", value=self.grupo.value); emb.add_field(name="Motivo", value=self.motivo.value)
                emb.set_image(url=url)
                await ch.send(embed=emb); await dm.send("✅ Sucesso.")
        except: await dm.send("Tempo esgotado.")

class TargetRequestView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Designar Alvo", style=discord.ButtonStyle.danger, custom_id="target_btn", emoji="🎯")
    async def btn(self, i: discord.Interaction, b: Button): await i.response.send_modal(TargetModal(i.client))

@bot.command(name="postarequisicao")
@commands.has_permissions(administrator=True)
async def postar_req(ctx):
    await ctx.message.delete()
    await ctx.send(embed=discord.Embed(title="Designar Alvo", color=discord.Color.dark_red()), view=TargetRequestView())

# --- COFRE E COMANDOS EXTRAS ---
@bot.command(name="cofre_setup")
@commands.has_permissions(administrator=True)
async def cofre_s(ctx):
    if ctx.channel.name != NOME_CANAL_COFRE: return
    msg = await ctx.send(embed=discord.Embed(title="Iniciando...", color=discord.Color.dark_grey()))
    save_vault({"message_id": msg.id, "items": []})
    await update_vault_embed(ctx.guild)
    await ctx.message.delete()

@bot.command(name="manifesto")
async def man1(ctx): await ctx.send("## O Manifesto da Sobrevivência...\n(Texto Longo Parte 1)"); await ctx.send("(Texto Longo Parte 2)...")

@bot.command(name="manifesto2")
async def man2(ctx): await ctx.send(embed=discord.Embed(title="Manifesto", description="Texto completo...", color=discord.Color.orange()))

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'{bot.user} Online!')
    bot.add_view(VerificationView())
    bot.add_view(AdminActionViewVerify())
    bot.add_view(TargetRequestView())
    bot.add_view(RoleRequestStartView())
    bot.add_view(RoleApprovalView())
    print("Views carregadas.")

@bot.event
async def on_message(message):
    if message.author.bot: return
    if message.channel.name == NOME_CANAL_COFRE:
        c = message.content.lower(); v = load_vault(); changed = False
        try:
            if c.startswith("colocar:"): v["items"].append(message.content[8:].strip()); changed=True
            elif c.startswith("remover:"): 
                item = message.content[8:].strip()
                if item in v["items"]: v["items"].remove(item); changed=True
            await message.delete()
        except: pass
        if changed: save_vault(v); await update_vault_embed(message.guild)
    await bot.process_commands(message)

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    keep_alive() # Inicia o servidor web numa thread separada
    
    if TOKEN_DO_BOT:
        bot.run(TOKEN_DO_BOT)
    else:
        print("ERRO: Configure a variável de ambiente 'DISCORD_TOKEN' no Render!")
