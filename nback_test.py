import json
import os
import random
import sys
import time

import pygame

# script_dir = os.path.dirname(os.path.abspath(__file__))
# sys.path.insert(0, script_dir)
sys.path.append(r"C:\Users\AdHawk\py-tools")

import adhawkapi
import adhawkapi.frontend
from adhawkapi import MarkerSequenceMode, PacketType

# pylint: disable=E1101

# Initialize pygame
pygame.init()

# Constants
SCREEN_WIDTH, SCREEN_HEIGHT = pygame.display.Info().current_w, pygame.display.Info().current_h
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# For consistent total number of stimuli and forced matches:
TOTAL_STIMULI = 48
FORCED_MATCHES = 8

STIMULUS_DURATION = 500 #2500  # milliseconds
BLANK_DURATION = 500 #2500   # milliseconds
FONT_SIZE = 75

# Set up the screen
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("N-back Memory Test")

# Set up font
font = pygame.font.Font(None, FONT_SIZE)


class Frontend:
    '''
    Frontend communicating with the backend
    '''

    def __init__(self):
        # Instantiate an API object
        self.api = adhawkapi.frontend.FrontendApi()

        # Register stream handlers
        self.api.register_stream_handler(PacketType.EYETRACKING_STREAM, lambda *args: None)
        self.api.register_stream_handler(PacketType.EVENTS, lambda *args: None)

        # Start the api and set its connection callback
        self.api.start(connect_cb=self._handle_connect_response)

    def shutdown(self, *_args):
        ''' Shuts down the backend connection '''
        # Stop the log session
        self.api.stop_log_session(lambda *_args: None)

        # Shuts down the api
        self.api.shutdown()
        print('Shut down api')

    def quickstart(self):
        ''' Runs a Quick Start using AdHawk Backend's GUI '''
        self.api.register_stream_handler(PacketType.GAZE, (lambda *args: None))
        self.api.quick_start_gui(mode=MarkerSequenceMode.FIXED_GAZE, marker_size_mm=35,
                                 callback=lambda *args: None)

    def calibrate(self):
        ''' Calibrates the gaze tracker using AdHawk Backend's GUI '''
        self.api.start_calibration_gui(mode=MarkerSequenceMode.FIXED_HEAD, n_points=9, marker_size_mm=35,
                                       randomize=False, callback=lambda *args: None)

    def _handle_connect_response(self, error):
        ''' Handler for backend connection responses '''
        if not error:
            print('Backend connected')

            control_bits = [
                adhawkapi.EventControlBit.BLINK,
            ]
            for control_bit in control_bits:
                self.api.set_event_control(control_bit, 1, callback=lambda *args: None)

            self.api.set_et_stream_control([
                adhawkapi.EyeTrackingStreamTypes.GAZE,
                adhawkapi.EyeTrackingStreamTypes.PER_EYE_GAZE,
                adhawkapi.EyeTrackingStreamTypes.PUPIL_DIAMETER,
            ], True, callback=lambda *args: None)
            self.api.set_et_stream_rate(250, callback=lambda *args: None)

            self.api.start_log_session(log_mode=adhawkapi.LogMode.DIAGNOSTICS_LITE, callback=lambda *args: None)


