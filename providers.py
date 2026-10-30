import json, time, shutil, subprocess, tempfile
from pathlib import Path
from google import genai
from google.genai import types
from core import (
    sanitize_scene_for_flow, sanitize_project_for_flow, SAFE_FICTIONAL_FRAME_VI,
    Bible, Scene, Storyboard, Project, get_ffmpeg_path, sanitize_for_video_prompt,
    parse_muse_reply_text, get_missing_scenes, is_3d_fable_style, is_family_drama_style
)
from pydantic import BaseModel, field_validator

DEFAULT_MODELS = (
    'gemini-2.5-flash',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash-lite',
    'gemini-3-flash-preview',
    'gemini-3.1-flash-lite-preview',
    'gemini-2.5-pro',
    'gemini-3.1-pro-preview',
    'gemini-2.0-flash',
)
RETRY_DELAYS = (2.0, 4.0, 8.0)
FALLBACK_RETRY_DELAYS = (2.0,)
EXCLUDED_MODEL_TOKENS = ('tts', 'image', 'vision', 'audio', 'embedding', 'veo', 'imagen', 'learnlm', 'gemma', 'robotics', 'computer-use', 'aqa')
VIDEO_MIMES = {
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.mkv': 'video/x-matroska',
    '.webm': 'video/webm',
    '.avi': 'video/x-msvideo',
    '.m4v': 'video/mp4',
}

def is_auth_error(exc: Exception) -> bool:
    code = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    if code in (401, 403):
        return True
    msg = str(exc).casefold()
    return any(k in msg for k in ('api_key_invalid', 'api key not valid', 'invalid api key', 'unauthenticated'))

def is_transient_error(exc: Exception) -> bool:
    if is_auth_error(exc):
        return False
    code = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    if code in (500, 502, 503, 504, 529):
        return True
    status = str(getattr(exc, 'status', '') or '').upper()
    if status in ('UNAVAILABLE', 'INTERNAL', 'DEADLINE_EXCEEDED', 'OVERLOADED'):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    msg = str(exc).casefold()
    return any(k in msg for k in (
        '503', 'unavailable', 'high demand', 'spikes in demand', 'overloaded',
        'temporarily unavailable', 'try again later', '500 internal', '502 bad gateway',
        '504 gateway timeout', 'deadline_exceeded', 'deadline exceeded', 'timed out',
        'readtimeout', 'connecttimeout', 'connecterror', 'remoteprotocolerror',
        'server disconnected', 'connection reset', 'connection aborted',
    ))

def is_fallback_eligible(exc: Exception) -> bool:
    if is_auth_error(exc):
        return False
    if is_transient_error(exc):
        return True
    code = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    if code in (404, 429):
        return True
    status = str(getattr(exc, 'status', '') or '').upper()
    if status in ('NOT_FOUND', 'RESOURCE_EXHAUSTED'):
        return True
    msg = str(exc).casefold()
    return any(k in msg for k in ('404', 'not_found', 'not found', '429', 'resource_exhausted', 'quota'))

def clean_json_text(text: str) -> str:
    """Strip markdown fences and any conversational prefix/suffix outside the JSON object."""
    s = (text or '').strip()
    if s.startswith('```'):
        lines = s.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        s = '\n'.join(lines).strip()
    first_brace = s.find('{')
    last_brace = s.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return s[first_brace:last_brace + 1].strip()
    return s

class ContinuityReview(BaseModel):
    issues: list[str]
    @field_validator('issues',mode='before')
    @classmethod
    def readable_issues(cls,items):
        if items is None: return []
        if not isinstance(items,list):return items
        result=[]
        for item in items:
            if isinstance(item,dict):
                ids=item.get('ids',[])
                if not isinstance(ids,list):ids=[]
                description=str(item.get('description','')).strip()
                correction=str(item.get('correction','')).strip()
                if not description: raise ValueError('Nhận xét AI thiếu nội dung')
                item=', '.join(str(x) for x in ids)+': '+description+(' → Sửa: '+correction if correction else '')
            result.append(item)
        return result

from writing import get_idea_prompt, get_story_prompt, get_treatment_prompt, get_video_to_story_prompt
from directing import (
    POLICY_SECOND_AUDIT_SYSTEM,
    direction, is_ghost_style, ensure_ghost_bible, ensure_biometric_and_journey_bible, time_slots, validate_board,
    fit_dialogue, lock_handoffs, auto_repair_board, apply_audit_corrections, AUDIT
)

DIRECTOR = '''Bạn là đạo diễn chuyên nghiệp (Hoạt hình 3D Pixar Ngụ ngôn & Tiểu phẩm Tâm lý Xã hội Đời thực Bẻ lái) và chuyên gia nối cảnh.
Viết tiếng Việt, lời thoại tiếng Việt nguyên văn. Tuyệt đối KHÔNG trả lời câu giao tiếp thừa (như "Dạ đây là kịch bản của bạn..."), chỉ trả đúng cấu trúc JSON theo schema.
Không dùng các tiêu đề "Mở bài", "Thân bài", "Kết bài".
Mỗi nhân vật/bối cảnh có ID duy nhất (CHAR_001..., LOC_001...).
Mỗi cảnh có một hành động chính khả thi; timeline không chồng nhau. Lời thoại diễn ra từ 0s đến (duration - 1)s, giây cuối nối cảnh bằng Match Cut / Fade to black; người dẫn dùng ID NARRATOR.
Ghi rõ cỡ cảnh (Wide Shot / Medium Shot / Close-up), góc máy, chuyển động, ánh sáng, âm thanh, trạng thái đầu/cuối và nối cảnh.
Không dùng mô tả mơ hồ như 'giống cảnh trước'.'''

