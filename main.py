import json
import threading
from pathlib import Path
import flet as ft

from core import (
    STYLE_FAMILY_DRAMA, STYLE_3D_FABLE, STYLE_LIVE_DRAMA, STYLE_REMAKE,
    AVAILABLE_STYLES, is_3d_fable_style, is_family_drama_style, normalize_style,
    TOOL_GOOGLE_FLOW, TOOL_META_MUSE, AVAILABLE_VIDEO_TOOLS, is_google_flow_tool,
    Project, compile_prompt, compile_flow_prompt, compile_all_image_prompts,
    compile_muse_batch_6_prompt, get_all_muse_batches_of_6, sanitize_scene_for_flow
)
from providers import Gemini, DEFAULT_MODELS
from directing import auto_repair_board


def main(page: ft.Page):
    page.title = "Quảng AI Video Studio • Mobile PRO V1.37"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0b0f19"
    page.padding = 12
    page.scroll = ft.ScrollMode.ADAPTIVE

    proj = Project(
        title="Dự án mới",
        style=STYLE_FAMILY_DRAMA,
        video_tool=TOOL_GOOGLE_FLOW,
        ratio="9:16",
        total_seconds=120,
        clip_seconds=10,
    )
    selected_scene_idx = [0]

    saved_api_key = page.client_storage.get("gemini_api_key") or ""
    saved_model = page.client_storage.get("gemini_model") or DEFAULT_MODELS[0]

    def show_snack(msg: str, color: str = "#10b981"):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(msg, color="#ffffff", weight=ft.FontWeight.BOLD),
            bgcolor=color,
        )
        page.snack_bar.open = True
        page.update()

    status_text = ft.Text(
        "✨ Sẵn sàng (Bản Mobile hiện đại: Đã lược bỏ trình duyệt & tự động).",
        size=12, color="#34d399", italic=True
    )
    progress_bar = ft.ProgressBar(visible=False, color="#10b981", bgcolor="#1f2937")

    def set_busy(busy: bool, msg: str = ""):
        progress_bar.visible = busy
        if msg:
            status_text.value = msg
        page.update()

    def get_client() -> Gemini:
        key = api_key_input.value.strip()
        if not key:
            raise ValueError("Chưa nhập Gemini API Key! Hãy sang tab '3. Cài Đặt API' để nhập Key trước.")
        page.client_storage.set("gemini_api_key", key)
        page.client_storage.set("gemini_model", model_dropdown.value)
        client = Gemini(
            key=key,
            model=model_dropdown.value,
            allow_fallback=fallback_switch.value,
            temperature=float(temp_slider.value),
        )
        client.progress = lambda m: (setattr(status_text, "value", f"⏳ {m}"), page.update())
        return client

    # =========================================================================
    # TAB 1: KỊCH BẢN & ĐẠO LẠI VIDEO MẪU (REMAKE)
    # =========================================================================
    title_input = ft.TextField(
        label="Tên dự án", value=proj.title,
        bgcolor="#111827", border_color="#1f2937", text_size=14, height=48
    )

    style_dropdown = ft.Dropdown(
        label="Phong cách Đạo diễn (4 Chế độ)",
        value=STYLE_FAMILY_DRAMA,
        options=[ft.dropdown.Option(s) for s in AVAILABLE_STYLES],
        bgcolor="#111827", border_color="#10b981", text_size=13,
    )

    ratio_dropdown = ft.Dropdown(
        label="Khung hình", value="9:16", width=110,
        options=[ft.dropdown.Option("9:16"), ft.dropdown.Option("16:9"), ft.dropdown.Option("1:1")],
        bgcolor="#111827", border_color="#1f2937",
    )

    total_sec_input = ft.TextField(
        label="Tổng giây", value="120", width=105, keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor="#111827", border_color="#1f2937"
    )

    clip_sec_input = ft.TextField(
        label="Giây/cảnh", value="10", width=105, keyboard_type=ft.KeyboardType.NUMBER,
        bgcolor="#111827", border_color="#1f2937"
    )

    mode_banner = ft.Container(
        padding=10, border_radius=8, bgcolor="#3b1d0a",
        border=ft.border.all(1, "#f59e0b"),
        content=ft.Text(
            "🏡 Gia đình Hoài cổ 80s–90s: Khóa sinh trắc học khuôn mặt 100%, hành trình 6 bối cảnh, chống chảy cơ thể & cấm lịch 2024.",
            size=12, color="#fef3c7"
        )
    )

    video_path_text = ft.Text("🎬 Chưa chọn video mẫu", size=12, color="#9ca3af", expand=True)

    def on_video_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            fpath = e.files[0].path
            proj.idea_video = fpath
            video_path_text.value = f"🎬 Đã chọn: {Path(fpath).name}"
            video_path_text.color = "#34d399"
            page.update()

    file_picker = ft.FilePicker(on_result=on_video_picked)
    page.overlay.append(file_picker)

    btn_pick_video = ft.ElevatedButton(
        "📁 Chọn Video",
        bgcolor="#374151", color="#ffffff",
        on_click=lambda _: file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.VIDEO)
    )

    btn_extract_video = ft.ElevatedButton(
        "✨ AI Phân Tích Video",
        bgcolor="#8b5cf6", color="#ffffff"
    )

    idea_input = ft.TextField(
        label="Ý tưởng / Chủ đề (Hoặc để trống để AI tự nghĩ kịch bản triệu view)",
        multiline=True, min_lines=2, max_lines=4,
        bgcolor="#111827", border_color="#1f2937", text_size=13
    )

    script_editor = ft.TextField(
        label="Nội dung Kịch bản chi tiết",
        multiline=True, min_lines=8, max_lines=14,
        bgcolor="#111827", border_color="#1f2937", text_size=13
    )

    feedback_input = ft.TextField(
        label="Nhập góp ý sửa kịch bản...",
        bgcolor="#111827", border_color="#1f2937", text_size=13, expand=True
    )

    def sync_project_from_ui():
        proj.title = title_input.value.strip() or "Dự án mới"
        proj.style = normalize_style(style_dropdown.value)
        proj.ratio = ratio_dropdown.value
        try:
            proj.total_seconds = max(10, min(600, int(total_sec_input.value)))
        except Exception:
            proj.total_seconds = 120
        try:
            proj.clip_seconds = max(5, min(30, int(clip_sec_input.value)))
        except Exception:
            proj.clip_seconds = 10
        proj.idea = idea_input.value
        proj.script = script_editor.value
        proj.video_tool = tool_dropdown.value

    def on_style_change(e):
        st = style_dropdown.value
        is_remake = "đạo lại" in st.casefold()
        is_3d = is_3d_fable_style(st)
        is_fam = is_family_drama_style(st)

        idea_input.visible = not is_remake
        btn_write_story.visible = not is_remake

        if is_remake:
            temp_slider.value = 0.70
            mode_banner.bgcolor = "#4c1d95"
            mode_banner.border = ft.border.all(1, "#8b5cf6")
            mode_banner.content.value = "♻️ CHẾ ĐỘ ĐẠO LẠI VIDEO (REMAKE): Chỉ chọn Video mẫu -> Bấm 'AI Phân Tích Video' -> So sánh & tích chọn Kịch bản Cũ hoặc Mới!"
        elif is_fam:
            temp_slider.value = 0.80
            mode_banner.bgcolor = "#3b1d0a"
            mode_banner.border = ft.border.all(1, "#f59e0b")
            mode_banner.content.value = "🏡 GIA ĐÌNH HOÀI CỔ 80s–90s: Khóa khuôn mặt 100%, hành trình 6 bối cảnh, chống chảy cơ thể & cấm lịch 2024."
        elif is_3d:
            temp_slider.value = 0.35
            mode_banner.bgcolor = "#0f2922"
            mode_banner.border = ft.border.all(1, "#10b981")
            mode_banner.content.value = "🐻 HOẠT HÌNH 3D PIXAR NGỤ NGÔN: Khóa nhân vật 3D đồng nhất (Form 4 mục + Bài học cuộc sống)."
        else:
            temp_slider.value = 0.50
            mode_banner.bgcolor = "#172554"
            mode_banner.border = ft.border.all(1, "#3b82f6")
            mode_banner.content.value = "🎭 TIỂU PHẨM TÂM LÝ & BẺ LÁI: Nhịp nhanh, kịch tính, có cú Plot Twist lật kèo cuối video (Form 5 mục)."
        page.update()

    style_dropdown.on_change = on_style_change

    def show_remake_comparison_dialog(orig_script: str, enhanced_script: str):
        choice_radio = ft.RadioGroup(
            value="enhanced",
            content=ft.Column([
                ft.Radio(value="enhanced", label="🌟 Chọn Kịch Bản Nâng Cấp (Giữ cốt truyện, lời thoại mặn mòi hơn, chuẩn 10s/cảnh)"),
                ft.Radio(value="original", label="📜 Chọn Kịch Bản Cũ (Chỉ tự động sửa tên nhân vật)"),
            ])
        )
        orig_box = ft.TextField(label="1. Kịch bản Cũ (Trích xuất từ Video)", value=orig_script, multiline=True, min_lines=5, max_lines=7, read_only=True, text_size=12)
        enh_box = ft.TextField(label="2. Kịch bản Mới Nâng Cấp (Giữ cốt truyện, thêm ý tưởng hay hơn)", value=enhanced_script, multiline=True, min_lines=5, max_lines=7, text_size=12)

        def confirm_choice(_):
            dlg.open = False
            page.update()
            if choice_radio.value == "original":
                final_txt = "[CHÚ Ý: KỊCH BẢN GỐC — TỰ ĐỘNG ĐỔI TÊN TẤT CẢ NHÂN VẬT SANG TÊN MỚI KHI LÊN PHÂN CẢNH]\n\n" + orig_box.value
                script_editor.value = final_txt
                proj.script = final_txt
                show_snack("✅ Đã chọn Kịch bản cũ (chỉ đổi tên nhân vật)!")
            else:
                script_editor.value = enh_box.value
                proj.script = enh_box.value
                show_snack("🌟 Đã chọn Kịch bản mới nâng cấp! Bấm '2. Lên Phân Cảnh' để tiếp tục.")
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("♻️ So Sánh 2 Kịch Bản Cũ & Mới", size=16, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=520,
                content=ft.Column([
                    orig_box,
                    enh_box,
                    ft.Divider(),
                    choice_radio,
                ], tight=True, scroll=ft.ScrollMode.ADAPTIVE)
            ),
            actions=[
                ft.ElevatedButton("✅ Chốt Kịch Bản Đã Tích Chọn", bgcolor="#10b981", color="#ffffff", on_click=confirm_choice)
            ]
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    def run_extract_video(_):
        sync_project_from_ui()
        if not proj.idea_video:
            show_snack("⚠️ Hãy bấm 'Chọn Video' trước!", "#ef4444")
            return
        def _job():
            try:
                set_busy(True, "🎬 AI đang xem video và phân tích kịch bản...")
                client = get_client()
                tag, text_out = client.extract_script_from_video(proj, feedback_input.value.strip())
                if tag == "JSON_REMAKE":
                    data = json.loads(text_out)
                    orig_s = data.get("original_script", "")
                    enh_s = data.get("enhanced_script", "")
                    set_busy(False, "✅ Đã phân tích xong 2 bản kịch bản!")
                    show_remake_comparison_dialog(orig_s, enh_s)
                else:
                    idea_input.value = tag
                    script_editor.value = text_out
                    proj.script = text_out
                    set_busy(False, "✅ Đã trích xuất kịch bản từ video thành công!")
                    show_snack("✨ Đã trích xuất xong kịch bản từ video!")
            except Exception as ex:
                set_busy(False, f"❌ Lỗi: {ex}")
                show_snack(str(ex)[:180], "#ef4444")
        threading.Thread(target=_job, daemon=True).start()

    btn_extract_video.on_click = run_extract_video

    def run_write_story(_):
        sync_project_from_ui()
        def _job():
            try:
                set_busy(True, "✍️ AI Đạo diễn đang sáng tạo kịch bản...")
                client = get_client()
                res = client.write(proj, feedback_input.value.strip(), treatment=False)
                script_editor.value = res
                proj.script = res
                feedback_input.value = ""
                set_busy(False, "✅ Đã viết xong kịch bản!")
                show_snack("✨ Đã viết xong kịch bản! Bấm '2. Lên Phân Cảnh' để tiếp tục.")
            except Exception as ex:
                set_busy(False, f"❌ Lỗi: {ex}")
                show_snack(str(ex)[:180], "#ef4444")
        threading.Thread(target=_job, daemon=True).start()

    def run_generate_board(_):
        sync_project_from_ui()
        def _job():
            try:
                set_busy(True, "🎬 Đang lập Hồ sơ nhân vật & Chia bảng phân cảnh JSON...")
                client = get_client()
                new_p = client.full_pipeline(proj, feedback_input.value.strip())
                proj.script = new_p.script
                proj.treatment = new_p.treatment
                proj.bible = new_p.bible
                proj.board = new_p.board
                script_editor.value = proj.script
                refresh_scenes_ui()
                set_busy(False, f"🎉 Đã tạo xong {len(proj.board.scenes)} phân cảnh! Đang chuyển sang Tab 2...")
                show_snack(f"🎉 Hoàn tất {len(proj.board.scenes)} phân cảnh!")
                nav_bar.selected_index = 1
                switch_tab(1)
            except Exception as ex:
                set_busy(False, f"❌ Lỗi: {ex}")
                show_snack(str(ex)[:180], "#ef4444")
        threading.Thread(target=_job, daemon=True).start()

    btn_write_story = ft.ElevatedButton(
        "✨ 1. AI Viết Kịch Bản", bgcolor="#10b981", color="#ffffff", expand=True, height=44,
        on_click=run_write_story
    )
    btn_gen_board = ft.ElevatedButton(
        "🎬 2. Lên Phân Cảnh (JSON)", bgcolor="#2563eb", color="#ffffff", expand=True, height=44,
        on_click=run_generate_board
    )

    tab1_view = ft.Column([
        title_input,
        style_dropdown,
        ft.Row([ratio_dropdown, total_sec_input, clip_sec_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        mode_banner,
        ft.Row([video_path_text, btn_pick_video, btn_extract_video], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        idea_input,
        ft.Row([btn_write_story, btn_gen_board], spacing=8),
        script_editor,
        ft.Row([
            feedback_input,
            ft.ElevatedButton("🔄 Sửa", bgcolor="#374151", color="#ffffff", on_click=run_write_story)
        ]),
    ], spacing=10, visible=True)

    # =========================================================================
    # TAB 2: PHÂN CẢNH & NÚT MŨI TÊN COPY THEO ĐỢT 6 CẢNH (1-6, 7-12...)
    # =========================================================================
    tool_dropdown = ft.Dropdown(
        label="Chuẩn câu lệnh xuất ra (Google Flow hoặc Meta Muse)",
        value=TOOL_GOOGLE_FLOW,
        options=[ft.dropdown.Option(t) for t in AVAILABLE_VIDEO_TOOLS],
        bgcolor="#111827", border_color="#3b82f6", text_size=12,
    )

    scene_dropdown = ft.Dropdown(
        label="Chọn Phân cảnh để xem / sửa câu lệnh",
        options=[], bgcolor="#111827", border_color="#10b981", text_size=13
    )

    prompt_viewer = ft.TextField(
        label="Câu lệnh Prompt của cảnh đang chọn (Chống chảy cơ thể & Khóa khuôn mặt 100%)",
        multiline=True, min_lines=10, max_lines=15,
        bgcolor="#111827", border_color="#1f2937", text_size=12
    )

    scene_fix_input = ft.TextField(
        label="Yêu cầu AI sửa riêng cảnh này...",
        bgcolor="#111827", border_color="#1f2937", text_size=12, expand=True
    )

    batch_copy_menu = ft.PopupMenuButton(
        content=ft.Container(
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            bgcolor="#d97706", border_radius=8,
            content=ft.Row([
                ft.Text("📦 Copy Đợt 6 Cảnh ▼", color="#ffffff", weight=ft.FontWeight.BOLD, size=13),
            ], tight=True, spacing=6)
        ),
        items=[]
    )

    def copy_batch_scenes(batch_scenes: list, batch_idx: int, start_num: int, end_num: int):
        sync_project_from_ui()
        txt = compile_muse_batch_6_prompt(proj, batch_scenes, batch_idx)
        page.set_clipboard(txt)
        prompt_viewer.value = txt
        show_snack(f"📦 Đã Copy Đợt {batch_idx} (Cảnh {start_num} → {end_num}) vào bộ nhớ tạm!")
        page.update()

    def copy_all_scenes_at_once(_):
        sync_project_from_ui()
        if not proj.board or not proj.board.scenes:
            show_snack("⚠️ Chưa có phân cảnh nào!", "#ef4444")
            return
        txt = compile_all_image_prompts(proj)
        page.set_clipboard(txt)
        prompt_viewer.value = txt
        show_snack(f"📋 Đã Copy toàn bộ {len(proj.board.scenes)} phân cảnh!")
        page.update()

    def rebuild_batch_menu():
        batch_copy_menu.items.clear()
        if not proj.board or not proj.board.scenes:
            return
        batches = get_all_muse_batches_of_6(proj)
        for b_idx, b_scenes in enumerate(batches, 1):
            s_start = (b_idx - 1) * 6 + 1
            s_end = s_start + len(b_scenes) - 1
            batch_copy_menu.items.append(
                ft.PopupMenuItem(
                    text=f"📦 Copy Đợt {b_idx}: Cảnh {s_start} → Cảnh {s_end} ({len(b_scenes)} cảnh)",
                    on_click=lambda _, bs=b_scenes, bi=b_idx, st=s_start, en=s_end: copy_batch_scenes(bs, bi, st, en)
                )
            )
        batch_copy_menu.items.append(ft.PopupMenuItem())
        batch_copy_menu.items.append(
            ft.PopupMenuItem(
                text=f"📋 Copy Tất Cả {len(proj.board.scenes)} Phân Cảnh Cùng Lúc",
                on_click=copy_all_scenes_at_once
            )
        )

    def update_selected_scene_prompt():
        if not proj.board or not proj.board.scenes:
            prompt_viewer.value = ""
            return
        idx = max(0, min(selected_scene_idx[0], len(proj.board.scenes) - 1))
        sc = proj.board.scenes[idx]
        if is_google_flow_tool(tool_dropdown.value):
            prompt_viewer.value = compile_flow_prompt(proj, sc)
        else:
            prompt_viewer.value = compile_prompt(proj, sc)
        page.update()

    def on_scene_select(e):
        try:
            idx = int(scene_dropdown.value)
            selected_scene_idx[0] = idx
            update_selected_scene_prompt()
        except Exception:
            pass

    scene_dropdown.on_change = on_scene_select
    tool_dropdown.on_change = lambda _: update_selected_scene_prompt()

    def refresh_scenes_ui():
        scene_dropdown.options.clear()
        if proj.board and proj.board.scenes:
            for i, s in enumerate(proj.board.scenes):
                scene_dropdown.options.append(
                    ft.dropdown.Option(key=str(i), text=f"Cảnh {i+1:02d} ({s.id}) • {s.title} ({s.duration:g}s)")
                )
            scene_dropdown.value = "0"
            selected_scene_idx[0] = 0
            update_selected_scene_prompt()
            rebuild_batch_menu()
        page.update()

    def copy_single_scene(_):
        if not proj.board or not proj.board.scenes:
            show_snack("⚠️ Chưa có phân cảnh để copy!", "#ef4444")
            return
        update_selected_scene_prompt()
        sc = proj.board.scenes[selected_scene_idx[0]]
        page.set_clipboard(prompt_viewer.value)
        show_snack(f"✅ Đã Copy câu lệnh sạch của {sc.id}!")

    def ai_fix_current_scene(_):
        if not proj.board or not proj.board.scenes:
            show_snack("⚠️ Chưa có phân cảnh để sửa!", "#ef4444")
            return
        idx = selected_scene_idx[0]
        cur_sc = proj.board.scenes[idx]
        req = scene_fix_input.value.strip()
        def _job():
            try:
                set_busy(True, f"🛠️ AI đang sửa mềm & đồng bộ cảnh {cur_sc.id}...")
                client = get_client()
                new_sc = client.assist_scene(proj, cur_sc, req)
                proj.board.scenes[idx] = sanitize_scene_for_flow(new_sc)
                proj.board = auto_repair_board(proj.board, proj.total_seconds, proj.clip_seconds, proj.bible, proj.style)
                scene_fix_input.value = ""
                update_selected_scene_prompt()
                page.set_clipboard(prompt_viewer.value)
                set_busy(False, f"✅ Đã sửa xong {cur_sc.id} và tự động Copy!")
                show_snack(f"🛠️ Đã sửa & Copy {cur_sc.id}!")
            except Exception as ex:
                set_busy(False, f"❌ Lỗi: {ex}")
                show_snack(str(ex)[:180], "#ef4444")
        threading.Thread(target=_job, daemon=True).start()

    tab2_view = ft.Column([
        tool_dropdown,
        scene_dropdown,
        ft.Row([
            ft.ElevatedButton("📋 Copy Cảnh Này", bgcolor="#10b981", color="#ffffff", on_click=copy_single_scene, expand=True),
            batch_copy_menu,
        ], spacing=8),
        prompt_viewer,
        ft.Row([
            scene_fix_input,
            ft.ElevatedButton("🛠️ AI Sửa Cảnh", bgcolor="#0d9488", color="#ffffff", on_click=ai_fix_current_scene)
        ]),
    ], spacing=10, visible=False)

    # =========================================================================
    # TAB 3: CÀI ĐẶT API KEY
    # =========================================================================
    api_key_input = ft.TextField(
        label="Gemini API Key (Tự lưu trên điện thoại)",
        value=saved_api_key, password=True, can_reveal_password=True,
        bgcolor="#111827", border_color="#10b981"
    )

    model_dropdown = ft.Dropdown(
        label="Model AI", value=saved_model,
        options=[ft.dropdown.Option(m) for m in DEFAULT_MODELS],
        bgcolor="#111827", border_color="#1f2937"
    )

    temp_slider = ft.Slider(min=0.1, max=1.0, divisions=18, value=0.80, label="{value}")
    fallback_switch = ft.Switch(label="Tự động đổi sang Model dự phòng khi quá tải (503)", value=True)

    def save_settings(_):
        page.client_storage.set("gemini_api_key", api_key_input.value.strip())
        page.client_storage.set("gemini_model", model_dropdown.value)
        show_snack("💾 Đã lưu API Key và cài đặt trên thiết bị!")

    tab3_view = ft.Column([
        ft.Text("⚙️ Cấu hình Gemini API (Mobile APK)", size=16, weight=ft.FontWeight.BOLD, color="#10b981"),
        api_key_input,
        model_dropdown,
        ft.Text("Độ sáng tạo (Temperature):", size=13, color="#9ca3af"),
        temp_slider,
        fallback_switch,
        ft.ElevatedButton("💾 Lưu Cài Đặt API Key", bgcolor="#10b981", color="#ffffff", height=44, on_click=save_settings),
    ], spacing=12, visible=False)

    def switch_tab(idx: int):
        tab1_view.visible = (idx == 0)
        tab2_view.visible = (idx == 1)
        tab3_view.visible = (idx == 2)
        page.update()

    nav_bar = ft.NavigationBar(
        selected_index=0,
        bgcolor="#111827",
        on_change=lambda e: switch_tab(e.control.selected_index),
        destinations=[
            ft.NavigationDestination(icon=ft.icons.EDIT_DOCUMENT, label="1. Kịch Bản"),
            ft.NavigationDestination(icon=ft.icons.MOVIE_FILTER, label="2. Phân Cảnh & Copy"),
            ft.NavigationDestination(icon=ft.icons.SETTINGS, label="3. Cài Đặt API"),
        ]
    )
    page.navigation_bar = nav_bar

    page.add(
        ft.Row([
            ft.Text("🎬 QUẢNG AI STUDIO • MOBILE PRO", size=18, weight=ft.FontWeight.BOLD, color="#10b981"),
        ]),
        progress_bar,
        status_text,
        ft.Divider(color="#1f2937", height=10),
        tab1_view,
        tab2_view,
        tab3_view,
    )


if __name__ == "__main__":
    ft.app(target=main)
