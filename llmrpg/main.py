from pathlib import Path
import argparse
import logging
from typing import Any
import pygame
from pytmx import load_pygame
import pytmx
from lxml import etree

def parse_args():
    parser = argparse.ArgumentParser(description="Pygame Tiled Map Renderer")
    parser.add_argument('--load-map', required=True, help='Path to the .tmx Tiled map file')
    parser.add_argument('--log', choices=['debug', 'info', 'warning', 'error'], 
                      default='info', help='Set logging level (default: info)')
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




class Tileset:
    def __init__(self, path: str):
        """Load and parse a Tiled tileset XML file"""
        # Parse XML with lxml
        tree = etree.parse(path)
        root = tree.getroot()
        
        # Extract basic tileset properties
        self.name = root.get("name", "untitled")
        self.tile_width = int(root.get("tilewidth", 16))
        self.tile_height = int(root.get("tileheight", 16))
        self.tile_count = int(root.get("tilecount", 0))
        self.columns = int(root.get("columns", 0))
        
        # Get the image source path
        image_node = root.find("image")
        if image_node is not None:
            self.image_source = image_node.get("source")
            self.image_width = int(image_node.get("width", 0))
            self.image_height = int(image_node.get("height", 0))
        else:
            self.image_source = None
            self.image_width = 0
            self.image_height = 0

        # Parse individual tile properties and animations
        self.tiles = {}
        for tile_node in root.findall("tile"):
            tile_id = int(tile_node.get("id"))
            tile_type = tile_node.get("type", "")
            
            # Parse properties
            props = {}
            properties_node = tile_node.find("properties")
            if properties_node is not None:
                for prop_node in properties_node.findall("property"):
                    props[prop_node.get("name")] = prop_node.get("value")
            
            # Parse animations
            animation = []
            anim_node = tile_node.find("animation")
            if anim_node is not None:
                for frame_node in anim_node.findall("frame"):
                    animation.append({
                        "tileid": int(frame_node.get("tileid")),
                        "duration": int(frame_node.get("duration"))
                    })
            
            self.tiles[tile_id] = {
                "type": tile_type,
                "properties": props,
                "animation": animation
            }

        # Group animations by imageset and direction
        self.animations = {}
        for tile in self.tiles.values():
            if tile["animation"]:
                imageset = tile["properties"].get("imageset", "unknown")
                direction = tile["properties"].get("direction", "unknown")
                
                if imageset not in self.animations:
                    self.animations[imageset] = {}
                if direction not in self.animations[imageset]:
                    self.animations[imageset][direction] = {}
                
                self.animations[imageset][direction].update(**{
                    "frames": tile["animation"],
                    "type": tile["type"],
                    "properties": tile["properties"]
                })

    def __repr__(self):
        """Return a string representation of the tileset"""
        return (
            f"<Tileset {self.name} ({self.tile_width}x{self.tile_height}) "
            f"tiles={self.tile_count} cols={self.columns} "
            f"image='{self.image_source}' "
            f"tiles_with_props={len([t for t in self.tiles.values() if t['properties']])}>"
        )


class GameData:
    def __init__(self):
        self.characters = Tileset("sprites/characters.tsx")


class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, tmx_data, gamedata: GameData):
        super().__init__()
        self.tile_width = tmx_data.tilewidth
        self.tile_height = tmx_data.tileheight

        # Store initial tile position
        self.tile_x = x
        self.tile_y = y

        # Calculate pixel position based on tile position
        self.x = x * self.tile_width
        self.y = y * self.tile_height

        # Load character spritesheet and setup animation
        logging.debug(f"Loading spritesheet from: sprites/characters.png")
        self.spritesheet = pygame.image.load("sprites/characters.png").convert_alpha()
        self.gamedata = gamedata
        logging.debug(f"Spritesheet loaded, size: {self.spritesheet.get_size()}")
        
        self.frames = [
            self.spritesheet.subsurface(pygame.Rect(0, 0, 16, 16)),
            self.spritesheet.subsurface(pygame.Rect(16, 0, 16, 16)),
            self.spritesheet.subsurface(pygame.Rect(32, 0, 16, 16))
        ]
        # self.frames = self.gamedata.characters.animations["boy"]["down"]
        logging.debug(f"Loaded {len(self.frames)} animation frames")
        for i, frame in enumerate(self.frames):
            logging.debug(f"Frame {i} size: {frame.get_size()}")
        self.current_frame = 0
        self.animation_time = 0
        self.animation_speed = 160  # ms per frame
        self.image = self.frames[self.current_frame]
        self.rect = self.image.get_rect(topleft=(self.x, self.y))

        # Store the map data
        self.tmx_data = tmx_data
        self.tile_layers = [layer for layer in tmx_data.visible_layers
                           if isinstance(layer, pytmx.TiledTileLayer)]

        # Track movement
        self.moving = False
        self.speed = 5  # pixels per frame

        self.collision_objects = []
        for obj in tmx_data.get_layer_by_name("Objects"):
            if obj.type == "wall":
                # Create a rect for the collision object
                rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
                self.collision_objects.append(rect)

    def move_to(self, new_x, new_y):
        """Attempt to move to new tile position"""
        if self._check_collision(new_x, new_y):
            return False  # Collision occurred

        self.moving = True
        self.target_x = new_x * self.tile_width
        self.target_y = new_y * self.tile_height
        self.target_tile_x = new_x
        self.target_tile_y = new_y
        return True

    def _check_collision(self, new_x, new_y):
        """Check collisions with both tiles and objects"""
        print(f"Checking collision at ({new_x}, {new_y})")
        # Convert tile coordinates to pixel coordinates
        target_rect = pygame.Rect(
            new_x * self.tile_width,
            new_y * self.tile_height,
            self.tile_width,
            self.tile_height
        )

        # Check map boundaries
        if (new_x < 0 or new_x >= self.tmx_data.width or
            new_y < 0 or new_y >= self.tmx_data.height):
            return True

        # Check object collisions
        for obj_rect in self.collision_objects:
            if target_rect.colliderect(obj_rect):
                return True

        return False

    def update(self):
        """Update player position animation"""
        # Update animation
        self.animation_time += 1000/60  # Assuming 60 FPS
        if self.animation_time >= self.animation_speed:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.image = self.frames[self.current_frame]
            self.animation_time = 0
            logging.debug(f"Switched to frame {self.current_frame}")

        if not self.moving:
            return
        
        logging.debug(f"Moving from ({self.tile_x},{self.tile_y}) to ({self.target_tile_x},{self.target_tile_y})")

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


def main():
    args = parse_args()
    logging.basicConfig(level=args.log.upper(),
                      format='%(asctime)s - %(levelname)s - %(message)s')
    map_path = args.load_map

    pygame.init()

    # Set up temporary small display for loading
    screen = pygame.display.set_mode((1, 1))

    tmx_data = load_pygame(map_path)

    characters = Tileset("sprites/characters.tsx")

    # Resize display to map size
    width = tmx_data.width * tmx_data.tilewidth
    height = tmx_data.height * tmx_data.tileheight
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption(f"Rendering {map_path}")

    clock = pygame.time.Clock()
    running = True

    gamedata = GameData()

    # Start player in a reasonable position
    player = Player(5, 5, tmx_data, gamedata)

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

        # Draw player after map
        screen.blit(player.image, player.rect)

        # Draw debug info
        font = pygame.font.SysFont(None, 24)
        text = font.render(f"Pos: {player.tile_x}, {player.tile_y}", True, (255, 255, 255))
        screen.blit(text, (10, 10))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
