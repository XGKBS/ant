"""Shared buttons and text, also used by modal setup/pause screens."""
import pygame
BG = (17, 23, 31)
PANEL = (25, 34, 45)
TEXT = (231, 237, 243)
MUTED = (163, 181, 199)
ACCENT = (74, 180, 188)

def button(screen, font, rect, label, selected=False, enabled=True, mouse=None):
    hover = enabled and rect.collidepoint(pygame.mouse.get_pos() if mouse is None else mouse)
    fill = (48, 83, 96) if selected else ((48, 62, 78) if hover else (33, 44, 59))
    pygame.draw.rect(screen, fill, rect, border_radius=6)
    pygame.draw.rect(screen, ACCENT if selected or hover else (68, 87, 104), rect, 2 if selected else 1, border_radius=6)
    # Long faction/ability names must remain inside their button at every size.
    label_font = font
    image = label_font.render(label, True, TEXT if enabled else (102, 117, 132))
    if image.get_width() > rect.w-16:
        ratio = (rect.w-16)/image.get_width()
        image = pygame.transform.smoothscale(image, (rect.w-16, max(1, round(image.get_height()*ratio))))
    screen.blit(image, image.get_rect(center=rect.center))

def text_lines(font, text, width):
    lines = []
    line = ''
    for word in text.split():
        candidate = (line+' '+word).strip()
        if line and font.size(candidate)[0] > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines

def wrapped(screen, font, text, position, width, color=TEXT, spacing=4):
    x, y = position
    for line in text_lines(font, text, width):
        screen.blit(font.render(line, True, color), (x, y))
        y += font.get_linesize()+spacing
    return y
