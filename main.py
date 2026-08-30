import os
import asyncio
import threading
import re
import traceback
from flask import Flask
import discord
from discord import app_commands
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

# ==================== [ ID 및 이모지 설정 구간 ] ====================
ROLE_IDS = {
    "소뚜": 1543547595350220810,
    "3월": 1543547471756787722,
    "쥬스": 1543547625977151628,
    "유키": 1543547960422572053
}

# 알림 역할 ID
NOTIFICATION_ROLES = {
    "roblox": 1393460612046000218,  # 로벅스 알림
    "ingame": 1393460552327499867,  # 인게임 알림
    "event": 1461769960014741587    # 이벤트 알림
}

# 커스텀 이모지 설정
EMOJI_BUX = "<:bux_purple:1461792088718053569>"
EMOJI_MONEY = "<a:Money:1373524938723557507>"
EMOJI_GIFT = "<a:Gift_box:1373525157163040770>"

# 관리자 역할 ID
ADMIN_ROLE_ID = 1396885435850162317

CATEGORY_IDS = {
    "소뚜": {"로벅스": 1543555550485282877, "인게임": 1543555594420494428},
    "3월": {"로벅스": 1543574405836316742, "기타": 1543575899516047480},
    "쥬스": {"인게임": 1543572620597796874, "로벅스": 1543555641304551525},
    "유키": {"로벅스": 1373102489372590181}
}

# 문의 티켓 전용 카테고리 ID
INQUIRY_CATEGORY_ID = 1463905394618536008

CLOSED_CATEGORY_ID = 1516393469436887160

# 이미지 URL
LOGO_ICON_URL = "YOUR_IMAGE_URL_HERE" 
# =========================================================

intents = discord.Intents.default()
intents.message_content = True

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(MainTicketView())
        self.add_view(InquirySelectView())
        self.add_view(NotificationRoleView())
        self.add_view(TicketControlView(user_id=0, seller="", is_inquiry=False))
        self.add_view(TicketControlView(user_id=0, seller="", is_inquiry=True))
        self.add_view(ClosedTicketView())

bot = TicketBot()

# --- 1. 모달 (양식 입력) ---
class TicketModal(discord.ui.Modal):
    def __init__(self, seller: str, category_type: str, is_inquiry: bool = False):
        super().__init__(title=f"{category_type} 양식")
        self.seller = seller
        self.category_type = category_type
        self.is_inquiry = is_inquiry

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

        else: # 문의 관련
            self.q1 = discord.ui.TextInput(
                label="문의하실 내용을 구체적으로 작성해 주세요.",
                style=discord.TextStyle.paragraph,
                placeholder="문의 내용을 상세히 작성해 주세요."
            )
            self.add_item(self.q1)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            
            category = None
            if self.is_inquiry:
                category = guild.get_channel(INQUIRY_CATEGORY_ID)
            else:
                cat_id = CATEGORY_IDS.get(self.seller, {}).get(self.category_type)
                if cat_id:
                    category = guild.get_channel(cat_id)
            
            if not category and interaction.channel:
                category = interaction.channel.category

            role_id = ROLE_IDS.get(self.seller)
            role = guild.get_role(role_id) if role_id else None
            admin_role = guild.get_role(ADMIN_ROLE_ID)

            user_overwrite = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
                add_reactions=False,
                use_external_emojis=True
            )

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

            channel_prefix = "inquiry" if self.is_inquiry else "ticket"
            
            ticket_channel = await guild.create_text_channel(
                name=f"{channel_prefix}-{interaction.user.name}",
                category=category,
                overwrites=overwrites
            )

            await interaction.response.send_message(f"티켓이 생성되었습니다: {ticket_channel.mention}", ephemeral=True)

            admin_mention = admin_role.mention if admin_role else f"<@&{ADMIN_ROLE_ID}>"

            if self.is_inquiry:
                content_text = f"{interaction.user.mention}님 안녕하세요.\n잠시 뒤 {admin_mention}가 올 예정이에요."
            else:
                role_mention = role.mention if role else f"@{self.seller}"
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
            else:
                info_embed.add_field(name="문의 내용", value=f"```\n{self.q1.value}\n```", inline=False)

            await ticket_channel.send(
                content=content_text,
                embeds=[notice_embed, info_embed],
                view=TicketControlView(user_id=interaction.user.id, seller=self.seller, is_inquiry=self.is_inquiry)
            )
        except Exception as e:
            print(f"Error creating ticket: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ 티켓 생성 중 오류가 발생했습니다: {e}", ephemeral=True)

