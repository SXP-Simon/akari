import os
from jmcomic import JmOption

class MangaDownloaderConfig:
    @staticmethod
    def load(option_path=None):
        if option_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            option_path = os.path.join(current_dir, 'option.yml')
        return JmOption.from_file(option_path) 