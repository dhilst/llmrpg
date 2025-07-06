from dataclasses import dataclass

@dataclass
class Stats:
    attack: int = 10
    defence: int = 5
    max_health: int = 100
    level: int = 1
    experience: int = 0
    experience_to_level: int = 20

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


