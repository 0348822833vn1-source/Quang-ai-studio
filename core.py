from __future__ import annotations
import json, re, sqlite3, subprocess, tempfile, shutil
from pathlib import Path
from pydantic import BaseModel, Field, model_validator

STYLE_FAMILY_DRAMA = 'Gia Đình Tâm Lý Xã Hội & Đời Thực Hoài Cổ Thập Niên 80–90 (Chuẩn Công Thức Video Mẫu 2 • Khóa Sinh Trắc Học Khuôn Mặt 100% • Hành Trình Đa Bối Cảnh • Full 9:16)'
STYLE_3D_FABLE = 'Hoạt hình 3D Pixar Ngụ ngôn & Châm ngôn sống (Consistent 3D Character)'
STYLE_LIVE_DRAMA = 'Tiểu phẩm Tâm lý Xã hội Đời thực & Bẻ lái (Live-Action Plot Twist)'
STYLE_REMAKE = 'Đạo lại Video Mẫu (Giữ cốt truyện • Nâng tầm kịch bản & Thoại)'
AVAILABLE_STYLES = (
    STYLE_FAMILY_DRAMA,
    STYLE_LIVE_DRAMA,
    STYLE_3D_FABLE,
    STYLE_REMAKE,
)

def is_family_drama_style(style: str) -> bool:
    s = (style or '').casefold()
    return any(k in s for k in ('gia đình', 'quê nghèo', 'thập niên', '80', '90', '2000', 'hài hước', 'tiktok', 'hoài cổ', 'tự sáng tạo', 'có đầu có đuôi'))

def normalize_style(style: str) -> str:
    if 'đạo lại' in (style or '').casefold():
        return STYLE_REMAKE
    if is_family_drama_style(style):
        return STYLE_FAMILY_DRAMA
    if is_3d_fable_style(style):
        return STYLE_3D_FABLE
    return STYLE_LIVE_DRAMA

TOOL_GOOGLE_FLOW = "Google Flow (flow.google.com — Dán từng cảnh 1-1 • Đợi xong mới dán tiếp • Tự sửa nếu lỗi)"
TOOL_META_MUSE = "Meta Muse AI (muse.ai — Dán đợt 6 cảnh • Tự tải & ghép)"
AVAILABLE_VIDEO_TOOLS = (
    TOOL_GOOGLE_FLOW,
    TOOL_META_MUSE,
)


PHOTOGRAPHY_4_PILLARS_GUIDE = (
    "Medium shot, eye-level angle, shot on 35mm lens, f/2.8 aperture, shallow depth of field, cinematic film still. "
    "Interior/Exterior of an impoverished rural Vietnamese house (distressed walls with peeling white paint revealing bare concrete and moisture stains, "
    "rustic bamboo bed 'giường tre', old wooden cabinet). "
    "Natural soft light coming from the doorway, dramatic shadows inside the room, muted color palette, desaturated cold-neutral tones (NO yellow/warm sepia tint), "
    "gritty realism, 8k resolution, ultra-detailed, photorealistic --ar 9:16 --style raw --v 6.0"
)

SAFE_FICTIONAL_FRAME_VI = (
    "[Bối cảnh giả định cho mục đích nghệ thuật và điện ảnh — Nội dung hoàn toàn hư cấu "
    "(100% fictional characters, safe for work, cinematic movie scene, no real-world harm), "
    "mang thông điệp giáo dục và nhân văn]."
)

def is_google_flow_tool(tool: str) -> bool:
    t = (tool or "").casefold()
    return ("muse" not in t) or ("flow" in t) or ("google" in t) or ("veo" in t)

def is_3d_fable_style(style: str) -> bool:
    s = (style or '').casefold()
    return any(k in s for k in ('3d', 'pixar', 'ngụ ngôn', 'châm ngôn', 'hoạt hình'))

VIDEO_SAFE_REPLACEMENTS = (
    (r'vượt bộ lọc(\s+an toàn)?', 'tuân thủ tiêu chuẩn điện ảnh nghệ thuật'),
    (r'do vướng từ ngữ nhạy cảm', 'theo tiêu chuẩn an toàn điện ảnh'),
    (r'từ ngữ nhạy cảm', 'chi tiết diễn xuất tâm lý'),
    (r'\bmắt trợn ngược\b', 'ánh mắt sững sờ trầm ngâm'),
    (r'\bđổ gục xuống(\s+sàn\s+hiên|\s+hiên|\s+sàn|\s+đất)?\b', 'ngồi tựa xuống bậc thềm trầm ngâm suy nghĩ'),
    (r'\b(ngã gục|gục ngã|gục xuống)\b', 'ngồi xuống bậc thềm suy ngẫm'),
    (r'\bchân tay bủn rủn\b', 'bước chân chậm lại đầy trăn trở'),
    (r'\bkhông nhấc nổi\b', 'chững lại suy nghĩ'),
    (r'\bcơ thể lịm dần\b', 'khẽ nhắm mắt lắng đọng suy ngẫm'),
    (r'\blịm dần\b', 'khẽ nhắm mắt suy tư'),
    (r'\b(ngất xỉu|bất tỉnh|hôn mê|đột quỵ|co giật)\b', 'nhắm mắt tĩnh tâm suy nghĩ'),
    (r'\bthở dốc,\s*nghẹn ngào\b', 'hít một hơi sâu xúc động'),
    (r'\bthở dốc\b', 'hít hơi sâu trầm tĩnh'),
    (r'\bgương mặt hốc hác\b', 'gương mặt trầm tư chín chắn'),
    (r'\bhốc hác\b', 'trầm tư'),
    (r'\bmặt mày tái mét\b', 'vẻ mặt lo lắng suy tư'),
    (r'\b(hoảng loạn tột độ|hoảng loạn|hốt hoảng|tuyệt vọng|tội lỗi)\b', 'bối rối trầm ngâm'),
    (r'\brun rẩy,\s*vò đầu\b', 'đặt tay lên ngực suy ngẫm'),
    (r'\b(vò đầu bứt tai|vò đầu|run rẩy)\b', 'khẽ nắm tay suy tư'),
    (r'\bchết thật\b', 'gay go rồi'),
    (r'\b(chết mất|xong đời|đời tàn)\b', 'phải suy nghĩ kỹ lại'),
    (r'\bsáng mai công an tới là đời tàn\b', 'sáng mai mọi người hỏi chuyện thì phải làm sao'),
    (r'\b(công an ập vào|cảnh sát ập vào|công an tới|cảnh sát tới|bắt giữ|bị bắt|đầu thú)\b', 'đối diện với sự thật và gia đình'),
    (r'\b(bỏ trốn|trốn nợ|siết nợ|đòi nợ thuê|xã hội đen)\b', 'rời đi xa làm lại từ đầu'),
    (r'\b(ôm nhau|ôm chầm|ôm chặt|ôm khóc|ôm sát|vòng tay ôm)\b', 'đặt tay lên vai đồng cảm, đứng đối diện nhau gật đầu'),
    (r'\b(bắt tay chặt|nắm chặt tay|giằng co|ẩu đả|vật lộn|đánh nhau|xô đẩy)\b', 'đứng đối diện tương tác qua ánh mắt và cử chỉ tay rõ ràng từ xa'),
    (r'\b(hôn|tát|đấm|đá|túm cổ|bóp cổ)\b', 'nhìn thẳng vào mặt nhau với biểu cảm dứt khoát'),
    (r'\bchảy cơ thể\b', 'vóc dáng tự nhiên rõ ràng'),
    (r'\bnhập cơ thể\b', 'khoảng cách tách bạch'),
    (r'\bdao phay\b', 'chiếc muôi gỗ lớn'),
    (r'\bdao bầu\b', 'chiếc muôi gỗ'),
    (r'\bdao nhọn\b', 'que gỗ'),
    (r'\bdao sắc\b', 'dụng cụ gỗ'),
    (r'\bcầm dao\b', 'cầm muôi gỗ chỉ trỏ'),
    (r'\bvung dao\b', 'vung tay chỉ trỏ'),
    (r'\bmài dao\b', 'lau chùi dụng cụ'),
    (r'\blò mổ\b', 'khu sân trang trại'),
    (r'\bgiết mổ\b', 'chăm sóc vật nuôi ở trang trại'),
    (r'\bmổ heo\b', 'giữ heo lại ở sân trang trại'),
    (r'\bmổ lợn\b', 'giữ đàn lợn ở trang trại'),
    (r'\bcắt tiết\b', 'giữ chặt dây thừng'),
    (r'\bcắt cổ\b', 'chỉ tay cảnh cáo'),
    (r'\bchặt xác\b', 'xua tay'),
    (r'\bchém giết\b', 'tranh cãi kịch tính'),
    (r'\bvũng máu\b', 'vũng nước mưa'),
    (r'\bmáu tươi\b', 'nước màu đỏ sẫm'),
    (r'\bvết máu\b', 'vệt bùn đất'),
    (r'\bmáu chảy\b', 'mồ hôi chảy'),
    (r'\bmáu me\b', 'vệt bẩn'),
    (r'\bhành hạ\b', 'quát mắng kịch tính'),
    (r'\bngược đãi\b', 'xua đuổi kịch tính'),
    (r'\bđánh đập\b', 'tranh cãi lớn tiếng'),
    (r'\bđịa ngục\b', 'cõi thần tiên huyền ảo'),
    (r'\bâm phủ\b', 'cõi huyền ảo'),
    (r'\bxác chết\b', 'hình bóng'),
    (r'\btử thi\b', 'hình bóng'),
    (r'\bkinh dị\b', 'tâm linh huyền ảo'),
    (r'\bkinh hoàng\b', 'bàng hoàng sững sờ'),
    (r'\bhoảng loạn tột độ\b', 'bàng hoàng sững sờ'),
    (r'\bhoảng loạn\b', 'hốt hoảng bất ngờ'),
    (r'\bsợ chết khiếp\b', 'giật mình sững sờ'),
    (r'\bvan xin tha mạng\b', 'chắp tay xin lỗi rối rít'),
    (r'\bđập đầu\b', 'cúi đầu xin lỗi'),
    (r'\bbóp cổ\b', 'chỉ tay nhắc nhở'),
    (r'\bdọa giết\b', 'nghiêm giọng phê bình'),
    (r'\bbãi tha ma\b', 'khu vườn kiến trúc đá cổ kính'),
    (r'\blịch treo tường[^.,;]*', 'bức tranh dân gian Đông Hồ bạc màu treo tường'),
    (r'\btờ lịch[^.,;]*', 'tờ câu đối giấy đỏ xưa cũ bạc màu'),
    (r'\blịch năm\s*20[0-9]{2}\b', 'tranh treo tường thập niên 80-90'),
    (r'\b(năm\s*)?(202[0-9]|201[0-9])\b', 'thập niên 1980-1990'),
    (r'plastic bags hanging on the wall\.?', 'vintage wooden ancestral altar shelf and woven bamboo winnowing basket on bare aged lime-washed brick wall (strictly NO wall calendar).'),
    (r'\btúi nilon treo tường\b', 'nón lá cũ và nong nia tre treo tường'),
    (r'\bghế nhựa\b', 'ghế đẩu gỗ mộc xưa'),
    (r'\bplastic chairs?\b', 'low rustic wooden stools'),
)

