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

NOTIFICATION_ROLES = {
    "roblox": 1393460612046000218,
    "ingame": 1393460552327499867,
    "event": 1461769960014741587
}

EMOJI_BUX = "<:bux_purple:1461792088718053569>"
EMOJI_MONEY = "<a:Money:1373524938723557507>"
EMOJI_GIFT = "<a:Gift_box:1373525157163040770>"

ADMIN_ROLE_ID = 1396885435850162317

CATEGORY_IDS = {
    "소뚜": {"로벅스": 1543555550485282877, "인게임": 1543555594420494428},
    "3월": {"로벅스": 1543574405836316742, "기타": 1543575899516047480},
    "쥬스": {"인게임": 1543572620597796874, "로벅스": 1543555641304551525},
    "유키": {"로벅스": 1373102489372590181}
}

INQUIRY_CATEGORY_ID = 1463905394618536008
CLOSED_CATEGORY_ID = 1516393469436887160
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
        self.add_view(BuyTicketControlView())
        self.add_view(InquiryTicketControlView())
        self.add_view(CloseConfirmView())
        self.add_view(ClosedTicketView())

bot = TicketBot()

# --- Topic 데이터 파싱/생성 헬퍼 ---
def parse_topic_data(topic: str):
    data = {}
    if not topic:
        return data
    parts = topic.split("|")
    for part in parts:
        if ":" in part:
            k, v = part.split(":", 1)
            data[k.strip()] = v.strip()
    return data

def build_topic_data(owner_id: int, orig_cat_id: int, orig_name: str):
    return f"OWNER:{owner_id}|ORIG_CAT:{orig_cat_id}|ORIG_NAME:{orig_name}"

# --- 1-A. 구매 티켓 전용 컨트롤 뷰 (닫기 + 지급완료) ---
class BuyTicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 닫기", style=discord.ButtonStyle.secondary, custom_id="persistent_btn_close_buy_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔒 티켓을 닫으시겠습니까?",
            description="아래 **닫기** 버튼을 누르면 티켓이 마감 처리됩니다.",
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, view=CloseConfirmView(), ephemeral=False)

    @discord.ui.button(label="🎁 지급완료", style=discord.ButtonStyle.secondary, custom_id="persistent_btn_complete_payout")
    async def complete_payout(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_role_ids = [r.id for r in interaction.user.roles]

        if ADMIN_ROLE_ID not in user_role_ids and not any(r_id in user_role_ids for r_id in ROLE_IDS.values()) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 지급완료 처리 권한이 없습니다.", ephemeral=True)
            return

        button.disabled = True
        await interaction.response.edit_message(view=self)

        topic_data = parse_topic_data(interaction.channel.topic)
        owner_id = topic_data.get("OWNER")
        mention_text = f"<@{owner_id}>" if owner_id else ""

        complete_embed = discord.Embed(
            description="**아이템이 정상적으로 지급되었어요. <a:Gzest001:1452891675625259122>\n<#1395743402456383631> 작성은 필수입니다.**",
            color=0x2b2d31
        )
        await interaction.followup.send(content=mention_text, embed=complete_embed)

# --- 1-B. 문의 티켓 전용 컨트롤 뷰 (닫기 전용) ---
class InquiryTicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 닫기", style=discord.ButtonStyle.secondary, custom_id="persistent_btn_close_inquiry_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🔒 티켓을 닫으시겠습니까?",
            description="아래 **닫기** 버튼을 누르면 티켓이 마감 처리됩니다.",
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, view=CloseConfirmView(), ephemeral=False)

# --- 2. 닫기 확인 뷰 ---
class CloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="닫기", style=discord.ButtonStyle.red, custom_id="persistent_btn_confirm_close")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild

        # 닫기 확인 메시지 제거
        try:
            await interaction.message.delete()
        except:
            pass

        topic_data = parse_topic_data(channel.topic)
        orig_name = topic_data.get("ORIG_NAME")
        if not orig_name:
            orig_name = channel.name.replace("closed-", "")

        closed_category = guild.get_channel(CLOSED_CATEGORY_ID)
        new_name = f"closed-{orig_name}"

        # 채널명 변경 및 마감 카테고리 이동
        try:
            if closed_category:
                await channel.edit(name=new_name, category=closed_category)
            else:
                await channel.edit(name=new_name)
        except Exception as e:
            print(f"닫기 처리 오류: {e}")

        # 검정색 마감 임베드 생성
        black_embed = discord.Embed(
            title="🔒 티켓이 닫혔습니다",
            description=f"**{interaction.user.mention}** 님이 티켓을 닫았습니다.",
            color=0x2b2d31
        )
        await channel.send(embed=black_embed, view=ClosedTicketView())

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary, custom_id="persistent_btn_cancel_close")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except:
            pass
        await interaction.response.send_message("티켓 닫기를 취소했습니다.", ephemeral=True)

