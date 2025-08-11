from flask import Flask, render_template, send_from_directory, abort, url_for
import datetime
import os
import secrets
from glob import glob

app = Flask(__name__)
# It's good practice to set the secret key from an environment variable in production
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

PHOTOS_DIR = 'photos'
CATEGORIES = ['category1', 'category2']

# In-memory cache for daily data.
# In a multi-worker setup, a proper cache (like Redis or Memcached) would be needed.
cache = {
    'date': None,
    'images': {}, # 'cat1_pic1' -> {'category': 'category1', 'filename': '...'}
    'url_map': {} # 'random_url' -> 'cat1_pic1'
}

def update_daily_data():
    """
    Checks if the cached data is for the current day. If not, it scans for
    today's images and generates new random URLs.
    """
    global cache
    today = datetime.date.today()
    if cache['date'] == today and cache['images']:
        return

    # User mentioned 730 pictures for 2 years. We'll use a day counter from a fixed start date.
    start_date = datetime.date(2024, 1, 1) # This should be configurable
    day_of_cycle = (today - start_date).days + 1

    if not (1 <= day_of_cycle <= 730):
        # No images for today, clear cache and return
        cache = {'date': today, 'images': {}, 'url_map': {}}
        return

    found_images = {}
    base_pattern = f"pic{day_of_cycle}"

    for category in CATEGORIES:
        cat_num = category[-1]
        for i in range(1, 3): # (catX-pic1), (catX-pic2)
            # e.g., pic5(cat1-pic1).jpg
            search_pattern = os.path.join(PHOTOS_DIR, category, f"{base_pattern}(cat{cat_num}-pic{i}).*")
            found_files = glob(search_pattern)
            if found_files:
                filename = os.path.basename(found_files[0])
                key = f"cat{cat_num}_pic{i}"
                found_images[key] = {'category': category, 'filename': filename}

    if len(found_images) != 4:
        # Not all images were found for today, treat as if none are available.
        # In a real scenario, we might want to log this error.
        cache = {'date': today, 'images': {}, 'url_map': {}}
        return

    # All images found, generate new URLs and update cache
    new_url_map = {}
    for key in found_images.keys():
        random_url = secrets.token_urlsafe(16)
        new_url_map[random_url] = key

    cache['date'] = today
    cache['images'] = found_images
    cache['url_map'] = new_url_map

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/main')
def main():
    update_daily_data()
    # We need to create a structure that's easy for the template to use.
    # It needs the random URL for the page and the image source for the thumbnail.
    template_images = {}

    # Reverse map from key ('cat1_pic1') to random_url
    key_to_url_map = {v: k for k, v in cache['url_map'].items()}

    for key, details in cache['images'].items():
        template_images[key] = {
            'url': url_for('image_page', random_url=key_to_url_map.get(key, '')),
            'src': url_for('image_file', category=details['category'], filename=details['filename'])
        }

    return render_template('main.html', images=template_images)

@app.route('/page/<random_url>')
def image_page(random_url):
    update_daily_data()
    if random_url not in cache['url_map']:
        abort(404)

    key = cache['url_map'][random_url]
    image_details = cache['images'][key]

    image_src = url_for('image_file', category=image_details['category'], filename=image_details['filename'])
    return render_template('image_page.html', image_src=image_src)

@app.route('/img/<category>/<filename>')
def image_file(category, filename):
    update_daily_data()
    # Security check: is this one of the valid images for today?
    is_valid = False
    for details in cache['images'].values():
        if details['category'] == category and details['filename'] == filename:
            is_valid = True
            break

    if not is_valid:
        abort(403) # Forbidden

    return send_from_directory(os.path.join(PHOTOS_DIR, category), filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
