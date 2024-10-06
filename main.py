from mastodon import Mastodon
from ohgo.ohgo_client import OHGOClient
import toml
import random
from ohgo.models.camera import Camera
import os
import pickle

def get_camera_cache(image_cache_file="camera_cache.pickle"):
    # If camera_cache_file is not None and exists, load it
    if image_cache_file is not None:
        # Camera cache is a json file containing all the cameras
        # Check if the file exists
        if not os.path.exists(image_cache_file):
            return None
        with open(image_cache_file, 'rb') as f:
            try:
                cameras = pickle.load(f)
                return cameras
            except Exception as e:
                print(f"Error loading camera cache: {e}")
                return None
    return None


class OHGOBot:
    """
    OHGOBot is a bot that posts a random image (or a set of images) from a random OHGO traffic camera to Mastodon. Along with the lat/lng coords marked up to link to openstreetmap.
    """

    _camera_cache: dict = None
    _camera_cache_file: str = None

    def __init__(self, config_file="config.toml", camera_cache_file="camera_cache.pickle"):
        self.config = toml.load(config_file)
        self.ohgo_client = OHGOClient(self.config['ohgo']['api_key'])
        # Config['mastodon']['api_base_url'] and ['access_token'] are required
        self.mastodon = Mastodon(
            api_base_url=self.config['mastodon']['api_base_url'],
            access_token=self.config['mastodon']['access_token']
        )
        self._camera_cache_file = camera_cache_file
        self._camera_cache = get_camera_cache(camera_cache_file)

    def save_camera_cache(self, cameras) -> bool:
        if cameras is not None and self._camera_cache_file is not None:
            #pickle.dump(cameras, open(self._camera_cache_file, 'w'))
            # Write object must be str not bytes
            with open(self._camera_cache_file, 'wb') as f:
                pickle.dump(cameras, f)
        return False

    def get_random_camera(self) -> Camera:
        # If camera_cache, then use it otherwise use get_cameras()
        if self._camera_cache is not None:
            cameras = self._camera_cache
        else:
            cameras = self.ohgo_client.get_cameras()
            self.save_camera_cache(cameras)
        return random.choice(cameras)

    def post_random_images(self):
        camera = self.get_random_camera()
        images = self.ohgo_client.get_images(camera, size="large") # List of PIL images
        # Upload all images to Mastodon
        media_ids = []
        for image in images:
            # Save image to file and upload to Mastodon
            with open("temp.jpg", "wb") as f:
                image.save(f, format="JPEG")
            media = self.mastodon.media_post("temp.jpg", mime_type="image/jpeg")
            media_ids.append(media['id'])

        # Get all views
        camera_views = "\n".join([ f"[View {index+1}]({view.large_url})" for index, view in enumerate(camera.camera_views)])
        
        # Post to Mastodon
        status = f"OHGO Traffic Camera: {camera.description}\n\n"
        status += f"Views:\n{camera_views}\n\n"
        status += f"Lat/Lng: [{camera.latitude}, {camera.longitude}](https://www.openstreetmap.org/?mlat={camera.latitude}&mlon={camera.longitude})"
        self.mastodon.status_post(status, media_ids=media_ids)

if __name__ == "__main__":
    bot = OHGOBot()
    bot.post_random_images()
