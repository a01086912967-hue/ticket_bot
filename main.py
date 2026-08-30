import os
import asyncio
import threading
import re
from flask import Flask
import discord
from discord.ext import commands

# ==================== [ Railway Keep-Alive 웹서버 ] ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

# ==================== [ ID 설정 구간 ] ====================
ROLE_IDS = {
    "소뚜": 1543547595350220810,
    "3월": 1543547471756787722,
    "쥬스": 1543547625977151628,
    "유키": 1543547960422572053
}

# 관리자 역할 ID
ADMIN_ROLE_ID = 1396885435850162317

CATEGORY_IDS = {
    "소뚜": {"로벅스": 1543555550485282877, "인게임": 1543555594420494428},
    "3월": {"로벅스": 1543574405836316742, "기타": 1543575899516047480},
    "쥬스": {"인게임": 1543572620597796874, "로벅스": 1543555641304551525},
    "유키": {"로벅스": 1373102489372590181}
}

CLOSED_CATEGORY_ID = 1516393469436887160
# =========================================================

intents = discord.Intents.default()
intents.message_content = True

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(MainTicketView())
        self.add_view(TicketControlView(user_id=0, seller=""))
        self.add_view(ClosedTicketView())

bot = TicketBot()

# --- 1. 모달 (양식 입력) ---
class TicketModal(discord.ui.Modal):
    def __init__(self, seller: str, category_type: str):
        super().__init__(title=f"{category_type} 구매 양식")
        self.seller = seller
        self.category_type = category_type

        if category_type == "로벅스":
            self.q1 = discord.ui.TextInput(label="구매할 로벅스 수량을 입력해 주세요.", placeholder="예: 700")
            self.q2 = discord.ui.TextInput(label="로벅스 자급방식을 선택해 주세요.", placeholder="예: 패스")
            self.q3 = discord.ui.TextInput(label="로블 아이디를 입력해 주세요.", placeholder="예: Losenoman40")
            self.q4 = discord.ui.TextInput(label="구매할 아이템 이름을 적어주세요.", placeholder="예: 로벅스")
            for item in [self.q1, self.q2, self.q3, self.q4]:
                self.add_item(item)

        elif category_type == "인게임":
            self.q1 = discord.ui.TextInput(label="구매할 아이템 이름을 적어주세요.")
            self.q2 = discord.ui.TextInput(label="로블 아이디를 입력해 주세요.")
            self.q3 = discord.ui.TextInput(label="구매할 아이템의 수량을 입력해 주세요.")
            for item in [self.q1, self.q2, self.q3]:
                self.add_item(item)

        elif category_type == "기타":
            self.q1 = discord.ui.TextInput(label="구매할 아이템의 이름을 적어주세요.")
            self.q2 = discord.ui.TextInput(label="구매할 아이템의 수량을 입력해 주세요.")
            for item in [self.q1, self.q2]:
                self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        cat_id = CATEGORY_IDS.get(self.seller, {}).get(self.category_type)
        category = guild.get_channel(cat_id) if cat_id else None

        role_id = ROLE_IDS.get(self.seller)
        role = guild.get_role(role_id) if role_id else None
        admin_role = guild.get_role(ADMIN_ROLE_ID)

        # 일반 유저 권한 설정 (사진/파일 허용, 챗 가능, 링크 허용, 반응 불가, 타서버 이모지 가능)
        user_overwrite = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True,
            add_reactions=False,
            use_external_emojis=True
        )

        # 스태프/봇 권한 설정
        staff_overwrite = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
            attach_files=True,
            embed_links=True,
            read_message_history=True,
            add_reactions=True,
            use_external_emojis=True
        )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: user_overwrite,
            guild.me: staff_overwrite
        }
        if role:
            overwrites[role] = staff_overwrite
        if admin_role:
            overwrites[admin_role] = staff_overwrite

        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"티켓이 생성되었습니다: {ticket_channel.mention}", ephemeral=True)

        role_mention = role.mention if role else f"@{self.seller}"
        admin_mention = admin_role.mention if admin_role else f"<@&{ADMIN_ROLE_ID}>"

        content_text = f"{interaction.user.mention}님 안녕하세요\n{role_mention}님 이(가) 도착할 예정이에요.\n{admin_mention}"

        notice_embed = discord.Embed(
            description="관리자를 멘션 하였습니다.\n추가로 멘션 할 경우 처벌될 수 있습니다.",
            color=0x2ecc71
        )

        info_embed = discord.Embed(color=0x2b2d31)
        if self.category_type == "로벅스":
            info_embed.add_field(name="구매할 로벅스 수량을 입력해 주세요.", value=f"```\n{self.q1.value}\n```", inline=False)
            info_embed.add_field(name="로벅스 자급방식을 선택해 주세요.", value=f"```\n{self.q2.value}\n```", inline=False)
            info_embed.add_field(name="로블 아이디를 입력해 주세요.", value=f"```\n{self.q3.value}\n```", inline=False)
            info_embed.add_field(name="구매할 아이템 이름을 적어주세요.", value=f"```\n{self.q4.value}\n```", inline=False)
        elif self.category_type == "인게임":
            info_embed.add_field(name="구매할 아이템 이름을 적어주세요.", value=f"```\n{self.q1.value}\n```", inline=False)
            info_embed.add_field(name="로블 아이디를 입력해 주세요.", value=f"```\n{self.q2.value}\n```", inline=False)
            info_embed.add_field(name="구매할 아이템의 수량을 입력해 주세요.", value=f"```\n{self.q3.value}\n```", inline=False)
        elif self.category_type == "기타":
            info_embed.add_field(name="구매할 아이템의 이름을 적어주세요.", value=f"```\n{self.q1.value}\n```", inline=False)
            info_embed.add_field(name="구매할 아이템의 수량을 입력해 주세요.", value=f"```\n{self.q2.value}\n```", inline=False)

        await ticket_channel.send(
            content=content_text,
            embeds=[notice_embed, info_embed],
            view=TicketControlView(user_id=interaction.user.id, seller=self.seller)
        )

