from flask import Flask, render_template, request, redirect, url_for

glozApp = Flask(__name__)

@glozApp.route('/')
def home():
    return 'Hello, Gloz!'

if __name__ == '__main__':
    glozApp.run(port=3000, debug=True)