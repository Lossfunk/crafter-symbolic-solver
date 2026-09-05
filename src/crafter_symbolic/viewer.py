"""Optional display of received frames only; no environment or policy access."""
import os


class ViewerUnavailable(RuntimeError):
    """The optional display dependency or desktop is unavailable."""


class FrameViewer:
    """Pixel-preserving enlargement; Space pauses, Escape/window-close stops."""

    def __init__(self, title, fps=10, scale=8):
        os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
        try:
            import pygame
        except ImportError as exc:
            raise ViewerUnavailable(
                'Live viewing needs pygame. Install with: '
                'python -m pip install pygame==2.6.1 '
                '(or python -m pip install ".[viewer]" from the source folder)'
            ) from exc
        self.pg, self.title, self.fps = pygame, title, fps
        self.paused = False
        try:
            pygame.display.init()  # No audio devices or mixer are initialized.
            self.screen = pygame.display.set_mode((64*scale, 64*scale))
            self.clock = pygame.time.Clock()
        except pygame.error as exc:
            pygame.display.quit()
            raise ViewerUnavailable(
                'Cannot open a desktop window. Run without --show to record a GIF instead.'
            ) from exc

    def show(self, rgb, step=0, action='reset', done=False):
        # Pygame uses x,y order; the agent's RGB uses row,column order.
        surface = self.pg.surfarray.make_surface(rgb.swapaxes(0, 1))
        enlarged = self.pg.transform.scale(surface, self.screen.get_size())
        while True:
            for event in self.pg.event.get():
                if event.type == self.pg.QUIT:
                    raise KeyboardInterrupt
                if event.type == self.pg.KEYDOWN:
                    if event.key == self.pg.K_ESCAPE:
                        raise KeyboardInterrupt
                    if event.key == self.pg.K_SPACE:
                        self.paused = not self.paused
            state = 'PAUSED' if self.paused else 'finished' if done else 'playing'
            self.pg.display.set_caption(
                f'{self.title} | step {step} | {action} | {state} | Space: pause, Esc: stop'
            )
            self.screen.blit(enlarged, (0, 0))
            self.pg.display.flip()
            self.clock.tick(30 if self.paused else self.fps)
            if not self.paused:
                return

    def close(self):
        self.pg.display.quit()
