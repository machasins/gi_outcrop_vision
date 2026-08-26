import cv2
import numpy as np
import pyautogui
from concurrent.futures import ThreadPoolExecutor

class FastImageFinderParallel:
    def __init__(self, image_paths, threshold=0.95, max_workers=None):
        """
        image_paths : list of file paths to template images
        threshold   : matching threshold (0-1, higher = stricter match)
        region      : optional (left, top, width, height) tuple for faster search
        max_workers : number of threads (defaults to CPU count)
        """
        self.image_paths = image_paths
        self.templates = [
            cv2.imread(path, cv2.IMREAD_COLOR) for path in image_paths
        ]
        if any(t is None for t in self.templates):
            raise FileNotFoundError("One or more template image paths are invalid.")

        self.threshold = threshold
        self.max_workers = max_workers

    def _match_one(self, screen_gray, template, path):
        """Return the file path if matched, else None."""
        res = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        if (res >= self.threshold).any():
            return path
        return None

    def find_matches(self, screenshot):
        """Return a list of file paths for templates found on screen."""

        # Convert to grayscale
        screen_gray = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Match in parallel
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = executor.map(
                lambda args: self._match_one(screen_gray, *args),
                zip(self.templates, self.image_paths)
            )

        # Filter out None results
        return [path for path in results if path is not None]