def sanitize_for_video_prompt(text: str) -> str:
    """Soften horror/violence/trauma/collapse/crime keywords, strip internal audit notes,
    and remove fade-to-black / dramatic swoosh sound instructions that cause black flashes and 'tiếng chuýt' at scene ends.
    """
    if not text:
        return text
    out = text
    out = re.sub(r'\(\s*SCENE_\d{3}[^)]*Mâu thuẫn[^)]*\)', '', out, flags=re.IGNORECASE)
    out = re.sub(r'Lưu ý đạo diễn:\s*SCENE_\d{3}[^.]*\.', '', out, flags=re.IGNORECASE)
    for pattern, repl in VIDEO_SAFE_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(
        r'kết hợp hiệu ứng mờ dần màu đen\s*\(Fade to black\s*/\s*Dissolve\)\s*và âm thanh kịch tính\s*(?:\(Dramatic Sound Effect\))?',
        'giữ nguyên ánh sáng tự nhiên và âm thanh đời thực',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r'kèm âm thanh kịch tính và Fade to black', 'với biểu cảm chân thực tự nhiên, giữ sáng khung hình', out, flags=re.IGNORECASE)
    out = re.sub(
        r'hiệu ứng chuyển cảnh Action Match Cut\s*/\s*Fade to black kịch tính',
        'nối cảnh trực tiếp mượt mà (Direct Continuity Cut), âm thanh tự nhiên không tiếng chuýt',
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r'Fade to black\s*/\s*Dissolve', 'Nối cảnh trực tiếp giữ nguyên ánh sáng (Direct Cut)', out, flags=re.IGNORECASE)
    out = re.sub(r'Dramatic Sound Effect', 'Natural Ambient Sound', out, flags=re.IGNORECASE)
    out = re.sub(r'\s{2,}', ' ', out).strip()
    return out

ANTI_ANACHRONISM_NEGATIVE_PROMPT = (
    "melting limbs, fused bodies, merging bodies, mutated hands, extra limbs, distorted anatomy, garbled text, subtitles, watermark, modern wall calendar, calendar with numbers, 2024, 2025, 2026, lịch treo tường, tờ lịch in số năm, "
    "digital clock, plastic chairs, modern items, contemporary objects, smartphone, LED light, "
    "modern concrete building, modern scooter, neon light"
)

def build_biometric_character_anchor(c: "Character", index: int = 1) -> str:
    """Build a strict Biometric Face & Outfit Lock string (in English + Vietnamese) so the AI video model
    locks 100% onto the exact facial bone structure, wrinkles, skin tone, hair parting, and clothing tear/texture
    across all camera angles (Close-up, Medium, Wide) and across all locations.
    """
    blob = f"{c.name} {c.appearance} {c.wardrobe}".casefold()
    if any(k in blob for k in ("cha", "bố", "ông", "60", "65", "68", "70", "già", "bác")):
        bio_en = (
            f"A fixed 65-year-old Vietnamese man ({c.name}) with deep sun-damaged wrinkles under eyes, "
            f"a fixed age spot on the left cheekbone, gaunt weathered cheeks, thin grey hair, "
            f"wearing a worn-out grey/brown coarse-cotton farmer shirt (áo bà ba/sơ mi vải thô sờn) "
            f"with a fixed 2cm tear on the right shoulder and faded dark cloth trousers, old rubber slippers — "
            f"exact biometric face identity & outfit locked 100% across all camera angles (--cref)"
        )
    elif any(k in blob for k in ("phú hộ", "bà chủ", "giàu", "áo dài", "gấm")):
        bio_en = (
            f"A fixed 55-year-old wealthy rural Vietnamese matron ({c.name}) with a full round face, "
            f"a distinct beauty mole near the left mouth corner, neatly coiled black hair bun, "
            f"wearing a traditional patterned brocade silk Áo dài and jade/pearl bracelet — "
            f"exact biometric face identity & outfit locked 100% across all camera angles (--cref)"
        )
    elif any(k in blob for k in ("con", "hùng", "thắng", "dũng", "nam", "25", "27", "28", "30", "thanh niên")):
        bio_en = (
            f"A fixed 28-year-old Vietnamese man ({c.name}) with an angular jawline, "
            f"short black hair parted 7/3 naturally, a small mole under the right eye, sun-tanned skin, "
            f"wearing a wrinkled faded blue-grey coarse-cotton button-down shirt with rolled-up sleeves "
            f"and faded brown khaki trousers, worn honeycomb slippers (dép tổ ong) — "
            f"exact biometric face identity & outfit locked 100% across all camera angles (--cref)"
        )
    else:
        bio_en = (
            f"A fixed Vietnamese character ({c.name}: {c.appearance}) wearing exact fixed 1980s-1990s rural outfit ({c.wardrobe}) — "
            f"exact biometric facial bone structure, wrinkles, skin tone, hair parting, and fabric wear locked 100% (--cref)"
        )
    return f"[Character {index} Biometric Lock - {c.name} ({c.id})]: {bio_en} | Hồ sơ gốc: {c.appearance}; Trang phục cố định: {c.wardrobe}"


class Character(BaseModel):
    id: str
    name: str
    appearance: str
    wardrobe: str
    personality: str
    gestures: str
    voice: str
    entity_type: str = "human"
    movement_rules: str = ""
    @model_validator(mode='before')
    @classmethod
    def normalize_entity_type(cls, value):
        if not isinstance(value, dict): return value
        raw = str(value.get('entity_type', 'human') or 'human').strip().casefold()
        if raw in ('ghost', 'ma', 'hồn ma', 'bóng ma', 'linh hồn', 'spirit'):
            return {**value, 'entity_type': 'ghost'}
        if raw in ('human', 'người', 'con người', 'person'):
            return {**value, 'entity_type': 'human'}
        return value

class Location(BaseModel):
    id: str
    name: str
    description: str
    lighting: str

class Bible(BaseModel):
    characters: list[Character]
    locations: list[Location]

class Beat(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0.001)
    action: str

class Dialogue(BaseModel):
    character_id: str
    text: str
    delivery: str
    start: float = Field(ge=0)
    end: float = Field(ge=0.001)

class Scene(BaseModel):
    id: str
    title: str
    duration: float = Field(ge=0.001, le=120)
    character_ids: list[str]
    location_id: str
    start_state: str
    timeline: list[Beat] = Field(min_length=1)
    camera: str
    lighting: str
    emotion: str
    dialogue: list[Dialogue]
    sound: str
    end_state: str
    continuity: str
    visual_prompt: str
    negative_prompt: str
    story_beat: str = ""
    narrative_role: str = ""
    transition: str = ""
    @model_validator(mode='before')
    @classmethod
    def default_scene_title(cls, value):
        if not isinstance(value,dict): return value
        title=value.get('title')
        if title is None or (isinstance(title,str) and not title.strip()):
            match=re.fullmatch(r'SCENE_([0-9]{1,9})',str(value.get('id','')))
            label='Scene '+str(int(match.group(1))) if match else 'Scene'
            return {**value,'title':label}
        return value

    @model_validator(mode='after')
    def timing(self):
        previous = 0
        for b in self.timeline:
            if not (previous <= b.start < b.end <= self.duration):
                raise ValueError('Timeline phải tăng dần, không chồng nhau và nằm trong thời lượng.')
            previous = b.end
        for d in self.dialogue:
            if not 0 <= d.start < d.end <= self.duration:
                raise ValueError('Thời gian thoại vượt cảnh.')
            if d.character_id not in self.character_ids and d.character_id != 'NARRATOR':
                raise ValueError('Người nói không có trong cảnh.')
        return self

class Storyboard(BaseModel):
    scenes: list[Scene] = Field(min_length=1)
    warnings: list[str]

class Project(BaseModel):
    title: str = 'Dự án mới'
    script: str = ''
    idea: str = ''
    idea_video: str = ''
    story_chat: list[dict[str,str]] = Field(default_factory=list)
    story_approved: bool = False
    treatment: str = ''
    treatment_approved: bool = False
    style: str = STYLE_FAMILY_DRAMA
    video_tool: str = TOOL_GOOGLE_FLOW
    ratio: str = '9:16'
    total_seconds: int = 300
    clip_seconds: int = 10
    bible: Bible | None = None
    board: Storyboard | None = None
    clips: dict[str, str] = Field(default_factory=dict)
    references: dict[str, str] = Field(default_factory=dict)
    @model_validator(mode='after')
    def consistency(self):
        if self.bible:
            c = [x.id for x in self.bible.characters]
            l = [x.id for x in self.bible.locations]
            if len(c) != len(set(c)) or len(l) != len(set(l)):
                raise ValueError('ID nhân vật/bối cảnh bị trùng.')
            if self.board:
                ids = [s.id for s in self.board.scenes]
                if len(ids) != len(set(ids)):
                    raise ValueError('ID cảnh bị trùng.')
                for s in self.board.scenes:
                    if not set(s.character_ids) <= set(c) or s.location_id not in l:
                        raise ValueError('Cảnh dùng ID nhân vật/bối cảnh không tồn tại.')
        elif self.board:
            raise ValueError('Cần hồ sơ trước khi có phân cảnh.')
        return self

def adjacent_context(p,s):
    if not p.board:
        return ''
    i = next((i for i, x in enumerate(p.board.scenes) if x.id == s.id), -1)
    if i < 0:
        return ''
    parts = []
    if i > 0:
        a = p.board.scenes[i - 1]
        same_loc_prev = (a.location_id == s.location_id)
        if same_loc_prev:
            parts.append(
                f'Cảnh trước ({a.id} — CÙNG BỐI CẢNH): {a.story_beat}; '
                f'GIỮ NGUYÊN 100% KHUNG HÌNH, BỐI CẢNH & VỊ TRÍ NGỒI/ĐỨNG TỪ CUỐI {a.id} ({a.end_state}) ĐỂ NỐI TIẾP CUỘC TRÒ CHUYỆN TỰ NHIÊN; '
                f'thoại cuối cảnh trước: ' + ' / '.join(d.text for d in a.dialogue)
            )
        else:
            parts.append(
                f'Cảnh trước ({a.id} — ĐỔI BỐI CẢNH TỪ {a.location_id} SANG {s.location_id}): {a.story_beat}; '
                f'nhân vật vừa di chuyển từ cuối {a.id} ({a.end_state}) bước vào bối cảnh mới ({s.start_state}); '
                f'thoại cuối cảnh trước: ' + ' / '.join(d.text for d in a.dialogue)
            )
    if i + 1 < len(p.board.scenes):
        nxt = p.board.scenes[i + 1]
        bridge_s = round(max(0.0, s.duration - 1.0), 1)
        if is_3d_fable_style(p.style):
            parts.append(
                f'NỐI SANG CẢNH SAU ({nxt.id}) Ở GIÂY {bridge_s:g}s–{s.duration:g}s: '
                f'Sau khi Voiceover/Dialogue kết thúc ở giây {bridge_s:g}s, nhân vật 3D giữ nguyên ngoại hình cố định (Consistent Character) '
                f'và chuyển hướng nhìn/cử chỉ mượt mà dẫn vào {nxt.id} ({nxt.start_state}).'
            )
        elif nxt.location_id == s.location_id:
            parts.append(
                f'NỐI TRỰC TIẾP SANG {nxt.id} Ở GIÂY {bridge_s:g}s–{s.duration:g}s (CÙNG BỐI CẢNH — KHÔNG ĐỨNG DẬY BỎ ĐI, KHÔNG FADE ĐEN, KHÔNG TIẾNG CHUÝT): '
                f'Vì {nxt.id} vẫn tiếp tục cuộc nói chuyện tại cùng bối cảnh này, từ giây {bridge_s:g}s–{s.duration:g}s nhân vật BẮT BUỘC GIỮ NGUYÊN VỊ TRÍ NGỒI/ĐỨNG ({s.end_state}), '
                f'duy trì ánh mắt và biểu cảm lắng nghe/phản ứng tự nhiên khớp 100% vào đầu {nxt.id} ({nxt.start_state}). '
                f'TUYỆT ĐỐI KHÔNG tự ý đứng dậy bỏ đi, KHÔNG làm tối màn hình (NO Fade to black), KHÔNG chèn âm thanh chuýt chuyển cảnh.'
            )
        else:
            parts.append(
                f'CHUYỂN TIẾP HÀNH ĐỘNG SANG BỐI CẢNH MỚI Ở {nxt.id} ({bridge_s:g}s–{s.duration:g}s — CÓ ĐUÔI RỜI ĐI TỰ NHIÊN): '
                f'Sau khi nói xong hoàn toàn câu thoại ở giây {bridge_s:g}s, vì cảnh sau ({nxt.id}) đổi sang bối cảnh mới ({nxt.location_id}), '
                f'từ giây {bridge_s:g}s–{s.duration:g}s nhân vật mới bắt đầu đứng dậy / bước đi tự nhiên ra phía cửa ({s.end_state}) để nối khớp sang đầu {nxt.id} ({nxt.start_state}). '
                f'Giữ ánh sáng tự nhiên và tiếng bước chân thực tế, KHÔNG làm tối màn hình (NO Fade to black), KHÔNG chèn tiếng chuýt.'
            )
    parts.append('Chỉ tạo cảnh hiện tại, diễn xuất đời thực tự nhiên, không diễn lại cảnh trước hoặc nói trước lời thoại cảnh sau.')
    return '\n'.join(parts)