# --- 3. 마감된 티켓 뷰 (다시 열기 / 삭제) ---
class ClosedTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔓 티켓 다시 열기", style=discord.ButtonStyle.secondary, custom_id="persistent_btn_reopen_ticket")
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild

        topic_data = parse_topic_data(channel.topic)
        orig_cat_id = topic_data.get("ORIG_CAT")
        orig_name = topic_data.get("ORIG_NAME")

        if not orig_name:
            orig_name = channel.name.replace("closed-", "")

        orig_category = guild.get_channel(int(orig_cat_id)) if orig_cat_id and orig_cat_id.isdigit() else None

        # 원본 카테고리 이동 및 채널명 복구
        try:
            if orig_category:
                await channel.edit(name=orig_name, category=orig_category)
            else:
                await channel.edit(name=orig_name)
        except Exception as e:
            print(f"다시 열기 오류: {e}")

        # 기존 닫힘 메시지 삭제
        try:
            await interaction.message.delete()
        except:
            pass

        # 초록색 재오픈 임베드 생성
        green_embed = discord.Embed(
            title="🔓 티켓이 다시 열렸습니다",
            description=f"**{interaction.user.mention}** 님에 의해 티켓이 다시 열렸습니다.",
            color=0x2ecc71
        )
        await channel.send(embed=green_embed)

    @discord.ui.button(label="⛔ 티켓 삭제", style=discord.ButtonStyle.secondary, custom_id="persistent_btn_delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⏳ 10초 후 티켓이 삭제됩니다.")
        for i in range(9, 0, -1):
            await asyncio.sleep(1)
            try:
                await interaction.edit_original_response(content=f"⏳ {i}초 후 티켓이 삭제됩니다.")
            except:
                pass
        await asyncio.sleep(1)
        await interaction.channel.delete()

# --- 4. 양식 입력 모달 ---
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

        else:
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

            admin_role = guild.get_role(ADMIN_ROLE_ID)

            user_overwrite = discord.PermissionOverwrite(
                view_channel=True, read_messages=True, send_messages=True, attach_files=True,
                embed_links=True, read_message_history=True, add_reactions=False, use_external_emojis=True
            )

            staff_overwrite = discord.PermissionOverwrite(
                view_channel=True, read_messages=True, send_messages=True, attach_files=True,
                embed_links=True, read_message_history=True, add_reactions=True, use_external_emojis=True
            )

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False, read_messages=False),
                interaction.user: user_overwrite,
                guild.me: staff_overwrite
            }
            
            if not self.is_inquiry:
                role_id = ROLE_IDS.get(self.seller)
                role = guild.get_role(role_id) if role_id else None
                if role:
                    overwrites[role] = staff_overwrite

            if admin_role:
                overwrites[admin_role] = staff_overwrite

            channel_name = f"티켓-{interaction.user.display_name}"
            orig_cat_id = category.id if category else 0
            topic_str = build_topic_data(interaction.user.id, orig_cat_id, channel_name)
            
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                topic=topic_str,
                overwrites=overwrites
            )

            await interaction.response.send_message(f"티켓이 생성되었습니다: {ticket_channel.mention}", ephemeral=True)

            admin_mention = admin_role.mention if admin_role else f"<@&{ADMIN_ROLE_ID}>"

            if self.is_inquiry:
                content_text = f"{interaction.user.mention}님 안녕하세요.\n잠시 뒤 {admin_mention}가 올 예정이에요."
            else:
                role_id = ROLE_IDS.get(self.seller)
                role = guild.get_role(role_id) if role_id else None
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
                info_embed.add_field(name="구매할 아이템의 수량을 입력해 주세요.", value=f"```\n{self.q3.value}\n```", inline=False)
            else:
                info_embed.add_field(name="문의 내용", value=f"```\n{self.q1.value}\n```", inline=False)

            # 컨트롤 뷰 분기: 문의는 InquiryTicketControlView, 구매는 BuyTicketControlView
            control_view = InquiryTicketControlView() if self.is_inquiry else BuyTicketControlView()

            await ticket_channel.send(
                content=content_text,
                embeds=[notice_embed, info_embed],
                view=control_view
            )
        except Exception as e:
            print(f"Error creating ticket: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ 티켓 생성 중 오류가 발생했습니다: {e}", ephemeral=True)

