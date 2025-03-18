from flask import Flask
import threading
import ssl

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello, both HTTP and HTTPS!"

def run_http():
    """ Spustí HTTP server na portu 5000 """
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)

def run_https():
    """ Spustí HTTPS server na portu 4433 """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    app.run(host="0.0.0.0", port=4433, ssl_context=context, debug=False, use_reloader=False)

if __name__ == "__main__":
    thread_http = threading.Thread(target=run_http)
    thread_https = threading.Thread(target=run_https)

    thread_http.start()
    thread_https.start()

    thread_http.join()
    thread_https.join()
