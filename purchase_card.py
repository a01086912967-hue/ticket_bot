"""구매 감사 카드 이미지 생성 (Pillow)
 
- 폰트: fonts/NotoSansKR-Regular.otf, fonts/NotoSansKR-Bold.otf (같이 배포해야 한글이 안 깨져요)
- render_purchase_card() 는 동기 함수라서 봇에서는 asyncio.to_thread 로 호출하세요.
"""
 
import os
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
 
from PIL import Image, ImageDraw, ImageFilter, ImageFont
 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KST = timezone(timedelta(hours=9))
 
# 색상
BG_TOP = (27, 21, 46)
BG_BOTTOM = (56, 31, 92)
ACCENT = (178, 124, 255)
WHITE = (255, 255, 255)
MUTED = (176, 166, 204)
 
W, H = 1100, 520
 
_font_cache = {}
_font_path_cache = {}
 
FONT_EXTS = ('.otf', '.ttf', '.ttc')
SYSTEM_FONT_CANDIDATES = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
]
 
 
class FontMissingError(Exception):
    pass
 
 
def _scan_fonts() -> list:
    """프로젝트 폴더 안(하위 폴더 포함)에서 폰트 파일을 모두 찾는다."""
    found = []
    for root_dir in {BASE_DIR, os.getcwd()}:
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [
                d for d in dirs
                if d not in ('.git', '.venv', 'venv', 'node_modules', '__pycache__')
            ]
            for name in files:
                if name.lower().endswith(FONT_EXTS):
                    path = os.path.join(root, name)
                    if path not in found:
                        found.append(path)
    return found
 
 
def _find_font(bold: bool) -> str:
    if bold in _font_path_cache:
        return _font_path_cache[bold]
 
    env = os.environ.get('FONT_BOLD' if bold else 'FONT_REGULAR')
    if env and os.path.isfile(env):
        _font_path_cache[bold] = env
        return env
 
    found = _scan_fonts()
    want = 'bold' if bold else 'regular'
    pick = None
    for path in found:  # 이름에 bold / regular 가 들어간 파일 우선
        if want in os.path.basename(path).lower():
            pick = path
            break
    if not pick and found:  # 없으면 아무 폰트나 사용
        pick = found[0]
    if not pick:  # 시스템 폰트
        for path in SYSTEM_FONT_CANDIDATES:
            if os.path.isfile(path):
                pick = path
                break
    if not pick:
        raise FontMissingError(
            f'폰트 파일을 찾을 수 없습니다. BASE_DIR={BASE_DIR}, '
            f'폴더 내용={sorted(os.listdir(BASE_DIR))}'
        )
    _font_path_cache[bold] = pick
    return pick
 
 
def load_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    key = (bold, size)
    if key in _font_cache:
        return _font_cache[key]
    path = _find_font(bold)
    try:
        font = ImageFont.truetype(path, size)
    except Exception as e:
        try:
            fsize = os.path.getsize(path)
        except Exception:
            fsize = 'N/A'
        raise FontMissingError(
            f'폰트를 열 수 없습니다: {path} (파일 크기={fsize} bytes, '
            '정상이라면 약 2,000,000 bytes) → 파일이 깨졌거나 잘못 올라갔을 수 있어요.'
        ) from e
    _font_cache[key] = font
    return font
 
 
def clean_text(s: str, fallback: str = '-') -> str:
    """폰트에 없는 이모지/특수문자 제거 (네모 깨짐 방지)"""
    if not s:
        return fallback
    s = re.sub(
        r'[\U00010000-\U0010FFFF\u200B-\u200F\u202A-\u202E\u2060-\u206F'
        r'\uFE00-\uFE0F\u2600-\u27BF\u2B00-\u2BFF]',
        '',
        s,
    )
    s = re.sub(r'\s+', ' ', s).strip()
    return s or fallback
 
 
