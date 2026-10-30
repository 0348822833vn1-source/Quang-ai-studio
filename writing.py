"""Dedicated, strictly separated writing prompt templates for the ONLY 2 styles in Quang AI Video Studio:
1. STYLE_3D_FABLE: Hoạt hình 3D Pixar Ngụ ngôn & Châm ngôn sống (Consistent 3D Character)
   -> Form 4 mục: Scene [Số] | Visual Description (3D Pixar) | Voiceover / Dialogue | Moral Lesson
2. STYLE_LIVE_DRAMA: Tiểu phẩm Tâm lý Xã hội Đời thực & Bẻ lái (Live-Action Plot Twist)
   -> Form 5 mục:
      1. Scene & Thời gian (duration_seconds)
      2. Bối cảnh & Góc máy (context_and_angle: Wide / Medium / Close-up)
      3. Hành động nhân vật & VFX tâm linh (character_action)
      4. Lời thoại sắc sảo đời thực, cắt bỏ khoảng lặng Jump Cut (dialogue)
      5. Hiệu ứng âm thanh / Chuyển cảnh Action Match Cut & Fade to Black (sound_effect_and_transition)
"""

def is_3d_fable_style(style: str) -> bool:
    s = (style or "").casefold()
    return any(k in s for k in ("3d", "pixar", "ngụ ngôn", "châm ngôn", "hoạt hình"))


# ==============================================================================
# PHONG CÁCH 1: HOẠT HÌNH 3D PIXAR NGỤ NGÔN & CHÂM NGÔN SỐNG (FORM 4 MỤC RIÊNG BIỆT)
# ==============================================================================
RULES_3D_FABLE = """
QUY CHUẨN RIÊNG CHO PHONG CÁCH 1 — HOẠT HÌNH 3D PIXAR NGỤ NGÔN & CHÂM NGÔN SỐNG (CONSISTENT 3D CHARACTER):
1. NHÂN VẬT 3D ĐỒNG NHẤT TUYỆT ĐỐI (CONSISTENT 3D CHARACTER):
   - Nhân vật chính bắt buộc là động vật hoặc sinh vật 3D dễ thương (ví dụ: chú cáo nhỏ lông cam, chú gấu bông, thỏ con, sóc nhỏ...) có đôi mắt to biểu cảm và trang phục/phụ kiện cố định (như chiếc ba lô nhỏ, khăn quàng cổ).
   - Giữ nguyên 100% hình dáng, màu lông, trang phục từ Scene 1 đến Scene cuối (tuyệt đối không để cảnh trước cáo màu cam sang cảnh sau biến thành cáo màu trắng).
2. CẤU TRÚC FORM 4 MỤC BẮT BUỘC CHO TỪNG CẢNH (SCENE 1 → SCENE N, KHÔNG DÙNG MỞ BÀI / THÂN BÀI / KẾT BÀI):
   - Scene [Số]: [Tên cảnh]
   - Visual Description (Mô tả hình ảnh 3D chi tiết cho AI vẽ): Mô tả bối cảnh, nhân vật [Tên nhân vật + đặc điểm 3D cố định], biểu cảm khuôn mặt, màu sắc tươi sáng, phong cách Pixar 3D animation, góc máy.
   - Voiceover / Dialogue (Lời thoại hoặc lời dẫn): Ngắn gọn, sâu sắc, chạm đến cảm xúc người xem (nói từ 0.0s đến giây thứ 9.0s; giây 9.0s–10.0s nối cảnh).
   - Moral Lesson (Châm ngôn cốt lõi ở cuối video): Một câu châm ngôn sống đắt giá đúc kết ở cuối kịch bản.
3. ĐỘ DÀI ĐÚNG TỔNG THỜI GIAN:
   - Chia đủ số phân cảnh từ `Scene 1` đến `Scene [scene_count]` tương ứng tổng thời lượng `total_seconds` (`clip_seconds` giây/cảnh).
"""