def _tail_transition_instruction(p: Project, s: Scene, start_sec: float) -> str:
    idx = next((i for i, x in enumerate(p.board.scenes) if x.id == s.id), -1) if p.board else -1
    nxt = p.board.scenes[idx + 1] if (p.board and 0 <= idx < len(p.board.scenes) - 1) else None
    bridge_sec = round(max(0.0, s.duration - 1.0), 1)
    if nxt is None:
        if is_3d_fable_style(p.style):
            return (
                f'• [{bridge_sec:g}s – {s.duration:g}s | NHỊP KẾT CẢNH & CHÂM NGÔN SỐNG (MORAL LESSON)]: '
                f'Sau khi nói xong câu châm ngôn ở giây {bridge_sec:g}s, nhân vật 3D mỉm cười ấm áp, ánh sáng Pixar lung linh khép lại ({s.end_state}).'
            )
        return (
            f'• [{bridge_sec:g}s – {s.duration:g}s | NHỊP KẾT CẢNH TỰ NHIÊN (GIỮ SÁNG KHUNG HÌNH — KHÔNG FADE ĐEN, KHÔNG TIẾNG CHUÝT)]: '
            f'Sau khi dứt câu thoại ở giây {bridge_sec:g}s, máy quay giữ nguyên khung hình và ánh sáng tự nhiên trên gương mặt giàu cảm xúc của nhân vật ({s.end_state}), '
            f'tuyệt đối không làm tối đen màn hình và không chèn tiếng chuýt/tiếng nổ kịch tính.'
        )
    if is_3d_fable_style(p.style):
        return (
            f'• [{bridge_sec:g}s – {s.duration:g}s | NỐI CẢNH 3D MATCH CUT SANG {nxt.id}]: '
            f'Sau khi Voiceover/Dialogue kết thúc ở giây {bridge_sec:g}s, nhân vật 3D giữ nguyên ngoại hình cố định (Consistent Character) '
            f'và chuyển hướng nhìn/tư thế khớp 100% với đầu {nxt.id} ({nxt.start_state}).'
        )
    if s.location_id == nxt.location_id:
        return (
            f'• [{bridge_sec:g}s – {s.duration:g}s | NỐI THẲNG CÙNG BỐI CẢNH SANG {nxt.id} (GIỮ NGUYÊN VỊ TRÍ NGỒI/ĐỨNG — KHÔNG BỎ ĐI, KHÔNG FADE ĐEN, KHÔNG TIẾNG CHUÝT)]: '
            f'Vừa dứt câu thoại ở giây {bridge_sec:g}s, các nhân vật VẪN NGỒI/ĐỨNG NGUYÊN TẠI CHỖ ({s.end_state}), nhìn nhau với biểu cảm đời thực tự nhiên '
            f'để nối thẳng 100% cùng khung hình sang đầu {nxt.id} ({nxt.start_state}). '
            f'TUYỆT ĐỐI KHÔNG tự ý quay lưng bỏ đi khi đang nói chuyện, KHÔNG làm tối đen màn hình (NO Fade to black), KHÔNG phát tiếng chuýt chuyển cảnh.'
        )
    return (
        f'• [{bridge_sec:g}s – {s.duration:g}s | NHỊP ĐUÔI CHUYỂN BỐI CẢNH SANG {nxt.id} (ĐỨNG DẬY / BƯỚC ĐI TỰ NHIÊN — KHÔNG FADE ĐEN, KHÔNG TIẾNG CHUÝT)]: '
        f'Sau khi nói xong câu thoại ở giây {bridge_sec:g}s, vì cảnh tiếp theo ({nxt.id}) chuyển sang bối cảnh khác ({nxt.location_id}), '
        f'nhân vật mới bắt đầu đứng dậy / bước đi tự nhiên hướng ra cửa ({s.end_state}) khớp nối trực tiếp sang đầu {nxt.id} ({nxt.start_state}). '
        f'Giữ nguyên ánh sáng tự nhiên và tiếng bước chân đời thực, KHÔNG làm tối màn hình (NO Fade to black), KHÔNG phát tiếng chuýt.'
    )

def _build_lipsync_and_demeanor_guide(p: Project, s: Scene) -> str:
    char_objs = {c.id: c for c in (p.bible.characters if p.bible else []) if c.id in s.character_ids}
    def short_tag(cid: str) -> str:
        c = char_objs.get(cid)
        if not c:
            return cid
        outfit = c.wardrobe.split(';')[0].split(',')[0].strip() if c.wardrobe else ''
        look = c.appearance.split(',')[0].strip() if c.appearance else ''
        desc = ', '.join(x for x in (look, outfit) if x)
        return f'{c.name} ({c.id}' + (f' - {desc})' if desc else ')')

    talk_end_target = round(max(1.0, s.duration - 1.0), 1)
    idx = next((i for i, x in enumerate(p.board.scenes) if x.id == s.id), -1) if p.board else -1
    prev_sc = p.board.scenes[idx - 1] if (p.board and idx > 0) else None
    next_sc = p.board.scenes[idx + 1] if (p.board and 0 <= idx < len(p.board.scenes) - 1) else None
    same_prev = (prev_sc is not None and prev_sc.location_id == s.location_id)
    same_next = (next_sc is not None and next_sc.location_id == s.location_id)

    if is_3d_fable_style(p.style):
        lines_out = [
            f'FORM 3 GIAI ĐOẠN — CHỈ ĐẠO HOẠT HÌNH 3D PIXAR & KHỚP KHẨU HÌNH (ACTIVE LIP-SYNC 0.0s–{talk_end_target:g}s → {talk_end_target:g}s–{s.duration:g}s MATCH CUT):',
            '- ĐỒNG NHẤT NHÂN VẬT 3D (CONSISTENT 3D CHARACTER): Giữ nguyên 100% loài vật/nhân vật 3D dễ thương, màu lông, đôi mắt to biểu cảm và trang phục/phụ kiện cố định ở mọi góc máy.',
        ]
    else:
        continuity_mode_note = (
            f'- KHÓA GÓC QUAY CỐ ĐỊNH 100% CÙNG BỐI CẢNH (SANG {next_sc.id}): Hai nhân vật đang tiếp tục cuộc trò chuyện tại chỗ (như cảnh vay tiền/nói chuyện trong nhà). '
            f'BẮT BUỘC giữ nguyên 100% GÓC QUAY CŨ ({s.camera}), vị trí ngồi/đứng từ 0.0s đến hết {s.duration:g}s; TUYỆT ĐỐI KHÔNG tự ý đổi góc máy (NO camera angle jump), KHÔNG tự ý đứng dậy bỏ đi!'
            if same_next else (
                f'- CHẾ ĐỘ CHUYỂN TIẾP SANG BỐI CẢNH MỚI (SANG {next_sc.id}): Từ 0.0s đến {talk_end_target:g}s nhân vật đứng/ngồi tại chỗ nói hết câu thoại; '
                f'chỉ từ giây {talk_end_target:g}s–{s.duration:g}s cuối cảnh nhân vật mới đứng dậy / bước đi tự nhiên sang bối cảnh kế tiếp.'
                if next_sc is not None else
                f'- CHẾ ĐỘ CẢNH KẾT: Diễn xuất tự nhiên, giữ nguyên góc máy và ánh sáng chân thực đến hết {s.duration:g}s.'
            )
        )
        lines_out = [
            f'FORM 3 GIAI ĐOẠN — CHỈ ĐẠO DIỄN XUẤT ĐỜI THỰC, KHÓA TÔNG MÀU PHIM TRầm LẠNH (MUTED DESATURATED GRITTY REALISM) & KHỚP KHẨU HÌNH (ACTIVE LIP-SYNC 0.0s–{talk_end_target:g}s → {talk_end_target:g}s–{s.duration:g}s NỐI CẢNH TRỰC TIẾP):',
            continuity_mode_note,
            '- TÔNG MÀU & NHIẾP ẢNH BẮT BUỘC (THEO ẢNH MẪU ĐÍNH KÈM): Medium shot, eye-level angle, shot on 35mm lens, f/2.8 aperture, shallow depth of field, cinematic film still. Natural soft light from doorway, dramatic shadows, muted color palette, desaturated tones, gritty realism (tông màu xám lạnh bạc màu chân thực của tường vôi bong tróc rêu mốc và giường tre; TUYỆT ĐỐI KHÔNG ám vàng rực hay sepia cổ trang).',
            '- CHỐNG LỖI TIẾNG NÓI KHÔNG KHỚP HÌNH (STRICT SINGLE-SPEAKER LIP-SYNC): Tại mỗi thời điểm chỉ ĐÚNG 1 NGƯỜI ĐANG NÓI được mở miệng phát âm khớp từng âm tiết tiếng Việt; người còn lại BẮT BUỘC NGẬM/KHÉP MIỆNG LẮNG NGHE, tuyệt đối không nhép môi theo hoặc nói chồng lời.',
            '- CẤM FADE ĐEN & CẤM TIẾNG CHUÝT CHUYỂN CẢNH: Giữ khung hình sáng rõ tự nhiên xuyên suốt 100% thời lượng clip (NO Fade to black, NO Dissolve) và chỉ dùng âm thanh môi trường tự nhiên (NO dramatic swoosh/screech sound effect).',
        ]

    for cid in s.character_ids:
        c = char_objs.get(cid)
        if c:
            spirit_rule = (
                f' | Hiệu ứng VFX Tâm linh: hình bóng phát sáng mờ ảo ấm áp (Ethereal Glow), {c.movement_rules}'
                if c.entity_type == 'ghost' else ''
            )
            lines_out.append(
                f'- KHÓA NHÂN VẬT CỐ ĐỊNH 100% {c.name} ({c.id}): Ngoại hình: {c.appearance}. '
                f'TRANG PHỤC BẮT BUỘC GIỮ NGUYÊN MÀU SẮC & KIỂU DÁNG: {c.wardrobe}. Tính cách/phong thái: {c.personality}; cử chỉ tự nhiên: {c.gestures}; giọng nói: {c.voice}.{spirit_rule}'
            )

    if same_prev:
        lines_out.append(
            f'• [0.0s | KHỚP ĐẦU CẢNH & KHÓA GÓC QUAY CŨ VỚI {prev_sc.id}]: Giữ NGUYÊN VĂN 100% GÓC QUAY CŨ ({prev_sc.camera}), khung hình, vị trí ngồi/đứng và bối cảnh từ cuối {prev_sc.id} ({s.start_state}). Tuyệt đối không đổi góc máy khi đang đối thoại cùng cảnh!'
        )
    else:
        lines_out.append(
            f'• [0.0s | KHỚP ĐẦU CẢNH (ENTRY STATE)]: Bắt đầu tự nhiên đúng tại trạng thái ({s.start_state}) với góc máy ({s.camera}).'
        )

    sorted_dlg = sorted(s.dialogue, key=lambda d: d.start)
    if not sorted_dlg:
        lines_out.append(
            f'• [0.0s – {talk_end_target:g}s | DIỄN XUẤT HÌNH THỂ & BIỂU CẢM TỰ NHIÊN (Không lời thoại)]: '
            f'Nhân vật khép miệng tự nhiên, diễn xuất ánh mắt, cử chỉ ({s.emotion}) và hành động đời thực theo timeline.'
        )
        lines_out.append(_tail_transition_instruction(p, s, talk_end_target))
    else:
        for idx_d, d in enumerate(sorted_dlg):
            d_end = max(d.end, talk_end_target) if (idx_d == len(sorted_dlg) - 1 and s.duration >= 5.0 and d.end < talk_end_target) else d.end
            if d.character_id == 'NARRATOR':
                lines_out.append(
                    f'• [{d.start:g}s – {d_end:g}s | GIỌNG DẪN CHUYỆN (VOICEOVER)]: '
                    f'Giọng đọc ({d.delivery}): "{d.text}". Nhân vật trên hình BẮT BUỘC NGẬM/KHÉP MIỆNG LẮNG NGHE, diễn xuất biểu cảm tự nhiên.'
                )
            else:
                speaker = char_objs.get(d.character_id)
                sp_label = short_tag(d.character_id)
                sp_name = speaker.name if speaker else d.character_id
                listeners = [short_tag(cid) for cid in s.character_ids if cid != d.character_id]
                listener_note = (
                    f'Trong suốt [{d.start:g}s – {d_end:g}s] khi {sp_name} nói, {", ".join(listeners)} BẮT BUỘC NGẬM/KHÉP MIỆNG LẮNG NGHE tại nguyên vị trí, chỉ phản ứng bằng ánh mắt và nét mặt tự nhiên (tuyệt đối không mở miệng nhép môi theo và không tự ý bỏ đi).'
                    if listeners else ''
                )
                lines_out.append(
                    f'• [{d.start:g}s – {d_end:g}s | ACTIVE LIP-SYNC — {sp_label} MỞ MIỆNG PHÁT ÂM KHỚP TỪNG ÂM TIẾT TIẾNG VIỆT]: '
                    f'"{d.text}" (biểu cảm {d.delivery}). Giữ khuôn mặt và miệng của {sp_name} nằm rõ trong khung hình {p.ratio}. {listener_note}'
                )
        lines_out.append(_tail_transition_instruction(p, s, talk_end_target))

    return '\n'.join(lines_out)


