import pygame

class Camera:
    WIDTH_TILES = 12
    HEIGHT_TILES = 12

    def __init__(self, width_px, height_px):
        self.rect = pygame.Rect(0, 0, width_px, height_px)

    def update(self, target_rect: pygame.Rect, map_width_px: int, map_height_px: int):
        # Center on player
        self.rect.center = target_rect.center

        # Clamp to map bounds
        self.rect.left = max(0, min(self.rect.left, map_width_px - self.rect.width))
        self.rect.top = max(0, min(self.rect.top, map_height_px - self.rect.height))

    def apply(self, target_rect: pygame.Rect) -> pygame.Rect:
        """Shift a rect by the camera offset"""
        return target_rect.move(-self.rect.left, -self.rect.top)