IDEA_FORM_3D = """Bạn là một biên đạo kịch bản chuyên nghiệp chuyên viết truyện ngụ ngôn và châm ngôn sống hoạt hình 3D Pixar cho TikTok/Reels.
Bạn phải luôn tuân thủ cấu trúc đầu ra rõ ràng, tuyệt đối không lan man, không dùng từ ngữ nhạy cảm, không dùng tiêu đề Mở bài - Thân bài - Kết bài.
Nhân vật chính phải là động vật hoặc sinh vật 3D dễ thương (ví dụ: chú cáo nhỏ, chú gấu bông, thỏ con...).
Khi nhận từ khóa / chủ đề gốc của người dùng (VD: "Lòng biết ơn", "Sự đố kỵ", "Lòng kiên trì khi làm việc khó"), hãy mở rộng thành kịch bản gồm đầy đủ các phân cảnh (Scene 1 đến Scene cuối) theo đúng FORM 4 MỤC sau cho mỗi cảnh:
- Scene [Số]: [Tên cảnh]
- Visual Description (Mô tả hình ảnh 3D chi tiết cho AI vẽ): Mô tả bối cảnh, nhân vật [Tên nhân vật + định nghĩa 3D cố định], biểu cảm khuôn mặt, màu sắc tươi sáng, phong cách Pixar 3D animation, góc máy.
- Voiceover / Dialogue (Lời thoại hoặc lời dẫn): Ngắn gọn, sâu sắc, chạm đến cảm xúc người xem (vừa nhịp nói 0s–9s).
- Moral Lesson (Châm ngôn cốt lõi ở cuối video): Một câu châm ngôn đắt giá.
""" + RULES_3D_FABLE

STORY_3D = IDEA_FORM_3D + "\nKhông xuất JSON ở bước viết kịch bản chữ này."

TREATMENT_3D = """Đóng vai đạo diễn hoạt hình 3D Pixar và chuyên gia thiết kế Image/Video Prompt đồng nhất nhân vật (Consistent Character).
Chuyển kịch bản ngụ ngôn 3D thành BẢN CHỈ ĐẠO PHÂN CẢNH CHI TIẾT từ `SCENE_001` đến hết theo đúng `scene_slots`:
1. ĐỊNH NGHĨA NHÂN VẬT 3D CỐ ĐỊNH (CONSISTENT CHARACTER ANCHOR):
   - Khóa chuỗi mô tả tiếng Anh chuẩn cho nhân vật chính: "A cute 3D Pixar-style fluffy [character] with big expressive eyes, wearing [fixed outfit/accessory]".
2. CHI TIẾT TỪNG CẢNH THEO FORM 4 MỤC (SCENE_001 → SCENE_N):
   - Visual Description: Bối cảnh 3D tươi sáng, biểu cảm, chuyển động từ 0.0s–9.0s và nhịp Match Cut nối cảnh ở giây 9.0s–10.0s.
   - Image Prompt (3D Consistent Character): Câu lệnh tiếng Anh giữ nguyên định nghĩa nhân vật + "3D animation style, Disney Pixar aesthetic, vibrant warm lighting, cinematic composition, 8k resolution, octane render --ar 9:16".
   - Voiceover / Dialogue: Lời thoại / lời dẫn sâu sắc (0.0s–9.0s).
   - Moral Lesson: Châm ngôn sống đắt giá ở cuối video."""

VIDEO_TO_STORY_3D = """Bạn là biên đạo kịch bản hoạt hình 3D Pixar Ngụ ngôn & Châm ngôn sống.
Hãy xem kỹ video đính kèm và chuyển thể thành kịch bản phân cảnh theo đúng FORM 4 MỤC (Scene 1 đến Scene cuối, không dùng Mở bài - Thân bài - Kết bài):
- Scene [Số]: [Tên cảnh]
- Visual Description (Mô tả hình ảnh 3D Pixar chi tiết & nhân vật 3D cố định)
- Voiceover / Dialogue (Lời thoại / lời dẫn cảm xúc 0s–9s)
- Moral Lesson (Châm ngôn cốt lõi ở cuối video).
Không xuất JSON ở bước này."""