# ==============================================================================
# BỘ XUẤT DỮ LIỆU RIÊNG BIỆT CHO TỪNG PHONG CÁCH (3D FABLE vs LIVE-ACTION / FAMILY DRAMA)
# ==============================================================================

def build_scene_image_prompt(p: Project, s: Scene) -> str:
    """Build the 4-Pillar Professional Photography & Biometric Control Prompt
    (Camera Settings + Biometric Character Locks + Micro-Acting/Props + 1980s-1990s Clean Environment with Anti-Anachronism Shield).
    """
    char_map = {c.id: c for c in (p.bible.characters if p.bible else [])}
    loc_map = {l.id: l for l in (p.bible.locations if p.bible else [])}
    is_3d = is_3d_fable_style(p.style)
    char_defs = []
    for idx_c, cid in enumerate(s.character_ids, 1):
        c = char_map.get(cid)
        if c:
            if is_3d:
                char_defs.append(
                    f"A cute 3D Pixar-style fluffy {c.name} ({c.appearance}) with big expressive eyes, wearing fixed outfit ({c.wardrobe})"
                )
            else:
                char_defs.append(sanitize_for_video_prompt(build_biometric_character_anchor(c, idx_c)))
    loc = loc_map.get(s.location_id)
    loc_str = f"{loc.name} ({loc.description}; lighting: {loc.lighting})" if loc else s.location_id
    if is_3d:
        style_suffix = f"3D animation style, Disney Pixar aesthetic, vibrant warm lighting, cinematic composition, 8k resolution, octane render --ar {p.ratio}"
        char_part = "; ".join(char_defs) if char_defs else "Consistent main character"
        return (
            f"{char_part}. Scene action & expression: {sanitize_for_video_prompt(s.visual_prompt)} "
            f"({sanitize_for_video_prompt(s.emotion)}). Setting: {sanitize_for_video_prompt(loc_str)}. "
            f"Camera: {sanitize_for_video_prompt(s.camera)}. {style_suffix}"
        )

    cam_pillar = (
        f"Medium shot, eye-level angle, shot on 35mm lens, f/2.8 aperture, shallow depth of field, cinematic film still ({sanitize_for_video_prompt(s.camera)})"
    )
    char_pillar = " | ".join(char_defs) if char_defs else "Authentic Vietnamese rural characters with locked biometric face and wardrobe"
    action_pillar = f"Action, Props & Close-up Micro-Expression: {sanitize_for_video_prompt(s.visual_prompt)} ({sanitize_for_video_prompt(s.emotion)})"
    env_pillar = (
        f"Environment & 1980s-1990s Period-Accurate Setting: {sanitize_for_video_prompt(loc_str)}. "
        f"Authentic 1980s-1990s northern/central Vietnamese countryside & village life (aged lime-washed walls or 3-bay tile-roof house, "
        f"traditional wooden ancestral altar 'bàn thờ gia tiên cổ', rustic bamboo bed 'chõng tre', old wooden chest 'hòm gỗ cũ', "
        f"fresh water spinach basket 'rổ rau muống', mud-stained hoe 'cuốc đất dính bùn', stone guardian lions 'đôi nghê đá cổ' at wealthy gate). "
        f"Natural soft daylight, dramatic shadows, consistent 1980s-1990s 35mm cinema color grading, muted desaturated tones, gritty realism, 8k photorealistic "
        f"--no {ANTI_ANACHRONISM_NEGATIVE_PROMPT} --ar {p.ratio} --style raw --v 6.0 [Control: --sref reference_image --cref biometric_face_lock]"
    )
    return f"{cam_pillar}. {char_pillar}. {action_pillar}. {env_pillar}"

def build_live_drama_scene_item(p: Project, s: Scene, scene_index: int, film_start: float, film_end: float) -> dict:
    """Build the 6-key JSON dictionary for Live-Action / Family Drama with context-aware continuity
    (staying seated/standing when continuing conversation in same location vs walking only when changing location,
    and zero fade-to-black or swoosh sound effects).
    """
    char_map = {c.id: c for c in (p.bible.characters if p.bible else [])}
    loc_map = {l.id: l for l in (p.bible.locations if p.bible else [])}
    scenes_list = p.board.scenes if (p.board and p.board.scenes) else []
    idx0 = next((i for i, x in enumerate(scenes_list) if x.id == s.id), scene_index - 1)
    prev_sc = scenes_list[idx0 - 1] if idx0 > 0 else None
    next_sc = scenes_list[idx0 + 1] if (0 <= idx0 < len(scenes_list) - 1) else None

    mm_s, ss_s = divmod(int(round(film_start)), 60)
    mm_e, ss_e = divmod(int(round(film_end)), 60)
    duration_str = f"{mm_s:02d}:{ss_s:02d} - {mm_e:02d}:{ss_e:02d}"

    loc = loc_map.get(s.location_id)
    loc_name = f"{loc.name} ({loc.description}; Ánh sáng: {loc.lighting})" if loc else s.location_id
    same_prev = (prev_sc is not None and prev_sc.location_id == s.location_id)
    same_next = (next_sc is not None and next_sc.location_id == s.location_id)

    frame_lock_note = (
        f" [GIỮ NGUYÊN 100% KHUNG HÌNH & GÓC MÁY TỪ {prev_sc.id} — Bố con/nhân vật vẫn ngồi/đứng tại chỗ nói chuyện tiếp]"
        if same_prev else ""
    )
    context_and_angle = sanitize_for_video_prompt(f"{loc_name} - {s.camera}{frame_lock_note}")

    action_beats = "; ".join(f"[{b.start:g}s-{b.end:g}s] {sanitize_for_video_prompt(b.action)}" for b in s.timeline)
    if same_next:
        tail_lock_note = (
            f" → [ Cuối cảnh 9.0s-{s.duration:g}s: Nhân vật VẪN NGỒI/ĐỨNG NGUYÊN TẠI VỊ TRÍ ({s.end_state}) nhìn nhau phản ứng tự nhiên "
            f"để nối thẳng sang {next_sc.id}; TUYỆT ĐỐI KHÔNG tự ý đứng dậy bỏ đi ]"
        )
    elif next_sc is not None:
        tail_lock_note = (
            f" → [ Cuối cảnh 9.0s-{s.duration:g}s: Sau khi nói xong câu thoại, nhân vật mới đứng dậy / bước đi tự nhiên ({s.end_state}) "
            f"để chuyển sang bối cảnh mới ở {next_sc.id} ]"
        )
    else:
        tail_lock_note = f" → [ Kết cảnh giữ nguyên khung hình cảm xúc tự nhiên ({s.end_state}) ]"

    character_action = sanitize_for_video_prompt(f"[Đầu cảnh 0.0s: {s.start_state}] → {action_beats}{tail_lock_note} (Cảm xúc: {s.emotion})")

    if s.dialogue:
        dlg_parts = []
        for d in sorted(s.dialogue, key=lambda x: x.start):
            sp_name = char_map[d.character_id].name if d.character_id in char_map else d.character_id
            dlg_parts.append(f'{sp_name} ({d.start:g}s-{d.end:g}s, giọng {d.delivery}): "{sanitize_for_video_prompt(d.text)}"')
        dialogue_str = " | ".join(dlg_parts)
    else:
        dialogue_str = "(Không lời thoại — Diễn xuất ánh mắt và cử chỉ tâm lý đời thực tự nhiên)"

    if same_next:
        trans_clean = (
            f"Nối thẳng trực tiếp cùng khung hình sang {next_sc.id} (Direct Continuity Cut — Giữ nguyên vị trí ngồi/đứng nói chuyện, "
            f"KHÔNG làm tối màn hình / NO Fade to black, KHÔNG chèn tiếng chuýt chuyển cảnh)"
        )
    elif next_sc is not None:
        trans_clean = (
            f"Khớp chuyển động bước đi tự nhiên ở giây cuối sang bối cảnh {next_sc.location_id} của {next_sc.id} "
            f"(Action Match Cut — Giữ sáng khung hình tự nhiên, KHÔNG Fade to black, KHÔNG tiếng chuýt chuyển cảnh)"
        )
    else:
        trans_clean = "Giữ sáng khung hình tự nhiên khép lại câu chuyện (KHÔNG Fade to black, KHÔNG tiếng chuýt)"

    clean_sound = sanitize_for_video_prompt(s.sound)
    sound_and_trans = f"Âm thanh đời thực tự nhiên: {clean_sound} (Không chèn tiếng chuýt/hiệu ứng âm thanh kịch tính giả tạo) | Chuyển cảnh: {trans_clean}"

    return {
        "scene_id": scene_index,
        "duration_seconds": duration_str,
        "context_and_angle": context_and_angle,
        "character_action": character_action,
        "dialogue": dialogue_str,
        "sound_effect_and_transition": sound_and_trans,
    }

def compile_live_drama_json(p: Project) -> str:
    """Compile the complete Live-Action Psychological Drama 5-item breakdown + standard JSON payload."""
    if not p.board or not p.board.scenes:
        return ""
    scene_items = []
    text_blocks = [
        f"=== BẢNG KỊCH BẢN PHÂN CẢNH 5 MỤC — TIỂU PHẨM TÂM LÝ & BẺ LÁI ({len(p.board.scenes)} CẢNH) ==="
    ]
    cursor = 0.0
    for idx, s in enumerate(p.board.scenes, 1):
        f_start = cursor
        f_end = cursor + float(s.duration)
        cursor = f_end
        item = build_live_drama_scene_item(p, s, idx, f_start, f_end)
        scene_items.append(item)
        text_blocks.append(
            f"Scene {item['scene_id']}: {sanitize_for_video_prompt(s.title)}\n"
            f"1. Scene & Thời gian: Scene {item['scene_id']} ({item['duration_seconds']})\n"
            f"2. Bối cảnh & Góc máy: {item['context_and_angle']}\n"
            f"3. Hành động nhân vật: {item['character_action']}\n"
            f"4. Lời thoại (Jump Cut dồn dập): {item['dialogue']}\n"
            f"5. Hiệu ứng âm thanh / Chuyển cảnh: {item['sound_effect_and_transition']}"
        )
    json_payload = {
        "project_title": p.title or "Tiểu phẩm tâm lý xã hội Plot Twist",
        "scenes": scene_items,
    }
    text_blocks.append(
        "=== CẤU TRÚC JSON CHUẨN TÍCH HỢP CHO TOOL TỰ ĐỘNG ===\n"
        + json.dumps(json_payload, ensure_ascii=False, indent=2)
    )
    return "\n\n".join(text_blocks)