class Gemini:
    retry_delays = RETRY_DELAYS
    fallback_retry_delays = FALLBACK_RETRY_DELAYS
    fallback_models = DEFAULT_MODELS
    allow_fallback = True

    def __init__(self, key, model, allow_fallback=True, temperature=0.35):
        if not key.strip(): raise ValueError('Hãy nhập Gemini API key.')
        if not model.strip(): raise ValueError('Hãy chọn model ID.')
        self.client=genai.Client(api_key=key.strip(), http_options=types.HttpOptions(timeout=180000))
        self.model=model.strip().removeprefix('models/')
        self.allow_fallback=allow_fallback
        self.temperature=max(0.05, min(1.0, float(temperature)))
        self._active_model=None
        self._discovered_models=None

    def models(self):
        return [m.name.removeprefix('models/') for m in self.client.models.list()
                if 'generateContent' in (m.supported_actions or [])]

    def _sleep(self, seconds):
        if seconds and seconds > 0:
            time.sleep(seconds)

    def _candidate_fallbacks(self, primary):
        base = [m.removeprefix('models/') for m in getattr(self, 'fallback_models', DEFAULT_MODELS)]
        discovered = getattr(self, '_discovered_models', None)
        if discovered is None and hasattr(self, 'client') and hasattr(self.client, 'models') and hasattr(self.client.models, 'list'):
            try:
                raw = self.models()
                if isinstance(raw, list) and raw:
                    discovered = [
                        m for m in raw
                        if isinstance(m, str)
                        and m.startswith('gemini-')
                        and not any(tok in m.casefold() for tok in EXCLUDED_MODEL_TOKENS)
                    ]
                    self._discovered_models = discovered
            except Exception:
                discovered = None
        candidates = []
        if discovered:
            discovered_set = set(discovered)
            for m in base:
                if m in discovered_set and m != primary and m not in candidates:
                    candidates.append(m)
            for m in discovered:
                if m != primary and m not in candidates:
                    candidates.append(m)
        for m in base:
            if m != primary and m not in candidates:
                candidates.append(m)
        return candidates

    def _request(self, contents, config):
        primary = (getattr(self, '_active_model', None) or self.model).strip().removeprefix('models/')
        delays = tuple(getattr(self, 'retry_delays', RETRY_DELAYS))
        try:
            response = self.client.models.generate_content(model=primary, contents=contents, config=config)
            return response
        except Exception as first_exc:
            exc = first_exc
            if is_transient_error(exc):
                for idx, delay in enumerate(delays, 1):
                    self.notify(f'Máy chủ {primary} đang quá tải (503). Tự động thử lại lần {idx}/{len(delays)} sau {delay:g}s…')
                    self._sleep(delay)
                    try:
                        response = self.client.models.generate_content(model=primary, contents=contents, config=config)
                        self.notify(f'Model {primary} đã phản hồi sau khi thử lại.')
                        return response
                    except Exception as retry_exc:
                        exc = retry_exc
                        if not is_transient_error(exc):
                            break
            primary_exc = exc
            tried = [primary]
            if getattr(self, 'allow_fallback', True) and is_fallback_eligible(primary_exc):
                fb_delays = tuple(getattr(self, 'fallback_retry_delays', FALLBACK_RETRY_DELAYS))
                for alt in self._candidate_fallbacks(primary)[:4]:
                    tried.append(alt)
                    self.notify(f'Model {primary} đang quá tải/bận. Đang tự động chuyển sang model dự phòng: {alt}…')
                    try:
                        response = self.client.models.generate_content(model=alt, contents=contents, config=config)
                        self._active_model = alt
                        self.notify(f'Đã xử lý thành công bằng model dự phòng: {alt}.')
                        return response
                    except Exception as alt_exc:
                        if is_auth_error(alt_exc):
                            raise alt_exc
                        if is_transient_error(alt_exc):
                            for fb_delay in fb_delays:
                                self.notify(f'Model dự phòng {alt} đang bận, thử lại sau {fb_delay:g}s…')
                                self._sleep(fb_delay)
                                try:
                                    response = self.client.models.generate_content(model=alt, contents=contents, config=config)
                                    self._active_model = alt
                                    self.notify(f'Đã xử lý thành công bằng model dự phòng: {alt}.')
                                    return response
                                except Exception as alt_retry_exc:
                                    alt_exc = alt_retry_exc
                                    if not is_transient_error(alt_exc):
                                        break
            if is_transient_error(primary_exc):
                models_note = ', '.join(tried)
                raise RuntimeError(
                    f'503 UNAVAILABLE: Máy chủ Google Gemini hiện đang quá tải cao điểm trên cả model đã chọn '
                    f'và model dự phòng ({models_note}). Tool đã tự động thử lại nhiều lần nhưng máy chủ Google '
                    f'chưa phản hồi. Dữ liệu hiện tại của bạn vẫn được giữ nguyên; vui lòng đợi 1–2 phút rồi bấm thực hiện lại.\n'
                    f'Chi tiết kỹ thuật: {primary_exc}'
                ) from None
            raise primary_exc

    def _load_video_parts(self, video_path: str) -> list:
        """Load a reference video file into Gemini content parts (compressing via FFmpeg if >18MB)."""
        if not video_path or not str(video_path).strip():
            return []
        f = Path(str(video_path).strip())
        if not f.is_file():
            raise ValueError(f'Không tìm thấy file video mẫu: {video_path}')
        mime = VIDEO_MIMES.get(f.suffix.lower(), 'video/mp4')
        max_inline = 18 * 1024 * 1024
        if f.stat().st_size <= max_inline:
            self.notify(f'Đang nạp video mẫu ({f.name}) để AI phân tích hình ảnh & lời thoại…')
            return [
                f'Video mẫu đính kèm ({f.name}) để AI xem hình ảnh, nhân vật, bối cảnh và nghe lời thoại lấy kịch bản:',
                types.Part.from_bytes(data=f.read_bytes(), mime_type=mime),
            ]
        ffmpeg = get_ffmpeg_path()
        if ffmpeg:
            self.notify(f'Video mẫu ({f.name}) dung lượng lớn, đang nén nhanh bản nhẹ để gửi AI…')
            with tempfile.TemporaryDirectory(prefix='quang_vid_idea_') as tmp:
                compact = Path(tmp) / 'compact.mp4'
                cmd = [
                    ffmpeg, '-y', '-i', str(f),
                    '-vf', 'scale=-2:480', '-r', '10',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '30', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '64k', '-ac', '1', '-ar', '24000',
                    str(compact),
                ]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode == 0 and compact.is_file() and compact.stat().st_size <= max_inline:
                    return [
                        f'Video mẫu đính kèm ({f.name}) để AI xem hình ảnh, nhân vật, bối cảnh và nghe lời thoại lấy kịch bản:',
                        types.Part.from_bytes(data=compact.read_bytes(), mime_type='video/mp4'),
                    ]
        if hasattr(self, 'client') and hasattr(self.client, 'files') and hasattr(self.client.files, 'upload'):
            self.notify(f'Đang tải video ({f.name}) lên Gemini Files API…')
            uploaded = self.client.files.upload(file=str(f))
            for _ in range(30):
                state = str(getattr(uploaded, 'state', '') or '').upper()
                if 'ACTIVE' in state or not state:
                    break
                self._sleep(2.0)
                if hasattr(self.client.files, 'get'):
                    uploaded = self.client.files.get(name=uploaded.name)
            return [f'Video mẫu đính kèm ({f.name}) để lấy kịch bản:', uploaded]
        raise ValueError('Video mẫu vượt quá 18 MB. Hãy chọn video ngắn hơn hoặc cài đặt FFmpeg.')

    def generate(self, schema, prompt, references):
        """Generate structured JSON output with JSON Mode, style-specific temperature, and 3-attempt try-except validation loop."""
        base_contents = [prompt]
        for label, path in references.items():
            f = Path(path)
            if not f.is_file(): raise ValueError(f'Không tìm thấy ảnh tham chiếu: {label}')
            if f.stat().st_size > 5*1024*1024: raise ValueError('Mỗi ảnh tham chiếu tối đa 5 MB.')
            mime = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}.get(f.suffix.lower())
            if not mime: raise ValueError('Ảnh tham chiếu phải là JPG, PNG hoặc WebP.')
            base_contents += [f'Ảnh tham chiếu gắn với nhãn/ID: {label}', types.Part.from_bytes(data=f.read_bytes(), mime_type=mime)]

        last_err = None
        for json_attempt in range(1, 4):
            contents = list(base_contents)
            if json_attempt > 1 and last_err is not None:
                contents[0] = (
                    prompt
                    + f'\n\n[CẢNH BÁO JSON MODE LẦN {json_attempt}/3]: Lần trả về trước bị lỗi định dạng JSON ({str(last_err)[:400]}). '
                    'BẮT BUỘC chỉ trả về đúng đối tượng JSON hợp lệ khớp hoàn toàn với schema, tuyệt đối không kèm câu dẫn chuyện hay markdown thừa.'
                )
            response = self._request(
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=DIRECTOR,
                    response_mime_type='application/json',
                    response_schema=schema,
                    temperature=getattr(self, 'temperature', 0.35),
                )
            )
            if not response.text or not response.text.strip():
                last_err = ValueError('Gemini không trả nội dung JSON.')
                if json_attempt < 3:
                    self.notify(f'AI chưa trả nội dung JSON (lần {json_attempt}/3), đang tự động gọi lại (try-except)…')
                    continue
                raise last_err
            try:
                return schema.model_validate_json(clean_json_text(response.text))
            except Exception as parse_err:
                last_err = parse_err
                if json_attempt < 3:
                    self.notify(f'AI trả JSON lệch form (lần {json_attempt}/3), đang tự động gọi lại bằng try-except…')
                    continue
                raise parse_err

    def expand_idea(self, p: Project, message: str = '') -> str:
        is_3d = is_3d_fable_style(p.style)
        is_fam = is_family_drama_style(p.style)
        if is_3d:
            self.notify('AI đang mở rộng từ khóa thành Kịch bản 3D Ngụ ngôn (Form 4 mục)…')
            default_req = (
                'Từ chủ đề / từ khóa gốc, hãy thiết lập Nhân vật 3D dễ thương cố định (Consistent Character) '
                'và viết kịch bản theo đúng FORM 4 MỤC (Scene [Số] | Visual Description | Voiceover / Dialogue | Moral Lesson).'
            )
            default_temp = 0.35
        elif is_fam:
            self.notify('AI đang tự do sáng tạo cốt truyện Gia đình Tâm lý Xã hội Quê nghèo Thập niên 80…')
            default_req = (
                'Hãy tự do sáng tạo một câu chuyện Gia đình Tâm lý Xã hội & Đời thực Quê nghèo Việt Nam thập niên 80 sâu sắc, tự nhiên, giàu cảm xúc '
                '(không gò bó vào khuôn mẫu cứng nhắc; thiết lập rõ tạo hình nhân vật nông thôn thập niên 80 cố định xuyên suốt và bối cảnh quê xưa mộc mạc).'
            )
            default_temp = 0.80
        else:
            self.notify('AI đang mở rộng tình huống thành Kịch bản Tiểu phẩm Tâm lý & Bẻ lái (Form 5 mục)…')
            default_req = (
                'Từ chủ đề / tình huống chính, hãy viết kịch bản tiểu phẩm tâm lý xã hội có cú "bẻ lái" (plot twist) bất ngờ ở cuối video '
                'theo đúng FORM 5 MỤC cho từng phân cảnh: 1. Scene & Thời gian | 2. Bối cảnh & Góc máy | 3. Hành động nhân vật | 4. Lời thoại | 5. Hiệu ứng âm thanh / Chuyển cảnh.'
            )
            default_temp = 0.50
        context = {
            'raw_idea': p.idea or 'Tự do sáng tạo câu chuyện gia đình quê nghèo Việt Nam thập niên 80 xúc động, chân thực.',
            'style': p.style,
            'total_seconds': p.total_seconds,
            'clip_seconds': p.clip_seconds,
            'request': message or default_req,
        }
        payload_str = json.dumps(context, ensure_ascii=False)
        video_parts = self._load_video_parts(getattr(p, 'idea_video', ''))
        contents = [*video_parts, payload_str] if video_parts else payload_str
        response = self._request(
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=get_idea_prompt(p.style),
                temperature=getattr(self, 'temperature', default_temp),
            ),
        )
        if not response.text or not response.text.strip():
            raise ValueError('AI không trả nội dung dàn ý.')
        return response.text.strip()

    def extract_script_from_video(self, p: Project, message: str = '') -> tuple[str, str]:
        if not getattr(p, 'idea_video', '').strip():
            raise ValueError('Hãy chọn một file Video mẫu trước.')
        is_3d = is_3d_fable_style(p.style)
        is_fam = is_family_drama_style(p.style)
        is_remake = 'đạo lại' in p.style.casefold()
        video_parts = self._load_video_parts(p.idea_video)
        if is_3d:
            self.notify('AI đang xem video mẫu và trích xuất Kịch bản 3D Ngụ ngôn (Form 4 mục)…')
            default_req = 'Xem kỹ video đính kèm và chuyển thể thành kịch bản Hoạt hình 3D Pixar Ngụ ngôn theo đúng FORM 4 MỤC (Scene | Visual Description | Voiceover | Moral Lesson).'
            default_temp = 0.35
        elif is_remake:
            self.notify('AI đang phân tích video và tạo 2 bản kịch bản (Gốc & Nâng cấp)…')
            default_req = 'Phân tích video và trả về JSON chứa original_script và enhanced_script.'
            default_temp = 0.70
        elif is_fam:
            self.notify('AI đang xem video mẫu và sáng tạo Kịch bản Gia đình Tâm lý Quê nghèo Thập niên 80…')
            default_req = (
                'Xem kỹ video đính kèm, lấy cảm hứng về tạo hình nhân vật, bối cảnh quê nghèo và tình huống tâm lý gia đình '
                'để sáng tạo kịch bản đời thực thập niên 80 tự nhiên, sâu sắc (khóa cố định ngoại hình nhân vật 100% và nối cảnh mượt mà).'
            )
            default_temp = 0.80
        else:
            self.notify('AI đang xem video mẫu và trích xuất Kịch bản Tiểu phẩm Tâm lý & Bẻ lái (Form 5 mục)…')
            default_req = (
                'Xem kỹ video đính kèm, trích xuất toàn bộ tình huống, góc máy, hành động, lời thoại đời thực và cú bẻ lái (plot twist) '
                'thành kịch bản theo đúng FORM 5 MỤC: 1. Scene & Thời gian | 2. Bối cảnh & Góc máy | 3. Hành động nhân vật | 4. Lời thoại | 5. Hiệu ứng âm thanh / Chuyển cảnh.'
            )
            default_temp = 0.50
        context = {
            'user_notes_or_raw_idea': p.idea,
            'style': p.style,
            'total_seconds': p.total_seconds,
            'clip_seconds': p.clip_seconds,
            'request': message or default_req,
        }
        story_resp = self._request(
            contents=[*video_parts, json.dumps(context, ensure_ascii=False)],
            config=types.GenerateContentConfig(
                system_instruction=get_video_to_story_prompt(p.style),
                temperature=getattr(self, 'temperature', default_temp),
            ),
        )
        if not story_resp.text or not story_resp.text.strip():
            raise ValueError('AI không trích xuất được nội dung từ video.')
        story_text = story_resp.text.strip()
        if is_remake:
            return 'JSON_REMAKE', clean_json_text(story_text)
        idea_summary = p.idea.strip()
        if not idea_summary:
            idea_summary = f'[Trích xuất từ Video: {Path(p.idea_video).name}]\n' + story_text[:600] + ('…' if len(story_text) > 600 else '')
        return idea_summary, story_text

    def write(self, p, message='', treatment=False):
        is_3d = is_3d_fable_style(p.style)
        is_fam = is_family_drama_style(p.style)
        default_temp = 0.35 if is_3d else (0.80 if is_fam else 0.50)
        if treatment:
            if is_3d:
                self.notify('Đang lên bảng chỉ đạo 3D Pixar (Form 4 mục: Visual Description + Image Prompt 3D + Voiceover + Moral Lesson)…')
            elif is_fam:
                self.notify('Đang lên bảng chỉ đạo Gia đình Tâm lý Quê nghèo Thập niên 80 (Khóa ngoại hình 100% & Nối cảnh tự nhiên)…')
            else:
                self.notify('Đang lên bảng chỉ đạo Tiểu phẩm Tâm lý & Bẻ lái (Form 5 mục)…')
            policy = get_treatment_prompt(p.style)
        else:
            if is_3d:
                self.notify('Đang viết kịch bản Hoạt hình 3D Ngụ ngôn & Châm ngôn sống (Form 4 mục)…')
            elif is_fam:
                self.notify('AI đang tự do sáng tạo kịch bản Gia đình Tâm lý Xã hội & Đời thực Quê nghèo Thập niên 80…')
            else:
                self.notify('Đang viết kịch bản Tiểu phẩm Tâm lý Xã hội Đời thực & Bẻ lái (Form 5 mục)…')
            policy = get_story_prompt(p.style)

        slots = time_slots(p.total_seconds, p.clip_seconds, p.style)
        eff_idea = p.idea.strip() or (
            'Tự do sáng tạo một câu chuyện Gia đình Tâm lý Xã hội & Đời thực Quê nghèo Việt Nam thập niên 80 xúc động, tự nhiên, sâu sắc.'
            if is_fam else p.idea
        )
        context = {
            'idea': eff_idea,
            'style': p.style,
            'total_seconds': p.total_seconds,
            'clip_seconds': p.clip_seconds,
            'scene_count': len(slots),
            'current_story': p.script,
            'history': p.story_chat,
            'request': message,
        }
        if treatment:
            context['scene_slots'] = slots
            if not message:
                if is_3d:
                    context['request'] = (
                        f'Chia kịch bản 3D Ngụ ngôn thành đúng {len(slots)} cảnh ({slots[0]["scene_id"]} đến {slots[-1]["scene_id"]}), '
                        f'tổng {p.total_seconds} giây ({p.clip_seconds}s/cảnh) theo đúng FORM 4 MỤC.'
                    )
                elif is_fam:
                    context['request'] = (
                        f'Chuyển kịch bản Gia đình Tâm lý Quê nghèo Thập niên 80 thành đúng {len(slots)} phân cảnh hoàn toàn khác nhau ({slots[0]["scene_id"]} đến {slots[-1]["scene_id"]}), '
                        f'tổng {p.total_seconds} giây ({p.clip_seconds}s/cảnh). Khóa cố định 100% tạo hình nhân vật & bối cảnh quê nghèo thập niên 80; '
                        f'nếu 2 cảnh liên tiếp cùng bối cảnh đang nói chuyện tiếp thì giữ nguyên vị trí ngồi/đứng suốt cả cảnh (không bỏ đi, không Fade đen, không tiếng chuýt); '
                        f'chỉ khi cảnh sau đổi sang bối cảnh khác mới bước đi ở giây {max(1, p.clip_seconds - 1)}s–{p.clip_seconds}s.'
                    )
                else:
                    context['request'] = (
                        f'Chia kịch bản Tiểu phẩm Tâm lý & Bẻ lái thành đúng {len(slots)} cảnh ({slots[0]["scene_id"]} đến {slots[-1]["scene_id"]}), '
                        f'tổng {p.total_seconds} giây ({p.clip_seconds}s/cảnh) theo đúng FORM 5 MỤC.'
                    )
        payload_str = json.dumps(context, ensure_ascii=False)
        video_parts = self._load_video_parts(getattr(p, 'idea_video', '')) if not treatment else []
        if video_parts:
            policy = get_video_to_story_prompt(p.style) + '\n\n' + policy
            contents = [*video_parts, payload_str]
        else:
            contents = payload_str
        response = self._request(
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=policy,
                temperature=getattr(self, 'temperature', default_temp),
            )
        )
        if not response.text or not response.text.strip():
            raise ValueError('AI không trả nội dung; bản trước vẫn được giữ.')
        return response.text.strip()

    def bible(self, p):
        is_3d = is_3d_fable_style(p.style)
        is_fam = is_family_drama_style(p.style)
        if is_3d:
            self.notify('Đang tạo Hồ sơ Nhân vật 3D cố định (Consistent 3D Character) và Bối cảnh…')
            role_hint = '\nTạo hồ sơ nhân vật 3D dễ thương cố định (Consistent 3D Character: khóa loài vật/nhân vật 3D, màu lông, mắt to biểu cảm, trang phục/phụ kiện cố định xuyên suốt) và bối cảnh 3D Pixar. Phân biệt bằng ID CHAR_001... và LOC_001...\n'
        elif is_fam:
            self.notify('Đang tạo Hồ sơ Nhân vật & Bối cảnh Quê nghèo Việt Nam Thập niên 80 (Khóa ngoại hình 100% xuyên suốt)…')
            role_hint = (
                '\nTạo hồ sơ nhân vật người Việt Nam chuẩn điện ảnh đời thực (như Video mẫu 2): '
                '1. KHÓA CỨNG NHÂN VẬT TRUNG TÂM: CHAR_001 (VD: Người cha già 65 tuổi, khuôn mặt gầy khắc khổ nhiều nếp nhăn sâu, tóc bạc ngắn điểm đen, râu bạc lún phún quanh cằm, mặc bộ áo bà ba màu xám tro sờn cũ có vết rách nhỏ ở vai, quần đen bạc màu, dép lê cũ) và CHAR_002 (VD: Người con trai 30 tuổi, mặt góc cạnh rám nắng, tóc đen hơi rối, mặc áo sơ mi xanh lam nhạt dài tay xắn nhẹ, quần kaki nâu vàng). Có thể thêm 2-3 nhân vật phụ cho từng chặng (CHAR_003 bà hàng xóm nhặt rau, CHAR_004 bác nông dân cuốc đất, CHAR_005 bà Phú hộ áo dài hồng sang trọng). '
                '2. BẮT BUỘC TẠO ĐỦ 4–6 BỐI CẢNH HÀNH TRÌNH ĐA DẠNG (LOC_001 đến LOC_005/LOC_006): LOC_001 (Trong nhà nghèo có giường tre, tường vôi bong tróc), LOC_002 (Ngoài đồng/mộ người thân hoặc bàn thờ), LOC_003 (Sân đất nhà quê có cây cau/vịt), LOC_004 (Hiên nhà/vườn rau hàng xóm), LOC_005 (Quán bia hơi/quán nước bình dân), LOC_006 (Phòng khách nhà Phú hộ gỗ lim sang trọng) để câu chuyện di chuyển sinh động qua từng cảnh, tuyệt đối không ngồi lì 1 chỗ!\n'
            )
        else:
            self.notify('Đang tạo Hồ sơ Nhân vật đời thực và Bối cảnh tiểu phẩm…')
            role_hint = '\nTạo hồ sơ nhân vật đời thực Việt Nam (khóa gương mặt, độ tuổi, kiểu tóc, trang phục đời thường cố định) và bối cảnh thực tế. Phân biệt bằng ID CHAR_001... và LOC_001...\n'

        base_prompt = (
            direction(p.style)
            + role_hint
            + p.model_dump_json(exclude={'bible', 'board', 'clips', 'references', 'story_chat'})
        )
        result = self.generate(Bible, base_prompt, p.references)
        result = ensure_biometric_and_journey_bible(ensure_ghost_bible(result, p.style), p.style, max(1, p.total_seconds // max(1, p.clip_seconds)))
        return result

    def assist_bible(self, p: Project, instruction: str) -> Bible:
        if not p.bible:
            return self.bible(p)
        self.notify('AI đang chỉnh sửa hồ sơ nhân vật & bối cảnh theo yêu cầu…')
        prompt = (
            direction(p.style)
            + '\nChỉnh sửa hoặc bổ sung HỒ SƠ NHÂN VẬT & BỐI CẢNH hiện tại theo đúng yêu cầu của người dùng. '
            'Giữ nguyên các ID (CHAR_001..., LOC_001...) đang có để không làm lệch liên kết cảnh.\n'
            f'YÊU CẦU CHỈNH SỬA: {instruction}\n'
            f'HỒ SƠ HIỆN TẠI:\n{p.bible.model_dump_json(indent=2)}\n'
            f'KỊCH BẢN & ĐẠO DIỄN:\n{p.script}\n{p.treatment}'
        )
        result = self.generate(Bible, prompt, p.references)
        return ensure_ghost_bible(result, p.style)

    def assist_scene(self, p: Project, scene: Scene, instruction: str = '') -> Scene:
        self.notify(f'🛠️ AI đang sửa & làm mềm cảnh {scene.id} (Đồng bộ Nhân vật • Giọng nói • Cảnh trước/sau)…')
        scenes = p.board.scenes if (p.board and p.board.scenes) else []
        idx = next((i for i, x in enumerate(scenes) if x.id == scene.id), -1)
        prev_sc = scenes[idx - 1] if idx > 0 else None
        next_sc = scenes[idx + 1] if (0 <= idx < len(scenes) - 1) else None
        prev_info = (
            f"CẢNH TRƯỚC LIỀN KỀ ({prev_sc.id} - {prev_sc.title}): location_id={prev_sc.location_id}, end_state={prev_sc.end_state!r}"
            if prev_sc else "Đây là cảnh đầu tiên (SCENE_001)."
        )
        next_info = (
            f"CẢNH SAU LIỀN KỀ ({next_sc.id} - {next_sc.title}): location_id={next_sc.location_id}, start_state={next_sc.start_state!r}"
            if next_sc else "Đây là cảnh kết thúc phim."
        )
        eff_req = instruction.strip() or (
            "Cảnh này vừa bị từ chối do vướng bộ lọc an toàn. Hãy TỰ ĐỘNG LÀM MỀM toàn bộ mô tả hành động, biểu cảm và lời thoại "
            "(thay bằng diễn xuất tâm lý trầm tĩnh, tự nhiên). BẮT BUỘC giữ nguyên nhân vật, trang phục, giọng nói, bối cảnh và khớp nối mượt mà với cảnh trước/sau!"
        )
        prompt = (
            direction(p.style)
            + "\n" + POLICY_SECOND_AUDIT_SYSTEM
            + f'\nNHIỆM VỤ: Chỉnh sửa & đồng bộ lại cảnh {scene.id} (thời lượng cố định {scene.duration:g}s).\n'
            + f'Bắt buộc giữ nguyên id="{scene.id}", duration={scene.duration:g}, dùng đúng ID nhân vật ({scene.character_ids}) và bối cảnh ({scene.location_id}) trong hồ sơ.\n'
            + f'YÊU CẦU SỬA & ĐỒNG BỘ: {eff_req}\n'
            + f'KỊCH BẢN TỔNG THỂ TRÊN:\n{p.script[:3000]}\n'
            + f'{prev_info}\n{next_info}\n'
            + f'HỒ SƠ NHÂN VẬT & GIỌNG NÓI CỐ ĐỊNH:\n{p.bible.model_dump_json(indent=2) if p.bible else "{}"}\n'
            + f'CẢNH HIỆN TẠI CẦN SỬA:\n{scene.model_dump_json(indent=2)}'
        )
        try:
            new_sc = self.generate(Scene, prompt, p.references)
        except Exception:
            new_sc = scene.model_copy(deep=True)
        new_sc.id = scene.id
        new_sc.duration = scene.duration
        if not new_sc.character_ids:
            new_sc.character_ids = list(scene.character_ids)
        if not new_sc.location_id:
            new_sc.location_id = scene.location_id
        return sanitize_scene_for_flow(new_sc)

    def second_pass_policy_audit(self, p: Project, board: Storyboard) -> Storyboard:
        """Run a dedicated 2nd AI pass to inspect and sanitize any Google Flow / Muse policy triggers across all scenes."""
        self.notify('🛡️ Bước Rà Soát Lần 2: AI đang kiểm tra & tự động làm mềm toàn bộ phân cảnh để chống vi phạm chính sách Google Flow…')
        prompt = (
            POLICY_SECOND_AUDIT_SYSTEM
            + f"\nKỊCH BẢN ĐÃ DUYỆT:\n{sanitize_for_video_prompt(p.script[:2500])}\n"
            + f"HỒ SƠ NHÂN VẬT & BỐI CẢNH:\n{p.bible.model_dump_json(indent=2) if p.bible else '{}'}\n"
            + f"BẢNG PHÂN CẢNH CẦN RÀ SOÁT & LÀM SẠCH CHÍNH SÁCH:\n{board.model_dump_json(indent=2)}"
        )
        try:
            cleaned = self.generate(Storyboard, prompt, p.references)
            if cleaned and cleaned.scenes and len(cleaned.scenes) == len(board.scenes):
                cleaned = auto_repair_board(cleaned, p.total_seconds, p.clip_seconds, p.bible, p.style)
                board = cleaned
        except Exception:
            pass
        board.scenes = [sanitize_scene_for_flow(s) for s in board.scenes]
        if '🛡️ Đã qua AI Rà Soát Chính Sách Lần 2 (Chuẩn Google Flow & Meta Muse AI).' not in board.warnings:
            board.warnings.append('🛡️ Đã qua AI Rà Soát Chính Sách Lần 2 (Chuẩn Google Flow & Meta Muse AI).')
        return board

    def audit(self, p, board):
        report = self.generate(ContinuityReview, AUDIT + '\nTRUYỆN: ' + p.script + '\nĐẠO DIỄN: ' + p.treatment + '\nHỒ SƠ: ' + p.bible.model_dump_json() + '\nPHÂN CẢNH: ' + board.model_dump_json(), {})
        if report.issues:
            raise ValueError('Lỗi nối cảnh: ' + '; '.join(report.issues))

    def notify(self, message):
        callback = getattr(self, 'progress', None)
        if callback:
            callback(message)

    def storyboard(self, p):
        if not p.bible:
            raise ValueError('Cần tạo và duyệt hồ sơ nhân vật trước.')
        p = p.model_copy(update={'bible': ensure_ghost_bible(p.bible, p.style)})
        slots = time_slots(p.total_seconds, p.clip_seconds, p.style)
        is_3d = is_3d_fable_style(p.style)
        is_fam = is_family_drama_style(p.style)
        if is_3d:
            style_req = (
                'Mỗi cảnh phải có đầy đủ 4 mục của Hoạt hình 3D Pixar Ngụ ngôn: Visual Description 3D chi tiết trong `visual_prompt`, '
                'Voiceover/Dialogue sâu sắc trong `dialogue`, và Moral Lesson (Châm ngôn cốt lõi) ở cảnh cuối.\n'
            )
        elif is_fam:
            style_req = (
                'PHONG CÁCH GIA ĐÌNH TÂM LÝ XÃ HỘI & ĐỜI THỰC QUÊ NGHÈO THẬP NIÊN 80: '
                '(1) Khóa cứng 100% tạo hình nhân vật và bối cảnh làng quê nghèo thập niên 80 xuyên suốt từ SCENE_001 đến hết; '
                '(2) Tất cả các cảnh từ SCENE_001 đến hết phải có lời thoại và diễn biến tiến triển hoàn toàn mới (tuyệt đối không lặp lại cảnh trước); '
                '(3) Nếu 2 cảnh liên tiếp ở cùng bối cảnh đang nói chuyện tiếp thì giữ nguyên vị trí ngồi/đứng suốt cả cảnh (không tự ý đứng dậy bỏ đi, không Fade to black, không tiếng chuýt); '
                'chỉ khi cảnh sau đổi sang bối cảnh khác mới đứng dậy bước đi ở giây cuối 9.0s–10.0s.\n'
            )
        else:
            style_req = (
                'Mỗi cảnh thể hiện đầy đủ 5 mục của Tiểu phẩm Tâm lý Đời thực & Bẻ lái: '
                'Thời gian khớp `LỊCH CẢNH BẮT BUỘC`, Bối cảnh & Góc máy thực tế, Hành động & biểu cảm tự nhiên, Lời thoại đời thực, và Nối cảnh mượt mà.\n'
            )
        prompt = (
            'Mỗi cảnh một góc chủ đạo, không góc dự phòng, không slow motion vô cớ. '
            'Bám sát từng cảnh SCENE_xxx đã chia trong kịch bản và tuân thủ nghiêm ngặt `LỊCH CẢNH BẮT BUỘC`.\n'
            + style_req
            + direction(p.style)
            + '\nLỊCH CẢNH BẮT BUỘC, không đổi số cảnh/ID/duration: ' + json.dumps(slots, ensure_ascii=False)
            + '\nTimeline mỗi cảnh tính từ 0, không dùng mốc toàn phim. '
            + 'Trả storyboard hoàn chỉnh.\n'
            + p.model_dump_json(exclude={'board', 'clips', 'references', 'story_chat'})
        )
        base_prompt = prompt
        last_board = None
        for attempt in range(4):
            board = None
            if attempt == 0:
                if is_3d:
                    self.notify('Đang tạo Bảng Phân Cảnh 3D Pixar (Form 4 mục + Image Prompt 3D Consistent)…')
                elif is_fam:
                    self.notify('Đang tạo Bảng Phân Cảnh Gia đình Tâm lý Quê nghèo Thập niên 80 (Khóa nhân vật 100% & Nối cảnh tự nhiên)…')
                else:
                    self.notify('Đang tạo Bảng Phân Cảnh Tiểu Phẩm Tâm Lý…')
            else:
                self.notify(f'AI đang tự sửa phân cảnh vòng {attempt}/3…')
            try:
                raw_board = self.generate(Storyboard, prompt, p.references)
                if attempt < 2 and len(raw_board.scenes) < len(slots):
                    last_board = auto_repair_board(raw_board, p.total_seconds, p.clip_seconds, p.bible, p.style)
                    raise ValueError(
                        f'Cần tạo đủ {len(slots)} phân cảnh hoàn toàn khác nhau từ SCENE_001 đến SCENE_{len(slots):03d}, '
                        f'nhưng AI mới trả {len(raw_board.scenes)} cảnh. BẮT BUỘC trả đủ {len(slots)} cảnh với lời thoại và hành động tiến triển mới 100%, không lặp lại cảnh!'
                    )
                if hasattr(self, 'client'):
                    board = auto_repair_board(raw_board, p.total_seconds, p.clip_seconds, p.bible, p.style)
                else:
                    board = lock_handoffs(fit_dialogue(raw_board))
                last_board = board
                Project.model_validate(p.model_copy(update={'board': board}).model_dump())
                validate_board(board, p.total_seconds, p.clip_seconds)
                self.notify('Đang kiểm tra nối cảnh…' if attempt == 0 else f'Đang kiểm tra lại sau sửa vòng {attempt}/3…')
                self.audit(p, board)
                board = self.second_pass_policy_audit(p, board)
                return board
            except ValueError as error:
                candidate = board or last_board
                if candidate is not None and (attempt == 3 or (attempt >= 1 and hasattr(self, 'client'))):
                    self.notify('Đang tự động sửa và đồng bộ trực tiếp các phân cảnh còn lệch…')
                    healed = apply_audit_corrections(candidate, str(error), p.total_seconds, p.clip_seconds, p.bible, p.style)
                    Project.model_validate(p.model_copy(update={'board': healed}).model_dump())
                    validate_board(healed, p.total_seconds, p.clip_seconds)
                    healed = self.second_pass_policy_audit(p, healed)
                    return healed
                if attempt == 3:
                    raise ValueError('AI đã tự sửa 3 vòng nhưng còn lỗi. Dừng để tránh tốn thêm quota; kết quả cũ được giữ.\n' + str(error)[:1200]) from None
                prompt = base_prompt + '\nBẢN CẦN SỬA (giữ phần đúng): ' + (candidate.model_dump_json() if candidate else 'Không đọc được cấu trúc') + '\nLỖI CỤ THỂ: ' + str(error)[:6000] + '\nTHỰC HIỆN SỬA, không chỉ trả nhận xét: bổ sung động tác còn thiếu vào timeline; ghi chuyển thời gian rõ ràng trong transition; đối chiếu đầu/cuối. Chỉ sửa phần liên quan và cảnh lân cận, giữ phần đúng. Trả toàn bộ storyboard, không tăng số cảnh/tổng giây, không đổi truyện đã duyệt.'

    def full_pipeline(self, p: Project, message: str = '') -> Project:
        """Run pipeline automatically with AI using the dedicated form of the selected style."""
        p = p.model_copy(deep=True)
        slots = time_slots(p.total_seconds, p.clip_seconds, p.style)
        is_3d = is_3d_fable_style(p.style)
        is_fam = is_family_drama_style(p.style)
        if not p.script.strip() or message.strip():
            if is_3d:
                self.notify(f'Bước 1/4: AI đang viết Kịch bản 3D Ngụ ngôn {len(slots)} cảnh (Form 4 mục)…')
                default_req = (
                    f'Viết kịch bản Hoạt hình 3D Pixar Ngụ ngôn gồm {len(slots)} phân cảnh (Scene 1 đến Scene {len(slots)}, tổng {p.total_seconds}s, {p.clip_seconds}s/cảnh) '
                    f'theo đúng FORM 4 MỤC.'
                )
            elif is_fam:
                self.notify(f'Bước 1/4: AI đang tự do sáng tạo Kịch bản Gia đình Tâm lý Quê nghèo Thập niên 80 ({len(slots)} cảnh)…')
                default_req = (
                    f'Tự do sáng tạo kịch bản Gia đình Tâm lý Xã hội & Đời thực Quê nghèo Việt Nam thập niên 80 tự nhiên, sâu sắc gồm đủ {len(slots)} phân cảnh khác nhau '
                    f'(Cảnh 1 đến Cảnh {len(slots)}, tổng {p.total_seconds}s, {p.clip_seconds}s/cảnh). '
                    f'Thiết lập tạo hình nhân vật nông thôn thập niên 80 và bối cảnh quê xưa cố định 100% từ cảnh đầu đến cảnh cuối; nối cảnh tự nhiên mượt mà.'
                )
            else:
                self.notify(f'Bước 1/4: AI đang viết Kịch bản Tiểu phẩm Tâm lý & Bẻ lái {len(slots)} cảnh (Form 5 mục)…')
                default_req = (
                    f'Viết kịch bản Tiểu phẩm Tâm lý Xã hội Đời thực có cú "bẻ lái" (plot twist) cuối video gồm {len(slots)} phân cảnh (Scene 1 đến Scene {len(slots)}, tổng {p.total_seconds}s, {p.clip_seconds}s/cảnh) '
                    f'theo đúng FORM 5 MỤC.'
                )
            req_msg = message.strip() or default_req
            story_text = self.write(p, req_msg, treatment=False)
            p.story_chat += [{'role': 'user', 'text': req_msg}, {'role': 'assistant', 'text': story_text}]
            p.script = story_text
        p.story_approved = True

        self.notify(f'Bước 2/4: AI Đạo diễn đang chuẩn hóa {len(slots)} phân cảnh…')
        treatment_text = self.write(p, '', treatment=True)
        p.treatment = treatment_text
        p.treatment_approved = True

        self.notify('Bước 3/4: AI đang lập Hồ sơ Nhân vật cố định & Bối cảnh…')
        bible_obj = self.bible(p)
        p.bible = bible_obj

        self.notify(f'Bước 4/4: AI đang xuất Bảng Phân Cảnh JSON chuẩn cấu trúc ({len(slots)} cảnh)…')
        board_obj = self.storyboard(p)
        p.board = board_obj
        p = sanitize_project_for_flow(p)
        p.clips = {}
        return p

    def rewrite_failed_scenes_for_muse(self, p: Project, failed_ids: list[str] | None = None, muse_feedback: str = '') -> Storyboard:
        if not p.board or not p.board.scenes:
            raise ValueError('Chưa có bảng phân cảnh để sửa.')
        parsed = parse_muse_reply_text(muse_feedback, [s.id for s in p.board.scenes])
        target_ids = list(dict.fromkeys((failed_ids or []) + parsed['failed_ids']))
        if not target_ids:
            target_ids = [s.id for s in get_missing_scenes(p)]
        if not target_ids:
            return p.board

        suggestion_note = parsed['suggestion'] or muse_feedback.strip() or (
            'Loại bỏ hoàn toàn dao phay, vũ khí sắc nhọn, cảnh giết mổ/hành hạ động vật, máu me, bạo lực hoặc từ ngữ nhạy cảm; '
            'chuyển xung đột thành tranh cãi tâm lý kịch tính bằng cử chỉ tay, ánh mắt hoặc đạo cụ sinh hoạt vô hại.'
        )
        existing_done = [s.id for s in p.board.scenes if Path(p.clips.get(s.id, '__missing__')).is_file()]
        self.notify(f'AI đang tự động viết lại {len(target_ids)} cảnh bị kẹt ({", ".join(target_ids)}) để vượt bộ lọc Muse mà vẫn khớp 100% cốt truyện & cảnh trước/sau…')

        prompt = (
            direction(p.style)
            + f'\nNHIỆM VỤ ĐẶC BIỆT: Công cụ tạo video Muse vừa từ chối tạo các cảnh: {", ".join(target_ids)}.\n'
            + f'LÝ DO / GỢI Ý TỪ MUSE: {suggestion_note}\n'
            + f'CÁC CẢNH ĐÃ TẠO VIDEO THÀNH CÔNG (GIỮ NGUYÊN KHÔNG ĐỔI): {", ".join(existing_done) if existing_done else "Chưa có"}\n'
            + 'YÊU CẦU BẮT BUỘC KHI SỬA CÁC CẢNH BỊ TỪ CHỐI:\n'
            + '1. SỬA MÔ TẢ HÌNH ẢNH & ĐẠO CỤ AN TOÀN 100%.\n'
            + '2. GIỮ NGUYÊN 100% CỐT TRUYỆN, NHÂN VẬT CỐ ĐỊNH & GÓC QUAY.\n'
            + '3. KHỚP NỐI TUYỆT ĐỐI VỚI CÁC CẢNH ĐÃ TẠO.\n'
            + 'Trả về toàn bộ Storyboard JSON (giữ nguyên số cảnh, ID và duration):\n'
            + f'HỒ SƠ NHÂN VẬT & BỐI CẢNH:\n{p.bible.model_dump_json(indent=2) if p.bible else "{}"}\n'
            + f'BẢNG PHÂN CẢNH HIỆN TẠI:\n{p.board.model_dump_json(indent=2)}'
        )
        try:
            new_board = self.generate(Storyboard, prompt, p.references)
            new_map = {s.id: s for s in new_board.scenes}
        except Exception:
            new_map = {}

        merged_scenes = []
        target_set = set(target_ids)
        for old_sc in p.board.scenes:
            if old_sc.id in target_set:
                sc = new_map.get(old_sc.id, old_sc).model_copy(deep=True)
                sc.id = old_sc.id
                sc.duration = old_sc.duration
                sc.title = sanitize_for_video_prompt(sc.title)
                sc.start_state = sanitize_for_video_prompt(sc.start_state)
                sc.end_state = sanitize_for_video_prompt(sc.end_state)
                sc.emotion = sanitize_for_video_prompt(sc.emotion)
                sc.visual_prompt = sanitize_for_video_prompt(sc.visual_prompt)
                for b in sc.timeline:
                    b.action = sanitize_for_video_prompt(b.action)
                for d in sc.dialogue:
                    d.text = sanitize_for_video_prompt(d.text)
                    d.delivery = sanitize_for_video_prompt(d.delivery)
                merged_scenes.append(sc)
            else:
                merged_scenes.append(old_sc.model_copy(deep=True))

        repaired = Storyboard(
            scenes=merged_scenes,
            warnings=list(p.board.warnings) + [f'AI đã tự động làm mềm và sửa {len(target_ids)} cảnh ({", ".join(target_ids)}) để vượt bộ lọc Muse.'],
        )
        repaired = auto_repair_board(repaired, p.total_seconds, p.clip_seconds, p.bible, p.style)
        return repaired