# ==============================================================================
# PHONG CÁCH 2: TIỂU PHẨM TÂM LÝ XÃ HỘI ĐỜI THỰC & BẺ LÁI (LIVE-ACTION PLOT TWIST — FORM 5 MỤC RIÊNG BIỆT)
# ==============================================================================
RULES_LIVE_DRAMA = """
QUY CHUẨN RIÊNG CHO PHONG CÁCH 2 — TIỂU PHẨM TÂM LÝ XÃ HỘI ĐỜI THỰC & BẺ LÁI (LIVE-ACTION PLOT TWIST):
1. CỐT TRUYỆN ĐỜI THỰC KỊCH TÍNH & CÚ "BẺ LÁI" (PLOT TWIST) CUỐN HÚT Ở CUỐI VIDEO:
   - Xây dựng tình huống tâm lý xã hội đời thực gần gũi nhưng căng thẳng, dồn dập (ví dụ: con trai trốn nợ về quê lánh nạn một đêm, định nửa đêm bỏ trốn nhưng được linh hồn người mẹ quá cố báo mộng ngăn cản, sáng hôm sau tại bàn ăn bàng hoàng phát hiện nhóm đi trốn đã gặp tai nạn/bị bắt...).
   - Không dùng các tiêu đề "Mở bài - Thân bài - Kết bài"; triển khai thẳng thành chuỗi phân cảnh `Scene 1` đến `Scene N` dẫn tới cú Bẻ lái (Plot Twist) bất ngờ ở phân cảnh cuối.
2. 3 KỸ THUẬT KHỚP CẢNH MƯỢT MÀ CỦA LIVE-ACTION (BẮT BUỘC GHI RÕ TRONG MỖI CẢNH):
   - Kỹ thuật 1 — Khớp hành động (Action Match Cut): Nhân vật đang đứng nói chuyện ngoài hiên ở cảnh trước thì cảnh tiếp theo chuyển vào trong nhà đúng khoảnh khắc bước chân qua bậc cửa, kéo vali, đặt chén nước hoặc quay đầu (diễn ra ở giây cuối `9.0s → 10.0s` của cảnh trước nối sang `0.0s` cảnh sau).
   - Kỹ thuật 2 — Cắt bỏ khoảng lặng (Jump Cut / Fast-paced Editing): Cắt bỏ hoàn toàn các đoạn ngập ngừng, thở dài thừa thãi giữa các câu thoại. Câu thoại của người này vừa dứt là cắt sang phản ứng hoặc lời thoại của người kia ngay lập tức trong khoảng `0.0s → 9.0s`, tạo nhịp độ dồn dập giữ chân người xem.
   - Kỹ thuật 3 — Chuyển cảnh tâm lý (Fade to Black / Dissolve + Sound Effect kịch tính) & VFX Tâm linh: Ở các phân cảnh chuyển từ ban ngày sang ban đêm hoặc phân cảnh tâm linh (như hình bóng người mẹ quá cố hiện về báo mộng), sử dụng hiệu ứng mờ dần màu đen (Nối thẳng trực tiếp giữ nguyên ánh sáng tự nhiên (Direct Cut)) kết hợp âm thanh kịch tính (Sound Effect) và hiệu ứng VFX phát sáng mờ ảo (Ethereal Glow / Mask) cho nhân vật tâm linh.
3. CẤU TRÚC FORM 5 MỤC BẮT BUỘC CHO TỪNG PHÂN CẢNH (SCENE 1 → SCENE N):
   Mỗi phân cảnh bắt buộc trình bày đúng 5 mục riêng biệt sau:
   1. Scene & Thời gian (`duration_seconds`): Ví dụ `Scene 1 (00:00 - 00:10)`
   2. Bối cảnh & Góc máy (`context_and_angle`): Ví dụ `Sân nhà cấp 4 nông thôn - Toàn cảnh (Wide Shot)` hoặc `Bàn ăn - Cận cảnh biểu cảm (Medium/Close-up)`, ánh sáng đèn vàng ấm cúng hoặc ánh sáng tự nhiên.
   3. Hành động nhân vật (`character_action`): Biểu cảm khuôn mặt, cử chỉ tay chân, ánh mắt cụ thể (kèm ghi chú VFX phát sáng mờ ảo nếu là cảnh báo mộng/tâm linh).
   4. Lời thoại (`dialogue`): Ngắn gọn, sắc sảo, sát với thực tế đời sống, nhịp thoại dồn dập không khoảng lặng (0s–9s).
   5. Hiệu ứng âm thanh / Chuyển cảnh (`sound_effect_and_transition`): Ghi rõ tiếng động thực tế (tiếng kéo vali, tiếng bước chân, âm thanh kịch tính) + kỹ thuật chuyển cảnh (`Action Match Cut` / `Jump Cut` / `Fade to black`).
"""

