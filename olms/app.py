from http.server import ThreadingHTTPServer
from olms_pkg import config
from olms_pkg.db import init_db
from olms_pkg.web import OLMSHandler


def main():
    init_db(config.DB_PATH, seed=True)
    server = ThreadingHTTPServer((config.HOST, config.PORT), OLMSHandler)
    print(f"OLMS running at http://{config.HOST}:{config.PORT} (DB: {config.DB_PATH})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down OLMS server.")
        server.server_close()


if __name__ == "__main__":
    main()
