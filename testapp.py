from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return 'HELLO WORLD'

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