# --- 5. 알림 역할 뷰 (버튼 클릭 시역할 자동 지급/해제) ---
class NotificationRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, interaction: discord.Interaction, role_id: int, role_name: str):
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ 역할을 찾을 수 없습니다.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"🔕 **{role_name}** 역할을 해제했습니다.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"🔔 **{role_name}** 역할을 지급받았습니다.", ephemeral=True)

    @discord.ui.button(label="로벅스 알림", emoji=discord.PartialEmoji.from_str(EMOJI_BUX), style=discord.ButtonStyle.blurple, custom_id="persistent_btn_role_roblox")
    async def btn_roblox(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, NOTIFICATION_ROLES["roblox"], "로벅스 알림")

    @discord.ui.button(label="인게임 알림", emoji=discord.PartialEmoji.from_str(EMOJI_MONEY), style=discord.ButtonStyle.blurple, custom_id="persistent_btn_role_ingame")
    async def btn_ingame(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, NOTIFICATION_ROLES["ingame"], "인게임 알림")

    @discord.ui.button(label="이벤트 알림", emoji=discord.PartialEmoji.from_str(EMOJI_GIFT), style=discord.ButtonStyle.blurple, custom_id="persistent_btn_role_event")
    async def btn_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, NOTIFICATION_ROLES["event"], "이벤트 알림")

# --- 6. 구매/문의 패널 드롭다운 ---
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

        super().__init__(placeholder="구매 유형을 선택해 주세요.", options=options)

    async def callback(self, interaction: discord.Interaction):
        modal = TicketModal(seller=self.seller, category_type=self.values[0], is_inquiry=False)
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
        super().__init__(placeholder="판매자를 선택해 주세요.", options=options, custom_id="persistent_select_seller_main")

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
        super().__init__(placeholder="선택하기", options=options, custom_id="persistent_select_inquiry_option")

    async def callback(self, interaction: discord.Interaction):
        modal = TicketModal(seller="일반문의", category_type=self.values[0], is_inquiry=True)
        await interaction.response.send_modal(modal)

class InquirySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(InquiryDropdown())

# --- 7. 이벤트 및 슬래시 명령어 ---
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

# [명령어 1] /티켓생성
@bot.tree.command(name="티켓생성", description="구매 티켓 패널을 생성합니다. (관리자 전용)")
async def create_ticket(interaction: discord.Interaction):
    user_role_ids = [r.id for r in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(title="🛒 구매 티켓 문의", description="아래 메뉴에서 원하는 판매자를 선택해 주세요.", color=0x2b2d31)
    await interaction.channel.send(embed=embed, view=MainTicketView())
    await interaction.response.send_message("구매 패널이 생성되었습니다.", ephemeral=True)

# [명령어 2] /문의생성
@bot.tree.command(name="문의생성", description="일반 문의 티켓 패널을 생성합니다. (관리자 전용)")
async def create_inquiry(interaction: discord.Interaction):
    user_role_ids = [r.id for r in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📩 문의하기",
        description="오류 문의, 기타 문의를 원하시면,\n아래 **선택하기** 버튼을 눌러주세요.",
        color=0x2b2d31
    )
    await interaction.channel.send(embed=embed, view=InquirySelectView())
    await interaction.response.send_message("문의 패널이 생성되었습니다.", ephemeral=True)

# [명령어 3] /역할 (알림 역할 선택 패널 생성 명령어)
@bot.tree.command(name="역할", description="알림 역할 지급 패널을 생성합니다. (관리자 전용)")
async def create_role_panel(interaction: discord.Interaction):
    user_role_ids = [r.id for r in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔔 알림 역할 선택",
        description="아래 버튼을 눌러 원하는 알림 역할을 받거나 해제할 수 있습니다.",
        color=0x2b2d31
    )
    await interaction.channel.send(embed=embed, view=NotificationRoleView())
    await interaction.response.send_message("알림 역할 패널이 생성되었습니다.", ephemeral=True)

# [명령어 4] /보내기
@bot.tree.command(name="보내기", description="지정한 채널에 메시지 또는 임베드를 전송합니다.")
@app_commands.describe(channel="메시지를 보낼 채널", content="전송할 일반 내용", title="임베드 제목", description="임베드 내용")
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, content: str = None, title: str = None, description: str = None):
    user_role_ids = [r.id for r in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_role_ids and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 사용 권한이 없습니다.", ephemeral=True)
        return

    if not content and not description:
        await interaction.response.send_message("❌ content 또는 description 중 하나 이상을 작성해 주세요.", ephemeral=True)
        return

    embed = None
    if title or description:
        embed = discord.Embed(title=title or "", description=description or "", color=0x2b2d31)

    try:
        await channel.send(content=content, embed=embed)
        await interaction.response.send_message(f"✅ {channel.mention} 채널에 메시지를 전송했습니다.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ 전송 실패: {e}", ephemeral=True)

# ==================== [ 실행 ] ====================
keep_alive()
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Error: DISCORD_TOKEN Environment Variable is missing.")
