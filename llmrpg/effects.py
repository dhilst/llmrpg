class BlinkEffect:
    """
    Manages a blinking state for an actor.
    """
    def __init__(self, duration_ms: int, blink_interval_ms: int):
        """
        Initializes the BlinkEffect.

        Args:
            duration_ms (int): The total duration of the blink effect in milliseconds.
            blink_interval_ms (int): The interval at which the blink state toggles in milliseconds.
        """
        self.duration_ms = duration_ms
        self.blink_interval_ms = blink_interval_ms
        self.elapsed_time = 0
        self.blink_timer = 0
        self.is_blinking_on = True  # True if the object should be visible during the blink cycle
        self.is_active = True      # True if the effect is currently active

    def update(self, dt_ms: int):
        """
        Updates the blink effect's state.

        Args:
            dt_ms (int): The time elapsed since the last update in milliseconds.
        """
        if not self.is_active:
            return

        self.elapsed_time += dt_ms
        self.blink_timer += dt_ms

        if self.elapsed_time >= self.duration_ms:
            self.is_active = False
            self.is_blinking_on = True  # Ensure visibility when effect ends
            return

        if self.blink_timer >= self.blink_interval_ms:
            self.is_blinking_on = not self.is_blinking_on
            self.blink_timer = 0

    def get_visibility(self) -> bool:
        """
        Returns whether the actor should be visible based on the blink effect.

        Returns:
            bool: True if the actor should be visible, False otherwise.
        """
        return self.is_blinking_on

    def is_effect_active(self) -> bool:
        """
        Checks if the blink effect is still active.

        Returns:
            bool: True if the effect is active, False otherwise.
        """
        return self.is_active


