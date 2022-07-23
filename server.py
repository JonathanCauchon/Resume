from ContraDC import *
from modules import *
from flask import Flask, render_template, request
import os
import time
from wtforms import Form, FloatField, IntegerField, SelectField, validators
from wtforms.fields.html5 import IntegerRangeField
import json
from flask import jsonify
import git
import hashlib
import hmac
from pathlib import Path


app = Flask(__name__)

try:
    GITHUB_WEBHOOKS_KEY = os.environ["PYTHONANYWHERE_KEY"]
except:
    pass


class cdcForm(Form):
    """ A class for the cdc form on the cv website """

    N = IntegerRangeField(label="Number of Periods",
                                default=1000)

    period = IntegerRangeField(label="Grating pitch", default=320)
    w1 = IntegerRangeField(label="Waveguide 1 width", default=560)
    w2 = IntegerRangeField(label="Waveguide 2 width", default=440)
    kappa = IntegerRangeField(label="Coupling power", default=45)
    T = IntegerRangeField(label="Temperature", default=300)


def computeCDC(N=1000, period=320, w1=560, w2=440, kappa=45, T=300):

    device = ContraDC(N=N, period=period*1e-9, w1=w1*1e-9, w2=w2*1e-9,
                      kappa=kappa*1e3, T=T, N_seg=100,
                      resolution=300, wvl_range=[1500e-9, 1600e-9])

    device.simulate().getGroupDelay().getPerformance()

    wvl = np.round(device._wavelength, 0).tolist()
    drop = device.drop.tolist()
    thru = device.thru.tolist()
    gd = (1e12*device.group_delay).tolist()
    bw = device.performance["BW"][0]
    center = device.performance["Ref. wvl"][0]

    return str(wvl), str(drop), str(thru), str(gd), str(bw), str(center)


def is_valid_signature(x_hub_signature, data, private_key):
    hash_algorithm, github_signature = x_hub_signature.split('=', 1)
    algorithm = hashlib.__dict__.get(hash_algorithm)
    encoded_key = bytes(private_key, 'latin-1')
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)


@ app.route("/", methods=['GET', 'POST'])
def index():
    form = cdcForm(request.form)
    # if request.method == 'POST':

    wvl, drop, thru, gd, bw, center = computeCDC()

    return render_template('style.html',
                           form=form, wvl=wvl, drop=drop, thru=thru, gd=gd, bw=bw, center=center)


@app.route("/simulate", methods=["POST"])
def simulate():

    N = request.form.get("N", 0, type=int)
    period = request.form.get("period", 0, type=int)
    w1 = request.form.get("w1", 0, type=int)
    w2 = request.form.get("w2", 0, type=int)
    kappa = request.form.get("kappa", 0, type=int)
    T = request.form.get("T", 0, type=int)

    wvl, drop, thru, gd, bw, center = computeCDC(
        N=N, period=period, w1=w1, w2=w2, kappa=kappa, T=T)

    return jsonify(wvl=wvl, drop=drop, thru=thru, gd=gd, bw=bw, center=center)


@app.route('/update-server', methods=['POST'])
def webhook():
    if request.method != 'POST':
        return 'OK'
    else:
        abort_code = 418
        # Do initial validations on required headers
        if 'X-Github-Event' not in request.headers:
            abort(abort_code)
        if 'X-Github-Delivery' not in request.headers:
            abort(abort_code)
        if 'X-Hub-Signature' not in request.headers:
            abort(abort_code)
        if not request.is_json:
            abort(abort_code)
        if 'User-Agent' not in request.headers:
            abort(abort_code)
        ua = request.headers.get('User-Agent')
        if not ua.startswith('GitHub-Hookshot/'):
            abort(abort_code)

        event = request.headers.get('X-GitHub-Event')
        if event == "ping":
            return json.dumps({'msg': 'Hi!'})
        if event != "pull_request":
            return json.dumps({'msg': "Wrong event type"})

        x_hub_signature = request.headers.get('X-Hub-Signature')
        # webhook content type should be application/json for request.data to have the payload
        # request.data is empty in case of x-www-form-urlencoded
        if not is_valid_signature(x_hub_signature, request.data, GITHUB_WEBHOOKS_KEY):
            print('Deploy signature failed: {sig}'.format(sig=x_hub_signature))
            abort(abort_code)

        payload = request.get_json()
        if payload is None:
            print('Deploy payload is empty: {payload}'.format(
                payload=payload))
            abort(abort_code)

        if payload['action'] != 'closed':
            return json.dumps({'msg': 'PR not closed, ignoring'})

        repo = git.Repo('.')
        origin = repo.remotes.origin

        pull_info = origin.pull()

        if len(pull_info) == 0:
            return json.dumps({'msg': "Didn't pull any information from remote!"})
        if pull_info[0].flags > 128:
            return json.dumps({'msg': "Didn't pull any information from remote!"})

        commit_hash = pull_info[0].commit.hexsha
        build_commit = f'build_commit = "{commit_hash}"'
        print(f'{build_commit}')

        Path("/var/www/jonathancauchon_pythonanywhere_com_wsgi.py").touch()

        return 'Updated PythonAnywhere server to commit {commit}'.format(commit=commit_hash)


if __name__ == '__main__':
    app.run(debug=True)
