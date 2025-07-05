from dataclasses import dataclass
import random 
from itertools import chain
from pathlib import Path
import argparse
import logging
from typing import Dict, Iterable, Optional
import pygame
from pytmx import load_pygame
import pytmx
from lxml import etree # type: ignore

def parse_args():
    parser = argparse.ArgumentParser(description="Pygame Tiled Map Renderer")
    parser.add_argument('--load-map', required=True, help='Path to the .tmx Tiled map file')
    parser.add_argument('--log', choices=['debug', 'info', 'warning', 'error'], 
                      default='info', help='Set logging level (default: info)')
    return parser.parse_args()


class PositionValidator:
    def __init__(self, tmx_data):
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


class Tileset:
    def __init__(self, filpath: str):
        """Load and parse a Tiled tileset XML file"""
        path = Path(filpath)
        self.spritesheet = pygame.image.load(path.with_suffix(".png")).convert_alpha()
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

    def frames(self, imageset: str):
        """
        Return a dict of direction to list of animation frames for the given imageset.
        e.g. { "down": [frame1, frame2, ...], "up": [...], ... }
        """
        frames_dict = {}
        if imageset not in self.animations:
            return frames_dict  # empty dict if imageset unknown

        for direction, anim_data in self.animations[imageset].items():
            frames_list = []
            for frame in anim_data["frames"]:
                tileid = frame["tileid"]
                x = (tileid % self.columns) * self.tile_width
                y = (tileid // self.columns) * self.tile_height
                rect = pygame.Rect(x, y, self.tile_width, self.tile_height)
                frames_list.append(self.spritesheet.subsurface(rect))
            frames_dict[direction] = frames_list

        return frames_dict

    def __repr__(self):
        """Return a string representation of the tileset"""
        return (
            f"<Tileset {self.name} ({self.tile_width}x{self.tile_height}) "
            f"tiles={self.tile_count} cols={self.columns} "
            f"image='{self.image_source}' "
            f"tiles_with_props={len([t for t in self.tiles.values() if t['properties']])}>"
        )



class GameData:
    def __init__(self, tmx_data: pytmx.TiledMap):
        self.tmx_data = tmx_data
        self.objectlayer = self._get_object_layer()
        self.spawn_areas = self._load_spawn_areas()  # Dictionary of spawn areas
        self.characters = Tileset("sprites/characters.tsx")
        self.collision_objects = []
        # get_layer_by_name returns an  TiledObjectGroup, not int, which is interable
        # the typehint says it returns int for some reason, so I'm skipping typechecking here
        for obj in tmx_data.get_layer_by_name("Objects"): # type: ignore
            if obj.type == "wall":
                # Create a rect for the collision object
                rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
                self.collision_objects.append(rect)
        
    def _get_object_layer(self) -> Optional[pytmx.TiledObjectGroup]:
        """Find and return the object layer from the TMX data."""
        for layer in self.tmx_data.layers:
            if isinstance(layer, pytmx.TiledObjectGroup):
                return layer
        return None
    
    def _load_spawn_areas(self) -> Dict[str, pygame.Rect]:
        """
        Load all spawn areas from the object layer.
        Returns dictionary with {spawn_name: pygame.Rect}
        """
        spawns = {}
        
        if not self.objectlayer:
            return spawns
            
        for obj in self.objectlayer:
            if obj.type == "spawn":
                spawns[obj.name] = pygame.Rect(
                    obj.x, 
                    obj.y, 
                    obj.width, 
                    obj.height
                )
        
        return spawns
    
    def get_spawn_area(self, name: str) -> Optional[pygame.Rect]:
        """Get a specific spawn area by name"""
        return self.spawn_areas.get(name)
    
    def get_player_spawn(self) -> Optional[pygame.Rect]:
        """Convenience method to get player spawn"""
        return self.get_spawn_area("player")
    
    def get_enemy_spawns(self) -> Dict[str, pygame.Rect]:
        """Get all non-player spawn areas"""
        return {
            name: rect 
            for name, rect in self.spawn_areas.items() 
            if name != "player"
        }


@dataclass
class Stats:
    attack: int = 10
    defence: int = 5
    max_health: int = 100
    level: int = 1
    experience: int = 0
    experience_to_level: int = 15
    
    def add_experience(self, amount: int) -> bool:
        """Add experience and return True if leveled up"""
        self.experience += amount
        if self.experience >= self.experience_to_level:
            self.level_up()
            return True
        return False
    
    def level_up(self):
        """Increase stats when leveling up"""
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * 1.5)  # Increase required XP
        self.max_health += 20
        self.attack += 2
        self.defence += 2