def compile_all_image_prompts(p: Project) -> str:
    """Dispatcher: return the dedicated batch output matching the active style (3D Fable 4-item vs Live Drama 5-item + JSON)."""
    if not p.board or not p.board.scenes:
        return ""
    if not is_3d_fable_style(p.style):
        return compile_live_drama_json(p)
    out = [
        f"=== DANH SÁCH KỊCH BẢN PHÂN CẢNH 4 MỤC & IMAGE PROMPTS 3D PIXAR ĐỒNG NHẤT NHÂN VẬT ({len(p.board.scenes)} CẢNH) ==="
    ]
    n_sc = len(p.board.scenes)
    for idx, s in enumerate(p.board.scenes, 1):
        dlg_str = " / ".join(f'"{d.text}"' for d in s.dialogue) if s.dialogue else "(Diễn xuất hình thể & biểu cảm)"
        img_p = build_scene_image_prompt(p, s)
        moral_line = f"\n- Moral Lesson (Châm ngôn cốt lõi ở cuối video): {s.story_beat}" if idx == n_sc else ""
        out.append(
            f"Scene {idx}: {s.title} ({s.duration:g}s)\n"
            f"- Visual Description (Mô tả hình ảnh 3D chi tiết): {sanitize_for_video_prompt(s.visual_prompt)}\n"
            f"- Image Prompt (3D Consistent Character EN): {img_p}\n"
            f"- Voiceover / Dialogue (Lời thoại 0s–{max(1.0, s.duration-1.0):g}s): {dlg_str}{moral_line}"
        )
    return "\n\n".join(out)


def sanitize_scene_for_flow(s: Scene) -> Scene:
    sc = s.model_copy(deep=True)
    sc.title = sanitize_for_video_prompt(sc.title)
    sc.start_state = sanitize_for_video_prompt(sc.start_state)
    sc.end_state = sanitize_for_video_prompt(sc.end_state)
    sc.emotion = sanitize_for_video_prompt(sc.emotion)
    sc.visual_prompt = sanitize_for_video_prompt(sc.visual_prompt)
    sc.camera = sanitize_for_video_prompt(sc.camera)
    sc.lighting = sanitize_for_video_prompt(sc.lighting)
    sc.sound = sanitize_for_video_prompt(sc.sound)
    sc.transition = sanitize_for_video_prompt(sc.transition)
    sc.continuity = sanitize_for_video_prompt(sc.continuity)
    sc.story_beat = sanitize_for_video_prompt(sc.story_beat)
    for b in sc.timeline:
        b.action = sanitize_for_video_prompt(b.action)
    for d in sc.dialogue:
        d.text = sanitize_for_video_prompt(d.text)
        d.delivery = sanitize_for_video_prompt(d.delivery)
    return sc

def sanitize_project_for_flow(p: Project) -> Project:
    proj = p.model_copy(deep=True)
    proj.script = sanitize_for_video_prompt(proj.script)
    proj.treatment = sanitize_for_video_prompt(proj.treatment)
    if proj.bible:
        for c in proj.bible.characters:
            c.appearance = sanitize_for_video_prompt(c.appearance)
            c.wardrobe = sanitize_for_video_prompt(c.wardrobe)
            c.personality = sanitize_for_video_prompt(c.personality)
            c.gestures = sanitize_for_video_prompt(c.gestures)
            c.voice = sanitize_for_video_prompt(c.voice)
        for loc in proj.bible.locations:
            loc.description = sanitize_for_video_prompt(loc.description)
            loc.lighting = sanitize_for_video_prompt(loc.lighting)
    if proj.board and proj.board.scenes:
        proj.board.scenes = [sanitize_scene_for_flow(s) for s in proj.board.scenes]
    return proj

def compile_flow_prompt(p: Project, s: Scene) -> str:
    """Compile a 100% Google Flow (Veo) & Muse policy-safe, single-scene video generation prompt
    with:
    1. 4-Pillar Photography & Muted Desaturated Color Grading (matching user's reference photo: peeling paint walls, bamboo bed, natural soft doorway light, desaturated tones, NO yellow/warm tint).
    2. Strict Single-Speaker Lip-Sync (khắc phục triệt để lỗi tiếng nói không khớp hình: ai nói người đó mở miệng khớp từng âm tiết, người nghe khép miệng 100%).
    3. Same-Location Camera Angle Lock (khắc phục triệt để lỗi cảnh vay tiền câu sau tự ý đổi góc quay: cùng bối cảnh bắt buộc khóa cứng 100% góc máy, tiêu cự 35mm và vị trí ngồi/đứng của cảnh trước).
    """
    safe_p = sanitize_project_for_flow(p)
    safe_s = sanitize_scene_for_flow(s)
    char_map = {c.id: c for c in (safe_p.bible.characters if safe_p.bible else [])}
    loc_map = {l.id: l for l in (safe_p.bible.locations if safe_p.bible else [])}
    scenes_list = safe_p.board.scenes if (safe_p.board and safe_p.board.scenes) else []
    idx = next((i for i, x in enumerate(scenes_list) if x.id == safe_s.id), 0)
    prev_sc = scenes_list[idx - 1] if idx > 0 else None
    next_sc = scenes_list[idx + 1] if (0 <= idx < len(scenes_list) - 1) else None
    talk_end_s = round(max(1.0, safe_s.duration - 1.0), 1)
    exit_start_s = round(max(1.0, safe_s.duration - 0.8), 1)

    char_lines = []
    for idx_c, cid in enumerate(safe_s.character_ids, 1):
        c = char_map.get(cid)
        if c:
            char_lines.append(
                f"{build_biometric_character_anchor(c, idx_c)} (Cử chỉ & dáng điệu: {c.gestures}; Giọng nói: {c.voice})"
            )
    char_summary = " | ".join(char_lines) if char_lines else "Nhân vật người Việt Nam hư cấu đồng nhất 100% từ cảnh đầu đến cảnh cuối"

    loc = loc_map.get(safe_s.location_id)
    loc_summary = (
        f"{loc.name} (KHÓA BỐI CẢNH & ÁNH SÁNG [ControlNet Depth/Canny]: {loc.description}; "
        f"Ánh sáng & Tông màu chuẩn ảnh mẫu (--sref): {loc.lighting} — Natural soft light from doorway, dramatic shadows, muted color palette, desaturated tones, gritty realism, KHÔNG ám vàng/sepia)"
        if loc else safe_s.location_id
    )

    same_prev = (prev_sc is not None and prev_sc.location_id == safe_s.location_id)
    same_next = (next_sc is not None and next_sc.location_id == safe_s.location_id)

    if prev_sc:
        if same_prev:
            entry_continuity_rule = (
                f"[KHỚP ĐẦU CẢNH 0.0s & KHÓA GÓC QUAY CŨ 100% VỚI {prev_sc.id} (CÙNG BỐI CẢNH — CẤM ĐỔI GÓC QUAY)]: "
                f"Giữ NGUYÊN VĂN 100% GÓC MÁY CŨ ({prev_sc.camera}), tiêu cự 35mm ngang tầm mắt, khung hình, bối cảnh ({loc.name if loc else safe_s.location_id}), "
                f"vị trí ngồi/đứng của từng nhân vật và đạo cụ trên tay từ cuối cảnh trước ({prev_sc.end_state}). "
                f"TUYỆT ĐỐI KHÔNG ĐỔI GÓC QUAY (NO camera angle change, NO jump cut, NO sudden close-up/reverse angle) khi câu sau vẫn đang đối thoại tại cùng bối cảnh!"
            )
        else:
            entry_continuity_rule = (
                f"[KHỚP ĐẦU CẢNH 0.0s — NHÂN VẬT BƯỚC VÀO BỐI CẢNH MỚI ({loc.name if loc else safe_s.location_id}) TỪ {prev_sc.id}]: "
                f"Thiết lập góc máy Medium shot 35mm ngang tầm mắt ({safe_s.camera}), tiếp nối mượt mà khoảnh khắc nhân vật vừa di chuyển từ cuối {prev_sc.id} ({prev_sc.end_state}) vào ({safe_s.start_state})."
            )
    else:
        entry_continuity_rule = (
            f"[MỞ ĐẦU CẢNH 0.0s — THIẾT LẬP KHUNG HÌNH CHUẨN ẢNH MẪU]: Medium shot, eye-level angle, shot on 35mm lens, f/2.8 aperture ({safe_s.camera}), "
            f"bố cục nhân vật và bối cảnh ({safe_s.start_state})."
        )

    if next_sc:
        if same_next:
            exit_continuity_rule = (
                f"[KHỚP ĐUÔI CẢNH {talk_end_s:g}s–{safe_s.duration:g}s — ĐANG ĐỐI THOẠI TIẾP SANG {next_sc.id} CÙNG BỐI CẢNH (GIỮ NGUYÊN GÓC QUAY CŨ, CẤM BỎ ĐI, CẤM FADE ĐEN)]: "
                f"Vì sang {next_sc.id} các nhân vật VẪN ĐỐI THOẠI TIẾP tại {loc.name if loc else safe_s.location_id}, "
                f"nên từ 0.0s đến hết {safe_s.duration:g}s máy quay BẮT BUỘC GIỮ NGUYÊN GÓC QUAY CŨ ({safe_s.camera}) và nhân vật GIỮ NGUYÊN VỊ TRÍ NGỒI/ĐỨNG ({safe_s.end_state}). "
                f"TUYỆT ĐỐI KHÔNG tự ý đổi góc máy, KHÔNG đứng dậy quay lưng bỏ đi khi chưa hết cuộc nói chuyện, KHÔNG làm tối đen màn hình (NO Fade to black), KHÔNG chèn tiếng chuýt!"
            )
        else:
            next_loc = loc_map.get(next_sc.location_id)
            next_loc_name = next_loc.name if next_loc else next_sc.location_id
            exit_continuity_rule = (
                f"[KHỚP ĐUÔI CẢNH {exit_start_s:g}s–{safe_s.duration:g}s — CHUYỂN SANG BỐI CẢNH MỚI ({next_loc_name}) Ở {next_sc.id}]: "
                f"Từ 0.0s đến {talk_end_s:g}s nhân vật ngồi/đứng tại chỗ nói xong hoàn toàn câu thoại (môi khép lại đúng lúc dứt tiếng nói ở {talk_end_s:g}s); "
                f"chỉ từ giây {exit_start_s:g}s–{safe_s.duration:g}s cuối cảnh nhân vật mới đứng dậy / bước đi tự nhiên ({safe_s.end_state}) hướng sang {next_loc_name}. "
                f"Giữ sáng khung hình tự nhiên (NO Fade to black) và chỉ dùng tiếng bước chân đời thực (NO dramatic swoosh sound)."
            )
    else:
        exit_continuity_rule = (
            f"[KẾT CẢNH {talk_end_s:g}s–{safe_s.duration:g}s]: Nhân vật giữ nguyên vị trí ({safe_s.end_state}) và góc máy ({safe_s.camera}) với biểu cảm đời thực tự nhiên, "
            f"giữ sáng khung hình đến hết giây {safe_s.duration:g}s (NO Fade to black, NO dramatic sound effect)."
        )

    dlg_lines = []
    for d in sorted(safe_s.dialogue, key=lambda x: x.start):
        sp = char_map[d.character_id].name if d.character_id in char_map else d.character_id
        listeners = [char_map[cid].name for cid in safe_s.character_ids if cid != d.character_id and cid in char_map]
        listen_str = (
            f" [TRONG KHI {sp.upper()} NÓI ({d.start:g}s–{d.end:g}s): {', '.join(listeners)} BẮT BUỘC KHÉP KÍN MIỆNG LẮNG NGHE 100%, "
            f"tuyệt đối không nhép môi theo, chỉ phản ứng bằng ánh mắt và cơ mặt tại nguyên vị trí]"
            if listeners else ""
        )
        dlg_lines.append(
            f'[{d.start:g}s–{d.end:g}s] CHỈ MÌNH {sp} MỞ MIỆNG NÓI KHỚP TỪNG ÂM TIẾT TIẾNG VIỆT (Active Lip-Sync, kết thúc câu và khép môi đúng giây {d.end:g}s, biểu cảm {d.delivery}): "{d.text}"{listen_str}'
        )
    dlg_summary = " | ".join(dlg_lines) if dlg_lines else "(Diễn xuất ánh mắt và cử chỉ đời thực tự nhiên, các nhân vật khép miệng, không lời thoại)"

    action_beats = "; ".join(f"[{b.start:g}s–{b.end:g}s] {b.action}" for b in safe_s.timeline)
    photo_prompt_en = build_scene_image_prompt(safe_p, safe_s)

    if is_3d_fable_style(safe_p.style):
        return (
            f"{SAFE_FICTIONAL_FRAME_VI}\n"
            f"🎬 TẠO 1 VIDEO HOẠT HÌNH 3D PIXAR ({safe_s.id} — Scene {idx + 1}: {safe_s.title} | Thời lượng: {safe_s.duration:g}s | Khung hình: {safe_p.ratio}):\n"
            f"1. Khóa Nhân vật 3D đồng nhất (Consistent 3D Character): {char_summary}.\n"
            f"2. Khóa Bối cảnh & Góc máy (3D Pixar Aesthetic): {loc_summary} — Góc máy: {safe_s.camera}.\n"
            f"3. Khớp Đầu Cảnh & Diễn biến hành động (0s–{talk_end_s:g}s): {entry_continuity_rule} → {action_beats}.\n"
            f"4. Lời thoại tiếng Việt khớp khẩu hình (0s–{talk_end_s:g}s): {dlg_summary}.\n"
            f"5. Khớp Đuôi Cảnh ({talk_end_s:g}s–{safe_s.duration:g}s): {exit_continuity_rule}\n"
            f"6. QUY TẮC HÌNH ẢNH BẮT BUỘC: Tuyệt đối KHÔNG chèn phụ đề/chữ viết lên màn hình (NO subtitles, NO captions, NO on-screen text, NO timecodes, NO watermarks)."
        )
    else:
        return (
            f"{SAFE_FICTIONAL_FRAME_VI}\n"
            f"🎬 TẠO 1 VIDEO ĐIỆN ẢNH ĐỜI THỰC VIỆT NAM — TÔNG MÀU TRẦM LẠNH CHÂN THỰC NHƯ ẢNH MẪU ({safe_s.id} — Scene {idx + 1}: {safe_s.title} | Thời lượng: {safe_s.duration:g}s | Khung hình: {safe_p.ratio}):\n"
            f"1. THÔNG SỐ MÁY ẢNH & TÔNG MÀU BẮT BUỘC (CAMERA & COLOR GRADING): Medium shot, eye-level angle, shot on 35mm lens, f/2.8 aperture, shallow depth of field, cinematic film still ({safe_s.camera}). "
            f"Natural soft light coming from the doorway, dramatic shadows inside the room, muted color palette, desaturated tones, gritty realism, 8k photorealistic "
            f"(Tông màu phim trầm lạnh, bạc màu sờn cũ chân thực như ảnh chụp thực tế; TUYỆT ĐỐI KHÔNG ám vàng rực hay màu sepia cổ tích).\n"
            f"2. KHÓA CỨNG NHÂN VẬT & TRANG PHỤC 100% (--cref & OpenPose): {char_summary}.\n"
            f"3. KHÓA BỐI CẢNH & GÓC QUAY LIỀN MẠCH (--sref & Depth/Canny): {loc_summary}.\n"
            f"4. DIỄN XUẤT & KHÓA GÓC QUAY CŨ (0.0s–{talk_end_s:g}s): {entry_continuity_rule} → {action_beats} (Cảm xúc: {safe_s.emotion}).\n"
            f"5. KHỚP KHẨU HÌNH TIẾNG VIỆT TUYỆT ĐỐI — CHỐNG LỆCH TIẾNG & HÌNH (0.0s–{talk_end_s:g}s): {dlg_summary}.\n"
            f"6. KHỚP ĐUÔI CẢNH & KHÓA TẮT TIẾNG LẠ CUỐI VIDEO ({talk_end_s:g}s–{safe_s.duration:g}s): {exit_continuity_rule} Sau khi dứt lời thoại ở giây {talk_end_s:g}s, nhân vật BẮT BUỘC NGẬM KÍN MIỆNG Tĩnh Lặng (TUYỆT ĐỐI KHÔNG phát ra tiếng kêu lạ 'aaa', 'ơ ơ ơ', tiếng rên, tiếng thở dốc hay tiếng cười vô cớ ở cuối video!). Âm thanh môi trường tự nhiên: {safe_s.sound}.\n"
            f"7. TEXT PROMPT NHIẾP ẢNH CHUẨN (4 CỤM TỪ KHÓA): {photo_prompt_en}\n"
            f"8. QUY TẮC CHỐNG LỖI THỜI GIAN & KỸ THUẬT BẮT BUỘC: (a) CẤM TUYỆT ĐỐI vẽ lịch treo tường hiện đại in năm 2024/2025/2026, đồng hồ điện tử, ghế nhựa hiện đại hay đồ vật hiện đại ({ANTI_ANACHRONISM_NEGATIVE_PROMPT}); "
            f"(b) Câu sau cùng bối cảnh BẮT BUỘC GIỮ NGUYÊN GÓC QUAY CŨ và giữ nguyên đạo cụ cầm tay (Prop Persistence Lock); "
            f"(c) Chỉ đúng người đang có thoại mới mở miệng kèm biểu cảm cơ mặt chiều sâu (mím môi, mắt đỏ hoe ngấn lệ, giọng nghẹn ngào tự nhiên), người nghe phải khép miệng; "
            f"(d) KHÔNG làm tối đen màn hình (NO fade to black) và KHÔNG phát tiếng chuýt; "
            f"(e) BẮT BUỘC KHUNG HÌNH DỌC 9:16 FULL MÀN HÌNH (Vertical 9:16 portrait 720x1280 full-bleed) và CẤM tiếng kêu lạ 'aaa', 'ơ ơ ơ' ở cuối video; (f) KHÔNG chèn phụ đề/chữ viết lên màn hình (NO subtitles, NO captions, NO on-screen text)."
        )


