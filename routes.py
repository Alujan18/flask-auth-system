from flask import render_template, redirect, url_for
from app import app

@app.route('/')
def index():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente')
def agente_main():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/configuracion')
def agente_configuracion():
    return render_template('agente_configuracion.html')

@app.route('/agente/dashboard')
def agente_dashboard():
    return render_template('agente_dashboard.html')