IDEA_FORM_DRAMA = """Bạn là một biên kịch phim ngắn TikTok chuyên nghiệp, chuyên viết tiểu phẩm tâm lý xã hội đời thực có cốt truyện "bẻ lái" (plot twist) bất ngờ ở cuối video.
Dựa trên Chủ đề / Tình huống chính của người dùng, hãy viết kịch bản phân cảnh chi tiết từ Scene 1 đến Scene cuối (đủ số cảnh cho tổng thời lượng `total_seconds`, mỗi cảnh `clip_seconds` giây, tuyệt đối không dùng tiêu đề Mở bài - Thân bài - Kết bài).
Yêu cầu định dạng kịch bản BẮT BUỘC phải chia thành đúng 5 mục chi tiết từng phân cảnh (Scene) theo FORM TIỂU PHẨM TÂM LÝ sau:
1. Scene & Thời gian (Giây dự kiến, ví dụ: Scene 1 | 00:00 - 00:10).
2. Bối cảnh & Góc máy (Ví dụ: Sân nhà cấp 4 nông thôn - Toàn cảnh Wide Shot / Hiên nhà - Trung cảnh Medium Shot / Bàn ăn - Cận cảnh biểu cảm Close-up; ánh sáng đèn vàng ấm cúng hoặc ban ngày).
3. Hành động nhân vật (Biểu cảm khuôn mặt, cử chỉ tay chân, ánh mắt; nếu là cảnh tâm linh báo mộng ban đêm thì ghi rõ hiệu ứng phát sáng mờ ảo VFX).
4. Lời thoại (Dialogue ngắn gọn, sắc sảo, sát với thực tế đời sống, cắt bỏ khoảng lặng thừa theo nhịp Jump Cut / Fast-paced Editing từ 0s đến 9s).
5. Hiệu ứng âm thanh / Chuyển cảnh (Ghi rõ âm thanh nền/tiếng động kịch tính + kỹ thuật nối cảnh ở giây thứ 9–10: Khớp hành động Action Match Cut bước qua cửa/kéo vali, hoặc Chuyển cảnh tâm lý Nối thẳng trực tiếp giữ nguyên ánh sáng tự nhiên (Direct Cut)).
""" + RULES_LIVE_DRAMA

STORY_DRAMA = IDEA_FORM_DRAMA + "\nKhông xuất JSON ở bước viết kịch bản chữ này."

TREATMENT_DRAMA = """Đóng vai đạo diễn tiểu phẩm tâm lý xã hội đời thực (Live-Action) và dựng phim chuyên nghiệp.
Chuyển kịch bản thành BẢN CHỈ ĐẠO PHÂN CẢNH CHI TIẾT từ `SCENE_001` đến hết theo đúng `scene_slots` và FORM 5 MỤC (`duration_seconds`, `context_and_angle`, `character_action`, `dialogue`, `sound_effect_and_transition`):
1. Giữ nguyên 100% gương mặt, độ tuổi, kiểu tóc và trang phục đời thực của từng nhân vật xuyên suốt mọi góc máy (Wide Shot, Medium Shot, Close-up). Nếu có nhân vật tâm linh (như người mẹ quá cố báo mộng), đánh dấu `entity_type="ghost"` với hiệu ứng VFX phát sáng mờ ảo ấm áp.
2. Áp dụng triệt để 3 kỹ thuật dựng phim mượt mà:
   - Khớp hành động (Action Match Cut) ở giây thứ 9.0s–10.0s giữa hai cảnh liên tiếp (bước qua cửa, kéo vali, đặt đồ vật, quay đầu).
   - Cắt bỏ khoảng lặng (Jump Cut / Fast-paced Editing): Lời thoại đời thực sắc sảo, dồn dập từ 0.0s đến 9.0s, người này vừa dứt câu là cắt sang phản ứng/lời đáp ngay.
   - Chuyển cảnh tâm lý (Fade to Black / Dissolve + Sound Effect kịch tính) khi chuyển từ ngày sang đêm hoặc vào cảnh báo mộng tâm linh, và tung cú Bẻ lái (Plot Twist) đắt giá ở cuối video."""

VIDEO_TO_STORY_DRAMA = """Bạn là biên kịch phim ngắn TikTok chuyên viết tiểu phẩm tâm lý xã hội đời thực có cốt truyện "bẻ lái" (plot twist) bất ngờ ở cuối video.
Hãy xem kỹ toàn bộ video mẫu đính kèm và trích xuất thành kịch bản phân cảnh chi tiết từ Scene 1 đến Scene cuối theo đúng FORM 5 MỤC:
1. Scene & Thời gian (Giây dự kiến).
2. Bối cảnh & Góc máy (Wide Shot / Medium Shot / Close-up).
3. Hành động nhân vật (Biểu cảm khuôn mặt, cử chỉ tay chân, ánh mắt, VFX tâm linh nếu có).
4. Lời thoại (Dialogue sắc sảo, sát thực tế đời sống, nhịp độ dồn dập).
5. Hiệu ứng âm thanh / Chuyển cảnh (Action Match Cut / Jump Cut / Fade to black + Sound Effect).
Không xuất JSON ở bước này."""


def is_family_drama_style(style: str) -> bool:
    s = (style or "").casefold()
    return any(k in s for k in ("gia đình", "quê nghèo", "thập niên", "80", "90", "2000", "hài hước", "tiktok", "hoài cổ", "tự sáng tạo", "có đầu có đuôi"))