class Actor(pygame.sprite.Sprite):
    def __init__(self, x, y, imageset: str, gamedata: GameData, stats: Stats):
        super().__init__()

        self.last_move_time = 0  # Track when mob last moved
        self.move_cooldown = 1000  # 3 seconds in milliseconds

        self.gamedata = gamedata
        self.imageset = imageset
        self.tile_width = gamedata.tmx_data.tilewidth
        self.tile_height = gamedata.tmx_data.tileheight
        self.stats = stats

        # Store initial tile position
        self.tile_x = x
        self.tile_y = y

        # Calculate pixel position based on tile position
        self.x = x * self.tile_width
        self.y = y * self.tile_height

        # Load character spritesheet and setup animation
        logging.debug(f"Loading spritesheet from: sprites/characters.png")
        
        self.frames = self.gamedata.characters.frames(self.imageset)  # dict: direction -> frames list
        self.direction = "down"  # default direction

        # fallback in case no animation frames for direction
        if self.direction not in self.frames:
            # Just pick any available direction or empty list
            self.direction = next(iter(self.frames)) if self.frames else None

        self.current_frame = 0
        self.animation_time = 0
        self.animation_speed = 160  # ms per frame

        # Set initial image
        if self.direction and self.frames.get(self.direction):
            self.image = self.frames[self.direction][self.current_frame]
        else:
            self.image = pygame.Surface((self.tile_width, self.tile_height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(self.x, self.y))

        # Store the map data
        self.tile_layers = [layer for layer in gamedata.tmx_data.visible_layers
                           if isinstance(layer, pytmx.TiledTileLayer)]

        # Track movement
        self.moving = False
        self.speed = 5  # pixels per frame

        self.health = 100
        self.invincible = False
        self.invincibility_time = 1000  # 1 second invincibility after hit
        self.last_hit_time = 0

    def calculate_damage(self, target) -> int:
        """Calculate damage dealt to target"""
        base_damage = max(1, self.stats.attack - target.stats.defence // 2)
        return random.randint(base_damage // 2, base_damage)

    def attack_target(self, target, current_time: int):
        """Attack another actor"""
        if self.invincible or target.invincible:
            return False
            
        damage = self.calculate_damage(target)
        target.take_damage(damage, current_time)
        
        return target.health <= 0

    def take_damage(self, amount: int, current_time: int):
        """Handle taking damage"""
        self.health -= amount
        self.last_hit_time = current_time
        self.invincible = True
        logging.info(f"{self.imageset} took {amount} damage! Health: {self.health}")

    def handle_player_hit(self, player, mob, current_time, game):
        """Handle what happens when player is hit by mob"""
        self.health -= 10  # Reduce health
        self.last_hit_time = current_time
        self.invincible = True
        
        # Apply knockback
        knockback_distance = 2  # tiles
        knockback_x = knockback_distance if player.tile_x < mob.tile_x else -knockback_distance
        knockback_y = knockback_distance if player.tile_y < mob.tile_y else -knockback_distance
        
        new_x = player.tile_x + knockback_x
        new_y = player.tile_y + knockback_y
        
        # Only move if knockback position is valid
        if not player._check_collision(new_x, new_y):
            player.move_to(new_x, new_y)
        
        logging.info(f"Player hit! Health: {self.health}")
        
        if self.health <= 0:
            game.game_over()


    def random_move(self, current_time):
        """Attempt a random move if cooldown has expired"""
        if current_time - self.last_move_time < self.move_cooldown:
            return False
            
        if self.moving:
            return False
            
        # Choose a random direction
        directions = [
            (self.tile_x - 1, self.tile_y),  # left
            (self.tile_x + 1, self.tile_y),  # right
            (self.tile_x, self.tile_y - 1),  # up
            (self.tile_x, self.tile_y + 1)   # down
        ]
        random.shuffle(directions)
        
        # Try each direction until one works
        for new_x, new_y in directions:
            if self.move_to(new_x, new_y):
                self.last_move_time = current_time
                return True
        return False

    def move_to(self, new_x, new_y):
        """Attempt to move to new tile position and update direction"""
        # Determine direction based on new vs current position
        dx = new_x - self.tile_x
        dy = new_y - self.tile_y

        if dx < 0:
            self.direction = "left"
        elif dx > 0:
            self.direction = "right"
        elif dy < 0:
            self.direction = "up"
        elif dy > 0:
            self.direction = "down"
        # else no change if no movement (shouldn't happen)

        if self._check_collision(new_x, new_y):
            self.moving = False
            return False  # Collision occurred

        self.moving = True
        self.target_x = new_x * self.tile_width
        self.target_y = new_y * self.tile_height
        self.target_tile_x = new_x
        self.target_tile_y = new_y
        return True

    def _check_collision(self, new_x, new_y):
        """Check collisions with both tiles and objects"""
        logging.debug(f"Checking collision at ({new_x}, {new_y})")
        # Convert tile coordinates to pixel coordinates
        target_rect = pygame.Rect(
            new_x * self.tile_width,
            new_y * self.tile_height,
            self.tile_width,
            self.tile_height
        )

        # Check map boundaries
        if (new_x < 0 or new_x >= self.gamedata.tmx_data.width or
            new_y < 0 or new_y >= self.gamedata.tmx_data.height):
            return True

        # Check object collisions
        for obj_rect in self.gamedata.collision_objects:
            if target_rect.colliderect(obj_rect):
                return True

        return False

    def update(self, current_time: int):
        """Update player position animation"""
        # Reset invincibility if time has passed
        if self.invincible and (current_time - self.last_hit_time >= self.invincibility_time):
            self.invincible = False

        # Update animation
        self.animation_time += 1000/60  # Assuming 60 FPS
        if self.animation_time >= self.animation_speed:
            if self.direction and self.direction in self.frames:
                frames_list = self.frames[self.direction]
                self.current_frame = (self.current_frame + 1) % len(frames_list)
                self.image = frames_list[self.current_frame]
            self.animation_time = 0
            logging.debug(f"Switched to frame {self.current_frame} direction {self.direction}")

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


class Game:
    def __init__(self, map_path: str, debug: bool = False):
        self.debug = debug
        self.mobs = []

        logging.debug("Initializing pygame...")
        pygame.init()

        # Set a minimal display mode before loading the map so convert() calls work
        pygame.display.set_mode((1, 1))
        pygame.mouse.set_visible(False)

        logging.debug(f"Loading TMX map: {map_path}")
        self.tmx_data = load_pygame(map_path)
        self.pos_validator = PositionValidator(self.tmx_data)

        self.width = self.tmx_data.width * self.tmx_data.tilewidth
        self.height = self.tmx_data.height * self.tmx_data.tileheight

        logging.debug(f"Setting up display: {self.width}x{self.height}")
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(f"Rendering {map_path}")

        self.clock = pygame.time.Clock()
        self.running = True

        self.gamedata = GameData(self.tmx_data)

        self.players = []
        logging.debug("Creating player1 (boy) at initial position (5, 5)")
        self.players.append(Actor(5, 5, "boy", self.gamedata, Stats(attack=100, defence=15)))
        self.players.append(Actor(7, 5, "girl", self.gamedata, Stats(attack=100, defence=5)))
        self.player1 = self.players[0]
        self.player2 = self.players[1]
        logging.debug("Creating player2 (girl) at initial position (7, 5)")

        self.font = pygame.font.SysFont(None, 24)

        # Max population for the mobs
        self.mobs_max_population = {
            "slime": 3, 
            "skeleton": 1,
            "ghost": 1,
            "bat": 4,
            "spider": 5,
        }

        self.mobs_names = list(self.mobs_max_population.keys())
        # Mobs stats by type
        self.mobs_stats = {
            "slime": Stats(3, 3), 
            "skeleton": Stats(20, 20),
            "ghost": Stats(20, 50),
            "bat": Stats(2, 1),
            "spider": Stats(1, 1),
        }
        # experience for each mob
        self.mobs_max_exp = {
            "slime": 3, 
            "skeleton": 10,
            "ghost": 20,
            "bat": 2,
            "spider": 1,
        }

        for mob in self.mobs_names:
            self.spawn_mob_by_name(mob, max_population=self.mobs_max_population.get(mob, 1))

    def check_collisions(self):
        current_time = pygame.time.get_ticks()
        
        # Check player-mob collisions
        for player in self.players:
            if player.invincible:
                continue
                
            for mob in self.mobs[:]:  # Create a copy for safe removal
                if player.rect.colliderect(mob.rect):
                    # Player attacks mob
                    if player.attack_target(mob, current_time):
                        if mob in self.mobs:  # Player killed a mob
                            player.stats.add_experience(self.mobs_max_exp[mob.imageset])
                            self.mobs.remove(mob)
                    # Mob attacks player
                    elif mob.attack_target(player, current_time):
                        if player.health <= 0:
                            self.game_over()

    def game_over(self):
        """Handle game over state"""
        logging.info("Game Over!")
        # You could add game over screen logic here
        self.running = False

    def update(self):
        current_time = pygame.time.get_ticks()
            
        for actor in self.actors():
            actor.update(current_time)
            if actor in self.mobs:
                actor.random_move(current_time)
                
        self.check_collisions()  # Add this line to check collisions each frame

    def draw_player_stats(self):
        """Draw player stats in bottom right corner"""
        stats = [
            f"Player 1: {self.player1.imageset} (Lvl {self.player1.stats.level})",
            f"Health: {self.player1.health}/{self.player1.stats.max_health}",
            f"XP: {self.player1.stats.experience}/{self.player1.stats.experience_to_level}",
            f"ATK/DEF: {self.player1.stats.attack}/{self.player1.stats.defence}",
            "",
            f"Player 2: {self.player2.imageset} (Lvl {self.player2.stats.level})",
            f"Health: {self.player2.health}/{self.player2.stats.max_health}",
            f"XP: {self.player2.stats.experience}/{self.player2.stats.experience_to_level}",
            f"ATK/DEF: {self.player2.stats.attack}/{self.player2.stats.defence}"
        ]
        
        # Calculate position (bottom right with padding)
        padding = 10
        line_height = 20
        start_y = self.height - (len(stats) * line_height) - padding
        
        for i, stat in enumerate(stats):
            text = self.font.render(stat, True, (255, 255, 255))
            text_rect = text.get_rect(
                bottomright=(self.width - padding, 
                           start_y + (i * line_height) + line_height)
            )
            self.screen.blit(text, text_rect)

    def draw(self):
        self.screen.fill((0, 0, 0))
        self.draw_map(self.screen, self.tmx_data)
        self.draw_actors()
        
        if self.debug:
            self.draw_object_layer_borders(self.screen)
            self.draw_debug_info()
        # Draw level up notification if needed
        for player in self.players:
            if player.stats.experience >= player.stats.experience_to_level:
                text = self.font.render(f"{player.imageset} leveled up!", True, (255, 255, 0))
                self.screen.blit(text, (self.width // 2 - 100, 50))

        self.draw_player_stats()
        pygame.display.flip()

    def draw_map(self, screen, tmx_data):
        # Draw all visible layers in proper order
        for layer in tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer: # type: ignore
                    tile = tmx_data.get_tile_image_by_gid(gid)
                    if tile:
                        # Convert tile to use alpha transparency
                        tile = tile.convert_alpha()
                        screen.blit(tile,
                            (x * tmx_data.tilewidth + layer.offsetx,
                             y * tmx_data.tileheight + layer.offsety))


    def spawn_mob_by_name(self, imageset: str, 
                          *,
                          spawn_area: str | None = None, 
                          min_x: int = 0, max_x: int | None = None,
                          min_y: int = 0, max_y: int | None = None,
                          max_population: int = 1,
                          ):
        """Spawn a mob at a random valid position
        
        Args:
            imageset: The name of the mob's imageset
            spawn_area: Optional name of spawn area to constrain to
            min_x: Minimum x tile coordinate (inclusive) - ignored if spawn_area specified
            max_x: Maximum x tile coordinate (inclusive) - ignored if spawn_area specified
            min_y: Minimum y tile coordinate (inclusive) - ignored if spawn_area specified
            max_y: Maximum y tile coordinate (inclusive) - ignored if spawn_area specified
        """
        spawn_area = imageset if spawn_area is None else spawn_area
        # If spawn area specified, use its bounds
        if spawn_area:
            spawn_rect = self.gamedata.get_spawn_area(spawn_area)
            if spawn_rect is None:
                logging.warning(f"Spawn area '{spawn_area}' not found")
                return
                
            # Convert pixel rect to tile coordinates
            tile_width = self.tmx_data.tilewidth
            tile_height = self.tmx_data.tileheight
            min_x = spawn_rect.x // tile_width
            max_x = (spawn_rect.x + spawn_rect.width) // tile_width
            min_y = spawn_rect.y // tile_height
            max_y = (spawn_rect.y + spawn_rect.height) // tile_height

        population = 0
        while population < max_population:
            # Rest of the method remains the same as before
            if max_x is None:
                max_x = self.tmx_data.width - 1
            if max_y is None:
                max_y = self.tmx_data.height - 1
                
            min_x = max(0, min(min_x, self.tmx_data.width - 1))
            max_x = max(0, min(max_x, self.tmx_data.width - 1))
            min_y = max(0, min(min_y, self.tmx_data.height - 1))
            max_y = max(0, min(max_y, self.tmx_data.height - 1))
            
            if min_x > max_x:
                min_x, max_x = max_x, min_x
            if min_y > max_y:
                min_y, max_y = max_y, min_y
            
            max_attempts = 10
            for _ in range(max_attempts):
                x = random.randint(min_x, max_x)
                y = random.randint(min_y, max_y)
                
                if not self._position_has_collision(x, y):
                    mob = Actor(x, y, imageset, self.gamedata, self.mobs_stats[imageset])
                    self.mobs.append(mob)
                    population += 1
                    break
                else:
                    logging.warning(f"Could not find valid spawn position for {imageset} in area "
                                   f"x:{min_x}-{max_x}, y:{min_y}-{max_y} after {max_attempts} attempts")
                    return

    def _position_has_collision(self, x: int, y: int) -> bool:
        """Check if a tile position has any collisions"""
        # Create a temporary rect for the position
        temp_rect = pygame.Rect(
            x * self.tmx_data.tilewidth,
            y * self.tmx_data.tileheight,
            self.tmx_data.tilewidth,
            self.tmx_data.tileheight
        )
        
        # Check against all collision objects
        for obj_rect in self.gamedata.collision_objects:
            if temp_rect.colliderect(obj_rect):
                return True
        
        # Check if position is occupied by any actor
        for actor in self.actors():
            if actor.tile_x == x and actor.tile_y == y:
                return True
                
        return False

    def draw_object_layer_borders(self, surface: pygame.Surface, color=(0, 0, 0), font_size=14):
        """Draw borders and names of all objects in the object layer"""
        if not self.gamedata.objectlayer:
            return
        
        # Load a font for the text rendering
        font = pygame.font.Font(None, font_size)  # None uses default font, 24 is size
        
        center_x = None
        center_y = None
        for obj in self.gamedata.objectlayer:
            if hasattr(obj, 'points'):  # Polygonal objects
                points = [(p[0], p[1]) for p in obj.points]
                if len(points) > 1:
                    pygame.draw.polygon(surface, color, points, 1)
                    # Calculate center for polygon
                    center_x = sum(p[0] for p in points) / len(points)
                    center_y = sum(p[1] for p in points) / len(points)
            else:  # Rectangular objects
                rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
                pygame.draw.rect(surface, color, rect, 1)
                center_x = obj.x + obj.width / 2
                center_y = obj.y + obj.height / 2
            
            # Render object name if it exists
            if obj.name and center_x is not None and center_y is not None:
                text = font.render(obj.name, True, color)
                text_rect = text.get_rect(center=(center_x, center_y))
                surface.blit(text, text_rect)


    def draw_debug_info(self):
        """Draw all debug information including mouse position"""
        screen = self.screen
        if not self.debug:
            return
            
        # Draw mouse position
        self._draw_mouse_position(screen)
        
        # Draw other debug info (object borders, etc.)
        self.draw_object_layer_borders(screen)

    def _draw_mouse_position(self, surface):
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

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logging.debug("Quit event detected")
                self.running = False

            if event.type == pygame.KEYDOWN:
                # Control player1 (boy) with arrow keys only if not moving
                if not self.player1.moving:
                    if event.key == pygame.K_LEFT:
                        self.player1.move_to(self.player1.tile_x - 1, self.player1.tile_y)
                    elif event.key == pygame.K_RIGHT:
                        self.player1.move_to(self.player1.tile_x + 1, self.player1.tile_y)
                    elif event.key == pygame.K_UP:
                        self.player1.move_to(self.player1.tile_x, self.player1.tile_y - 1)
                    elif event.key == pygame.K_DOWN:
                        self.player1.move_to(self.player1.tile_x, self.player1.tile_y + 1)
                    elif event.key == pygame.K_h:
                        self.debug = not self.debug
                    elif event.key == pygame.K_r:  # Reset player1 position
                        logging.debug("Resetting player1 position")
                        self.player1 = Actor(5, 5, "boy", self.gamedata, stats=self.player1.stats)

                # Control player2 (skeleton) with WASD only if not moving
                if not self.player2.moving:
                    if event.key == pygame.K_a:
                        self.player2.move_to(self.player2.tile_x - 1, self.player2.tile_y)
                    elif event.key == pygame.K_d:
                        self.player2.move_to(self.player2.tile_x + 1, self.player2.tile_y)
                    elif event.key == pygame.K_w:
                        self.player2.move_to(self.player2.tile_x, self.player2.tile_y - 1)
                    elif event.key == pygame.K_s:
                        self.player2.move_to(self.player2.tile_x, self.player2.tile_y + 1)
                    elif event.key == pygame.K_t:  # Reset player2 position (using 't' key)
                        logging.debug("Resetting player2 position")
                        self.player2 = Actor(7, 5, "skeleton", self.gamedata, stats=self.player2.stats)

    def actors(self) -> Iterable[Actor]:
        return chain(self.players, self.mobs)


    def draw_actors(self):
        for actor in self.actors():
            # logging.debug(f"Drawing {actor.imageset}")
            self.screen.blit(actor.image, actor.rect)

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)

        pygame.quit()


def main():
    args = parse_args()
    logging.basicConfig(level=args.log.upper(),
                        format='%(asctime)s - %(levelname)s - %(message)s')

    game = Game(args.load_map)
    game.run()


if __name__ == "__main__":
    main()
