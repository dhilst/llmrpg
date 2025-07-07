import logging
import pytmx
import pygame 

def draw_mouse_position(surface):
    """Draw current mouse position and coordinates"""
    mouse_pos = pygame.mouse.get_pos()
    font = pygame.font.Font(None, 14)

    # Create text
    text = font.render(f"{mouse_pos}", True, (255, 255, 255))


    # Draw to screen
    surface.blit(text, (20, 150))

    # Draw crosshair at mouse position
    pygame.draw.line(surface, (255, 0, 0),
                     (mouse_pos[0] - 10, mouse_pos[1]),
                     (mouse_pos[0] + 10, mouse_pos[1]), 1)
    pygame.draw.line(surface, (255, 0, 0),
                     (mouse_pos[0], mouse_pos[1] - 10),
                     (mouse_pos[0], mouse_pos[1] + 10), 1)


def draw_player_stats(screen, player1, player2, height, width, font):
    """Draw player stats in bottom right corner"""
    stats = [
        f"Player 1: {player1.imageset} (Lvl {player1.stats.level})",
        f"Health: {player1.health}/{player1.stats.max_health}",
        f"XP: {player1.stats.experience}/{player1.stats.experience_to_level}",
        f"ATK/DEF: {player1.stats.attack}/{player1.stats.defence}",
        "",
        f"Player 2: {player2.imageset} (Lvl {player2.stats.level})",
        f"Health: {player2.health}/{player2.stats.max_health}",
        f"XP: {player2.stats.experience}/{player2.stats.experience_to_level}",
        f"ATK/DEF: {player2.stats.attack}/{player2.stats.defence}"
    ]

    # Calculate position (bottom right with padding)
    padding = 10
    line_height = 20
    start_y = height - (len(stats) * line_height) - padding

    for i, stat in enumerate(stats):
        text = font.render(stat, True, (255, 255, 255))
        text_rect = text.get_rect(
            bottomright=(width - padding,
                         start_y + (i * line_height) + line_height)
        )
        screen.blit(text, text_rect)


def draw_map(screen, tmx_data):
    # Draw all visible layers in proper order
    for layer in tmx_data.visible_layers:
        if isinstance(layer, pytmx.TiledTileLayer):
            for x, y, gid in layer: # type: ignore
                tile = tmx_data.get_tile_image_by_gid(gid)
                if tile:
                    screen.blit(tile,
                        (x * tmx_data.tilewidth + layer.offsetx,
                         y * tmx_data.tileheight + layer.offsety))


def draw_actors(screen, actors):
    live_actors = [actor for actor in actors if not actor.is_dead()]
    dead_actors = [actor for actor in actors if actor.is_dead()]
    for actor in dead_actors:
        actor.draw(screen)

    for actor in live_actors:
        actor.draw(screen)
