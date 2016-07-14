"""`main` is the top level module for your Flask application."""

from Crypto.Cipher import AES

# Import the Flask Framework
from flask import Flask, session, redirect, url_for, request, jsonify
app = Flask(__name__)
# Note: We don't need to call run() since our application is embedded within
# the App Engine WSGI application server.

import base64
import logging

import os

from google.appengine.ext import ndb

import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Config(ndb.Model):
  github_client_id = ndb.StringProperty()
  github_client_secret = ndb.StringProperty()
  lemonstand_auth_token = ndb.StringProperty()
  aes_key = ndb.StringProperty()
  flask_session_secret = ndb.StringProperty()
  github_auth_token = ndb.StringProperty()

config_key = ndb.Key(Config, "default")
config = config_key.get()
if not config:
  config = Config(key=config_key)
  config.put()

BS = 16
def pad(s):
  return s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
def unpad(s):
  return s[0:-ord(s[-1])]

AES_KEY = base64.b64decode(config.aes_key)

app.config['GITHUB_CLIENT_ID'] = config.github_client_id
app.config['GITHUB_CLIENT_SECRET'] = config.github_client_secret
app.config['PERMANENT_SESSION_LIFETIME'] = 365 * 24 * 60 * 60
app.secret_key = base64.b64decode(config.flask_session_secret)

from flask_github import GitHub

github = GitHub(app)

import contributor_discount

@app.route('/')
def index():
  template = JINJA_ENVIRONMENT.get_template('index.html')
  return template.render()

@app.route('/api/discount')
def discount():
  author = request.args.get('user_id')
  if not author:
    return "{}"
  discount_percentage, score, thanks = contributor_discount.compute_discount(github, author)
  response = {"discount_percentage": discount_percentage, "score": score, "thanks": thanks}
  if author == session['user_id']:
    response["discount_code"] = contributor_discount.get_discount_code(config.lemonstand_auth_token, author, discount_percentage, score)
  return jsonify(**response)

@github.access_token_getter
def token_getter():
  if "o" in session:
    aes = AES.new(AES_KEY, AES.MODE_CBC, bytes(session["o"])[:16])
    return unpad(aes.decrypt(bytes(session["o"])[16:]))
  return config.github_auth_token

@app.route('/github-callback')
@github.authorized_handler
def authorized(access_token):
  if request.args.get('error_description'):
    return request.args.get('error_description')
  next_url = request.args.get('next') or url_for('index')
  if access_token is None or access_token == config.github_auth_token:
    return redirect(next_url)

  session.permanent = True
  iv = os.urandom(16)
  aes = AES.new(AES_KEY, AES.MODE_CBC, iv)
  session["o"] = iv + aes.encrypt(pad(bytes(access_token)))
  user_info = github.get("user")

  session['user_id'] = user_info["login"]
  resp = redirect(next_url)
  resp.set_cookie('loggedIn', "true")
  return resp

@app.route('/login')
def login():
  next_url = request.args.get('next') or url_for('index')
  if "o" not in session:
    return github.authorize(scope=None, redirect_uri="https://ckd-acd.appspot.com" + url_for('authorized') + "?next=" + next_url)
  else:
    return redirect(next_url)


@app.route('/logout')
def logout():
  session.pop('o', None)
  session.pop('user_id', None)
  resp = redirect(url_for('index'))
  resp.set_cookie('loggedIn', '', expires=0)
  return resp

@app.route('/user')
def user():
    return str(github.get('user'))

@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, Nothing at this URL.', 404


@app.errorhandler(500)
def application_error(e):
    """Return a custom 500 error."""
    return 'Sorry, unexpected error: {}'.format(e), 500
