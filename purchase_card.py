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
FONT_REGULAR_PATH = os.environ.get(
    'FONT_REGULAR', os.path.join(BASE_DIR, 'fonts', 'NotoSansKR-Regular.otf')
)
FONT_BOLD_PATH = os.environ.get(
    'FONT_BOLD', os.path.join(BASE_DIR, 'fonts', 'NotoSansKR-Bold.otf')
)
 
KST = timezone(timedelta(hours=9))
 
# 색상
BG_TOP = (27, 21, 46)
BG_BOTTOM = (56, 31, 92)
ACCENT = (178, 124, 255)
WHITE = (255, 255, 255)
MUTED = (176, 166, 204)
 
W, H = 1100, 520
 
_font_cache = {}
 
 
class FontMissingError(Exception):
    pass
 
 
def load_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    key = (bold, size)
    if key in _font_cache:
        return _font_cache[key]
    path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    try:
        font = ImageFont.truetype(path, size)
    except Exception as e:
        raise FontMissingError(
            f'폰트를 불러올 수 없습니다: {path} (fonts 폴더를 같이 올렸는지 확인)'
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
    staff_name: str,
    avatar_bytes: bytes | None,
    avatar_is_roblox: bool,
) -> BytesIO:
    """
    buyer_name    : 디스코드 표시 이름
    purchase_text : '로벅스 700' / '아이템명 3개' 같은 구매 요약
    info_items    : [(라벨, 값), ...] 최대 4개 (2x2 배치)
    avatar_bytes  : 이미지 바이트 (없으면 기본 아이콘 자리)
    avatar_is_roblox : True면 전신 이미지, False면 원형 프로필
    """
    buyer_name = clean_text(buyer_name, '구매자')
    purchase_text = clean_text(purchase_text, '상품')
    staff_name = clean_text(staff_name, '-')
 
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
    rw = W - 36 - rx  # 사용 가능한 너비
 
    # 상단 태그
    tag_font = load_font(True, 22)
    tag_text = '지급 완료'
    tw = draw.textlength(tag_text, font=tag_font)
    draw.rounded_rectangle([rx, 48, rx + tw + 40, 90], radius=21, fill=ACCENT + (255,))
    draw.text((rx + 20, 69), tag_text, font=tag_font, fill=(30, 18, 54), anchor='lm')
 
    # 타이틀
    draw.text((rx, 104), '구매 감사합니다!', font=load_font(True, 58), fill=WHITE)
 
    # 구매자 이름
    name_text, name_font = fit_text(draw, f'{buyer_name} 님', True, 36, 22, rw)
    draw.text((rx, 184), name_text, font=name_font, fill=(222, 205, 255))
 
    # 구매 내역 (강조)
    pur_text, pur_font = fit_text(draw, f'{purchase_text} 구매', True, 32, 20, rw)
    draw.text((rx, 236), pur_text, font=pur_font, fill=ACCENT)
 
    # 구분선
    draw.line([(rx, 304), (W - 36, 304)], fill=(104, 82, 146), width=2)
 
    # 정보 그리드 (2x2)
    col_w = rw // 2 - 10
    label_font = load_font(False, 20)
    for i, (label, value) in enumerate(info_items[:4]):
        col, row = i % 2, i // 2
        x = rx + col * (col_w + 20)
        y = 322 + row * 78
        draw.text((x, y), clean_text(label), font=label_font, fill=MUTED)
        v_text, v_font = fit_text(draw, clean_text(value), True, 28, 16, col_w)
        draw.text((x, y + 28), v_text, font=v_font, fill=WHITE)
 
    # 푸터
    now = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    footer = f'{now}  ·  이용해 주셔서 감사합니다'
    f_text, f_font = fit_text(draw, footer, False, 18, 12, rw)
    draw.text((rx, 476), f_text, font=f_font, fill=MUTED)
 
    # ---------- 둥근 모서리 마스크 ----------
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=40, fill=255)
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
 
    buf = BytesIO()
    out.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    return buf
 
