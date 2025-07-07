import random
from itertools import chain
import argparse
import logging
from typing import Any, Dict, Iterable, Literal, Optional
import pygame
from pytmx import load_pygame
import pytmx

from llmrpg.gamedata import GameData
from llmrpg.effects import BlinkEffect
from llmrpg.validations import PositionValidator
from llmrpg.playerstats import Stats
from llmrpg import drawing

def parse_args():
    parser = argparse.ArgumentParser(description="Pygame Tiled Map Renderer")
    parser.add_argument('--load-map', required=True, help='Path to the .tmx Tiled map file')
    parser.add_argument('--log', choices=['debug', 'info', 'warning', 'error'],
                        default='info', help='Set logging level (default: info)')
    return parser.parse_args()

class Actor(pygame.sprite.Sprite):
    def __init__(self, x, y, imageset: str, game: "Game", stats: Stats, kind: Literal["player", "mob"]):
        super().__init__()

        self.kind = kind
        self.last_move_time = 0  # Track when mob last moved
        self.move_cooldown = 1000  # 3 seconds in milliseconds

        self.game = game
        gamedata = game.gamedata
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

        self.frames = self.gamedata.characters.frames(self.imageset)  # dict: direction -> frames list
        self.frames["dead"] = self.gamedata.dead_characters.tiles(self.imageset)
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
        self.death_time = None  # Track when actor died
        # --- Integration of BlinkEffect ---
        self.effects = [] # List to hold various effects

    def is_dead(self) -> bool:
        return self.health <= 0

    def add_effect(self, effect):
        """
        Adds an effect to the actor.
        Args:
            effect: An instance of an effect class (e.g., BlinkEffect).
        """
        self.effects.append(effect)

    def calculate_damage(self, target) -> int:
        """Calculate damage dealt to target"""
        base_damage = max(1, self.stats.attack - target.stats.defence // 2)
        return random.randint(base_damage // 2, base_damage)

    def attack_target(self, target: "Actor", current_time: int) -> bool:
        """Attack another actor and return True if target was killed"""
        # Check if target is currently invincible due to a BlinkEffect
        if target.kind == self.kind:
            return False

        for effect in self.effects:
            if isinstance(effect, BlinkEffect) and effect.is_effect_active():
                return False # Cannot attack if currently blinking due to invincibility

        damage = self.calculate_damage(target)
        target.take_damage(damage, current_time)

        if target.is_dead():
            self.stats.add_experience(self.game.mobs_max_exp[target.imageset] * self.game.exp_modifier)

        # Return whether target was killed
        return target.is_dead()

    def take_damage(self, amount: int, current_time: int):
        """Handle taking damage"""
        if self.is_dead():
            return

        # Check if the actor is currently invincible
        for effect in self.effects:
            if isinstance(effect, BlinkEffect) and effect.is_effect_active():
                return # Do not take damage if currently invincible

        self.health = max(0, self.health - amount)  # Ensure health doesn't go below 0
        logging.info(f"{self.imageset} took {amount} damage! Health: {self.health}")

        # Apply a blink effect for invincibility
        # Ensure only one invincibility blink effect is active at a time
        for effect in list(self.effects): # Iterate over a copy
            if isinstance(effect, BlinkEffect) and effect.is_effect_active():
                self.effects.remove(effect) # Remove any existing blink effects

        if self.is_dead():
            self.current_frame = 0
            self.direction = "dead"
            self.death_time = current_time
            return

        invincibility_blink = BlinkEffect(duration_ms=1000, blink_interval_ms=100)
        self.add_effect(invincibility_blink)


    def random_move(self, current_time: int):
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
            if self.move_to(new_x, new_y, current_time):
                self.last_move_time = current_time
                return True
        return False

    def move_to(self, new_x: int, new_y: int, current_time: int) -> bool:
        """Attempt to move to new tile position and update direction"""
        # First check if we're already at this position
        if new_x == self.tile_x and new_y == self.tile_y:
            return False

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

        # Check collision before allowing movement
        if self._check_collision(new_x, new_y, current_time):
            return False

        self.moving = True
        self.target_x = new_x * self.tile_width
        self.target_y = new_y * self.tile_height
        self.target_tile_x = new_x
        self.target_tile_y = new_y
        return True

    def _check_collision(self, new_x: int, new_y: int, current_time: int) -> bool:
        """Check collisions with both tiles, objects, and other actors"""
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

        for actor in self.game.actors():
            if actor is not self and actor.tile_x == new_x and actor.tile_y == new_y and not actor.is_dead():
                self.attack_target(actor, current_time)
                return True

        return False

    def update(self, current_time: int):
        """Update player position, animation, and effects."""
        # Update all active effects
        # Iterate over a copy of the list to safely remove effects during iteration
        for effect in list(self.effects):
            # dt_ms for effects will be the delta time from the game loop, 
            # which we are assuming is 1000/60 for animation updates
            effect.update(1000/60) 
            if not effect.is_effect_active():
                self.effects.remove(effect)

        # If dead, don't update animation or movement
        if self.is_dead():
            # Freeze animation on death frame
            if self.direction in self.frames and self.frames[self.direction]:
                self.image = self.frames[self.direction][0]
            return

        # Update animation
        self.animation_time += 1000/60  # Assuming 60 FPS
        if self.animation_time >= self.animation_speed:
            if self.direction and self.direction in self.frames:
                frames_list = self.frames[self.direction]
                self.current_frame = (self.current_frame + 1) % len(frames_list)
                self.image = frames_list[self.current_frame]
            self.animation_time = 0

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
        """
        Draws the actor on the screen, considering any active effects like blinking.
        """
        should_draw = True
        for effect in self.effects:
            if isinstance(effect, BlinkEffect):
                if not effect.get_visibility():
                    should_draw = False
                    break # If any blink effect says don't draw, then don't draw

        if should_draw:
            screen.blit(self.image, self.rect)


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
        self.players.append(Actor(5, 5, "boy", self, Stats(attack=100, defence=15), "player"))
        self.players.append(Actor(7, 5, "girl", self, Stats(attack=100, defence=5), "player"))
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
        self.exp_modifier = 2

        for mob in self.mobs_names:
            self._spawn_mob_by_name(mob, max_population=self.mobs_max_population.get(mob, 1))

    def game_over(self):
        """Handle game over state"""
        logging.info("Game Over!")
        # You could add game over screen logic here
        self.running = False

    def update(self):
        current_time = pygame.time.get_ticks()

        for actor in self.actors():
            if actor in self.mobs:
                if not actor.is_dead():
                    actor.random_move(current_time)
            actor.update(current_time)

        # Remove mobs that have been dead for 5 seconds
        for mob in list(self.mobs):
            if mob.is_dead() and current_time - mob.death_time >= 5000:
                self.mobs.remove(mob)

    def draw(self):
        self.screen.fill((0, 0, 0))
        self._draw_map()
        self._draw_actors()
        self._draw_object_layer_borders()
        self._draw_debug_info()
        self._draw_notifications()
        self._draw_player_stats()
        pygame.display.flip()

    def actors(self) -> list[Actor]:
        return list(chain(self.players, self.mobs))

    def run(self):
        while self.running:
            self._handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)

        pygame.quit()

    def _draw_notifications(self):
        # Draw level up notification if needed
        for player in self.players:
            if player.stats.experience >= player.stats.experience_to_level:
                text = self.font.render(f"{player.imageset} leveled up!", True, (255, 255, 0))
                self.screen.blit(text, (self.width // 2 - 100, 50))

    def _draw_player_stats(self):
        """Draw player stats in bottom right corner"""
        drawing.draw_player_stats(self.screen, self.player1, self.player2,
                                  self.height, self.width, self.font)
    def _draw_map(self):
        return drawing.draw_map(self.screen, self.tmx_data)


    def _spawn_mob_by_name(self, imageset: str,
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
                    mob = Actor(x, y, imageset, self, self.mobs_stats[imageset], "mob")
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

    def _draw_object_layer_borders(self, color=(0, 0, 0), font_size=14):
        """Draw borders and names of all objects in the object layer"""
        if not self.debug:
            return

        if not self.gamedata.objectlayer:
            return

        surface = self.screen
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


    def _draw_debug_info(self):
        """Draw all debug information including mouse position"""
        if not self.debug:
            return

        self._draw_mouse_position()
        self._draw_object_layer_borders()

    def _draw_mouse_position(self):
        """Draw current mouse position and coordinates"""
        return drawing.draw_mouse_position(self.screen)

    def _handle_events(self):
        for event in pygame.event.get():
            current_time = pygame.time.get_ticks()
            if event.type == pygame.QUIT:
                logging.debug("Quit event detected")
                self.running = False

            if event.type == pygame.KEYDOWN:
                # Control player1 (boy) with arrow keys only if not moving
                if not self.player1.moving:
                    if event.key == pygame.K_LEFT:
                        self.player1.move_to(self.player1.tile_x - 1, self.player1.tile_y,
                                             current_time)
                    elif event.key == pygame.K_RIGHT:
                        self.player1.move_to(self.player1.tile_x + 1, self.player1.tile_y,
                                             current_time)
                    elif event.key == pygame.K_UP:
                        self.player1.move_to(self.player1.tile_x, self.player1.tile_y - 1,
                                             current_time)
                    elif event.key == pygame.K_DOWN:
                        self.player1.move_to(self.player1.tile_x, self.player1.tile_y + 1,
                                             current_time)
                    elif event.key == pygame.K_h:
                        self.debug = not self.debug
                    elif event.key == pygame.K_r:  # Reset player1 position
                        logging.debug("Resetting player1 position")
                        self.player1 = Actor(5, 5, "boy", self, stats=self.player1.stats, kind="player")

                # Control player2 (skeleton) with WASD only if not moving
                if not self.player2.moving:
                    if event.key == pygame.K_a:
                        self.player2.move_to(self.player2.tile_x - 1, self.player2.tile_y,
                                             current_time)
                    elif event.key == pygame.K_d:
                        self.player2.move_to(self.player2.tile_x + 1, self.player2.tile_y,
                                             current_time)
                    elif event.key == pygame.K_w:
                        self.player2.move_to(self.player2.tile_x, self.player2.tile_y - 1,
                                             current_time)
                    elif event.key == pygame.K_s:
                        self.player2.move_to(self.player2.tile_x, self.player2.tile_y + 1,
                                             current_time)
                    elif event.key == pygame.K_t:  # Reset player2 position (using 't' key)
                        logging.debug("Resetting player2 position")
                        self.player2 = Actor(7, 5, "skeleton", self, stats=self.player2.stats, kind="player")

    def _draw_actors(self):
        return drawing.draw_actors(self.screen, self.actors())

def main():
    args = parse_args()
    logging.basicConfig(level=args.log.upper(),
                        format='%(asctime)s - %(levelname)s - %(message)s')

    game = Game(args.load_map)
    game.run()


if __name__ == "__main__":
    main()
