# Slightly modified example for Ant Simulation
# created by Generative AI (Google)

"""
Instructions for installing Pygame: https://www.pygame.org/wiki/GettingStarted

Overview:
- Imports: Import necessary libraries (Pygame for graphics and random for ant movement).
- Initialization: Initialize Pygame, set up the game window, and define colors.
- Ant class: Create an Ant class that inherits from pygame.sprite.Sprite.
             This class defines the ant's appearance, movement, and behavior.
- Create ants: Create a group of ants and initialize their positions randomly.
- Game loop: The main game loop handles events, updates the ants' positions, and
             draws them on the screen.

Ideas for Enhancement:
- Food: Add food sources that ants can collect and bring back to a nest.
- Pheromones: Implement pheromone trails that ants follow to find food and the nest.
- Different ant types: Create different types of ants with specialized roles (e.g., workers, soldiers).
- Obstacles: Add obstacles that ants must navigate around.
- Improved movement: Make the ant movement more realistic using steering behaviors or other algorithms.
"""

import pygame
import random

# Initialize Pygame
pygame.init()

# Screen dimensions
screen_width = 800
screen_height = 600
screen = pygame.display.set_mode((screen_width, screen_height))
pygame.display.set_caption("Ant Simulation")

# Colors
black = (0, 0, 0)
white = (255, 255, 255)
red = (255, 0, 0)

# Ant class
class Ant(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((5, 5))
        self.image.fill(black)
        self.rect = self.image.get_rect(center=(x, y))
        self.direction = random.randint(0, 359)

    def update(self):
        # Move the ant
        x = self.rect.x + 2 * random.randint(-1, 1)
        y = self.rect.y + 2 * random.randint(-1, 1)
        self.rect.x = max(0, min(x, screen_width - self.rect.width))
        self.rect.y = max(0, min(y, screen_height - self.rect.height))

def main():
    # Create ants
    ants = pygame.sprite.Group()
    for i in range(10):
        x = random.randint(0, screen_width)
        y = random.randint(0, screen_height)
        ants.add(Ant(x, y))

    # Game loop
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Update ants
        ants.update()

        # Draw everything
        screen.fill(white)
        ants.draw(screen)
        pygame.display.flip()

    pygame.quit()

main()