def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    bold: bool,
    max_size: int,
    min_size: int,
    max_width: int,
):
    """너비에 맞게 글자 크기를 줄이고, 그래도 넘치면 말줄임표 처리"""
    for size in range(max_size, min_size - 1, -2):
        font = load_font(bold, size)
        if draw.textlength(text, font=font) <= max_width:
            return text, font
    font = load_font(bold, min_size)
    t = text
    while len(t) > 1 and draw.textlength(t + '…', font=font) > max_width:
        t = t[:-1]
    return t + '…', font
 
 
def _gradient_bg() -> Image.Image:
    bg = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / (H - 1)
        c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c + (255,))
    return bg
 
 
def _glow(size, color, radius) -> Image.Image:
    layer = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse([size[0] * 0.15, size[1] * 0.15, size[0] * 0.85, size[1] * 0.85], fill=color)
    return layer.filter(ImageFilter.GaussianBlur(radius))
 
 
def _circle_crop(img: Image.Image, diameter: int) -> Image.Image:
    img = img.convert('RGBA').resize((diameter, diameter), Image.LANCZOS)
    mask = Image.new('L', (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter - 1, diameter - 1], fill=255)
    out = Image.new('RGBA', (diameter, diameter), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out
 
 
def render_purchase_card(
    *,
    buyer_name: str,
    purchase_text: str,
    info_items: list,
    avatar_bytes: bytes | None,
    avatar_is_roblox: bool,
    buyer_avatar_bytes: bytes | None = None,
    guild_name: str = '',
    guild_icon_bytes: bytes | None = None,
    staff_name: str = '',
) -> BytesIO:
    """
    buyer_name         : 구매자 디스코드 닉네임
    purchase_text      : '로벅스 700' / '아이템명 3개' 같은 구매 요약
    info_items         : [(라벨, 값), ...] 최대 4개 (2x2 배치). 값이 None이면 현재 시각(KST)
    avatar_bytes       : 왼쪽 큰 이미지 (로블록스 전신 or 디스코드 프사)
    avatar_is_roblox   : True면 전신 이미지, False면 원형 프로필
    buyer_avatar_bytes : 구매자 디스코드 프사 (닉네임 옆 작은 원형)
    guild_name/icon    : 상단 우측 서버 이름/아이콘 (작게)
    """
    buyer_name = clean_text(buyer_name, '구매자')
    purchase_text = clean_text(purchase_text, '상품')
    guild_name = clean_text(guild_name, '') if guild_name else ''
    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
 
    base = _gradient_bg()
 
    # 배경 장식 글로우
    base.alpha_composite(_glow((620, 620), ACCENT + (95,), 90), (-120, -170))
    base.alpha_composite(_glow((560, 560), (110, 70, 220, 80), 90), (700, 280))
 
    draw = ImageDraw.Draw(base)
 
    # ---------- 왼쪽 아바타 패널 ----------
    px0, py0, px1, py1 = 36, 36, 484, 484
    panel = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle([px0, py0, px1, py1], radius=32, fill=(255, 255, 255, 20),
                         outline=(255, 255, 255, 46), width=2)
    base.alpha_composite(panel)
 
    pcx, pcy = (px0 + px1) // 2, (py0 + py1) // 2
    base.alpha_composite(_glow((420, 420), ACCENT + (110,), 60), (pcx - 210, pcy - 210))
 
    if avatar_bytes:
        try:
            av = Image.open(BytesIO(avatar_bytes)).convert('RGBA')
            if avatar_is_roblox:
                target = 424
                av = av.resize((target, target), Image.LANCZOS)
                base.alpha_composite(av, (pcx - target // 2, pcy - target // 2))
            else:
                dia = 280
                ring = Image.new('RGBA', (dia + 16, dia + 16), (0, 0, 0, 0))
                ImageDraw.Draw(ring).ellipse(
                    [0, 0, dia + 15, dia + 15], fill=ACCENT + (255,)
                )
                base.alpha_composite(ring, (pcx - (dia + 16) // 2, pcy - (dia + 16) // 2))
                base.alpha_composite(
                    _circle_crop(av, dia), (pcx - dia // 2, pcy - dia // 2)
                )
        except Exception as e:
            print(f'아바타 합성 오류: {e}')
 
    # ---------- 오른쪽 텍스트 ----------
    rx = 524
    right_edge = W - 36
    rw = right_edge - rx  # 사용 가능한 너비
 
    # 상단 좌측 태그
    tag_font = load_font(True, 22)
    tag_text = '지급 완료'
    tw = draw.textlength(tag_text, font=tag_font)
    draw.rounded_rectangle([rx, 48, rx + tw + 40, 90], radius=21, fill=ACCENT + (255,))
    draw.text((rx + 20, 69), tag_text, font=tag_font, fill=(30, 18, 54), anchor='lm')
 
    # 상단 우측: 서버 아이콘 + 서버 이름 (아주 작게)
    if guild_name or guild_icon_bytes:
        g_text, g_font = ('', load_font(False, 16))
        if guild_name:
            g_text, g_font = fit_text(draw, guild_name, False, 16, 12, 260)
        g_w = draw.textlength(g_text, font=g_font) if g_text else 0
        if g_text:
            draw.text((right_edge, 69), g_text, font=g_font, fill=MUTED, anchor='rm')
        if guild_icon_bytes:
            try:
                icon_d = 26
                gi = Image.open(BytesIO(guild_icon_bytes))
                gx = int(right_edge - g_w - (8 if g_text else 0) - icon_d)
                base.alpha_composite(_circle_crop(gi, icon_d), (gx, 69 - icon_d // 2))
            except Exception as e:
                print(f'서버 아이콘 합성 오류: {e}')
 
    # 타이틀
    draw.text((rx, 104), '구매 감사합니다!', font=load_font(True, 58), fill=WHITE)
 
    # 구매자 프사(원형) + 닉네임
    av_d = 52
    name_x = rx
    if buyer_avatar_bytes:
        try:
            bav = Image.open(BytesIO(buyer_avatar_bytes))
            base.alpha_composite(_circle_crop(bav, av_d), (rx, 180))
            name_x = rx + av_d + 14
        except Exception as e:
            print(f'구매자 프사 합성 오류: {e}')
    name_text, name_font = fit_text(
        draw, f'{buyer_name} 님', True, 36, 22, right_edge - name_x
    )
    draw.text((name_x, 206), name_text, font=name_font, fill=(222, 205, 255), anchor='lm')
 
    # 구매 내역 (강조)
    pur_text, pur_font = fit_text(draw, f'{purchase_text} 구매', True, 32, 20, rw)
    draw.text((rx, 248), pur_text, font=pur_font, fill=ACCENT)
 
    # 구분선
    draw.line([(rx, 308), (right_edge, 308)], fill=(104, 82, 146), width=2)
 
    # 정보 그리드 (2x2)
    col_w = rw // 2 - 10
    label_font = load_font(False, 20)
    for i, item in enumerate(info_items[:4]):
        label, value = item[0], item[1]
        if value is None:
            value = now_str
        col, row = i % 2, i // 2
        x = rx + col * (col_w + 20)
        y = 326 + row * 76
        draw.text((x, y), clean_text(label), font=label_font, fill=MUTED)
        v_text, v_font = fit_text(draw, clean_text(str(value)), True, 28, 16, col_w)
        draw.text((x, y + 28), v_text, font=v_font, fill=WHITE)
 
    # 푸터
    f_text, f_font = fit_text(draw, '이용해 주셔서 감사합니다', False, 18, 12, rw)
    draw.text((rx, 478), f_text, font=f_font, fill=MUTED)
 
    # ---------- 둥근 모서리 마스크 ----------
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=40, fill=255)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
 
    buf = BytesIO()
    out.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf
 
