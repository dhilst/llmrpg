import pytmx

class PositionValidator:
    def __init__(self, tmx_data: pytmx.TiledMap):
        self.tmx_data = tmx_data

    def __call__(self, x: int , y : int) -> tuple[int, int]:
        """Ensure tile position is within map boundaries"""
        max_tiles_x = self.tmx_data.width
        max_tiles_y = self.tmx_data.height

        # Clamp the position to map boundaries
        return (max(0, min(x, max_tiles_x - 1 if max_tiles_x > 0 else 0)),
                max(0, min(y, max_tiles_y - 1 if max_tiles_y > 0 else 0)))

    def is_valid(self, x: int, y: int) -> bool:
        new_x, new_y = self(x, y)
        return new_x == x and new_y == y


