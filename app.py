"""
Spotify API test
"""

import requests as re
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from urllib.parse import urlencode
from tempfile import mkdtemp
import time
import datetime
import json
import plotly
import plotly.express as px
import scipy.signal as sg
import pandas as pd
import numpy as np


app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

BASE_URL = 'https://api.spotify.com/v1/'
auth_url = 'https://accounts.spotify.com/api/token'
client_id = "313b84bd0e5440c1b9ae2b752ca7a6ff"
secret_key = "b48c1db7336649bea6810ab94fe1e612"
user_auth_url = 'https://accounts.spotify.com/authorize'


@app.route("/index")
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login():

    payload = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': "http://127.0.0.1:5000/callback",
        'scope': 'user-read-private user-read-email user-library-read',
        'state': 'YaBoi12345678912'
    }

    return redirect(f'{user_auth_url}/?{urlencode(payload)}')


@app.route("/callback")
def callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if state is None or state != 'YaBoi12345678912':
        return render_template("index.html", info="state went wrong")

    if error:
        return render_template("index.html", info=f'{error}')

    time.sleep(0.01)
    authorization = re.post(auth_url, {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': "http://127.0.0.1:5000/callback",
        'client_id': client_id,
        'client_secret': secret_key
    })

    full_token = authorization.json()
    # next line will fail if you refresh /home without going back to login
    access_token = full_token['access_token']

    if access_token:
        info = "success"
    else:
        info = "something wrong with access token"

    session["access_token"] = access_token

    return redirect("/home")


@app.route("/home")
def home():
    return render_template("home.html")


@app.route("/saved_analysis", methods=['GET', 'POST'])
def saved_analysis():
    # get a list of the user's saved tracks (max 50)

    access_token = session["access_token"]

    feature = 'danceability'
    no_songs = 200

    if request.method == 'POST':
        feature = request.form.get("feature")
        no_songs = request.form.get("quantity")

        if feature is None:
            feature = 'danceability'

        if no_songs is None:
            no_songs = 200
        else:
            try:
                no_songs = int(float(no_songs))
            except ValueError:
                no_songs = 200

    headers = {
        'Authorization': f'Bearer {access_token}',
    }

    limit = '50'
    offset = '0'

    list_of_saved = []
    saved_ids = []
    time_elapsed = []

    # change the range for how many songs you want to have x50
    no_requests = int(no_songs / 50)
    for i in range(no_requests):
        offset = str(50 * i)
        query = f'?limit={limit}&offset={offset}'

        response = re.get(f'{BASE_URL}me/tracks{query}', headers=headers)
        songs = response.json()

        for i, track in enumerate(songs["items"]):
            list_of_saved.append(track["track"]["name"])
            saved_ids.append(track["track"]["id"])

            # find how long ago song added from its timestamp
            ad = track["added_at"]
            ar = list(map(int, [ad[0:4], ad[5:7], ad[8:10], ad[11:13],
                          ad[14:16], ad[17:19]]))
            datey = datetime.datetime(ar[0], ar[1], ar[2], ar[3], ar[4], ar[5])
            now = datetime.datetime.now()
            diff = now - datey
            time_elapsed.append(diff.total_seconds())

    # get audio details of all the songs requested (max 100)

    headers = {
            'Authorization': f'Bearer {access_token}',
        }

    d_list = []

    for i in range(int(len(list_of_saved) / 100)):
        batch = saved_ids[int((100 * i)):int((100 * i) + 100)]
        batch = ",".join(batch)
        query = f'?ids={batch}'

        response = re.get(f'{BASE_URL}audio-features{query}', headers=headers)
        track_details = response.json()

        for track in track_details["audio_features"]:
            d_list.append(track[f'{feature}'])

    # smooth the danceablility data
    window = int((len(d_list) / 2) + 1)
    d_list = sg.savgol_filter(d_list, window, 2)

    # make a dataframe from the columns and adjust time to days/months/years
    maxtime = np.array(time_elapsed).astype(int).max() / (3600 * 24)
    if maxtime < 120:
        # days
        time_elapsed = np.array(time_elapsed).astype(int) / (3600 * 24)
        time_label = "days"
    elif maxtime < 500:
        # months
        time_elapsed = np.array(time_elapsed).astype(int) / (3600 * 24 * 30)
        time_label = "months"
    else:
        # years
        time_elapsed = np.array(time_elapsed).astype(int) / (3600 * 24 * 365)
        time_label = "years"

    data = list(zip(time_elapsed, d_list, list_of_saved))
    df = pd.DataFrame(data, columns=["time_elapsed", "d_list", "track_names"])

    axis_labels = {'time_elapsed': f'Time since song added / {time_label}',
                   'd_list': f'{feature}'}

    # make the plotly graph of the data
    fig = px.scatter(df, x='time_elapsed', y='d_list',
                     hover_data=['track_names'], labels=axis_labels)
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template("saved_analysis.html", graphJSON=graphJSON,
                           no_points=len(list_of_saved), feature=feature)


@app.route("/search", methods=['POST'])
def search():
    authorisation = re.post(auth_url, {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': secret_key
    })

    auth_response_data = authorisation.json()
    access_token = auth_response_data['access_token']

    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    query = f'q={request.form["trackname"]}&type=track'

    r = re.get(BASE_URL + 'search?' + query, headers=headers)
    r = r.json()["tracks"]

    return render_template("index.html", info=r)