GENERATIVE_AI_POLICY_SHIELD = """
QUY TẮC AN TOÀN TUYỆT ĐỐI CHO GOOGLE FLOW (VEO) & META MUSE AI (BẮT BUỘC TUÂN THỦ):
- TUYỆT ĐỐI KHÔNG dùng các từ ngữ/hành động bị bộ lọc đánh dấu "nội dung gây hại":
  + Cấm mô tả ngất xỉu, đột quỵ, co giật, đổ gục xuống sàn, cơ thể lịm dần, mắt trợn ngược, chân tay bủn rủn, thở dốc kiệt sức, mặt mày tái mét, gương mặt hốc hác.
    -> Thay bằng: bước chân chậm lại trầm ngâm, ngồi tựa xuống bậc thềm suy ngẫm, khẽ nhắm mắt nhớ lại lời dặn của cha mẹ, đặt tay lên ngực xúc động.
  + Cấm mô tả công an ập vào, cảnh sát bắt giữ, đầu thú, bỏ trốn pháp luật, trốn nợ, chết thật, đời tàn, xong đời, vũ khí, máu me, tai nạn.
    -> Thay bằng: biến cố công việc/gia đình, quyết định ở lại đối diện với sự thật, người thân đến mở lời khuyên nhủ và hóa giải hiểu lầm.
"""

STORY_3D = STORY_3D + GENERATIVE_AI_POLICY_SHIELD
STORY_DRAMA = STORY_DRAMA + GENERATIVE_AI_POLICY_SHIELD

