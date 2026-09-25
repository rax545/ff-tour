import io
import unittest
from PIL import Image
from utils.cards import room_pass, points_table, booyah, mvp


class CardTests(unittest.TestCase):
    def test_dimensions(self):
        row = {'name': 'Wolves', 'matches': 2, 'kills': 12, 'pts': 33}
        for image, size in [(room_pass('Wolves', 'Cup', 1, 'Bermuda'), (1100, 500)),
                            (points_table('Cup', [row]), (1200, 880)),
                            (booyah('Wolves', 'Cup', 33), (1100, 500)),
                            (mvp('Player', 'Wolves', 12), (1100, 500))]:
            self.assertEqual(Image.open(io.BytesIO(image.getvalue())).size, size)


if __name__ == '__main__':
    unittest.main()
