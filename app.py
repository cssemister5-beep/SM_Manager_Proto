import os
import json
import datetime
import requests
from urllib.parse import quote, unquote
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, session, Response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")

# --------- Load/Save User Data ---------
def load_users():
    try:
        with open('users.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users_data):
    with open('users.json', 'w') as f:
        json.dump(users_data, f, indent=4)

users = load_users()


# --------- Jinja Filters ---------
@app.template_filter('url_encode')
def url_encode_filter(s):
    return quote(s, safe='')


# --------- Authentication Routes ---------
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    global users
    if request.method == 'POST':
        if 'register-submit' in request.form:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')

            if not all([username, email, password]):
                flash("All fields are required for registration.", 'error')
                return redirect(url_for('auth'))

            if email in users:
                flash("User already exists.", 'error')
                return redirect(url_for('auth'))

            hashed_password = generate_password_hash(password)
            users[email] = {
                'username': username,
                'password': hashed_password,
                'created_at': datetime.datetime.now().isoformat()
            }
            save_users(users)
            flash("Registration successful!", 'success')
            return redirect(url_for('auth'))

        elif 'login-submit' in request.form:
            email = request.form.get('email')
            password = request.form.get('password')
            user = users.get(email)

            if not user or not check_password_hash(user['password'], password):
                flash("Invalid login credentials.", 'error')
                return redirect(url_for('auth'))

            session['email'] = email
            session['username'] = user['username']
            return redirect(url_for('dashboard_home'))

    return render_template('auth.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", 'success')
    return redirect(url_for('auth'))

                                                                                                                                 #I Wrote this my self @Tech-Raj https://github.com/Techy-Raj
@app.route('/new_home')
def home_user():
    return redirect(url_for('dashboard_home'))

# @app.route('/new_home')
# def new_home():
#     return render_template('dashboard_home')


# --------- Home & Dashboard Navigation ---------
@app.route('/')
def home():
    if 'email' not in session:
        return redirect(url_for('auth'))
    return redirect(url_for('dashboard_home'))


@app.route('/dashboard')
def dashboard_home():
    if 'email' not in session:
        flash("You must be logged in.", 'error')
        return redirect(url_for('auth'))
    return render_template('dashboard_home.html', user=session.get('username'))


# --------- Instagram Dashboard Page ---------
@app.route('/instagram', methods=["GET", "POST"])
def instagram_dashboard():
    if 'email' not in session:
        flash("You must be logged in to use the dashboard.", 'error')
        return redirect(url_for('auth'))

    profile_data = None
    posts = []
    summary = {}
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        if username:
            url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            headers = {
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "x-ig-app-id": "936619743392459",
            }

            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    user = data.get("data", {}).get("user", {})

                    if user:
                        profile_data = {
                            "username": user.get("username", "N/A"),
                            "full_name": user.get("full_name", "N/A"),
                            "biography": user.get("biography", "N/A"),
                            "followers": user.get("edge_followed_by", {}).get("count", 0),
                            "following": user.get("edge_follow", {}).get("count", 0),
                            "posts": user.get("edge_owner_to_timeline_media", {}).get("count", 0),
                            "is_verified": user.get("is_verified", False),
                            "is_private": user.get("is_private", False),
                            "category": user.get("category_name", "N/A"),
                            "website": user.get("external_url", "N/A"),
                            "email": user.get("business_email", "N/A"),
                            "phone": user.get("business_phone_number", "N/A"),
                            "profile_pic_url": user.get("profile_pic_url_hd", "")
                        }

                        edges = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
                        total_likes = total_comments = 0

                        for edge in edges:
                            node = edge.get("node", {})
                            image_url = node.get("display_url") or node.get("thumbnail_src", "")
                            if not image_url and node.get("thumbnail_resources"):
                                image_url = node["thumbnail_resources"][-1].get("src", "")

                            caption = ""
                            if node.get("edge_media_to_caption", {}).get("edges"):
                                caption = node["edge_media_to_caption"]["edges"][0]["node"].get("text", "")

                            likes = node.get("edge_liked_by", {}).get("count", 0)
                            comments = node.get("edge_media_to_comment", {}).get("count", 0)
                            total_likes += likes
                            total_comments += comments

                            followers = max(profile_data['followers'], 1)
                            engagement_rate_post = round((likes + comments) / followers * 100, 2)

                            posts.append({
                                "thumbnail": image_url,
                                "caption": caption,
                                "likes": likes,
                                "comments": comments,
                                "timestamp": datetime.datetime.fromtimestamp(node.get("taken_at_timestamp", 0)).strftime("%b %d, %Y"),
                                "shortcode": node.get("shortcode", ""),
                                "engagement_rate": engagement_rate_post
                            })

                        num_posts = len(posts) if posts else 1
                        summary = {
                            "avg_likes": int(total_likes / num_posts),
                            "avg_comments": int(total_comments / num_posts),
                            "engagement_rate": round(((total_likes + total_comments) / max(profile_data['followers'], 1)) * 100, 2)
                        }

                    else:
                        error = "User not found!"
                else:
                    error = f"Error: {response.status_code}"
            except Exception as e:
                error = f"Request failed: {e}"

    return render_template("dashboard.html", profile=profile_data, posts=posts, summary=summary, error=error)


# --------- Proxy Route ---------
@app.route("/proxy/<path:url>")
def proxy(url):
    try:
        real_url = unquote(url)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.instagram.com/",
            "accept-language": "en-US,en;q=0.9",
        }
        resp = requests.get(real_url, headers=headers, stream=True, timeout=10)
        resp.raise_for_status()
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return f"Proxy error: {e}", 500


# --------- Startup Check ---------
if __name__ == "__main__":
    if not os.path.exists('users.json'):
        save_users({})
    app.run(debug=True)
