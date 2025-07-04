import argparse
import pygame
from pytmx import load_pygame
import pytmx

def parse_args():
    parser = argparse.ArgumentParser(description="Pygame Tiled Map Renderer")
    parser.add_argument('--load-map', required=True, help='Path to the .tmx Tiled map file')
    return parser.parse_args()

                                                                                            
def draw_map(screen, tmx_data):                                                             
    # Draw all visible layers in proper order                                               
    for layer in tmx_data.visible_layers:                                                   
        if isinstance(layer, pytmx.TiledTileLayer):                                         
            for x, y, gid in layer:                                                         
                tile = tmx_data.get_tile_image_by_gid(gid)                                  
                if tile:                                                                    
                    # Convert tile to use alpha transparency                                
                    tile = tile.convert_alpha()                                             
                    screen.blit(tile,                                                       
                        (x * tmx_data.tilewidth + layer.offsetx,                            
                         y * tmx_data.tileheight + layer.offsety))                          
                                                                    

class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, tmx_data):
        super().__init__()
        self.tile_width = tmx_data.tilewidth
        self.tile_height = tmx_data.tileheight

        # Store initial tile position
        self.tile_x = x
        self.tile_y = y

        # Calculate pixel position based on tile position
        self.x = x * self.tile_width
        self.y = y * self.tile_height

        # Create a simple rectangle player (replace with your own image)
        self.image = pygame.Surface((self.tile_width, self.tile_height))
        self.image.fill((255, 0, 0))  # Red rectangle
        self.rect = self.image.get_rect(topleft=(self.x, self.y))

        # Store the map data
        self.tmx_data = tmx_data
        self.tile_layers = [layer for layer in tmx_data.visible_layers
                           if isinstance(layer, pytmx.TiledTileLayer)]

        # Track movement
        self.moving = False
        self.speed = 5  # pixels per frame

    def move_to(self, new_x, new_y):
        """Attempt to move to new tile position"""
        # if self._check_collision(new_x, new_y):
        #     return False  # Collision occurred

        self.moving = True
        self.target_x = new_x * self.tile_width
        self.target_y = new_y * self.tile_height
        self.target_tile_x = new_x
        self.target_tile_y = new_y
        return True

    def _check_collision(self, x, y):
        """Check if target position is collidable"""
        # Check boundaries first
        if (x < 0 or x >= self.tmx_data.width or
            y < 0 or y >= self.tmx_data.height):
            return True

        # Check each visible tile layer for collisions
        for layer in self.tile_layers:
            # Get the GID of the target tile
            for lx, ly, gid in layer:
                if lx == x and ly == y and gid != 0:
                    return True
        return False

    def update(self):
        """Update player position animation"""
        if not self.moving:
            return

        # Calculate direction and step
        dx = self.target_x - self.x
        dy = self.target_y - self.y

        # Only move if we're not close enough to snap
        if abs(dx) > 2 or abs(dy) > 2:
            move_x = self.x + (dx / abs(dx)) * min(self.speed, abs(dx)) if dx != 0 else self.x
            move_y = self.y + (dy / abs(dy)) * min(self.speed, abs(dy)) if dy != 0 else self.y
            self.x = move_x
            self.y = move_y
            self.rect.topleft = (int(move_x), int(move_y))
        else:
            # We're close enough, snap to target position
            self.x = self.target_x
            self.y = self.target_y
            self.rect.topleft = (int(self.x), int(self.y))
            self.tile_x = self.target_tile_x
            self.tile_y = self.target_tile_y
            self.moving = False

    def draw(self, screen):
        screen.blit(self.image, (self.x, self.y))

def main():
    args = parse_args()
    map_path = args.load_map

    pygame.init()

    # Set up temporary small display for loading
    screen = pygame.display.set_mode((1, 1))

    tmx_data = load_pygame(map_path)

    # Resize display to map size
    width = tmx_data.width * tmx_data.tilewidth
    height = tmx_data.height * tmx_data.tileheight
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"Rendering {map_path}")

    clock = pygame.time.Clock()
    running = True

    # Start player in a reasonable position
    player = Player(5, 5, tmx_data)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and not player.moving:
                if event.key == pygame.K_LEFT:
                    player.move_to(player.tile_x - 1, player.tile_y)
                elif event.key == pygame.K_RIGHT:
                    player.move_to(player.tile_x + 1, player.tile_y)
                elif event.key == pygame.K_UP:
                    player.move_to(player.tile_x, player.tile_y - 1)
                elif event.key == pygame.K_DOWN:
                    player.move_to(player.tile_x, player.tile_y + 1)
                elif event.key == pygame.K_r:  # Reset position
                    player = Player(5, 5, tmx_data)

        player.update()

        screen.fill((0, 0, 0))
        draw_map(screen, tmx_data)
        player.draw(screen)

        # Draw debug info
        font = pygame.font.SysFont(None, 24)
        text = font.render(f"Pos: {player.tile_x}, {player.tile_y}", True, (255, 255, 255))
        screen.blit(text, (10, 10))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