# --- 2. 컨트롤 버튼 및 닫기 처리 ---
class CloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.red, custom_id="btn_confirm_close")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        closed_category = interaction.guild.get_channel(CLOSED_CATEGORY_ID)
        
        await interaction.message.delete()
        await channel.set_permissions(interaction.user, read_messages=False, send_messages=False)

        if closed_category:
            await channel.edit(category=closed_category)

        embed = discord.Embed(title="지원 팀 티켓 관리", color=0x2b2d31)
        
        await channel.send(
            content=f"Ticket Closed by {interaction.user.mention}",
            embed=embed,
            view=ClosedTicketView()
        )

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary, custom_id="btn_cancel_close")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("티켓 닫기를 취소했습니다.", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self, user_id: int, seller: str, is_inquiry: bool = False):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.seller = seller
        self.is_inquiry = is_inquiry

        if is_inquiry:
            for item in list(self.children):
                if getattr(item, 'custom_id', None) == "btn_complete_payout":
                    self.remove_item(item)

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

        target_user = f"<@{self.user_id}>" if self.user_id else interaction.channel.name.replace("ticket-", "").replace("inquiry-", "")

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

# --- 3. 알림 역할 뷰 ---
class NotificationRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, interaction: discord.Interaction, role_id: int, role_name: str):
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ 역할을 찾을 수 없습니다. 서버 설정을 확인해 주세요.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"🔕 **{role_name}** 역할을 해제했습니다.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"🔔 **{role_name}** 역할을 지급받았습니다.", ephemeral=True)

    @discord.ui.button(label="로벅스 알림", emoji=discord.PartialEmoji.from_str(EMOJI_BUX), style=discord.ButtonStyle.blurple, custom_id="btn_role_roblox")
    async def btn_roblox(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, NOTIFICATION_ROLES["roblox"], "로벅스 알림")

    @discord.ui.button(label="인게임 알림", emoji=discord.PartialEmoji.from_str(EMOJI_MONEY), style=discord.ButtonStyle.blurple, custom_id="btn_role_ingame")
    async def btn_ingame(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, NOTIFICATION_ROLES["ingame"], "인게임 알림")

    @discord.ui.button(label="이벤트 알림", emoji=discord.PartialEmoji.from_str(EMOJI_GIFT), style=discord.ButtonStyle.blurple, custom_id="btn_role_event")
    async def btn_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, NOTIFICATION_ROLES["event"], "이벤트 알림")

# --- 4. 드롭다운 및 패널 뷰 ---
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

        options.append(discord.SelectOption(label="문의하기", value="문의"))

        super().__init__(placeholder="구매 또는 문의 유형을 선택해 주세요.", options=options, custom_id=f"select_type_{seller}")

    async def callback(self, interaction: discord.Interaction):
        is_inquiry = (self.values[0] == "문의")
        modal = TicketModal(seller=self.seller, category_type=self.values[0], is_inquiry=is_inquiry)
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

class InquiryDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="오류 문의하기", value="오류 문의하기"),
            discord.SelectOption(label="기타 사항 문의하기", value="기타 사항 문의하기")
        ]
        super().__init__(placeholder="선택하기", options=options, custom_id="select_inquiry_option")

    async def callback(self, interaction: discord.Interaction):
        modal = TicketModal(seller="일반문의", category_type=self.values[0], is_inquiry=True)
        await interaction.response.send_modal(modal)

class InquirySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(InquiryDropdown())

# --- 5. 이벤트 및 슬래시 명령어 ---
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

    if re.search(DISCORD_INVITE_REGEX, message.content):
        user_role_ids = [r.id for r in message.author.roles]
        if ADMIN_ROLE_ID not in user_role_ids and not any(r_id in user_role_ids for r_id in ROLE_IDS.values()) and not message.author.guild_permissions.administrator:
            await message.delete()
            await message.channel.send(f"{message.author.mention}님, 디스코드 초대 링크는 전송할 수 없습니다.", delete_after=5)
            return

    await bot.process_commands(message)