class NBackTest:  # pylint: disable=R0902, R0902, R1702
    ''' Main class for the GUI '''

    def __init__(self, n_back=2):
        ''' Class constructor '''
        # Test parameters
        self.n_back = n_back

        # We are now fixing the total stimuli and forced matches globally
        self.num_digits = TOTAL_STIMULI
        self.num_matches = FORCED_MATCHES

        # Display settings
        self.screen_width, self.screen_height = pygame.display.Info().current_w, pygame.display.Info().current_h
        self.background_color = BLACK
        self.font_color = WHITE

        # Timing settings
        self.STIMULUS_DURATION = STIMULUS_DURATION
        self.blank_duration = BLANK_DURATION
        self.font_size = FONT_SIZE

        # Initialize pygame
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.FULLSCREEN)
        pygame.display.set_caption("N-back Memory Test")
        self.font = pygame.font.Font(None, self.font_size)

        # The digits for the test will be generated after the user selects n_back
        self.digits = []
        self.timestamps = []
        self.timestamps_wrong = []

        self.frontend = Frontend()

        # For 0-back
        self.zero_back_target = None

        # Start the overall test flow
        self.run()

    def select_nback_value(self):
        """
        Display a screen to let the user press 0, 1, 2, or 3 to select the N-back level.
        Press ESC to quit.
        """
        selecting = True
        while selecting:
            # Display instructions in the center
            self.screen.fill(self.background_color)
            text_surface = self.font.render(
                "Press 0, 1, 2, or 3 to select an N-back level. ESC to quit.",
                True,
                self.font_color
            )
            text_rect = text_surface.get_rect(center=(self.screen_width / 2, self.screen_height / 2))
            self.screen.blit(text_surface, text_rect)
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_0:
                        self.n_back = 0
                        selecting = False
                    elif event.key == pygame.K_1:
                        self.n_back = 1
                        selecting = False
                    elif event.key == pygame.K_2:
                        self.n_back = 2
                        selecting = False
                    elif event.key == pygame.K_3:
                        self.n_back = 3
                        selecting = False
                    elif event.key == pygame.K_ESCAPE:
                        self.end()
                        pygame.quit()
                        sys.exit()

    def generate_n_back_sequence(self):
        """
        Generate a sequence of length self.num_digits (= 48).
        There are always exactly self.num_matches (= 8) target occurrences:
         - For n=0, that means 8 appearances of the same 'target digit'.
         - For n>0, that means 8 forced n-back matches in the sequence.
        """

        if self.n_back == 0:
            # 0-back logic: pick one random digit as the target,
            # place it exactly 8 times among 48 positions,
            # fill the others with random digits != target.
            target = str(random.randint(1, 9))
            self.zero_back_target = target

            # Create an array of length 48
            # Randomly choose 8 positions for the target
            sequence = [None] * self.num_digits
            target_positions = random.sample(range(self.num_digits), self.num_matches)

            # Fill those positions with the target
            for pos in target_positions:
                sequence[pos] = target

            # Fill the remaining positions with random digits != target
            for i in range(self.num_digits):
                if sequence[i] is None:
                    while True:
                        digit = str(random.randint(1, 9))
                        if digit != target:
                            sequence[i] = digit
                            break

            return sequence

        else:
            # n-back logic for n>0: ensure exactly 8 forced matches
            # We'll store the first n digits randomly, then pick 8 positions to force matches
            sequence = [str(random.randint(1, 9)) for _ in range(self.n_back)]

            # We'll have to create a list of possible match positions from [n_back..(num_digits-1)]
            # Then we choose exactly 8 of them to be forced matches.
            # The rest are random digits that do NOT create accidental matches.
            total_positions = range(self.n_back, self.num_digits)
            match_positions = random.sample(total_positions, self.num_matches)

            for i in range(self.n_back, self.num_digits):
                if i in match_positions:
                    # Force a match at position i
                    sequence.append(sequence[i - self.n_back])
                else:
                    # Generate a digit that doesn't accidentally create a match at i
                    while True:
                        digit = str(random.randint(1, 9))
                        if digit != sequence[i - self.n_back]:
                            sequence.append(digit)
                            break

            return sequence

    def display_text(self, text, color=None):
        """Display text in the center of the screen, supporting line breaks."""
        self.screen.fill(self.background_color)
        color = color or self.font_color
        
        # Split the text into lines based on \n
        lines = text.split('\n')
        
        # Calculate total height for vertical centering
        line_height = self.font.get_linesize()
        total_height = line_height * len(lines)
        start_y = (self.screen_height - total_height) // 2

        # Render and blit each line
        for i, line in enumerate(lines):
            text_surface = self.font.render(line, True, color)
            text_rect = text_surface.get_rect(center=(self.screen_width / 2, start_y + i * line_height))
            self.screen.blit(text_surface, text_rect)
        
        pygame.display.flip()

    def start_test(self):
        if self.n_back == 0:
            self.digits = self.generate_n_back_sequence()
            target_digit = self.zero_back_target
            message = (
                f"Welcome to the {self.n_back}-back test.\n"
                f"Your target digit is '{target_digit}'.\n"
                "Press SPACE to start."
            )
        else:
            self.digits = self.generate_n_back_sequence()
            message = f"Welcome to the {self.n_back}-back test.\nPress SPACE to start."

        self.display_text(message)
        waiting_to_start = True
        while waiting_to_start:
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        waiting_to_start = False
                        self.frontend.api.log_annotation(
                            annotid='experiment', parent=0,
                            name='Test.start',
                            data=json.dumps({'N': self.n_back}),
                            callback=lambda *args: print("Test.start logged")
                        )
                    elif event.key == pygame.K_ESCAPE:
                        self.end()
                        pygame.quit()
                        sys.exit()

    def run_test_loop(self):
        """
        Run the main test loop to show digits/digits and log responses.
        If n_back == 0, check for matches with the single target digit.
        If n_back > 0, check for standard n-back matches.
        """
        previous_digits = []
        running = True

        # If we haven't generated for n>0 yet, do it now (safety check).
        # For 0-back, we've already generated inside `start_test()`.
        if self.n_back > 0 and not self.digits:
            self.digits = self.generate_n_back_sequence()

        for i, digit in enumerate(self.digits):
            if not running:
                break

            # Determine if there's an n-back match
            if self.n_back > 0:
                # For n>0, a match is current digit == digit from i-n_back
                if len(previous_digits) >= self.n_back:
                    matches = (digit == previous_digits[-self.n_back])
                else:
                    matches = False
            else:
                # For 0-back, a match is digit == zero_back_target
                matches = (digit == self.zero_back_target)

            print(f"Stimulus {i}: {digit} {'*' if matches else ''}")

            self.frontend.api.log_annotation(
                annotid=0, parent='experiment',
                name='Stimuli',
                data=json.dumps({'digit': digit, 'matches': matches}),
                callback=lambda *args: None
            )

            self.display_text(digit)
            start_time = time.time()

            while time.time() - start_time < self.STIMULUS_DURATION / 1000:
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            # Evaluate correctness
                            if self.n_back == 0:
                                correct = (digit == self.zero_back_target)
                            else:
                                correct = False
                                if len(previous_digits) >= self.n_back:
                                    correct = (digit == previous_digits[-self.n_back])

                            # Log it
                            self.frontend.api.log_annotation(
                                annotid=0, parent='experiment',
                                name='Response',
                                data=json.dumps({'Correct': correct}),
                                callback=lambda *args: None
                            )

                            # Store timestamps
                            if correct:
                                self.timestamps.append((digit, time.time()))
                                print(f"  Correct response at {time.time()} for '{digit}'")
                            else:
                                self.timestamps_wrong.append((digit, time.time()))
                                print(f"  Wrong response at {time.time()} for '{digit}'")

                        elif event.key == pygame.K_ESCAPE:
                            self.end()
                            running = False
                            break
                if not running:
                    break

            # Hide the digit (blank) for blank_duration ms
            # self.screen.fill(self.background_color)
            # pygame.display.flip()
            self.display_text("#")
            time.sleep(self.blank_duration / 1000)

            # Update previous digits list (for n>0)
            previous_digits.append(digit)
            if self.n_back > 0 and len(previous_digits) > self.n_back:
                previous_digits.pop(0)

    def display_results(self):
        """Print the timestamps for all keypresses."""
        print("Timestamps of correct keypresses:")
        for digit, timestamp in self.timestamps:
            print(f"  Correct response '{digit}': {timestamp}")
        print("Timestamps of incorrect keypresses:")
        for digit, timestamp in self.timestamps_wrong:
            print(f"  Wrong response '{digit}': {timestamp}")

    def run(self):
        """Manage the entire flow of the test."""
        self.select_nback_value()  # Choose n_back
        self.start_test()          # Possibly display or generate the 0-back target
        self.run_test_loop()
        self.display_results()
        self.end()
        pygame.quit()

    def end(self):
        ''' Prepare for close '''
        self.frontend.api.log_annotation(
            annotid='experiment', parent=0,
            name='Test.end',
            data=json.dumps({'N': self.n_back}),
            callback=lambda *args: None
        )
        time.sleep(3)
        self.frontend.shutdown()
        print('Test terminated')

if __name__ == "__main__":
    pygame.init()
    # Simply create an instance of the test. The N-back level will be selected via GUI (including 0).
    test = NBackTest()



