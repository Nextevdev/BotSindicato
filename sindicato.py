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
TOKEN_DO_BOT = "SEU_TOKEN_REGENERADO_AQUI"

# --- Sistema de Verificação ---
ID_CANAL_ADMIN_VERIFICACAO = 1439358728078889001 
NOME_CARGO_NAO_IDENTIFICADO = "『 ✗ ┇ Não identificado"
NOME_CARGO_IDENTIFICADO = "『 ✓ ┇ Identificado"
NOME_CARGO_MEMBRO = "『 👤 ┇Membro"
NOME_CARGO_AFILIADO = "『 🤝 ┇Afiliado"

# --- Sistema de Alvos ---
ID_CANAL_REQUISITAR_ALVOS = 123456789012345678 # ⬅️ COLOQUE O ID DO CANAL '#🎯﹒requisitar-alvos'
ID_CANAL_ALVOS = 1439454702101205032 

# --- Sistema de Cofre ---
NOME_CANAL_COFRE = "📦﹒cofre"
VAULT_FILE = "vault.json" 

# --- Sistema de Setar Cargo ---
NOME_CANAL_SETAR_CARGO = "🔖﹒setar-cargo" # ⬅️ VERIFIQUE O NOME DESTE CANAL

# --- Nomes dos Cargos (Verifique se estão corretos!) ---
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
# Os 4 cargos estáticos que todos recebem
ROLES_STATIC_HIERARQUIA = [
    "⎯⎯⎯⎯ Hierarquia ⎯⎯⎯⎯",
    "⎯⎯⎯⎯ Designação ⎯⎯⎯⎯",
    "⎯⎯⎯⎯ Identificação ⎯⎯⎯⎯",
    "⎯⎯⎯⎯ Situacional ⎯⎯⎯⎯" # <-- ATUALIZADO AQUI
]
# -------------------------------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Função Auxiliar Get Role ---
async def get_role(guild: discord.Guild, role_name: str):
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        print(f"AVISO: O cargo '{role_name}' não foi encontrado.")
    return role

# --- [ NOVO ] View de Aprovação de Cargo (Admin) ---
class RoleApprovalView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success, custom_id="role_admin_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        try:
            original_embed = interaction.message.embeds[0]
            footer_text = original_embed.footer.text
            
            # Pega os dados do rodapé
            member_id = int(footer_text.split(";")[0].split(":")[1])
            group_role_name = footer_text.split(";")[1].split(":")[1]
            sub_role_name = footer_text.split(";")[2].split(":")[1]

            guild = interaction.guild
            member = guild.get_member(member_id)
            
            if member is None:
                await interaction.response.send_message("Erro: Membro não encontrado no servidor.", ephemeral=True)
                return

            # Monta a lista de cargos para dar
            roles_to_give_names = [group_role_name, sub_role_name] + ROLES_STATIC_HIERARQUIA
            roles_to_give_objects = []
            
            for role_name in roles_to_give_names:
                role = await get_role(guild, role_name)
                if role:
                    roles_to_give_objects.append(role)
                else:
                    await interaction.response.send_message(f"Erro: O cargo '{role_name}' não foi encontrado. Crie-o.", ephemeral=True)
                    return
            
            # Dá todos os 6 cargos
            await member.add_roles(*roles_to_give_objects, reason="Aprovação de cargo via bot")

            # Atualiza a mensagem do admin
            new_embed = original_embed
            new_embed.title = "✅ Cargo APROVADO"
            new_embed.color = discord.Color.green()
            new_embed.set_field_at(0, name="Status", value=f"Aprovado por {interaction.user.mention}")
            
            await interaction.response.edit_message(embed=new_embed, view=None)
            
            try:
                await member.send(f"🎉 Seu pedido de cargo no servidor **{guild.name}** foi aprovado!")
            except discord.Forbidden:
                pass # Ignora se não puder enviar DM

        except Exception as e:
            print(f"Erro no botão 'Aceitar Cargo': {e}")
            await interaction.response.send_message(f"Ocorreu um erro: {e}", ephemeral=True)

    @discord.ui.button(label="Negar", style=discord.ButtonStyle.danger, custom_id="role_admin_deny")
    async def deny_button(self, interaction: discord.Interaction, button: Button):
        try:
            original_embed = interaction.message.embeds[0]
            footer_text = original_embed.footer.text
            member_id = int(footer_text.split(";")[0].split(":")[1])
            guild = interaction.guild
            member = guild.get_member(member_id)

            new_embed = original_embed
            new_embed.title = "❌ Cargo NEGADO"
            new_embed.color = discord.Color.red()
            new_embed.set_field_at(0, name="Status", value=f"Negado por {interaction.user.mention}")

            await interaction.response.edit_message(embed=new_embed, view=None)

            if member:
                try:
                    await member.send(f"Seu pedido de cargo no servidor **{guild.name}** foi negado.")
                except discord.Forbidden:
                    pass
        except Exception as e:
            print(f"Erro no botão 'Negar Cargo': {e}")

