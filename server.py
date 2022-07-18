from ContraDC import *
from modules import *
from flask import Flask, render_template, request
import os
import time
from wtforms import Form, FloatField, IntegerField, SelectField, validators
from wtforms.fields.html5 import IntegerRangeField
import json
from flask import jsonify


app = Flask(__name__)


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


if __name__ == '__main__':
    app.run(debug=True)
