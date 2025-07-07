import pygame
import pygame_gui
from pygame_gui.elements import UIPanel, UILabel, UIStatusBar

class GameGUI:
    def __init__(self, width: int, height: int, gui_width: int = 200):
        self.gui_width = gui_width
        
        # Create UI Manager
        self.manager = pygame_gui.UIManager((width + gui_width, height))
        
        # Create GUI panel on left side
        panel_rect = pygame.Rect(0, 0, gui_width, height)
        self.panel = UIPanel(
            relative_rect=panel_rect,
            manager=self.manager
        )
        
        # Setup stats display
        self._setup_stats_display()
    
    def _setup_stats_display(self):
        """Initialize all GUI elements for displaying stats"""
        y_offset = 10
        x_offset = 10
        bar_width = self.gui_width - x_offset
        
        # Health display
        self.health_label = UILabel(
            relative_rect=pygame.Rect(10, y_offset, self.gui_width-20, 20),
            text="HP:",
            manager=self.manager,
            container=self.panel
        )

        y_offset += 25
        self.health_bar = UIStatusBar(
            relative_rect=pygame.Rect(5, y_offset, bar_width, 20),
            manager=self.manager,
            container=self.panel
        )

        # XP display
        y_offset += 25
        self.xp_label = UILabel(
            relative_rect=pygame.Rect(10, y_offset, self.gui_width-20, 20),
            text="XP:",
            manager=self.manager,
            container=self.panel
        )

        y_offset += 25
        self.xp_bar = UIStatusBar(
            relative_rect=pygame.Rect(5, y_offset, bar_width, 20),
            manager=self.manager,
            container=self.panel
        )

        # Stats labels
        y_offset += 25
        self.level_label = UILabel(
            relative_rect=pygame.Rect(10, y_offset, self.gui_width-20, 20),
            text="",
            manager=self.manager,
            container=self.panel
        )
        y_offset += 25
        self.attack_label = UILabel(
            relative_rect=pygame.Rect(10, y_offset, self.gui_width-20, 20),
            text="",
            manager=self.manager,
            container=self.panel
        )
        y_offset += 25
        self.defence_label = UILabel(
            relative_rect=pygame.Rect(10, y_offset, self.gui_width-20, 20),
            text="",
            manager=self.manager,
            container=self.panel
        )

    def update_stats(self, player):
        """Update all player stats in the GUI"""
        if player:
            self.health_bar.percent_full = (player.health / player.stats.max_health) * 100
            self.xp_bar.percent_full = (player.stats.experience / player.stats.experience_to_level) * 100
            self.level_label.set_text(f"Level: {player.stats.level}")
            self.attack_label.set_text(f"Attack: {player.stats.attack}")
            self.defence_label.set_text(f"Defence: {player.stats.defence}")

    def process_events(self, event):
        """Handle pygame GUI events"""
        self.manager.process_events(event)

    def update(self, time_delta):
        """Update the GUI manager"""
        self.manager.update(time_delta)

    def draw(self, surface):
        """Draw the GUI elements"""
        self.manager.draw_ui(surface)