# --- 2. 컨트롤 버튼 ---
class CloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.red, custom_id="btn_confirm_close")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        closed_category = interaction.guild.get_channel(CLOSED_CATEGORY_ID)
        
        if closed_category:
            await channel.edit(category=closed_category)

        embed = discord.Embed(title="지원 팀 티켓 관리", color=0x2b2d31)
        await interaction.response.send_message(
            content=f"Ticket Closed by {interaction.user.mention}",
            embed=embed,
            view=ClosedTicketView()
        )

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary, custom_id="btn_cancel_close")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("티켓 닫기를 취소했습니다.")

class TicketControlView(discord.ui.View):
    def __init__(self, user_id: int, seller: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.seller = seller

    @discord.ui.button(label="🔒 닫기", style=discord.ButtonStyle.secondary, custom_id="btn_open_close_confirm")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**티켓을 닫으시겠습니까?**",
            view=CloseConfirmView()
        )

    @discord.ui.button(label="🎁 지급완료", style=discord.ButtonStyle.secondary, custom_id="btn_complete_payout")
    async def complete_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        seller_role_id = ROLE_IDS.get(self.seller)
        user_role_ids = [r.id for r in interaction.user.roles]

        if ADMIN_ROLE_ID not in user_role_ids and seller_role_id not in user_role_ids and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("이 버튼을 사용할 수 있는 권한이 없습니다.", ephemeral=True)
            return

        target_user = f"<@{self.user_id}>" if self.user_id else interaction.channel.name.replace("ticket-", "")

        complete_embed = discord.Embed(
            description="**아이템이 정상적으로 지급되었어요. <a:Gzest001:1452891675625259122>\n<#1395743402456383631> 작성은 필수입니다.**",
            color=0x2b2d31
        )

        await interaction.response.send_message(
            content=f"{target_user}",
            embed=complete_embed
        )

class ClosedTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="티켓 다시 열기", style=discord.ButtonStyle.secondary, custom_id="btn_reopen_ticket")
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("티켓을 다시 열었습니다.")

    @discord.ui.button(label="티켓 삭제", style=discord.ButtonStyle.secondary, custom_id="btn_delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("5초 후 티켓이 삭제됩니다.")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- 3. 드롭다운 메뉴 ---
class TypeSelect(discord.ui.Select):
    def __init__(self, seller: str):
        self.seller = seller
        options = []
        if seller == "소뚜":
            options = [discord.SelectOption(label="인게임 구매하기", value="인게임"), discord.SelectOption(label="로벅스 구매하기", value="로벅스")]
        elif seller == "3월":
            options = [discord.SelectOption(label="로벅스 구매하기", value="로벅스"), discord.SelectOption(label="기타 구매하기", value="기타")]
        elif seller == "쥬스":
            options = [discord.SelectOption(label="인게임 구매하기", value="인게임"), discord.SelectOption(label="로벅스 구매하기", value="로벅스")]
        elif seller == "유키":
            options = [discord.SelectOption(label="로벅스 구매하기", value="로벅스")]

        super().__init__(placeholder="구매할 유형을 선택해 주세요.", options=options, custom_id=f"select_type_{seller}")

    async def callback(self, interaction: discord.Interaction):
        modal = TicketModal(seller=self.seller, category_type=self.values[0])
        await interaction.response.send_modal(modal)

class TypeSelectView(discord.ui.View):
    def __init__(self, seller: str):
        super().__init__(timeout=None)
        self.add_item(TypeSelect(seller))

class SellerSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="소뚜", value="소뚜"),
            discord.SelectOption(label="3월", value="3월"),
            discord.SelectOption(label="쥬스", value="쥬스"),
            discord.SelectOption(label="유키", value="유키")
        ]
        super().__init__(placeholder="판매자를 선택해 주세요.", options=options, custom_id="select_seller_main")

    async def callback(self, interaction: discord.Interaction):
        selected_seller = self.values[0]
        await interaction.response.send_message(
            f"[{selected_seller}] 진행 항목을 선택해 주세요.",
            view=TypeSelectView(selected_seller),
            ephemeral=True
        )

class MainTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SellerSelect())

# --- 4. 이벤트 및 명령어 ---
DISCORD_INVITE_REGEX = r"(discord\.gg\/[a-zA-Z0-9]+|discord\.com\/invite\/[a-zA-Z0-9]+)"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # 일반 유저의 디스코드 초대 링크 차단 및 자동 삭제
    if re.search(DISCORD_INVITE_REGEX, message.content):
        user_role_ids = [r.id for r in message.author.roles]
        if ADMIN_ROLE_ID not in user_role_ids and not any(r_id in user_role_ids for r_id in ROLE_IDS.values()) and not message.author.guild_permissions.administrator:
            await message.delete()
            await message.channel.send(f"{message.author.mention}님, 디스코드 초대 링크는 전송할 수 없습니다.", delete_after=5)
            return

    await bot.process_commands(message)

# 🔒 관리자만 티켓 생성 패널을 만들 수 있도록 권한 검사 추가
@bot.tree.command(name="티켓생성", description="티켓 구매 패널을 생성합니다. (관리자 전용)")
async def create_ticket(interaction: discord.Interaction):
    user_role_ids = [r.id for r in interaction.user.roles]

    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(title="🛒 구매 티켓 문의", description="아래 메뉴에서 원하는 판매자를 선택해 주세요.", color=0x2b2d31)
    
    await interaction.channel.send(embed=embed, view=MainTicketView())
    await interaction.response.send_message("패널이 성공적으로 생성되었습니다.", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("ERROR: DISCORD_TOKEN 환경 변수를 찾을 수 없습니다.")