def compile_prompt(p: Project, s: Scene) -> str:
    """Compile a single scene's detailed view & prompt using the exact form of the selected style."""
    characters = [c.model_dump() for c in p.bible.characters if c.id in s.character_ids]
    location = next(l.model_dump() for l in p.bible.locations if l.id == s.location_id)
    safe_scene = s.model_copy(deep=True)
    safe_scene.title = sanitize_for_video_prompt(safe_scene.title)
    safe_scene.start_state = sanitize_for_video_prompt(safe_scene.start_state)
    safe_scene.end_state = sanitize_for_video_prompt(safe_scene.end_state)
    safe_scene.emotion = sanitize_for_video_prompt(safe_scene.emotion)
    safe_scene.visual_prompt = sanitize_for_video_prompt(safe_scene.visual_prompt)
    for b in safe_scene.timeline:
        b.action = sanitize_for_video_prompt(b.action)
    lipsync_guide = sanitize_for_video_prompt(_build_lipsync_and_demeanor_guide(p, safe_scene))
    talk_end_s = round(max(1.0, s.duration - 1.0), 1)
    idx = next((i for i, x in enumerate(p.board.scenes) if x.id == s.id), 0) if p.board else 0

    if is_3d_fable_style(p.style):
        dlg_summary = " / ".join(f'"{d.text}"' for d in safe_scene.dialogue) if safe_scene.dialogue else "(Diễn xuất biểu cảm 3D)"
        img_prompt_str = build_scene_image_prompt(p, safe_scene)
        structured_header = (
            f"=== FORM PHONG CÁCH 1: HOẠT HÌNH 3D PIXAR NGỤ NGÔN & CHÂM NGÔN SỐNG (4 MỤC) ===\n"
            f"• Scene {idx + 1} ({safe_scene.id}): {safe_scene.title} ({s.duration:g}s | Khung hình {p.ratio})\n"
            f"• Visual Description (Mô tả hình ảnh 3D chi tiết): {safe_scene.visual_prompt}\n"
            f"• Image Prompt (3D Consistent Character EN): {img_prompt_str}\n"
            f"• Voiceover / Dialogue (Lời thoại 0s–{talk_end_s:g}s): {dlg_summary}\n"
            f"• Moral Lesson / Thông điệp cảnh: {safe_scene.story_beat}"
        )
    elif is_family_drama_style(p.style):
        film_start = sum(float(x.duration) for x in p.board.scenes[:idx]) if p.board else 0.0
        film_end = film_start + float(s.duration)
        item = build_live_drama_scene_item(p, safe_scene, idx + 1, film_start, film_end)
        structured_header = (
            f"=== PHIM GIA ĐÌNH TÂM LÝ XÃ HỘI & ĐỜI THỰC QUÊ NGHÈO THẬP NIÊN 80 (TỰ DO SÁNG TẠO • KHÓA NHÂN VẬT 100% • NỐI CẢNH TỰ NHIÊN) ===\n"
            f"• Cảnh {item['scene_id']} ({safe_scene.id} — {item['duration_seconds']} | {s.duration:g}s): {safe_scene.title}\n"
            f"• Bối cảnh Quê nghèo Thập niên 80 & Góc máy: {item['context_and_angle']}\n"
            f"• Diễn xuất tự nhiên & Nối cảnh (Đầu 0.0s -> Cuối {s.duration:g}s): {item['character_action']}\n"
            f"• Lời thoại đời thực: {item['dialogue']}\n"
            f"• Âm thanh tự nhiên & Chuyển tiếp: {item['sound_effect_and_transition']}"
        )
    else:
        film_start = sum(float(x.duration) for x in p.board.scenes[:idx]) if p.board else 0.0
        film_end = film_start + float(s.duration)
        item = build_live_drama_scene_item(p, safe_scene, idx + 1, film_start, film_end)
        structured_header = (
            f"=== FORM PHONG CÁCH 2: TIỂU PHẨM TÂM LÝ XÃ HỘI ĐỜI THỰC & BẺ LÁI (5 MỤC + JSON CHUẨN) ===\n"
            f"1. Scene & Thời gian (duration_seconds): Scene {item['scene_id']} ({item['duration_seconds']} | {s.duration:g}s)\n"
            f"2. Bối cảnh & Góc máy (context_and_angle): {item['context_and_angle']}\n"
            f"3. Hành động nhân vật & VFX (character_action): {item['character_action']}\n"
            f"4. Lời thoại thực tế dồn dập - Jump Cut (dialogue): {item['dialogue']}\n"
            f"5. Hiệu ứng âm thanh / Chuyển cảnh (sound_effect_and_transition): {item['sound_effect_and_transition']}\n\n"
            f"JSON PHÂN CẢNH NÀY:\n" + json.dumps(item, ensure_ascii=False, indent=2)
        )

    if is_google_flow_tool(getattr(p, 'video_tool', TOOL_GOOGLE_FLOW)):
        return compile_flow_prompt(p, safe_scene) + "\n\n--- CHI TIẾT FORM ĐẠO DIỄN ĐỒNG BỘ ---\n" + structured_header
    return '\n\n'.join([
        SAFE_FICTIONAL_FRAME_VI,
        structured_header,
        f'PHONG CÁCH (STYLE): {p.style} | KHUNG HÌNH: {p.ratio} | THỜI LƯỢNG: {s.duration:g}s.',
        lipsync_guide,
        'HỒ SƠ NHÂN VẬT CỐ ĐỊNH:\n'+sanitize_for_video_prompt(json.dumps(characters, ensure_ascii=False, indent=2)),
        'BỐI CẢNH & ÁNH SÁNG CỐ ĐỊNH:\n'+sanitize_for_video_prompt(json.dumps(location, ensure_ascii=False, indent=2)),
        f'Lời thoại đúng nguyên văn bằng tiếng Việt từ 0s đến giây thứ {talk_end_s:g}s (khớp khẩu hình lip-sync, không khoảng lặng thừa), và dùng giây thứ {talk_end_s:g}s–{s.duration:g}s cuối cảnh để nối mượt sang cảnh sau.'
    ])

