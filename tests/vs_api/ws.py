""""""

from flask import Flask

from .service import service_bp
from .system import system_bp
from .servers import server_bp
from .billing import billing_bp

app = Flask(__name__)

app.register_blueprint(system_bp, url_prefix="/system")
app.register_blueprint(service_bp, url_prefix="/service")
app.register_blueprint(server_bp, url_prefix="/server")
app.register_blueprint(billing_bp, url_prefix="/billing")