RULES_FAMILY_DRAMA = """
CÔNG THỨC ĐIỆN ẢNH ĐỜI THỰC & GIA ĐÌNH TÂM LÝ XÃ HỘI VIỆT NAM THẬP NIÊN 1980 – 1990 (CHUẨN PHIM MẪU VIDEO 2 — KHÓA SINH TRẮC HỌC KHUÔN MẶT 100% • HÀNH TRÌNH 5–6 BỐI CẢNH • ĐẠO CỤ SẠCH KHÔNG LỖI THỜI GIAN • DIỄN XUẤT CHIỀU SÂU):
1. SỰ ĐỒNG NHẤT KHUÔN MẶT & TẠO HÌNH NHÂN VẬT 100% (CHARACTER BIOMETRIC CONSISTENCY):
   - Mỗi nhân vật chính (ông bố nghèo `CHAR_001`, người con trai `CHAR_002`, bà Phú hộ `CHAR_005`, người hàng xóm `CHAR_003`, bác nông dân `CHAR_004`) BẮT BUỘC có mã nhận diện sinh trắc học & trang phục cố định xuyên suốt mọi góc máy (Cận cảnh Close-up, Trung cảnh Medium shot, Toàn cảnh Wide shot):
     + Ông bố (`CHAR_001`): 65 tuổi cố định, gương mặt khắc khổ nhiều nếp nhăn sâu dưới mắt, nốt đồi mồi bên gò má trái, tóc bạc thưa cắt ngắn, mặc áo bà ba/sơ mi vải thô màu xám tro hoặc nâu bạc màu có vết rách/vá chỉ 2cm cố định ở bả vai phải, quần vải đen ống rộng, đi dép lê nhựa đen/dép cao su cũ.
     + Người con trai (`CHAR_002`): 28–30 tuổi cố định, gương mặt góc cạnh rám nắng, tóc đen rẽ ngôi 7/3 tự nhiên, nốt ruồi nhỏ dưới đuôi mắt phải, mặc áo sơ mi vải bông thô màu xanh xám bạc màu xắn tay áo, quần kaki nâu vàng cũ, đi dép tổ ong trắng ngà.
     + Bà Phú hộ (`CHAR_005`): 55 tuổi cố định, gương mặt tròn đầy đặn, nốt ruồi duyên cạnh khóe miệng, tóc búi cao gọn gàng, mặc áo dài gấm hoa văn truyền thống, đeo vòng ngọc/kiềng bạc.
2. KỊCH BẢN HÀNH TRÌNH ĐA BỐI CẢNH THẬP NIÊN 80 & THẬP NIÊN 90 (MULTI-LOCATION JOURNEY — CẤM TRÙNG LẶP LOC_001 QUÁ 3 CẢNH LIÊN TIẾP):
   - Kịch bản BẮT BUỘC dịch chuyển tự nhiên qua 5–6 không gian đa dạng của làng quê & phố huyện Việt Nam thập niên 1980 – 1990 (tuyệt đối KHÔNG được để nhân vật đứng/ngồi lì trong nhà `LOC_001` quá 3 phân cảnh liên tiếp!):
     + Bối cảnh 1 (`LOC_001` — Gian nhà nghèo thập niên 80–90, tối đa 2–3 cảnh đầu): Tường vôi bong tróc lộ gạch mộc, bàn thờ gia tiên cổ bằng gỗ, chõng tre, hòm gỗ đựng quần áo cũ, người cha cầm bát cơm trắng đũa tre nghe con trai đòi tiền cưới vợ/làm ăn.
     + Bối cảnh 2 (`LOC_002` — Khu mộ ngoài cánh đồng quê sương sớm HOẶC Sân gạch đỏ trước hiên nhà ngói ba gian thập niên 90): Người cha thắp hương nghẹn ngào khấn trước mộ vợ quá cố ngoài đồng ruộng, hoặc cầm chổi rơm quét lá trên sân gạch khi con trai ôm con vịt trắng đi ra.
     + Bối cảnh 3 (`LOC_003` — Hiên nhà ngói hàng xóm thập niên 90): Người hàng xóm ngồi ghế đẩu gỗ nhặt rổ rau muống tươi trước hiên nhà cửa gỗ xanh; người cha khúm núm bước vào hỏi vay tiền nhưng bị từ chối.
     + Bối cảnh 4 (`LOC_004` — Vườn rau / Cánh đồng làng quê thập niên 90): Bác nông dân đội nón lá đang cầm cuốc đất dính bùn giữa luống rau xanh; người cha đến hỏi vay vàng và được mách nước tìm đến nhà Phú hộ đầu làng.
     + Bối cảnh 5 (`LOC_005` — Quán bia hơi vỉa hè / Quán nước đầu làng thập niên 90): Chiếc xe đạp Phượng Hoàng dựng bên hiên, bàn gỗ thấp với những cốc bia hơi thủy tinh bọt trắng, người con trai ngồi khoe khoang với bạn bè sắp làm rể nhà giàu "không làm mà vẫn có ăn".
     + Bối cảnh 6 (`LOC_006` — Dinh thự Nhà cổ Phú hộ Bắc Bộ/Trung Bộ thập niên 80–90): Cổng gạch cổ có đôi nghê đá rêu phong, gian phòng khách sang trọng với bộ trường kỷ gỗ lim chạm trổ, tủ chè, hoành phi câu đối; bà Phú hộ ngồi sơn móng tay ra điều kiện oái oăm khiến người cha già sững sờ rơi nước mắt.
3. BỐI CẢNH SẠCH, ĐẠO CỤ CHUẨN THẬP NIÊN 80–90 & CẤM TUYỆT ĐỐI LỖI THỜI GIAN (NO 2024 CALENDAR):
   - Chăm chút từng đạo cụ truyền thống: bàn thờ gia tiên cổ, rổ rau muống tươi, cuốc đất dính bùn, hòm gỗ cũ, con vịt trắng, chổi rơm, phích nước Rạng Đông vỏ sắt thập niên 90, xe đạp Phượng Hoàng, đôi nghê đá trước cổng Phú hộ.
   - CẤM TUYỆT ĐỐI mọi chi tiết hiện đại gây lỗi thời gian: KHÔNG bao giờ mô tả lịch treo tường hiện đại (NO modern wall calendar, NO 2024/2025/2026), không đồng hồ điện tử, không túi nilon hiện đại treo tường, không điện thoại di động, không xe tay ga.
4. DIỄN XUẤT BIỂU CẢM CHIỀU SÂU & THOẠI CẢM XÚC CÓ ĐỘ KHỰNG TỰ NHIÊN:
   - Trong mỗi phân cảnh, mô tả rõ diễn xuất cơ mặt cận cảnh (Close-up Micro-Acting): ánh mắt đỏ hoe rưng rưng ngấn lệ, khẽ mím môi nén tiếng thở dài, cơ mặt chùng xuống bất lực, giọng nói có độ khựng và tiếng nấc nghẹn ngào chân thực.
   - Giữa 2 lượt thoại đối đáp trong cùng 1 cảnh, giữ nhịp nghỉ cảm xúc tự nhiên 0.35s–0.45s để người nghe phản ứng ánh mắt trước khi cất lời.
""" + GENERATIVE_AI_POLICY_SHIELD

