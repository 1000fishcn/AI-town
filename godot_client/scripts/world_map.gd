extends Node2D

class_name WorldMap

const TILE_SIZE := 16
const MAP_WIDTH := 60
const MAP_HEIGHT := 38


func _ready() -> void:
	z_index = 0
	queue_redraw()


func _draw() -> void:
	_draw_grass()
	_draw_paths()
	_draw_water()
	_draw_houses()
	_draw_trees()


func _draw_grass() -> void:
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			var color := Color("#7fbe64")
			if (x * 11 + y * 7) % 9 == 0:
				color = Color("#76b85e")
			if (x * 5 + y * 13) % 17 == 0:
				color = Color("#8acb70")
			draw_rect(Rect2(Vector2(x, y) * TILE_SIZE, Vector2(TILE_SIZE, TILE_SIZE)), color)


func _draw_paths() -> void:
	_draw_tile_rect(0, 18, 60, 4, Color("#d7b377"))
	_draw_tile_rect(28, 0, 5, 38, Color("#d7b377"))
	_draw_tile_rect(2, 19, 56, 1, Color("#c99b62"))
	_draw_tile_rect(30, 2, 1, 34, Color("#c99b62"))


func _draw_water() -> void:
	_draw_tile_rect(48, 4, 8, 7, Color("#4da6d8"))
	_draw_tile_rect(49, 5, 6, 5, Color("#5db9e8"))
	for index in range(5):
		draw_rect(Rect2(Vector2(50 + index, 7) * TILE_SIZE, Vector2(8, 2)), Color("#bdefff"))


func _draw_houses() -> void:
	_draw_house(Vector2(8, 8), Color("#b56576"), Color("#f6bd60"))
	_draw_house(Vector2(38, 9), Color("#6d597a"), Color("#f7ede2"))
	_draw_house(Vector2(12, 26), Color("#52796f"), Color("#f2cc8f"))


func _draw_house(tile_pos: Vector2, roof_color: Color, wall_color: Color) -> void:
	var origin := tile_pos * TILE_SIZE
	draw_rect(Rect2(origin + Vector2(0, 20), Vector2(80, 48)), wall_color)
	draw_rect(Rect2(origin + Vector2(-8, 8), Vector2(96, 18)), roof_color)
	draw_rect(Rect2(origin + Vector2(32, 44), Vector2(16, 24)), Color("#5c4033"))
	draw_rect(Rect2(origin + Vector2(12, 34), Vector2(14, 12)), Color("#88c0d0"))
	draw_rect(Rect2(origin + Vector2(54, 34), Vector2(14, 12)), Color("#88c0d0"))


func _draw_trees() -> void:
	var positions := [
		Vector2(5, 5), Vector2(20, 6), Vector2(43, 4), Vector2(54, 15),
		Vector2(5, 29), Vector2(24, 30), Vector2(41, 27), Vector2(52, 30),
		Vector2(18, 13), Vector2(36, 23)
	]
	for tile_pos in positions:
		_draw_tree(tile_pos)


func _draw_tree(tile_pos: Vector2) -> void:
	var origin := tile_pos * TILE_SIZE
	draw_rect(Rect2(origin + Vector2(10, 18), Vector2(8, 18)), Color("#7b4f2a"))
	draw_rect(Rect2(origin + Vector2(0, 4), Vector2(28, 20)), Color("#3d8f4f"))
	draw_rect(Rect2(origin + Vector2(4, 0), Vector2(20, 12)), Color("#4daa57"))


func _draw_tile_rect(x: int, y: int, width: int, height: int, color: Color) -> void:
	draw_rect(Rect2(Vector2(x, y) * TILE_SIZE, Vector2(width, height) * TILE_SIZE), color)
