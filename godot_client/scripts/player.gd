extends CharacterBody2D

class_name Player

signal nearby_npc_changed(npc)
signal interaction_requested(npc)

@export var speed := 150.0
@export var map_min := Vector2(24, 32)
@export var map_max := Vector2(936, 592)

var can_move := true
var facing := Vector2.DOWN
var nearby_npcs: Array = []

@onready var interaction_area: Area2D = Area2D.new()


func _ready() -> void:
	name = "Player"
	z_index = 10
	_add_collision()
	_add_interaction_area()


func _physics_process(_delta: float) -> void:
	if not can_move:
		velocity = Vector2.ZERO
		return

	var input_vector := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if input_vector.length() > 0.0:
		facing = input_vector.normalized()

	velocity = input_vector.normalized() * speed
	move_and_slide()
	position = position.clamp(map_min, map_max)
	queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("interact") and can_move:
		var npc = get_nearest_npc()
		if npc != null:
			interaction_requested.emit(npc)


func get_nearest_npc():
	if nearby_npcs.is_empty():
		return null

	var best_npc = null
	var best_distance := INF
	for npc in nearby_npcs:
		if not is_instance_valid(npc):
			continue
		var distance := global_position.distance_to(npc.global_position)
		if distance < best_distance:
			best_distance = distance
			best_npc = npc
	return best_npc


func _draw() -> void:
	# 用矩形直接画像素风角色，后面可以替换成 AnimatedSprite2D。
	draw_rect(Rect2(Vector2(-7, -20), Vector2(14, 10)), Color("#f3c69a"))
	draw_rect(Rect2(Vector2(-8, -22), Vector2(16, 5)), Color("#4b2a1b"))
	draw_rect(Rect2(Vector2(-9, -10), Vector2(18, 18)), Color("#3d7ee8"))
	draw_rect(Rect2(Vector2(-13, -7), Vector2(4, 13)), Color("#f3c69a"))
	draw_rect(Rect2(Vector2(9, -7), Vector2(4, 13)), Color("#f3c69a"))
	draw_rect(Rect2(Vector2(-8, 8), Vector2(6, 9)), Color("#2e3440"))
	draw_rect(Rect2(Vector2(2, 8), Vector2(6, 9)), Color("#2e3440"))

	var eye_y := -16
	if abs(facing.x) > abs(facing.y):
		var eye_x := 4 if facing.x > 0 else -6
		draw_rect(Rect2(Vector2(eye_x, eye_y), Vector2(2, 2)), Color("#1f1f1f"))
	else:
		draw_rect(Rect2(Vector2(-4, eye_y), Vector2(2, 2)), Color("#1f1f1f"))
		draw_rect(Rect2(Vector2(3, eye_y), Vector2(2, 2)), Color("#1f1f1f"))


func _add_collision() -> void:
	var shape := RectangleShape2D.new()
	shape.size = Vector2(16, 14)

	var collision := CollisionShape2D.new()
	collision.position = Vector2(0, 8)
	collision.shape = shape
	add_child(collision)


func _add_interaction_area() -> void:
	var shape := CircleShape2D.new()
	shape.radius = 52

	var collision := CollisionShape2D.new()
	collision.shape = shape

	interaction_area.name = "InteractionArea"
	interaction_area.monitoring = true
	interaction_area.add_child(collision)
	interaction_area.body_entered.connect(_on_body_entered)
	interaction_area.body_exited.connect(_on_body_exited)
	add_child(interaction_area)


func _on_body_entered(body: Node) -> void:
	if body.is_in_group("npc") and not nearby_npcs.has(body):
		nearby_npcs.append(body)
		nearby_npc_changed.emit(get_nearest_npc())


func _on_body_exited(body: Node) -> void:
	if nearby_npcs.has(body):
		nearby_npcs.erase(body)
		nearby_npc_changed.emit(get_nearest_npc())
