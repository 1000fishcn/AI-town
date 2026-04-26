extends CanvasLayer

class_name DialogueUI

signal message_submitted(npc, text: String)
signal closed

var current_npc = null
var waiting := false

var hint_label: Label
var dialogue_panel: PanelContainer
var name_label: Label
var log_text: RichTextLabel
var input_line: LineEdit
var send_button: Button


func _ready() -> void:
	_build_hint()
	_build_dialogue_panel()
	hide_hint()
	close_dialogue()


func show_hint(npc) -> void:
	if npc == null:
		hide_hint()
		return
	hint_label.text = "按 E 和 " + npc.npc_name + " 对话"
	hint_label.visible = true


func hide_hint() -> void:
	hint_label.visible = false


func open_dialogue(npc) -> void:
	current_npc = npc
	dialogue_panel.visible = true
	hide_hint()
	name_label.text = npc.npc_name
	if log_text.text.is_empty():
		add_system_message("正在和 " + npc.npc_name + " 对话。输入文字后按 Enter 或发送。")
	input_line.grab_focus()


func close_dialogue() -> void:
	dialogue_panel.visible = false
	current_npc = null
	waiting = false
	_set_input_enabled(true)
	closed.emit()


func add_user_message(text: String) -> void:
	log_text.append_text("[color=#dff6ff]你：[/color]" + _escape_bbcode(text) + "\n")
	_scroll_to_bottom()


func add_npc_message(npc_name: String, text: String) -> void:
	log_text.append_text("[color=#ffe08a]" + _escape_bbcode(npc_name) + "：[/color]" + _escape_bbcode(text) + "\n")
	_scroll_to_bottom()


func add_system_message(text: String) -> void:
	log_text.append_text("[color=#9fb3c8]" + _escape_bbcode(text) + "[/color]\n")
	_scroll_to_bottom()


func set_waiting(value: bool) -> void:
	waiting = value
	_set_input_enabled(not waiting)
	send_button.text = "等待中..." if waiting else "发送"


func _unhandled_input(event: InputEvent) -> void:
	if dialogue_panel.visible and event.is_action_pressed("ui_cancel"):
		close_dialogue()
		get_viewport().set_input_as_handled()


func _submit_current_text() -> void:
	if current_npc == null or waiting:
		return
	var text := input_line.text.strip_edges()
	if text.is_empty():
		return
	input_line.text = ""
	message_submitted.emit(current_npc, text)


func _build_hint() -> void:
	hint_label = Label.new()
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.add_theme_font_size_override("font_size", 18)
	hint_label.add_theme_color_override("font_color", Color("#f8f1e5"))
	hint_label.add_theme_color_override("font_shadow_color", Color("#1d1d1d"))
	hint_label.add_theme_constant_override("shadow_offset_x", 2)
	hint_label.add_theme_constant_override("shadow_offset_y", 2)
	hint_label.anchor_left = 0.35
	hint_label.anchor_right = 0.65
	hint_label.anchor_top = 0.05
	hint_label.anchor_bottom = 0.12
	add_child(hint_label)


func _build_dialogue_panel() -> void:
	dialogue_panel = PanelContainer.new()
	dialogue_panel.anchor_left = 0.08
	dialogue_panel.anchor_right = 0.92
	dialogue_panel.anchor_top = 0.64
	dialogue_panel.anchor_bottom = 0.96
	dialogue_panel.add_theme_stylebox_override("panel", _panel_style(Color("#1f2933"), Color("#f2cc8f"), 4))
	add_child(dialogue_panel)

	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 14)
	margin.add_theme_constant_override("margin_right", 14)
	margin.add_theme_constant_override("margin_top", 10)
	margin.add_theme_constant_override("margin_bottom", 10)
	dialogue_panel.add_child(margin)

	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 8)
	margin.add_child(layout)

	name_label = Label.new()
	name_label.add_theme_font_size_override("font_size", 20)
	name_label.add_theme_color_override("font_color", Color("#ffe08a"))
	layout.add_child(name_label)

	log_text = RichTextLabel.new()
	log_text.bbcode_enabled = true
	log_text.fit_content = false
	log_text.scroll_following = true
	log_text.custom_minimum_size = Vector2(0, 104)
	log_text.add_theme_color_override("default_color", Color("#f8f1e5"))
	layout.add_child(log_text)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	layout.add_child(row)

	input_line = LineEdit.new()
	input_line.placeholder_text = "输入你想说的话..."
	input_line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	input_line.text_submitted.connect(func(_text: String): _submit_current_text())
	row.add_child(input_line)

	send_button = Button.new()
	send_button.text = "发送"
	send_button.pressed.connect(_submit_current_text)
	row.add_child(send_button)


func _set_input_enabled(enabled: bool) -> void:
	input_line.editable = enabled
	send_button.disabled = not enabled
	if enabled and dialogue_panel.visible:
		input_line.grab_focus()


func _scroll_to_bottom() -> void:
	log_text.scroll_to_line(999999)


func _panel_style(bg_color: Color, border_color: Color, border_width: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg_color
	style.border_color = border_color
	style.border_width_left = border_width
	style.border_width_right = border_width
	style.border_width_top = border_width
	style.border_width_bottom = border_width
	style.corner_radius_top_left = 0
	style.corner_radius_top_right = 0
	style.corner_radius_bottom_left = 0
	style.corner_radius_bottom_right = 0
	return style


func _escape_bbcode(text: String) -> String:
	return text.replace("[", "\\[").replace("]", "\\]")
