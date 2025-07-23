from flask import Flask, request, jsonify, render_template
import feedparser
import sqlite3
import schedule
import time
import threading

app = Flask(__name__)

# Initialize SQLite database
def init_db():
    with sqlite3.connect('rss.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS feeds
                     (id INTEGER PRIMARY KEY, url TEXT UNIQUE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS articles
                     (id INTEGER PRIMARY KEY, feed_url TEXT, title TEXT, link TEXT, pub_date TEXT, description TEXT)''')
        conn.commit()

# Fetch and store articles from a feed URL
def fetch_feed(url):
    try:
        feed = feedparser.parse(url)
        if feed.bozo:
            print(f"Error parsing feed {url}: {feed.bozo_exception}")
            return False
        with sqlite3.connect('rss.db') as conn:
            c = conn.cursor()
            for entry in feed.entries:
                pub_date = entry.get('published', '') or entry.get('updated', '')
                c.execute('''INSERT OR IGNORE INTO articles (feed_url, title, link, pub_date, description)
                             VALUES (?, ?, ?, ?, ?)''',
                          (url, entry.get('title', ''), entry.get('link', ''),
                           pub_date, entry.get('description', '')))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error fetching feed {url}: {e}")
        return False

# Schedule feed fetching
def schedule_feeds():
    with sqlite3.connect('rss.db') as conn:
        c = conn.cursor()
        c.execute("SELECT url FROM feeds")
        urls = [row[0] for row in c.fetchall()]
    for url in urls:
        fetch_feed(url)

# Run scheduler in a separate thread
def run_scheduler():
    schedule.every(1).hours.do(schedule_feeds)
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start scheduler in a background thread
threading.Thread(target=run_scheduler, daemon=True).start()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_feed', methods=['POST'])
def add_feed():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    try:
        with sqlite3.connect('rss.db') as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO feeds (url) VALUES (?)", (url,))
            conn.commit()
        if fetch_feed(url):
            return jsonify({'message': 'Feed added successfully'})
        else:
            return jsonify({'error': 'Failed to fetch feed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/feeds')
def get_feeds():
    with sqlite3.connect('rss.db') as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM articles ORDER BY pub_date DESC")
        articles = [{'id': row[0], 'feed_url': row[1], 'title': row[2],
                     'link': row[3], 'pub_date': row[4], 'description': row[5]}
                    for row in c.fetchall()]
    return jsonify(articles)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)