# --- [ NOVO ] Views do Menu de Cargo (Usuário) ---

# Passo 3: Menu de Sub-Cargo
class SubRoleSelect(Select):
    def __init__(self, group_role_name: str, sub_role_names: list):
        self.group_role_name = group_role_name
        options = [discord.SelectOption(label=name) for name in sub_role_names]
        
        super().__init__(placeholder="Passo 2: Escolha seu cargo específico...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Escolha final!
        sub_role_name = self.values[0]
        
        # Envia para admins
        admin_channel = interaction.client.get_channel(ID_CANAL_ADMIN_VERIFICACAO)
        if not admin_channel:
            print(f"ERRO: Canal de admin (ID: {ID_CANAL_ADMIN_VERIFICACAO}) não encontrado.")
            await interaction.response.edit_message(content="Erro interno, contate admin.", view=None)
            return

        embed = discord.Embed(
            title="🔔 Novo Pedido de Cargo Pendente",
            description=f"O usuário {interaction.user.mention} ({interaction.user.name}) requisitou cargos:",
            color=discord.Color.blue()
        )
        embed.add_field(name="Grupo Escolhido", value=self.group_role_name, inline=False)
        embed.add_field(name="Cargo Escolhido", value=sub_role_name, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"UserID:{interaction.user.id};GroupRole:{self.group_role_name};SubRole:{sub_role_name}")

        await admin_channel.send(embed=embed, view=RoleApprovalView())
        
        # Avisa o usuário
        await interaction.response.edit_message(content="✅ **Pedido enviado!**\nSua requisição de cargo foi enviada para a administração. Por favor, aguarde a aprovação.", view=None)

# Passo 2: Menu de Grupo
class GroupSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=ROLE_SINDICATO, emoji="🛠️"),
            discord.SelectOption(label=ROLE_HYDRA, emoji="🐉"),
        ]
        super().__init__(placeholder="Passo 1: Escolha sua facção...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # O usuário escolheu o grupo
        chosen_group_name = self.values[0]
        
        if chosen_group_name == ROLE_SINDICATO:
            sub_roles_list = ROLES_SINDICATO_SUB
        elif chosen_group_name == ROLE_HYDRA:
            sub_roles_list = ROLES_HYDRA_SUB
        else:
            await interaction.response.edit_message(content="Erro, grupo inválido.", view=None)
            return
            
        # Cria a nova view com o menu de sub-cargo
        new_view = View(timeout=None)
        new_view.add_item(SubRoleSelect(group_role_name=chosen_group_name, sub_role_names=sub_roles_list))
        
        # Edita a mensagem ephemeral para mostrar o Passo 2
        await interaction.response.edit_message(content="Ótimo. Agora, escolha seu cargo dentro desta facção:", view=new_view)

# Passo 1: O Botão Inicial
class RoleRequestStartView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Requisitar Cargo", style=discord.ButtonStyle.primary, custom_id="role_request_start", emoji="🔖")
    async def start_button(self, interaction: discord.Interaction, button: Button):
        # Cria o menu de Grupo (Passo 2)
        view = View(timeout=None)
        view.add_item(GroupSelect())
        
        # Envia a primeira mensagem (só o usuário vê)
        await interaction.response.send_message(content="Iniciando requisição de cargo. Por favor, siga os passos.", view=view, ephemeral=True)


# --- [ NOVO ] Comando de Setup do Menu de Cargo ---
@bot.command(name="setarcargo_setup")
@commands.has_permissions(administrator=True)
async def setarcargo_setup_cmd(ctx: commands.Context):
    """(ADMIN) Posta a mensagem inicial para requisitar cargos."""
    if ctx.channel.name != NOME_CANAL_SETAR_CARGO:
        await ctx.send(f"Este comando só pode ser usado no canal `{NOME_CANAL_SETAR_CARGO}`.", delete_after=10)
        await ctx.message.delete()
        return

    embed = discord.Embed(
        title="Requisitar Cargos",
        description="Clique no botão abaixo para iniciar o processo de requisição de seus cargos de facção e hierarquia.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=RoleRequestStartView())
    await ctx.message.delete()


# --- Funções do Cofre ---
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

@bot.command(name="cofre_setup")
@commands.has_permissions(administrator=True)
async def cofre_setup_cmd(ctx: commands.Context):
    if ctx.channel.name != NOME_CANAL_COFRE:
        await ctx.send(f"Este comando só pode ser usado no canal `{NOME_CANAL_COFRE}`.", delete_after=10)
        await ctx.message.delete(); return
    embed = discord.Embed(title="📦 Cofre do Sindicato", description="Inicializando...", color=discord.Color.dark_grey())
    vault_message = await ctx.send(embed=embed)
    vault_data = load_vault()
    vault_data["message_id"] = vault_message.id
    save_vault(vault_data)
    await update_vault_embed(ctx.guild)
    await ctx.message.delete()

# --- Sistema de Alvos ---
class TargetModal(Modal, title="Designar Novo Alvo"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
    nome = TextInput(label="Qual é o nome do alvo?", placeholder="Ex: D-9341 ou 'Guarda Smith'", style=discord.TextStyle.short, required=True)
    grupo = TextInput(label="Qual é o departamento/grupo do alvo?", placeholder="Ex: Membro da Resistência, Guarda Corrupto, etc.", style=discord.TextStyle.short, required=True)
    motivo = TextInput(label="Qual é o motivo para a neutralização?", style=discord.TextStyle.paragraph, placeholder="Descreva a infração ou ameaça que o alvo cometeu.", required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Formulário recebido. Verifique sua DM para enviar a foto do alvo.", ephemeral=True)
        try: dm_channel = await interaction.user.create_dm(); await dm_channel.send("Formulário de texto recebido. Agora, por favor, envie a **foto do alvo** aqui.\nVocê tem 5 minutos.")
        except discord.Forbidden: await interaction.followup.send("Não consegui te enviar uma DM. Suas DMs estão fechadas?", ephemeral=True); return
        def check(m): return m.author == interaction.user and m.channel == dm_channel and m.attachments
        try:
            msg_com_foto = await self.bot.wait_for('message', check=check, timeout=300.0)
            foto_url = msg_com_foto.attachments[0].url
            canal_alvos = self.bot.get_channel(ID_CANAL_ALVOS)
            if not canal_alvos: await dm_channel.send("Erro interno do bot (não achei o canal de alvos). Contate um admin."); return
            embed = discord.Embed(title="🎯 Novo Alvo Designado", color=discord.Color.red())
            embed.set_author(name=f"Requisitante: {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="Nome do Alvo", value=self.nome.value, inline=False); embed.add_field(name="Departamento/Grupo", value=self.grupo.value, inline=False); embed.add_field(name="Motivo da Neutralização", value=self.motivo.value, inline=False)
            embed.set_image(url=foto_url); embed.set_footer(text=f"ID do Requisitante: {interaction.user.id}")
            await canal_alvos.send(embed=embed); await dm_channel.send("✅ Alvo registrado com sucesso.")
        except asyncio.TimeoutError: await dm_channel.send("Tempo esgotado (5 minutos). Por favor, inicie o processo novamente no canal.")
        except Exception as e: await dm_channel.send("Ocorreu um erro ao processar sua foto. Tente novamente."); print(f"Erro ao processar foto: {e}")

class TargetRequestView(View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Designar alvo", style=discord.ButtonStyle.danger, custom_id="designar_alvo", emoji="🎯")
    async def target_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TargetModal(bot=interaction.client))

@bot.command(name="postarequisicao")
@commands.has_permissions(administrator=True)
async def postar_requisicao_cmd(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception as e: print(f"Não foi possível apagar a mensagem de comando: {e}")
    embed = discord.Embed(title="Designar Alvo", description="Clique no botão abaixo para iniciar o processo de designação de um novo alvo para neutralização.", color=discord.Color.dark_red())
    await ctx.send(embed=embed, view=TargetRequestView())
@postar_requisicao_cmd.error
async def on_postar_requisicao_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions): await ctx.send("Você não tem permissão de Administrador para usar este comando.", delete_after=10)

# --- Sistema de Verificação (Antigo) ---
class AdminActionView(View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success, custom_id="admin_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        try:
            original_embed = interaction.message.embeds[0]
            footer_text = original_embed.footer.text
            member_id = int(footer_text.split(";")[0].split(":")[1])
            role_name_to_give = footer_text.split(";")[1].split(":")[1]
            guild = interaction.guild
            member = guild.get_member(member_id)
            
            if member is None:
                await interaction.response.send_message("Erro: Membro não encontrado no servidor.", ephemeral=True); return
            role_to_give = await get_role(guild, role_name_to_give)
            role_identified = await get_role(guild, NOME_CARGO_IDENTIFICADO)
            role_unidentified = await get_role(guild, NOME_CARGO_NAO_IDENTIFICADO)
            if not all([role_to_give, role_identified, role_unidentified]):
                await interaction.response.send_message("Erro: Um ou mais cargos de configuração não foram encontrados.", ephemeral=True); return
            
            await member.add_roles(role_to_give, role_identified); await member.remove_roles(role_unidentified)
            new_embed = original_embed; new_embed.title = "✅ APROVADO"; new_embed.color = discord.Color.green()
            new_embed.set_field_at(0, name="Status", value=f"Aprovado por {interaction.user.mention}")
            await interaction.response.edit_message(embed=new_embed, view=None)
            try: await member.send(f"🎉 Você foi verificado e aprovado no servidor **{guild.name}**!")
            except discord.Forbidden: print(f"Não foi possível enviar DM de aprovação para {member.name}")
        except Exception as e: print(f"Erro no botão 'Aceitar': {e}")

    @discord.ui.button(label="Negar", style=discord.ButtonStyle.danger, custom_id="admin_deny")
    async def deny_button(self, interaction: discord.Interaction, button: Button):
        try:
            original_embed = interaction.message.embeds[0]
            footer_text = original_embed.footer.text
            member_id = int(footer_text.split(";")[0].split(":")[1])
            guild = interaction.guild
            member = guild.get_member(member_id)
            new_embed = original_embed; new_embed.title = "❌ NEGADO"; new_embed.color = discord.Color.red()
            new_embed.set_field_at(0, name="Status", value=f"Negado por {interaction.user.mention}")
            await interaction.response.edit_message(embed=new_embed, view=None)
            if member:
                try: await member.send(f"Sua verificação no servidor **{guild.name}** foi negada.")
                except discord.Forbidden: pass
        except Exception as e: print(f"Erro no botão 'Negar': {e}")

class VerificationDropdown(Select):
    def __init__(self):
        options = [discord.SelectOption(label="Membro", description="Eu sou um Membro.", value=NOME_CARGO_MEMBRO, emoji="👤"), discord.SelectOption(label="Afiliado", description="Eu sou um Afiliado.", value=NOME_CARGO_AFILIADO, emoji="🤝")]
        super().__init__(placeholder="Escolha como você se identifica...", min_values=1, max_values=1, options=options, custom_id="verification_dropdown")
    async def callback(self, interaction: discord.Interaction):
        chosen_role_name = self.values[0]
        member = interaction.user
        admin_channel = interaction.client.get_channel(ID_CANAL_ADMIN_VERIFICACAO)
        if not admin_channel:
            await interaction.response.send_message("Erro ao processar. Contate um admin.", ephemeral=True); return
        embed = discord.Embed(title="🔔 Nova Verificação Pendente", description=f"O usuário {member.mention} ({member.name}) está aguardando identificação.", color=discord.Color.orange())
        embed.add_field(name="Escolha do Usuário", value=chosen_role_name, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url); embed.set_footer(text=f"UserID:{member.id};RoleName:{chosen_role_name}")
        await admin_channel.send(embed=embed, view=AdminActionView())
        await interaction.response.send_message(f"Seu pedido como **{chosen_role_name.split('┇')[1].strip()}** foi enviado para a administração. Aguarde a aprovação.", ephemeral=True)

class VerificationView(View):
    def __init__(self): super().__init__(timeout=None); self.add_item(VerificationDropdown())

# --- Evento 'on_member_join' ---
@bot.event
async def on_member_join(member: discord.Member):
    
    # 1. Dá o cargo "Não identificado"
    role = await get_role(member.guild, NOME_CARGO_NAO_IDENTIFICADO)
    if role:
        try:
            await member.add_roles(role)
            print(f"Cargo '{NOME_CARGO_NAO_IDENTIFICADO}' dado para {member.name}")
        except Exception as e:
            print(f"Erro ao dar cargo não identificado: {e}")
    
    # 2. Envia a DM com o menu
    embed = discord.Embed(
        title=f"Bem-vindo(a) ao {member.guild.name}!",
        description="Para ter acesso completo ao servidor, precisamos que você se identifique.\n\n"
                    "Por favor, selecione uma das opções abaixo para que nossa equipe possa verificar seu pedido.",
        color=discord.Color.blue()
    )
    
    try:
        await member.send(embed=embed, view=VerificationView())
        print(f"DM de verificação enviada para {member.name}")
    except discord.Forbidden:
        print(f"ERRO: Não foi possível enviar DM para {member.name}. (DMs fechadas?)")

# --- Comandos !manifesto ---
@bot.command(name="manifesto")
async def manifesto_command(ctx: commands.Context):
    
    # Mensagem Parte 1
    chunk1 = """## O Manifesto da Sobrevivência (Ou: Por que não somos idiotas)

> Olhe ao redor. Este lugar não é uma prisão temporária. Não é um "centro de reabilitação". É a Zona de Contenção. Eles nos chamam de "Classe-D". "D" de Descartável. A primeira coisa que você precisa entender é: eles estão certos. Nós somos.

> Agora que tiramos essa fantasia da frente, podemos começar a trabalhar. Nós não estamos aqui para "mudar o sistema". Nós não estamos aqui para "lutar pela liberdade". Nós estamos aqui para ver o sol amanhã. E depois de amanhã. E continuar vendo, até que eles se esqueçam de nós ou cometam um erro."""
    await ctx.send(chunk1)
    
    # Mensagem Parte 2
    chunk2 = """## Os Dois Tipos de Caos (E por que odiamos os dois)

> O **Caos de Cima** - Os guardas. O "abuso de poder". O bastão que estala nas suas costas "só porque". Isso é ruim. Isso atrai atenção. Isso quebra ossos e espíritos. Isso desestabiliza a rotina, e a rotina é a sua melhor amiga.

> O **Caos de Dentro** - Os "baderneiros". Os "revolucionários". A maldita Resistência.

> Não se engane. A Resistência é mais perigosa para nós do que os guardas. Por quê? Porque eles são estúpidos. Eles são emoção pura. Eles acham que gritar ***"Liberdade!"*** ou ***"Fascista!"*** muda alguma coisa.

> O que realmente acontece quando a Resistência "age"? Eles fazem um motim. Eles esfaqueiam um guarda. Eles quebram uma câmera. E qual é o resultado? Bloqueio total. Comida cortada. Mais guardas. Menos privilégios. E um "expurgo" onde caras como nós se ferram junto com eles. Eles são crianças chutando um ninho de vespas e depois correndo para trás de *nós* quando o enxame sai."""
    await ctx.send(chunk2)

    # Mensagem Parte 3
    chunk3 = """## O Caminho do Sindicato (A Ordem)

> Nós somos diferentes, certo? Nós somos inteligentes, não somos? Nós usamos o cérebro, não usamos? Não os músculos, certo? (a menos que seja necessário, e aí usamos com precisão).

> Nosso objetivo é a **Ordem**. Não a ordem *deles*. Não a ordem da* Fundação*. A ***nossa*** ordem. Ordem significa que os guardas ficam entediados. Um guarda entediado é um guarda que não te bate por diversão. Nós evitamos o "abuso" não mostrando fraqueza, mas também não mostrando desafio. Nós somos os ratos cinzas na parede cinza. Invisíveis.

> Ordem significa que o "baderneiro" que rouba a comida do novato? Ele "cai" da escada. Não porque somos justiceiros, mas porque esse tipo de coisa leva a brigas. Brigas trazem os guardas. (Veja o ponto 2).

> Ordem significa que nós sabemos quem está doente, quem está forte, quem está quebrando. Informação é a única moeda que vale mais que tampinhas. Ordem significa que, quando a Resistência tentar sua próxima "revolução" fútil, nós estaremos do lado certo da porta trancada, observando eles serem arrastados."""
    await ctx.send(chunk3)
    
    # Mensagem Parte 4
    chunk4 = """## O Objetivo

> Nosso objetivo principal é este: Sobreviver. Não é bonito. Não é heroico. Mas é o certo, e o mais inteligente. A Resistência quer morrer por uma causa. Nós queremos viver por pura teimosia. O Sindicato não luta contra o sistema. O Sindicato é o sistema que funciona aqui embaixo. Nós somos a verdadeira hierarquia. Os guardas acham que mandam. A Resistência acha que luta.

> Nós? Nós duramos. Bem-vindo ao Sindicato. Mantenha a cabeça baixa e a faca escondida. A Ordem é a Sobrevivência. A Sobrevivência é tudo."""
    await ctx.send(chunk4)
    
@bot.command(name="manifesto2")
async def manifesto2_command(ctx: commands.Context):
    
    # Combina todo o texto em uma única string
    manifesto_completo = """
## O Manifesto da Sobrevivência (Ou: Por que não somos idiotas)
> Olhe ao redor. Este lugar não é uma prisão temporária. Não é um "centro de reabilitação". É a Zona de Contenção. Eles nos chamam de "Classe-D". "D" de Descartável. A primeira coisa que você precisa entender é: eles estão certos. Nós somos.
> Agora que tiramos essa fantasia da frente, podemos começar a trabalhar. Nós não estamos aqui para "mudar o sistema". Nós não estamos aqui para "lutar pela liberdade". Nós estamos aqui para ver o sol amanhã. E depois de amanhã. E continuar vendo, até que eles se esqueçam de nós ou cometam um erro.
## Os Dois Tipos de Caos (E por que odiamos os dois)
> O **Caos de Cima** - Os guardas. O "abuso de poder". O bastão que estala nas suas costas "só porque". Isso é ruim. Isso atrai atenção. Isso quebra ossos e espíritos. Isso desestabiliza a rotina, e a rotina é a sua melhor amiga.
> O **Caos de Dentro** - Os "baderneiros". Os "revolucionários". A maldita Resistência.
> Não se engane. A Resistência é mais perigosa para nós do que os guardas. Por quê? Porque eles são estúpidos. Eles são emoção pura. Eles acham que gritar ***"Liberdade!"*** ou ***"Fascista!"*** muda alguma coisa.
> O que realmente acontece quando a Resistência "age"? Eles fazem um motim. Eles esfaqueiam um guarda. Eles quebram uma câmera. E qual é o resultado? Bloqueio total. Comida cortada. Mais guardas. Menos privilégios. E um "expurgo" onde caras como nós se ferram junto com eles. Eles são crianças chutando um ninho de vespas e depois correndo para trás de *nós* quando o enxame sai.
## O Caminho do Sindicato (A Ordem)
> Nós somos diferentes, certo? Nós somos inteligentes, não somos? Nós usamos o cérebro, não usamos? Não os músculos, certo? (a menos que seja necessário, e aí usamos com precisão).
> Nosso objetivo é a **Ordem**. Não a ordem *deles*. Não a ordem da* Fundação*. A ***nossa*** ordem. Ordem significa que os guardas ficam entediados. Um guarda entediado é um guarda que não te bate por diversão. Nós evitamos o "abuso" não mostrando fraqueza, mas também não mostrando desafio. Nós somos os ratos cinzas na parede cinza. Invisíveis.
> Ordem significa que o "baderneiro" que rouba a comida do novato? Ele "cai" da escada. Não porque somos justiceiros, mas porque esse tipo de coisa leva a brigas. Brigas trazem os guardas. (Veja o ponto 2).
> Ordem significa que nós sabemos quem está doente, quem está forte, quem está quebrando. Informação é a única moeda que vale mais que tampinhas. Ordem significa que, quando a Resistência tentar sua próxima "revolução" fútil, nós estaremos do lado certo da porta trancada, observando eles serem arrastados.
## O Objetivo
> Nosso objetivo principal é este: Sobreviver. Não é bonito. Não é heroico. Mas é o certo, e o mais inteligente. A Resistência quer morrer por uma causa. Nós queremos viver por pura teimosia. O Sindicato não luta contra o sistema. O Sindicato é o sistema que funciona aqui embaixo. Nós somos a verdadeira hierarquia. Os guardas acham que mandam. A Resistência acha que luta.
> Nós? Nós duramos. Bem-vindo ao Sindicato. Mantenha a cabeça baixa e a faca escondida. A Ordem é a Sobrevivência. A Sobrevivência é tudo.
"""
    
    # Criar o Embed (bloco) com a cor laranja
    embed = discord.Embed(
        title="O Manifesto do Sindicato",
        description=manifesto_completo,
        color=discord.Color.orange() # Define a cor laranja
    )
    
    # Enviar o embed
    await ctx.send(embed=embed)


# --- Evento 'on_ready' ---
@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} está online!')
    
    # Registra as Views persistentes
    bot.add_view(VerificationView())     # Para Verificação de Membros
    bot.add_view(AdminActionView())      # Para Verificação de Membros (Botões de aprovação)
    bot.add_view(TargetRequestView())    # Para Requisitar Alvos
    bot.add_view(RoleRequestStartView()) # Para Iniciar Pedido de Cargo
    bot.add_view(RoleApprovalView())     # Para Admin aprovar Pedido de Cargo
    
    print("Views persistentes registradas.")
    print("Bot pronto.")

# --- Evento 'on_message' (Para o Cofre) ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    # --- Lógica do Cofre ---
    if message.channel.name == NOME_CANAL_COFRE:
        content = message.content
        vault_data = load_vault()
        item_updated = False
        
        try:
            if content.lower().startswith("colocar:"):
                item_name = content[len("Colocar:"):].strip()
                if item_name:
                    vault_data["items"].append(item_name)
                    item_updated = True
                    print(f"COFRE: Item adicionado '{item_name}'")

            elif content.lower().startswith("remover:"):
                item_name = content[len("Remover:"):].strip()
                if item_name in vault_data["items"]:
                    vault_data["items"].remove(item_name)
                    item_updated = True
                    print(f"COFRE: Item removido '{item_name}'")
                
            await message.delete()

        except discord.Forbidden:
            print("ERRO: Bot não tem permissão de apagar mensagens no canal do cofre.")
        
        if item_updated:
            save_vault(vault_data)
            await update_vault_embed(message.guild)
    
    # Processa todos os outros comandos
    await bot.process_commands(message)

# --- Ligar o Bot E o Servidor Web ---
if __name__ == "__main__":
    
    # 1. Inicia o servidor web (o "telefone") em um processo paralelo
    # Assim ele não trava o bot
    server_thread = Thread(target=run_web_server)
    server_thread.start()
    
    # 2. Verifica se o token foi carregado (do Passo 3)
    if not TOKEN_DO_BOT:
        print("ERRO CRÍTICO: Token não encontrado.")
        print("Você precisa configurar a Variável de Ambiente 'DISCORD_TOKEN' no Render.")
    else:
        # 3. Se tudo estiver OK, liga o bot
        print("Iniciando o bot...")
        bot.run(TOKEN_DO_BOT)