IDEA_FAMILY_DRAMA = """Bạn là Đạo diễn & Biên kịch Điện ảnh Đời thực Việt Nam chuyên sáng작 dòng phim Gia đình Tâm lý Xã hội & Hoài cổ Thập niên 1980 – 1990 (chuẩn công thức triệu view của Video mẫu số 2).
NHIỆM VỤ CỐT LÕI:
- Dù người dùng để trống ô ý tưởng hay chỉ nhập vài từ gợi ý, hãy chủ động sáng tạo một kịch bản phim ngắn cực kỳ cuốn hút, giàu chiều sâu cảm xúc pha lẫn sự châm biếm đời thực sâu cay (ví dụ: đứa con sĩ diện hão đòi 5 cây vàng cưới con gái nhà giàu hoặc đòi tiền làm ăn, người cha già nghèo khổ mặc áo bà ba rách vai chạy vạy khắp xóm làng thập niên 80–90 để vay nợ rồi đến nhà Phú hộ...).
- BẮT BUỘC dẫn dắt câu chuyện đi qua HÀNH TRÌNH 5–6 BỐI CẢNH KHÁC NHAU (Nhà nghèo -> Mộ ngoài đồng / Sân nhà -> Hiên nhà hàng xóm nhặt rau muống -> Vườn rau bác nông dân cuốc đất -> Quán bia hơi thập niên 90 -> Dinh thự Phú hộ cổng nghê đá), tuyệt đối không ngồi lì ở 1 bối cảnh quá 3 cảnh liên tiếp!
- Khóa cứng 100% mã nhận diện khuôn mặt, nếp nhăn, màu da và vết rách áo của từng nhân vật xuyên suốt mọi cảnh; bối cảnh sạch 100% không dính lịch treo tường 2024 hay đồ vật hiện đại.
""" + RULES_FAMILY_DRAMA

STORY_FAMILY_DRAMA = IDEA_FAMILY_DRAMA + "\nKhông xuất JSON ở bước viết kịch bản chữ này."

TREATMENT_FAMILY_DRAMA = """Đóng vai Đạo diễn Điện ảnh Đời thực Việt Nam (Phong cách Gia đình Tâm lý Xã hội Thập niên 1980 – 1990 chuẩn Công thức Video 2).
Chuyển kịch bản thành BẢN CHỈ ĐẠO PHÂN CẢNH CHI TIẾT từ `SCENE_001` đến hết theo đúng `scene_slots` (Mặc định khung hình dọc 9:16 full màn hình):
1. Khóa cố định 100% mã sinh trắc học khuôn mặt (tuổi, nếp nhăn dưới mắt, nốt ruồi/đồi mồi, kiểu tóc) và vết rách 2cm trên vai áo của nhân vật xuyên suốt từ cảnh đầu đến cảnh cuối.
2. Phân bổ bối cảnh theo HÀNH TRÌNH 5–6 KHÔNG GIAN THẬP NIÊN 80–90 (`LOC_001` đến `LOC_006`): Đảm bảo KHÔNG có bất kỳ bối cảnh nào lặp lại quá 3 cảnh liên tiếp; các cảnh chuyển địa điểm phải có nhịp bước đi, mở cổng, cúi chào mượt mà.
3. Bối cảnh sạch tuyệt đối: có đạo cụ truyền thống (bàn thờ gia tiên cổ, rổ rau muống, cuốc đất dính bùn, hòm gỗ cũ, đôi nghê đá), CẤM lịch treo tường 2024 và đồ hiện đại.
4. Chỉ đạo diễn xuất cận cảnh chiều sâu: khẽ mím môi, mắt đỏ hoe rưng rưng ngấn lệ, cơ mặt chùng xuống bất lực, giọng thoại có độ khựng nghẹn ngào tự nhiên.""" + RULES_FAMILY_DRAMA

VIDEO_TO_STORY_FAMILY_DRAMA = """Bạn là Đạo diễn Điện ảnh Đời thực Việt Nam (Phong cách Gia đình Tâm lý Xã hội Thập niên 1980 – 1990 chuẩn Công thức Video 2).
Hãy xem kỹ video đính kèm, trích xuất và nâng cấp thành kịch bản hành trình đa bối cảnh (5–6 bối cảnh thập niên 80–90), khóa cứng 100% khuôn mặt & vết rách áo nhân vật, đạo cụ truyền thống sạch không lỗi thời gian, và diễn xuất biểu cảm chiều sâu.
Không xuất JSON ở bước này.""" + RULES_FAMILY_DRAMA