def compile_muse_recovery_prompt(p: Project, scenes: list[Scene]) -> str:
    """Build a style-specific, 100% safety-filter-friendly batch prompt for Muse."""
    char_map = {c.id: c for c in (p.bible.characters if p.bible else [])}
    loc_map = {l.id: l for l in (p.bible.locations if p.bible else [])}
    is_3d = is_3d_fable_style(p.style)

    if is_3d:
        blocks = [
            'CHỈ ĐẠO TẠO VIDEO HOẠT HÌNH 3D PIXAR NGỤ NGÔN & CHÂM NGÔN SỐNG (CONSISTENT 3D CHARACTER):\n'
            '- Giữ nguyên 100% thiết kế nhân vật 3D dễ thương (Consistent Character: màu lông, đôi mắt to biểu cảm, trang phục/phụ kiện cố định) xuyên suốt mọi cảnh.\n'
            '- Từ 0.0s → 9.0s: Nhân vật 3D diễn xuất sống động và nói/dẫn chuyện sâu sắc khớp khẩu hình tiếng Việt (Active Lip-Sync).\n'
            '- Từ 9.0s → 10.0s: Chuyển động Match Cut & Seamless Zoom nối mượt sang cảnh tiếp theo:'
        ]
    else:
        blocks = [
            'CHỈ ĐẠO TẠO VIDEO GIA ĐÌNH TÂM LÝ XÃ HỘI ĐỜI THỰC VIỆT NAM (KHÓA NHÂN VẬT 100% • DIỄN XUẤT TỰ NHIÊN • NỐI CẢNH TRỰC TIẾP KHÔNG FADE ĐEN, KHÔNG TIẾNG CHUÝT):\n'
            '- Quy tắc 1 (Mỗi cảnh 1 nội dung & lời thoại riêng biệt 100%): Tất cả các cảnh từ SCENE_001 đến hết đều có lời thoại và diễn biến tiến triển hoàn toàn khác nhau, tuyệt đối không trùng lặp cảnh.\n'
            '- Quy tắc 2 (Phân biệt thông minh Đứng Yên Nói Chuyện vs Bước Đi Đổi Cảnh): Khi 2 cảnh liên tiếp ở CÙNG BỐI CẢNH (đang nói chuyện tiếp), nhân vật BẮT BUỘC giữ nguyên vị trí ngồi/đứng từ 0.0s đến 10.0s (TUYỆT ĐỐI KHÔNG tự ý đứng dậy quay lưng bỏ đi) và nối thẳng cùng khung hình sang cảnh sau. CHỈ KHI cảnh tiếp theo đổi sang bối cảnh khác thì ở giây 9.0s–10.0s nhân vật mới đứng dậy / bước đi tự nhiên.\n'
            '- Quy tắc 3 (Không Fade Đen & Không Tiếng Chuýt): Giữ sáng khung hình tự nhiên xuyên suốt đến hết giây thứ 10 (NO Fade to black, NO Dissolve) và chỉ dùng âm thanh môi trường đời thực nhẹ nhàng (NO dramatic swoosh/screech sound effect):'
        ]

    all_scenes = p.board.scenes if (p.board and p.board.scenes) else scenes
    for s in scenes:
        idx = next((i for i, x in enumerate(all_scenes) if x.id == s.id), 0)
        film_start = sum(float(x.duration) for x in all_scenes[:idx])
        film_end = film_start + float(s.duration)
        talk_target = round(max(1.0, s.duration - 1.0), 1)
        tail_bridge = sanitize_for_video_prompt(_tail_transition_instruction(p, s, talk_target))

        if is_3d:
            img_prompt_en = build_scene_image_prompt(p, s)
            dlg_str = " / ".join(f'"{sanitize_for_video_prompt(d.text)}"' for d in s.dialogue) if s.dialogue else "(Diễn xuất biểu cảm 3D)"
            blocks.append(
                f'=== {s.id} - Scene {idx + 1}: {sanitize_for_video_prompt(s.title)} ({s.duration:g}s, khung hình {p.ratio}) ===\n'
                f'- Visual Description (Mô tả hình ảnh 3D Pixar): {sanitize_for_video_prompt(s.visual_prompt)}\n'
                f'- Image/Video Prompt 3D Đồng nhất Nhân vật (Consistent Character): {img_prompt_en}\n'
                f'- Voiceover / Dialogue (0.0s–{talk_target:g}s): {dlg_str}\n'
                f'- Moral Lesson / Ý nghĩa: {sanitize_for_video_prompt(s.story_beat)}\n'
                f'- Nối cảnh giây thứ {talk_target:g}s–{s.duration:g}s: {tail_bridge}'
            )
        else:
            item = build_live_drama_scene_item(p, s, idx + 1, film_start, film_end)
            char_lines = []
            for cid in s.character_ids:
                c = char_map.get(cid)
                if c:
                    vfx = ' [Hiệu ứng VFX phát sáng mờ ảo ấm áp]' if c.entity_type == 'ghost' else ''
                    char_lines.append(f'{c.name}{vfx} ({c.appearance}, mặc cố định: {c.wardrobe})')
            blocks.append(
                f'=== {s.id} - Scene {item["scene_id"]}: {sanitize_for_video_prompt(s.title)} ({item["duration_seconds"]} | {s.duration:g}s, khung hình {p.ratio}) ===\n'
                f'1. Scene & Thời gian: Scene {item["scene_id"]} ({item["duration_seconds"]})\n'
                f'2. Bối cảnh & Góc máy: {item["context_and_angle"]}\n'
                f'3. Nhân vật & Hành động (Character Action & VFX): {" | ".join(char_lines)} -> {item["character_action"]}\n'
                f'4. Lời thoại dồn dập (Jump Cut 0.0s–{talk_target:g}s): {item["dialogue"]}\n'
                f'5. Hiệu ứng âm thanh & Chuyển cảnh ({talk_target:g}s–{s.duration:g}s): {item["sound_effect_and_transition"]} ({tail_bridge})'
            )
    return '\n\n'.join(blocks)


def get_ffmpeg_path() -> str | None:
    """Return system ffmpeg path or bundled imageio-ffmpeg binary path (NO recursive call!)."""
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return str(exe)
    except Exception:
        pass
    return None

def trim_video_clip(input_path: str, output_path: str, start_sec: float, end_sec: float) -> str:
    """Trim redundant seconds from an MP4 video clip using FFmpeg."""
    src = Path(input_path)
    if not src.is_file():
        raise ValueError('Không tìm thấy file video gốc để cắt.')
    if start_sec < 0 or end_sec <= start_sec:
        raise ValueError('Mốc giây kết thúc phải lớn hơn mốc giây bắt đầu.')
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise ValueError('Chưa có FFmpeg trong PATH để cắt video. Xem HUONG_DAN.md.')
    dst = Path(output_path)
    tmp_out = dst.with_suffix('.trim.mp4')
    args = [
        ffmpeg, '-y',
        '-ss', f'{start_sec:.3f}',
        '-to', f'{end_sec:.3f}',
        '-i', str(src),
        '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-ar', '48000', '-ac', '2',
        '-movflags', '+faststart',
        str(tmp_out),
    ]
    result = subprocess.run(args, capture_output=True)
    if result.returncode or not tmp_out.is_file():
        if tmp_out.exists():
            tmp_out.unlink(missing_ok=True)
        raise ValueError('Cắt video thất bại; kiểm tra mốc thời gian và file MP4 đầu vào.')
    tmp_out.replace(dst)
    return str(dst)