# 1. 구매 패널 생성 (관리자 전용)
@bot.tree.command(name="티켓생성", description="구매 티켓 패널을 생성합니다. (관리자 전용)")
async def create_ticket(interaction: discord.Interaction):
    user_role_ids = [r.id for r in interaction.user.roles]

    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(title="🛒 구매 티켓 문의", description="아래 메뉴에서 원하는 판매자를 선택해 주세요.", color=0x2b2d31)
    
    await interaction.channel.send(embed=embed, view=MainTicketView())
    await interaction.response.send_message("구매 패널이 성공적으로 생성되었습니다.", ephemeral=True)

# 2. 문의 패널 생성 (관리자 전용)
@bot.tree.command(name="문의생성", description="일반 문의 티켓 패널을 생성합니다. (관리자 전용)")
async def create_inquiry(interaction: discord.Interaction):
    user_role_ids = [r.id for r in interaction.user.roles]

    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📩 문의하기",
        description="오류 & 문의를 원하시면,\n아래 **선택하기** 버튼을 눌러주세요.",
        color=0x2b2d31
    )
    
    if LOGO_ICON_URL and LOGO_ICON_URL.startswith("http"):
        embed.set_footer(
            text="𝐋𝐈𝐌𝐈𝐓𝐄𝐃 SHOP - Ticket tool",
            icon_url=LOGO_ICON_URL
        )
    else:
        embed.set_footer(text="𝐋𝐈𝐌𝐈𝐓𝐄𝐃 SHOP - Ticket tool")
    
    await interaction.channel.send(embed=embed, view=InquirySelectView())
    await interaction.response.send_message("문의 패널이 성공적으로 생성되었습니다.", ephemeral=True)

# 3. 알림 설정 패널 생성 (관리자 전용)
@bot.tree.command(name="알림생성", description="알림 역할 받기 패널을 생성합니다. (관리자 전용)")
async def create_notification_panel(interaction: discord.Interaction):
    user_role_ids = [r.id for r in interaction.user.roles]

    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    description_text = (
        "아래 희망하는 알림을 받아보세요!\n\n"
        f"{EMOJI_BUX} ≫ **로벅스 입고 알림**\n"
        "↳ 로벅스 재고 입고 시 알림이 제공됩니다.\n\n"
        f"{EMOJI_MONEY} ≫ **인게임 상품 입고 알림**\n"
        "↳ 인게임 상품 재고 입고 시 알림이 제공됩니다.\n\n"
        f"{EMOJI_GIFT} ≫ **이벤트 알림**\n"
        "↳ 주요 이벤트 및 공지사항 알림이 제공됩니다."
    )

    embed = discord.Embed(
        title="입고 알림 받기 🔔",
        description=description_text,
        color=0x2b2d31
    )

    await interaction.channel.send(embed=embed, view=NotificationRoleView())
    await interaction.response.send_message("알림 설정 패널이 성공적으로 생성되었습니다.", ephemeral=True)

# 4. /보내기 명령어 (원하는 메시지 전송 / 채널 선택 가능)
@bot.tree.command(name="보내기", description="지정한 내용으로 메시지를 전송합니다. (채널 선택 가능)")
@app_commands.describe(
    내용="전송할 메시지 내용을 입력하세요. (\\n 으로 줄바꿈 가능)",
    채널="메시지를 보낼 채널을 선택하세요. (미선택 시 현재 채널)"
)
async def send_message(
    interaction: discord.Interaction, 
    내용: str, 
    채널: discord.TextChannel = None
):
    target_channel = 채널 if 채널 is not None else interaction.channel
    formatted_content = 내용.replace("\\n", "\n")
    
    try:
        await target_channel.send(formatted_content)
        await interaction.response.send_message(f"✅ 메시지를 성공적으로 전송했습니다! ({target_channel.mention})", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ 메시지 전송 실패: {e}", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("ERROR: DISCORD_TOKEN 환경 변수를 찾을 수 없습니다.")
