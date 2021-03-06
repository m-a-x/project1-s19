#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases
Example webserver

To run locally

    python server.py

Go to http://localhost:8111 in your browser


A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session
import random


tmpl_dir = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

DB_USER = "mwm2154"
DB_PASSWORD = "YOfW6Nutxe"

DB_SERVER = "w4111.cisxo09blonu.us-east-1.rds.amazonaws.com"

DATABASEURI = "postgresql://"+DB_USER+":"+DB_PASSWORD+"@"+DB_SERVER+"/w4111"

#
# This line creates a database engine that knows how to connect to the URI above
#
engine = create_engine(DATABASEURI)


@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request 
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request

    The variable g is globally accessible
    """
    try:
        g.conn = engine.connect()
    except:
        print "uh oh, problem connecting to database"
        import traceback
        traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass

@app.route('/')
def index():
    """
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
    """

    # DEBUG: this is debugging code to see what request looks like
    print request.args
    
    #
    if not session.get('logged_in'):
        return render_template('login.html')

    cmd = "SELECT lid, username, listname FROM favoriteslists WHERE username = :uname"
    cursor = g.conn.execute(text(cmd), uname=session['username'])
    listlist = []
    names = {}
    for result in cursor:
        listdata = {}
        listdata['lid'] = result['lid']
        listdata['listname'] = result['listname']
        listlist.append(listdata)
        if listdata['listname'] in names.keys():
            names[listdata['listname']] += 1
        else:
            names[listdata['listname']] = 1

    displayname_to_lid ={}
    for listdata in listlist:
        if names[listdata['listname']] > 1:
            displayname = listdata['listname'] + ' (' + str(listdata['lid']) + ')'
        else:
            displayname = listdata['listname']
        displayname_to_lid[displayname] = listdata['lid']
    session['displayname_to_lid'] = displayname_to_lid
    context = dict(data=list(displayname_to_lid.keys()))

    return render_template("index.html", **context)


@app.route('/login', methods=['POST'])
def login():
    cursor = g.conn.execute("SELECT username, password FROM webappusers")
    logins = {}
    err_msg = ''
    for result in cursor:
        logins[result['username']] = result['password']
    try:
        if logins[str(request.form['username'])] == str(request.form['password']):
            session['logged_in'] = True
            session['username'] = str(request.form['username'])
            return redirect('/')
        else:
            err_msg = dict(data=['Incorrect Username / Password'])
            return render_template('login.html',**err_msg)
    except:
        err_msg = dict(data=['Incorrect Username / Password'])
        return render_template('login.html',**err_msg)

@app.route('/add_meme_to_list', methods=['POST'])
def add_meme_to_list():
    try:
        list_chosen = str(request.form['list_choice'])
        lid_chosen = session['displayname_to_lid'][list_chosen]
        post_chosen = request.form['post_choice']
        cmd = 'INSERT INTO favoriteslistsposts(lid, pid) VALUES (:list_id, :post_id)'
        g.conn.execute(text(cmd), list_id=lid_chosen, post_id=post_chosen)

        return redirect('/')
    except:
        return redirect('/')

@app.route('/view_favorites_list', methods=['POST'])
def view_favorites_list():
    try:
        list_chosen = str(request.form['list_choice'])
        lid_chosen = session['displayname_to_lid'][list_chosen]
    except:
        return redirect('/')
    cmd = "SELECT * FROM posts JOIN favoriteslistsposts ON posts.pid=favoriteslistsposts.pid WHERE favoriteslistsposts.lid = :lid"
    cursor = g.conn.execute(text(cmd), lid=lid_chosen)
    postlist = []
    for result in cursor:
        img_link = result['img_link']
        if img_link is None:
            img_link = ''
        postlist.append({
            'pid': result['pid'],
            'fbid': result['fbid'],
            'img_link': img_link,
            'num_reactions': result['num_reactions'],
            'post_text': result['post_text']
        })
    context = postlist
    return render_template('view_favorites_list.html', data=context, list_chosen=list_chosen)

@app.route('/create')
def create():
    return render_template("create.html")

@app.route('/group_lists')
def group_lists():
    group_data = {}
    groupname_to_gid = {}
    cursor = g.conn.execute("SELECT gid, name FROM fbgroups")
    for result in cursor:
        group_data[result['gid']] = [result['name'], 0]  # id, counts in next block of code
        groupname_to_gid[result['name']] = result['gid']
    session['groupname_to_gid'] = groupname_to_gid
    
    cursor = g.conn.execute("SELECT gid, COUNT(gid) FROM grouppopulations GROUP BY gid")
    for result in cursor:
        # group populations
        group_data[result['gid']][1] = result['count']
    
    group_ui_labels = [t[0] + ' | ' + str(t[1]) + ' member(s)' for t in group_data.values()]
    context = dict(data=group_ui_labels)
    
    return render_template("group_lists.html", **context)

@app.route('/group_posts', methods=['POST'])
def group_posts():
    try:
        group_chosen = str(request.form['options'])
        gid_chosen = session['groupname_to_gid'][group_chosen]
    except:
        return redirect('/group_lists')
    cmd = "SELECT * FROM posts JOIN fbusers ON posts.fbid=fbusers.fbid WHERE posts.gid = :gid"
    cursor = g.conn.execute(text(cmd), gid=gid_chosen)
    postlist = []
    for result in cursor:
        img_link = result['img_link']
        if img_link is None:
            img_link = ''
        postlist.append({
            'pid': result['pid'],
            'fbid': result['fbid'],
            'img_link': img_link,
            'num_reactions': result['num_reactions'],
            'post_text': result['post_text'],
            'name': result['name']
        })
    
    
    context = postlist
    displayname_to_lid = session['displayname_to_lid']
    listnames = list(displayname_to_lid.keys())
    
    return render_template('group_posts.html', data=context, group_chosen=group_chosen, listnames=listnames)

@app.route('/create_favorites_list', methods=['POST'])
def create_favorites_list():
    
    listname = str(request.form['listname'])
    if listname == '':
        return redirect('/')
    cmd = 'INSERT INTO favoriteslists(lid, username, listname) VALUES (:list_id, :uname, :lname)'
    lid = random.randint(0, 99999999)
    g.conn.execute(text(cmd), list_id=lid, uname=session['username'], lname=listname)
    return redirect('/')
    
@app.route("/create_submit", methods=['POST'])
def create_submit():
    username = str(request.form['username'])
    password = str(request.form['password'])
    cmd = 'INSERT INTO webappusers(username, password) VALUES (:uname, :pword)'
    try:
        g.conn.execute(text(cmd), uname=username, pword=password)
        context = dict(data=['account creation successful, please log in'])
    except:
        context = dict(data=['username already in use, please choose a different username'])
    return render_template('login.html', **context)


if __name__ == "__main__":
    import click
    app.secret_key = 'dont tell its a secret'
    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using

            python server.py

        Show the help text using

            python server.py --help

        """

        HOST, PORT = host, port
        print "running on %s:%d" % (HOST, PORT)
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

    run()