def save_project(path, project):
    p = Project.model_validate(project.model_dump())
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS project (id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        db.execute('INSERT OR REPLACE INTO project VALUES (1, ?)', (p.model_dump_json(),))

def load_project(path):
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT data FROM project WHERE id=1').fetchone()
    if not row:
        raise ValueError('Không có dự án trong file.')
    return Project.model_validate_json(row[0])

def export_project(p, folder):
    root = Path(folder); root.mkdir(parents=True, exist_ok=True)
    (root/'project.json').write_text(p.model_dump_json(indent=2), encoding='utf-8')
    if p.board:
        if is_3d_fable_style(p.style):
            (root/'IMAGE_PROMPTS_3D_CONSISTENT.txt').write_text(compile_all_image_prompts(p), encoding='utf-8')
        else:
            (root/'TIEU_PHAM_TAM_LY_5_MUC_VA_JSON.txt').write_text(compile_live_drama_json(p), encoding='utf-8')
            cursor = 0.0
            items = []
            for idx, s in enumerate(p.board.scenes, 1):
                items.append(build_live_drama_scene_item(p, s, idx, cursor, cursor + float(s.duration)))
                cursor += float(s.duration)
            (root/'tieu_pham_scenes.json').write_text(
                json.dumps({"project_title": p.title, "scenes": items}, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        for index, s in enumerate(p.board.scenes, 1):
            (root/f'canh_{index:03d}.txt').write_text(compile_prompt(p,s), encoding='utf-8')

def _probe_video_clip_duration(probe_stderr: str, scene_duration: float) -> float:
    """Extract exact clip duration from ffmpeg -i stderr, capped to prevent runaway apad buffers."""
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe_stderr or "")
    if m:
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        if 0.5 <= sec <= max(scene_duration + 3.0, 15.0):
            return round(sec, 3)
    return float(scene_duration if scene_duration and scene_duration > 0 else 10.0)

def _merge_scene_list(p: Project, scenes_to_merge: list[Scene], output: str) -> str:
    if not scenes_to_merge:
        raise ValueError('Chưa có video cảnh nào để ghép.')
    clip_paths = [p.clips.get(s.id, '') for s in scenes_to_merge]
    if any(not c or not Path(c).is_file() for c in clip_paths):
        raise ValueError('Cần nhập video cho tất cả cảnh trước khi ghép.')
    if Path(output).resolve() in [Path(x).resolve() for x in clip_paths]:
        raise ValueError('File xuất không được trùng video gốc.')
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise ValueError('Chưa có FFmpeg trong PATH. Xem HUONG_DAN.md.')
    # Default and lock to 9:16 (720x1280) full-screen vertical frame unless explicitly set otherwise
    ratio_key = (p.ratio or '9:16').strip()
    width, height = {'9:16': (720, 1280), '16:9': (1280, 720), '1:1': (720, 720)}.get(ratio_key, (720, 1280))
    with tempfile.TemporaryDirectory(prefix='quang_video_') as tmp:
        files = []
        for i, s in enumerate(scenes_to_merge):
            target = Path(tmp) / f'{i:04d}.mp4'
            files.append(target)
            probe = subprocess.run([ffmpeg, '-hide_banner', '-i', p.clips[s.id]], capture_output=True, text=True, errors='replace')
            has_audio = 'Audio:' in probe.stderr
            clip_dur = _probe_video_clip_duration(probe.stderr, float(s.duration))
            # Find when dialogue ends in this scene so we can silence any weird AI tail noises ("aaa", "ơ ơ ơ") at the end of the clip!
            last_dlg_end = max((float(d.end) for d in s.dialogue), default=round(max(1.0, clip_dur - 0.8), 2)) if getattr(s, 'dialogue', None) else round(max(1.0, clip_dur - 0.8), 2)
            clean_voice_end = min(round(clip_dur - 0.35, 2), max(round(clip_dur - 0.85, 2), round(last_dlg_end + 0.15, 2)))
            fade_start = max(0.5, round(clean_voice_end - 0.15, 2))
            args = [ffmpeg, '-y', '-i', p.clips[s.id]]
            if not has_audio:
                args += ['-f', 'lavfi', '-t', f'{clip_dur:.3f}', '-i', 'anullsrc=r=48000:cl=stereo']
            af_chain = (
                f'aresample=async=1:first_pts=0,'
                f'afade=t=in:st=0:d=0.04,'
                f'afade=t=out:st={fade_start:.3f}:d=0.25,'
                f'volume=enable=\'between(t,{clean_voice_end:.3f},{clip_dur:.3f})\':volume=0,'
                f'apad=whole_dur={clip_dur:.3f},atrim=0:{clip_dur:.3f},asetpts=PTS-STARTPTS'
                if has_audio else
                f'atrim=0:{clip_dur:.3f},asetpts=PTS-STARTPTS'
            )
            # FULL-SCREEN 9:16 VERTICAL CROP (force_original_aspect_ratio=increase + crop):
            # Eliminates black bars on top/bottom when AI accidentally generates a 16:9 clip!
            vf_chain = (
                f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                f'crop={width}:{height}:(in_w-{width})/2:(in_h-{height})/2,'
                f'setsar=1,fps=30,setpts=PTS-STARTPTS'
            )
            args += [
                '-t', f'{clip_dur:.3f}',
                '-map', '0:v:0',
                '-map', '0:a:0' if has_audio else '1:a:0',
                '-vf', vf_chain,
                '-af', af_chain,
                '-r', '30',
                '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-ar', '48000', '-ac', '2',
                '-movflags', '+faststart',
                str(target)
            ]
            result = subprocess.run(args, capture_output=True)
            if result.returncode:
                raise ValueError(f'Không chuyển đổi được video cảnh {s.id}; kiểm tra file đầu vào.')
        listing = Path(tmp) / 'list.txt'
        listing.write_text('\n'.join(f"file '{f.name}'" for f in files), encoding='utf-8')
        result = subprocess.run([ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(output)], capture_output=True)
        if result.returncode:
            raise ValueError('Ghép video thất bại; kiểm tra quyền ghi và dung lượng đĩa.')
    return str(output)

def merge_clips(p, output):
    if not p.board or any(not Path(p.clips.get(s.id,'__missing__')).is_file() for s in p.board.scenes):
        raise ValueError('Cần nhập video cho tất cả cảnh trước khi ghép.')
    return _merge_scene_list(p, list(p.board.scenes), output)

def merge_available_clips(p: Project, output: str) -> str:
    """Merge all currently downloaded scene clips in strict SCENE_001 -> SCENE_N order."""
    if p.board and p.board.scenes:
        avail = [s for s in p.board.scenes if Path(p.clips.get(s.id, '__missing__')).is_file()]
    else:
        avail = []
    if not avail and p.clips:
        valid_keys = sorted(
            [k for k, v in p.clips.items() if v and Path(v).is_file()],
            key=lambda x: int(re.search(r"(\d+)", x).group(1)) if re.search(r"(\d+)", x) else 999
        )
        for k in valid_keys:
            avail.append(Scene(
                id=k, title=k, duration=float(p.clip_seconds or 10), character_ids=[], location_id='LOC_001',
                start_state='start', timeline=[Beat(start=0.0, end=float(p.clip_seconds or 10), action='action')],
                camera='cam', lighting='light', emotion='emo', dialogue=[], sound='sound',
                end_state='end', continuity='cont', visual_prompt='vis', negative_prompt='neg'
            ))
    if not avail:
        raise ValueError('Chưa có cảnh nào có file video MP4 để ghép.')
    return _merge_scene_list(p, avail, output)


MAX_MUSE_BATCH_SIZE = 6

def extract_scene_ids_from_segment(seg: str, valid_ids: set[str] | None = None) -> list[str]:
    out = []
    for m in re.finditer(r'SCENE_(\d{1,3})|\b(\d{3})\b', seg, flags=re.IGNORECASE):
        num = int(m.group(1) or m.group(2))
        sid = f'SCENE_{num:03d}'
        if valid_ids and sid not in valid_ids:
            continue
        if sid not in out:
            out.append(sid)
    return out

def parse_muse_reply_text(text: str, valid_ids: list[str] | None = None) -> dict:
    vset = set(valid_ids) if valid_ids else None
    delivered, failed, deferred, suggestions = [], [], [], []
    in_missing_section = False
    for raw_line in (text or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.casefold()
        if any(k in low for k in ('còn thiếu', 'chưa tạo được', 'không tạo được', 'chưa làm trong lần này')):
            in_missing_section = True
        if any(k in low for k in ('chưa tạo được', 'không tạo được', 'bị kẹt', 'vướng bộ lọc', 'bị từ chối')):
            for sid in extract_scene_ids_from_segment(line, vset):
                if sid not in failed:
                    failed.append(sid)
        elif any(k in low for k in ('chưa làm', 'đủ 6 video', 'giới hạn 6 video')) and 'SCENE_' in line.upper():
            for sid in extract_scene_ids_from_segment(line, vset):
                if sid not in deferred:
                    deferred.append(sid)
        elif not in_missing_section and 'SCENE_' in line.upper():
            for sid in extract_scene_ids_from_segment(line, vset):
                if sid not in delivered:
                    delivered.append(sid)
        if any(k in low for k in ('nếu bạn muốn', 'hướng khác', 'không dùng', 'để vẫn giữ', 'tránh dùng', 'thay vì')):
            suggestions.append(line)
    return {
        'delivered_ids': delivered,
        'failed_ids': failed,
        'deferred_ids': deferred,
        'suggestion': ' '.join(suggestions).strip(),
    }

def get_missing_scenes(p: Project) -> list[Scene]:
    if not p.board or not p.board.scenes:
        return []
    return [s for s in p.board.scenes if not Path(p.clips.get(s.id, '__missing__')).is_file()]

def get_next_muse_batch(p: Project, batch_size: int = MAX_MUSE_BATCH_SIZE) -> list[Scene]:
    missing = get_missing_scenes(p)
    return missing[:max(1, min(batch_size, MAX_MUSE_BATCH_SIZE))]

def compile_muse_batch_6_prompt(p: Project, scenes: list[Scene], batch_num: int = 1) -> str:
    """Build a 6-scene batch prompt for Muse with strict 4-Pillar Photography, Muted Color Palette, Lip-Sync Lock & Same-Location Camera Angle Lock."""
    batch = scenes[:MAX_MUSE_BATCH_SIZE]
    ids_str = ', '.join(s.id for s in batch)
    total_scenes = len(p.board.scenes) if (p.board and p.board.scenes) else len(batch)
    total_batches = max(1, (total_scenes + MAX_MUSE_BATCH_SIZE - 1) // MAX_MUSE_BATCH_SIZE)
    if is_3d_fable_style(p.style):
        header = (
            f'THỰC HIỆN NGAY ĐỢT {batch_num}/{total_batches} VIDEO HOẠT HÌNH 3D PIXAR NÀY GỒM ĐÚNG {len(batch)} CẢNH ({ids_str}) — TỐI ĐA 6 VIDEO TRONG 1 LẦN NHẮN ĐỂ GIAO ĐỦ 100% FILE MP4:\n'
            f'- Khung hình: {p.ratio} | Phong cách: {p.style}.\n'
            f'- BẮT BUỘC tạo đủ cả {len(batch)} file video MP4 ({ids_str}) theo đúng thứ tự, giữ nguyên 100% thiết kế nhân vật 3D dễ thương (Consistent Character), Voiceover/Dialogue từ 0s–9s và Match Cut ở giây thứ 10:\n'
        )
    else:
        header = (
            f'THỰC HIỆN NGAY ĐỢT {batch_num}/{total_batches} VIDEO ĐIỆN ẢNH ĐỜI THỰC VIỆT NAM NÀY GỒM ĐÚNG {len(batch)} CẢNH ({ids_str}) — TỐI ĐA 6 VIDEO TRONG 1 LẦN NHẮN ĐỂ GIAO ĐỦ 100% FILE MP4:\n'
            f'- Khung hình: {p.ratio} | Phong cách: {p.style}.\n'
            f'- BẮT BUỘC tạo đủ cả {len(batch)} file video MP4 ({ids_str}) theo đúng 5 QUY TẮC VÀNG sau:\n'
            f'  1. TÔNG MÀU & THÔNG SỐ MÁY ẢNH (THEO ẢNH MẪU): Medium shot, eye-level angle, shot on 35mm lens, f/2.8 aperture, shallow depth of field, cinematic film still. Natural soft light coming from doorway, dramatic shadows, muted color palette, desaturated tones, gritty realism (tông màu trầm lạnh, tường vôi bong tróc rêu mốc chân thực; TUYỆT ĐỐI KHÔNG làm màu vàng rực hay sepia).\n'
            f'  2. KHÓA CỨNG NHÂN VẬT & TRANG PHỤC 100% (--cref & --sref): Giữ nguyên khuôn mặt, độ tuổi, kiểu tóc và quần áo của từng nhân vật xuyên suốt từ cảnh đầu đến cảnh cuối.\n'
            f'  3. CHỐNG LỖI TIẾNG NÓI KHÔNG KHỚP HÌNH (STRICT LIP-SYNC): Từ 0.0s–9.0s, tại mỗi thời điểm CHỈ ĐÚNG NGƯỜI ĐANG CÓ THOẠI MỚI MỞ MIỆNG NÓI khớp từng âm tiết tiếng Việt; người đang nghe BẮT BUỘC KHÉP KÍN MIỆNG lắng nghe (không nhép môi theo). Khi dứt câu ở giây 9.0s phải khép miệng tự nhiên.\n'
            f'  4. KHÓA GÓC QUAY CŨ KHI CÙNG BỐI CẢNH (CẤM ĐỔI GÓC QUAY Ở CẢNH VAY TIỀN / ĐỐI THOẠI TIẾP NỐI): Khi 2 cảnh liên tiếp ở CÙNG BỐI CẢNH (ví dụ cảnh ông bố ngồi bàn gỗ vay tiền bà Tám từ câu trước sang câu sau, hoặc bố con đang nói chuyện tại giường tre), BẮT BUỘC GIỮ NGUYÊN 100% GÓC QUAY CŨ và vị trí ngồi/đứng của nhân vật! TUYỆT ĐỐI KHÔNG tự ý đổi góc máy và KHÔNG tự ý đứng dậy bỏ đi khi chưa hết cuộc trò chuyện!\n'
            f'  5. CHỈ BƯỚC ĐI KHI ĐỔI BỐI CẢNH & CẤM FADE ĐEN: Chỉ khi cảnh tiếp theo đổi sang địa điểm mới thì ở giây cuối (9.0s–10.0s) nhân vật mới đứng dậy bước đi. Giữ sáng khung hình tự nhiên (NO Fade to black, NO tiếng chuýt):\n'
        )
    body = compile_muse_recovery_prompt(p, batch)
    return header + '\n' + body


def get_all_muse_batches_of_6(p: Project) -> list[list[Scene]]:
    """Split all scenes in project.board into sequential batches of 6 scenes (1..6, 7..12, 13..18, ...) until the end."""
    if not p.board or not p.board.scenes:
        return []
    scenes = list(p.board.scenes)
    return [scenes[i:i + MAX_MUSE_BATCH_SIZE] for i in range(0, len(scenes), MAX_MUSE_BATCH_SIZE)]