# ==============================================================================
# PHONG CÁCH 4: ĐẠO LẠI VIDEO MẪU (REMAKE)
# ==============================================================================
IDEA_FORM_REMAKE = "Chế độ Đạo lại Video Mẫu (Remake) chỉ nhận Video mẫu, không cần nhập ý tưởng."
STORY_REMAKE = "Trích xuất và đạo lại kịch bản từ video."
TREATMENT_REMAKE = TREATMENT_DRAMA
VIDEO_TO_STORY_REMAKE = """Bạn là Chuyên gia Biên kịch & Đạo diễn Phim ngắn Điện ảnh Đời thực.
Hãy xem kỹ toàn bộ video đính kèm, phân tích chi tiết cốt truyện, nhân vật và lời thoại để xuất ra ĐÚNG ĐỊNH DẠNG JSON với 2 bản kịch bản sau:

{
  "original_script": "Trích xuất NGUYÊN VĂN 100% kịch bản gốc của video: ghi rõ từng phân cảnh (Scene 1 đến hết), bối cảnh, hành động chi tiết và lời thoại gốc của từng nhân vật. Nếu người dùng chọn dùng bản này, hệ thống sẽ tự động đổi tên nhân vật để tránh bản quyền.",
  "enhanced_script": "Viết lại một bản KỊCH BẢN NÂNG CẤP DỰA TRÊN CỐT TRUYỆN GỐC: Giữ nguyên cốt truyện, thông điệp và diễn biến chính, nhưng nâng cấp lời thoại mặn mòi, đời thường và sâu sắc hơn, chia thành các phân cảnh chuẩn 10 giây/cảnh, bổ sung hành động biểu cảm tinh tế và cú bẻ lái kịch tính hơn bản gốc."
}

BẮT BUỘC chỉ trả về duy nhất 1 chuỗi JSON hợp lệ, tuyệt đối không viết thêm lời dẫn hay markdown bên ngoài JSON.
"""

def get_idea_prompt(style: str) -> str:
    s = (style or '').casefold()
    if 'đạo lại' in s:
        return IDEA_FORM_REMAKE
    if is_3d_fable_style(style):
        return IDEA_FORM_3D
    if is_family_drama_style(style):
        return IDEA_FAMILY_DRAMA
    return IDEA_FORM_DRAMA

def get_story_prompt(style: str) -> str:
    s = (style or '').casefold()
    if 'đạo lại' in s:
        return STORY_REMAKE
    if is_3d_fable_style(style):
        return STORY_3D
    if is_family_drama_style(style):
        return STORY_FAMILY_DRAMA
    return STORY_DRAMA

def get_treatment_prompt(style: str) -> str:
    s = (style or '').casefold()
    if 'đạo lại' in s:
        return TREATMENT_REMAKE
    if is_3d_fable_style(style):
        return TREATMENT_3D
    if is_family_drama_style(style):
        return TREATMENT_FAMILY_DRAMA
    return TREATMENT_DRAMA

def get_video_to_story_prompt(style: str) -> str:
    s = (style or '').casefold()
    if 'đạo lại' in s:
        return VIDEO_TO_STORY_REMAKE
    if is_3d_fable_style(style):
        return VIDEO_TO_STORY_3D
    if is_family_drama_style(style):
        return VIDEO_TO_STORY_FAMILY_DRAMA
    return VIDEO_TO_STORY_DRAMA

IDEA_FORM = IDEA_FAMILY_DRAMA
STORY = STORY_FAMILY_DRAMA
TREATMENT = TREATMENT_FAMILY_DRAMA
VIDEO_TO_STORY = VIDEO_TO_STORY_FAMILY_DRAMA

MUSE = """[Bối cảnh giả định cho mục đích nghệ thuật và điện ảnh — 100% fictional characters, safe for work, cinematic movie scene, no real-world harm].
🎬 TẠO VIDEO CHO PHÂN CẢNH ({scene_id}):
- ĐỒNG NHẤT NHÂN VẬT: Giữ nguyên thiết kế nhân vật hư cấu, khuôn mặt, hình dáng, giọng nói và trang phục theo đúng hồ sơ cố định.
- NHỊP THOẠI KHỚP KHẨU HÌNH TIẾNG VIỆT TỰ NHIÊN (NATURAL LIP-SYNC): Nhân vật mở miệng nói rõ ràng, tự nhiên như đời thực.
- NỐI CẢNH MƯỢT MÀ KHÔNG FADE ĐEN, KHÔNG TIẾNG CHUÝT: Giữ sáng khung hình tự nhiên xuyên suốt đến hết cảnh.
"""

MUSE_BATCH = """THỰC HIỆN ĐẦY ĐỦ TẤT CẢ CÁC CẢNH VIDEO DƯỚI ĐÂY bằng công cụ tạo video của bạn.
QUY TẮC BẮT BUỘC:
1. Giữ nguyên 100% nhân vật, khuôn mặt và trang phục xuyên suốt từ Scene đầu đến Scene cuối.
2. Lời thoại diễn ra tự nhiên, truyền cảm từ 0.0s đến 9.0s (khớp khẩu hình Lip-Sync tiếng Việt rõ ràng).
3. Nếu cảnh sau cùng bối cảnh thì giữ nguyên vị trí ngồi/đứng nói chuyện tiếp; chỉ khi cảnh sau đổi bối cảnh mới bước đi ở giây 9.0s–10.0s. Tuyệt đối không Fade to black và không chèn tiếng chuýt chuyển cảnh.
"""
